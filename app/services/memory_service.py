from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.models.user import User
from app.schemas.memory import MemoryCreate, MemoryOut, MemoryUpdate
from app.services.realtime_sync_service import realtime_sync_service


class MemoryService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: MemoryCreate) -> Memory:
        self._require_user(payload.user_id)
        memory = Memory(
            user_id=payload.user_id,
            title=payload.title.strip(),
            content=payload.content.strip(),
            source=payload.source.strip(),
            importance=payload.importance,
            pinned=payload.pinned,
        )
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        self._publish("memory.created", memory)
        return memory

    def list_by_user(self, user_id: UUID) -> list[Memory]:
        self._require_user(user_id)
        return (
            self.db.query(Memory)
            .filter(Memory.user_id == user_id)
            .order_by(Memory.pinned.desc(), Memory.updated_at.desc())
            .all()
        )

    def update(self, memory_id: UUID, user_id: UUID, payload: MemoryUpdate) -> Memory:
        memory = self.get_for_user(memory_id, user_id)
        updates = payload.model_dump(exclude_unset=True)
        for key, value in updates.items():
            if isinstance(value, str):
                value = value.strip()
            setattr(memory, key, value)
        memory.updated_at = datetime.utcnow()
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        self._publish("memory.updated", memory)
        return memory

    def delete(self, memory_id: UUID, user_id: UUID) -> None:
        memory = self.get_for_user(memory_id, user_id)
        payload = MemoryOut.model_validate(memory).model_dump(mode="json")
        self.db.delete(memory)
        self.db.commit()
        realtime_sync_service.publish(user_id, "memory.deleted", {"memory": payload})

    def get_for_user(self, memory_id: UUID, user_id: UUID) -> Memory:
        memory = (
            self.db.query(Memory)
            .filter(Memory.id == memory_id, Memory.user_id == user_id)
            .first()
        )
        if not memory:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
        return memory

    def _require_user(self, user_id: UUID) -> None:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    def _publish(self, event_type: str, memory: Memory) -> None:
        realtime_sync_service.publish(
            memory.user_id,
            event_type,
            {
                "memory": MemoryOut.model_validate(memory).model_dump(mode="json"),
                **realtime_sync_service.status_payload(memory.user_id),
            },
        )
