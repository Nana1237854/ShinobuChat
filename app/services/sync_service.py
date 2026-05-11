from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.memory import Memory
from app.models.message import Message
from app.models.sync import SyncOperation, SyncRecord
from app.models.todo import Todo
from app.models.user import User
from app.schemas.memory import MemoryOut
from app.schemas.message import MessageOut
from app.schemas.sync import (
    SyncChangeIn,
    SyncChangeOut,
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
    SyncPushResult,
    TodoOut,
)
from app.services.realtime_sync_service import realtime_sync_service


class SyncService:
    def __init__(self, db: Session):
        self.db = db

    def push(self, payload: SyncPushRequest) -> SyncPushResponse:
        self._require_user(payload.user_id)
        if payload.last_seen_version == 0:
            self._backfill_existing(payload.user_id)
        results: list[SyncPushResult] = []

        for change in payload.changes:
            results.append(self._apply_client_change(payload.user_id, payload.device_id, change))

        changes = self._changes_since(payload.user_id, payload.last_seen_version, exclude_device_id=payload.device_id)
        server_version = self.current_version(payload.user_id)
        return SyncPushResponse(
            user_id=payload.user_id,
            device_id=payload.device_id,
            server_version=server_version,
            next_since_version=server_version,
            results=results,
            changes=changes,
        )

    def pull(self, user_id: UUID, since_version: int, device_id: str | None = None) -> SyncPullResponse:
        self._require_user(user_id)
        if since_version == 0:
            self._backfill_existing(user_id)
        server_version = self.current_version(user_id)
        changes = self._changes_since(user_id, since_version, exclude_device_id=device_id)
        return SyncPullResponse(
            user_id=user_id,
            server_version=server_version,
            next_since_version=server_version,
            changes=changes,
        )

    def current_version(self, user_id: UUID) -> int:
        value = (
            self.db.query(func.max(SyncOperation.server_version))
            .filter(SyncOperation.user_id == user_id)
            .scalar()
        )
        return int(value or 0)

    def record_server_change(
        self,
        user_id: UUID,
        entity_type: str,
        entity_id: UUID,
        operation: str,
        data: dict[str, Any],
        updated_at: datetime | None = None,
        source_device_id: str = "server",
        notify: bool = True,
    ) -> SyncRecord:
        record = self._get_or_create_record(user_id, entity_type, entity_id)
        next_version = self.current_version(user_id) + 1
        clock = dict(record.vector_clock or {})
        clock[source_device_id] = int(clock.get(source_device_id, 0)) + 1

        record.version = next_version
        record.vector_clock = clock
        record.deleted = operation == "delete"
        record.updated_at = self._normalize_dt(updated_at or datetime.utcnow())
        self.db.add(record)
        self.db.flush()
        self._append_operation(record, operation, data, source_device_id, conflict=False)
        self.db.commit()
        self.db.refresh(record)
        if notify:
            self._publish_sync_change(record, operation, data)
        return record

    def _backfill_existing(self, user_id: UUID) -> None:
        conversation_ids = select(Conversation.id).where(Conversation.user_id == user_id)
        messages = self.db.query(Message).filter(Message.conversation_id.in_(conversation_ids)).all()
        for message in messages:
            if self._record_for("messages", message.id):
                continue
            self.record_server_change(
                user_id,
                "messages",
                message.id,
                "upsert",
                MessageOut.model_validate(message).model_dump(mode="json"),
                message.created_at,
                "server-bootstrap",
                notify=False,
            )

        todos = self.db.query(Todo).filter(Todo.user_id == user_id).all()
        for todo in todos:
            if self._record_for("todos", todo.id):
                continue
            self.record_server_change(
                user_id,
                "todos",
                todo.id,
                "upsert",
                TodoOut.model_validate(todo).model_dump(mode="json"),
                todo.updated_at,
                "server-bootstrap",
                notify=False,
            )

        memories = self.db.query(Memory).filter(Memory.user_id == user_id).all()
        for memory in memories:
            if self._record_for("memory", memory.id):
                continue
            self.record_server_change(
                user_id,
                "memory",
                memory.id,
                "upsert",
                MemoryOut.model_validate(memory).model_dump(mode="json"),
                memory.updated_at,
                "server-bootstrap",
                notify=False,
            )

    def _apply_client_change(self, user_id: UUID, device_id: str, change: SyncChangeIn) -> SyncPushResult:
        record = self._record_for(change.entity_type, change.entity_id)
        incoming_clock = self._tick_clock(change.vector_clock, device_id)
        incoming_updated_at = self._normalize_dt(change.updated_at)

        if record is None:
            return self._accept_change(user_id, device_id, change, incoming_clock, incoming_updated_at, conflict=False)

        if record.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync entity not found")

        relation = self._compare_clocks(incoming_clock, record.vector_clock or {})
        if relation == "older":
            return self._build_result(change, record, "ignored", conflict=False, remote=self._record_to_change(record))

        if relation == "concurrent" and incoming_updated_at < self._normalize_dt(record.updated_at):
            return self._build_result(change, record, "remote_won", conflict=True, remote=self._record_to_change(record))

        resolution = "local_won" if relation == "concurrent" else "applied"
        merged_clock = self._merge_clocks(incoming_clock, record.vector_clock or {})
        return self._accept_change(
            user_id,
            device_id,
            change,
            merged_clock,
            incoming_updated_at,
            conflict=relation == "concurrent",
            resolution=resolution,
        )

    def _accept_change(
        self,
        user_id: UUID,
        device_id: str,
        change: SyncChangeIn,
        vector_clock: dict[str, int],
        updated_at: datetime,
        conflict: bool,
        resolution: str = "applied",
    ) -> SyncPushResult:
        data = self._apply_entity_change(user_id, change, updated_at)
        record = self._get_or_create_record(user_id, change.entity_type, change.entity_id)
        record.version = self.current_version(user_id) + 1
        record.vector_clock = vector_clock
        record.deleted = change.operation == "delete"
        record.updated_at = updated_at
        self.db.add(record)
        self.db.flush()
        operation = self._append_operation(record, change.operation, data, device_id, conflict)
        self.db.commit()
        self.db.refresh(record)
        self._publish_sync_change(record, change.operation, data)

        return SyncPushResult(
            client_change_id=change.client_change_id,
            entity_type=change.entity_type,
            entity_id=change.entity_id,
            operation=change.operation,
            resolution=resolution,  # type: ignore[arg-type]
            server_version=operation.server_version,
            vector_clock=record.vector_clock,
            conflict=conflict,
            remote=None,
        )

    def _apply_entity_change(self, user_id: UUID, change: SyncChangeIn, updated_at: datetime) -> dict[str, Any]:
        if change.operation == "delete":
            self._delete_entity(user_id, change.entity_type, change.entity_id)
            return {}
        if change.entity_type == "messages":
            return self._upsert_message(user_id, change, updated_at)
        if change.entity_type == "todos":
            return self._upsert_todo(user_id, change, updated_at)
        if change.entity_type == "memory":
            return self._upsert_memory(user_id, change, updated_at)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported sync entity")

    def _upsert_message(self, user_id: UUID, change: SyncChangeIn, updated_at: datetime) -> dict[str, Any]:
        conversation_id = self._required_uuid(change.data, "conversation_id")
        conversation = self.db.query(Conversation).filter(Conversation.id == conversation_id, Conversation.user_id == user_id).first()
        if not conversation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

        message = self.db.query(Message).filter(Message.id == change.entity_id).first()
        if message and message.conversation_id != conversation_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Message belongs to a different conversation")
        if not message:
            message = Message(id=change.entity_id, conversation_id=conversation_id)

        message.role = str(change.data.get("role", "user"))
        message.content = str(change.data.get("content", "")).strip()
        message.route_mode = change.data.get("route_mode")
        message.created_at = self._coerce_datetime(change.data.get("created_at")) or updated_at
        conversation.updated_at = updated_at
        self.db.add(message)
        self.db.add(conversation)
        self.db.flush()
        return MessageOut.model_validate(message).model_dump(mode="json")

    def _upsert_todo(self, user_id: UUID, change: SyncChangeIn, updated_at: datetime) -> dict[str, Any]:
        todo = self.db.query(Todo).filter(Todo.id == change.entity_id, Todo.user_id == user_id).first()
        if not todo:
            todo = Todo(id=change.entity_id, user_id=user_id, created_at=self._coerce_datetime(change.data.get("created_at")) or updated_at)

        todo.title = str(change.data.get("title", getattr(todo, "title", ""))).strip() or "Untitled"
        todo.notes = self._optional_str(change.data.get("notes"))
        todo.completed = bool(change.data.get("completed", False))
        todo.priority = int(change.data.get("priority", 2))
        todo.due_at = self._coerce_datetime(change.data.get("due_at"))
        todo.updated_at = updated_at
        self.db.add(todo)
        self.db.flush()
        return TodoOut.model_validate(todo).model_dump(mode="json")

    def _upsert_memory(self, user_id: UUID, change: SyncChangeIn, updated_at: datetime) -> dict[str, Any]:
        memory = self.db.query(Memory).filter(Memory.id == change.entity_id, Memory.user_id == user_id).first()
        if not memory:
            memory = Memory(id=change.entity_id, user_id=user_id, created_at=self._coerce_datetime(change.data.get("created_at")) or updated_at)

        memory.category = str(change.data.get("category", "long_term"))
        memory.title = str(change.data.get("title", "Untitled")).strip()[:120] or "Untitled"
        memory.content = str(change.data.get("content", "")).strip()
        memory.source = str(change.data.get("source", "sync")).strip()[:50] or "sync"
        memory.importance = int(change.data.get("importance", 2))
        memory.pinned = bool(change.data.get("pinned", False))
        memory.tags = [str(item).strip()[:40] for item in change.data.get("tags", []) if str(item).strip()][:12]
        memory.emotion_label = self._optional_str(change.data.get("emotion_label"))
        memory.inferred = bool(change.data.get("inferred", False))
        memory.confidence = float(change.data.get("confidence", 1.0))
        memory.archived = bool(change.data.get("archived", False))
        memory.archived_reason = self._optional_str(change.data.get("archived_reason"))
        memory.archived_at = self._coerce_datetime(change.data.get("archived_at"))
        memory.embedding_model = change.data.get("embedding_model")
        memory.last_accessed_at = self._coerce_datetime(change.data.get("last_accessed_at"))
        memory.updated_at = updated_at
        self.db.add(memory)
        self.db.flush()
        return MemoryOut.model_validate(memory).model_dump(mode="json")

    def _delete_entity(self, user_id: UUID, entity_type: str, entity_id: UUID) -> None:
        model = {"messages": Message, "todos": Todo, "memory": Memory}[entity_type]
        entity = self.db.query(model).filter(model.id == entity_id).first()
        if not entity:
            return
        if entity_type == "messages":
            conversation = self.db.query(Conversation).filter(Conversation.id == entity.conversation_id).first()
            if not conversation or conversation.user_id != user_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync entity not found")
        elif entity.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync entity not found")
        self.db.delete(entity)
        self.db.flush()

    def _changes_since(self, user_id: UUID, since_version: int, exclude_device_id: str | None = None) -> list[SyncChangeOut]:
        query = (
            self.db.query(SyncOperation)
            .filter(SyncOperation.user_id == user_id, SyncOperation.server_version > since_version)
            .order_by(SyncOperation.server_version.asc(), SyncOperation.id.asc())
        )
        if exclude_device_id:
            query = query.filter(SyncOperation.source_device_id != exclude_device_id)
        return [self._operation_to_change(item) for item in query.all()]

    def _operation_to_change(self, operation: SyncOperation) -> SyncChangeOut:
        record = self._record_for(operation.entity_type, operation.entity_id)
        updated_at = record.updated_at if record else operation.created_at
        deleted = bool(record.deleted) if record else operation.operation == "delete"
        return SyncChangeOut(
            entity_type=operation.entity_type,  # type: ignore[arg-type]
            entity_id=operation.entity_id,
            operation=operation.operation,  # type: ignore[arg-type]
            data=operation.payload,
            vector_clock=operation.vector_clock,
            server_version=operation.server_version,
            updated_at=updated_at,
            deleted=deleted,
        )

    def _record_to_change(self, record: SyncRecord) -> SyncChangeOut:
        operation = (
            self.db.query(SyncOperation)
            .filter(SyncOperation.user_id == record.user_id, SyncOperation.server_version == record.version)
            .order_by(SyncOperation.id.desc())
            .first()
        )
        data = operation.payload if operation else {}
        return SyncChangeOut(
            entity_type=record.entity_type,  # type: ignore[arg-type]
            entity_id=record.entity_id,
            operation=("delete" if record.deleted else "upsert"),
            data=data,
            vector_clock=record.vector_clock,
            server_version=record.version,
            updated_at=record.updated_at,
            deleted=record.deleted,
        )

    def _append_operation(
        self,
        record: SyncRecord,
        operation: str,
        data: dict[str, Any],
        source_device_id: str,
        conflict: bool,
    ) -> SyncOperation:
        sync_operation = SyncOperation(
            user_id=record.user_id,
            entity_type=record.entity_type,
            entity_id=record.entity_id,
            operation=operation,
            server_version=record.version,
            vector_clock=record.vector_clock,
            payload=data,
            conflict=conflict,
            source_device_id=source_device_id,
        )
        self.db.add(sync_operation)
        self.db.flush()
        return sync_operation

    def _publish_sync_change(self, record: SyncRecord, operation: str, data: dict[str, Any]) -> None:
        realtime_sync_service.publish(
            record.user_id,
            "sync.change",
            self._record_to_change(record).model_dump(mode="json") | {"data": data},
        )

    def _build_result(
        self,
        change: SyncChangeIn,
        record: SyncRecord,
        resolution: str,
        conflict: bool,
        remote: SyncChangeOut | None,
    ) -> SyncPushResult:
        return SyncPushResult(
            client_change_id=change.client_change_id,
            entity_type=change.entity_type,
            entity_id=change.entity_id,
            operation=change.operation,
            resolution=resolution,  # type: ignore[arg-type]
            server_version=record.version,
            vector_clock=record.vector_clock,
            conflict=conflict,
            remote=remote,
        )

    def _get_or_create_record(self, user_id: UUID, entity_type: str, entity_id: UUID) -> SyncRecord:
        record = self._record_for(entity_type, entity_id)
        if record:
            return record
        return SyncRecord(user_id=user_id, entity_type=entity_type, entity_id=entity_id)

    def _record_for(self, entity_type: str, entity_id: UUID) -> SyncRecord | None:
        return (
            self.db.query(SyncRecord)
            .filter(SyncRecord.entity_type == entity_type, SyncRecord.entity_id == entity_id)
            .first()
        )

    def _compare_clocks(self, incoming: dict[str, int], current: dict[str, int]) -> str:
        incoming_dominates = self._dominates(incoming, current)
        current_dominates = self._dominates(current, incoming)
        if incoming_dominates and not current_dominates:
            return "newer"
        if current_dominates and not incoming_dominates:
            return "older"
        if incoming == current:
            return "same"
        return "concurrent"

    def _dominates(self, left: dict[str, int], right: dict[str, int]) -> bool:
        keys = set(left) | set(right)
        return all(int(left.get(key, 0)) >= int(right.get(key, 0)) for key in keys) and any(
            int(left.get(key, 0)) > int(right.get(key, 0)) for key in keys
        )

    def _merge_clocks(self, left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
        return {key: max(int(left.get(key, 0)), int(right.get(key, 0))) for key in set(left) | set(right)}

    def _tick_clock(self, clock: dict[str, int], device_id: str) -> dict[str, int]:
        ticked = {key: int(value) for key, value in clock.items()}
        ticked[device_id] = int(ticked.get(device_id, 0)) + 1
        return ticked

    def _required_uuid(self, data: dict[str, Any], key: str) -> UUID:
        value = data.get(key)
        if not value:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{key} is required")
        return UUID(str(value))

    def _require_user(self, user_id: UUID) -> None:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    def _optional_str(self, value: Any) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    def _coerce_datetime(self, value: Any) -> datetime | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return self._normalize_dt(value)
        return self._normalize_dt(datetime.fromisoformat(str(value).replace("Z", "+00:00")))

    def _normalize_dt(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)
