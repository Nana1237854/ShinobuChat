from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db_utils import require_user
from app.models.memory import Memory, MemoryPreference
from app.schemas.memory import (
    MemoryCategory,
    MemoryCreate,
    MemoryOut,
    MemoryPreferenceUpdate,
    MemorySearchHit,
    MemorySearchRequest,
    MemoryUpdate,
)
from app.services.embedding_service import EmbeddingService
from app.services.realtime_sync_service import realtime_sync_service
from app.services.sync_service import SyncService


class MemoryService:
    def __init__(self, db: Session):
        self.db = db
        self.embedding = EmbeddingService(db)

    def create(self, payload: MemoryCreate) -> Memory:
        require_user(self.db, payload.user_id)
        self._ensure_inference_allowed(payload.user_id, payload.inferred)
        embedding = self.embedding.embed(f"{payload.title} {payload.content} {' '.join(payload.tags)}")
        memory = Memory(
            user_id=payload.user_id,
            category=payload.category.value,
            title=payload.title.strip(),
            content=payload.content.strip(),
            source=payload.source.strip(),
            importance=payload.importance,
            pinned=payload.pinned,
            tags=self._clean_tags(payload.tags),
            emotion_label=self._clean_optional(payload.emotion_label),
            inferred=payload.inferred,
            confidence=payload.confidence,
            embedding_model=settings.memory_embedding_model,
            embedding=embedding,
        )
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        SyncService(self.db).record_server_change(
            memory.user_id,
            "memory",
            memory.id,
            "upsert",
            MemoryOut.model_validate(memory).model_dump(mode="json"),
            memory.updated_at,
        )
        self._publish("memory.created", memory)
        return memory

    def list_by_user(
        self,
        user_id: UUID,
        category: MemoryCategory | None = None,
        include_archived: bool = False,
    ) -> list[Memory]:
        require_user(self.db, user_id)
        query = self.db.query(Memory).filter(Memory.user_id == user_id)
        if category:
            query = query.filter(Memory.category == category.value)
        if not include_archived:
            query = query.filter(Memory.archived.is_(False))
        return query.order_by(Memory.pinned.desc(), Memory.updated_at.desc()).all()

    def search(self, payload: MemorySearchRequest) -> list[MemorySearchHit]:
        require_user(self.db, payload.user_id)
        query_embedding = self.embedding.embed(payload.query)
        return self.embedding.search(
            payload.user_id,
            query_embedding,
            category=payload.category,
            limit=payload.limit,
            min_similarity=payload.min_similarity,
            include_archived=payload.include_archived,
        )

    def update(self, memory_id: UUID, user_id: UUID, payload: MemoryUpdate) -> Memory:
        memory = self.get_for_user(memory_id, user_id, include_archived=True)
        updates = payload.model_dump(exclude_unset=True)
        should_refresh_embedding = False

        for key, value in updates.items():
            if isinstance(value, str):
                value = value.strip()
            if key == "category" and value is not None:
                value = value.value
                should_refresh_embedding = True
            if key in {"title", "content", "tags"}:
                should_refresh_embedding = True
            if key == "tags" and value is not None:
                value = self._clean_tags(value)
            if key == "emotion_label":
                value = self._clean_optional(value)
            if key == "archived":
                memory.archived_at = datetime.utcnow() if value else None
                memory.archived_reason = "manual_archive" if value else None
            setattr(memory, key, value)

        if should_refresh_embedding:
            memory.embedding = self.embedding.embed(f"{memory.title} {memory.content} {' '.join(memory.tags)}")
            memory.embedding_model = settings.memory_embedding_model

        memory.updated_at = datetime.utcnow()
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        SyncService(self.db).record_server_change(
            memory.user_id,
            "memory",
            memory.id,
            "upsert",
            MemoryOut.model_validate(memory).model_dump(mode="json"),
            memory.updated_at,
        )
        self._publish("memory.updated", memory)
        return memory

    def undo_inference(self, memory_id: UUID, user_id: UUID) -> Memory:
        memory = self.get_for_user(memory_id, user_id, include_archived=True)
        if not memory.inferred:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only inferred memories can be undone",
            )
        memory.archived = True
        memory.archived_reason = "user_undo_inference"
        memory.archived_at = datetime.utcnow()
        memory.updated_at = datetime.utcnow()
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        SyncService(self.db).record_server_change(
            memory.user_id,
            "memory",
            memory.id,
            "upsert",
            MemoryOut.model_validate(memory).model_dump(mode="json"),
            memory.updated_at,
        )
        self._publish("memory.inference_undone", memory)
        return memory

    def delete(self, memory_id: UUID, user_id: UUID) -> None:
        memory = self.get_for_user(memory_id, user_id, include_archived=True)
        payload = MemoryOut.model_validate(memory).model_dump(mode="json")
        SyncService(self.db).record_server_change(user_id, "memory", memory.id, "delete", payload, datetime.utcnow())
        self.db.delete(memory)
        self.db.commit()
        realtime_sync_service.publish(user_id, "memory.deleted", {"memory": payload})

    def get_for_user(self, memory_id: UUID, user_id: UUID, include_archived: bool = False) -> Memory:
        query = self.db.query(Memory).filter(Memory.id == memory_id, Memory.user_id == user_id)
        if not include_archived:
            query = query.filter(Memory.archived.is_(False))
        memory = query.first()
        if not memory:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
        return memory

    def get_preferences(self, user_id: UUID) -> MemoryPreference:
        require_user(self.db, user_id)
        preference = self.db.query(MemoryPreference).filter(MemoryPreference.user_id == user_id).first()
        if preference:
            return preference
        preference = MemoryPreference(user_id=user_id, enabled=True)
        self.db.add(preference)
        self.db.commit()
        self.db.refresh(preference)
        return preference

    def update_preferences(self, user_id: UUID, payload: MemoryPreferenceUpdate) -> MemoryPreference:
        preference = self.get_preferences(user_id)
        preference.enabled = payload.enabled
        preference.updated_at = datetime.utcnow()
        self.db.add(preference)
        self.db.commit()
        self.db.refresh(preference)
        realtime_sync_service.publish(
            user_id,
            "memory.preference_updated",
            {"memory_enabled": preference.enabled, **realtime_sync_service.status_payload(user_id)},
        )
        return preference

    def _ensure_inference_allowed(self, user_id: UUID, inferred: bool) -> None:
        if inferred and not self.get_preferences(user_id).enabled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Memory inference is paused for this user",
            )

    def _publish(self, event_type: str, memory: Memory) -> None:
        realtime_sync_service.publish(
            memory.user_id,
            event_type,
            {
                "memory": MemoryOut.model_validate(memory).model_dump(mode="json"),
                **realtime_sync_service.status_payload(memory.user_id),
            },
        )

    def _clean_tags(self, tags: list[str]) -> list[str]:
        return [tag.strip()[:40] for tag in tags if tag and tag.strip()][:12]

    def _clean_optional(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None
