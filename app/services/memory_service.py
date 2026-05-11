from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.vector import format_vector
from app.models.memory import Memory, MemoryPreference
from app.models.user import User
from app.schemas.memory import (
    MemoryCategory,
    MemoryCreate,
    MemoryOut,
    MemoryPreferenceUpdate,
    MemorySearchHit,
    MemorySearchRequest,
    MemoryUpdate,
)
from app.services.realtime_sync_service import realtime_sync_service
from app.services.sync_service import SyncService


class MemoryService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: MemoryCreate) -> Memory:
        self._require_user(payload.user_id)
        self._ensure_inference_allowed(payload.user_id, payload.inferred)
        embedding = self._embed_payload(payload.title, payload.content, payload.tags)
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
        self._require_user(user_id)
        query = self.db.query(Memory).filter(Memory.user_id == user_id)
        if category:
            query = query.filter(Memory.category == category.value)
        if not include_archived:
            query = query.filter(Memory.archived.is_(False))
        return query.order_by(Memory.pinned.desc(), Memory.updated_at.desc()).all()

    def search(self, payload: MemorySearchRequest) -> list[MemorySearchHit]:
        self._require_user(payload.user_id)
        query_embedding = self._embed_text(payload.query)
        if (
            settings.memory_pgvector_enabled
            and self.db.bind
            and self.db.bind.dialect.name == "postgresql"
        ):
            return self._search_pgvector(payload, query_embedding)
        return self._search_in_python(payload, query_embedding)

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
            memory.embedding = self._embed_payload(memory.title, memory.content, memory.tags)
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
        self._require_user(user_id)
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

    def _search_pgvector(
        self,
        payload: MemorySearchRequest,
        query_embedding: list[float],
    ) -> list[MemorySearchHit]:
        filters = ["user_id = :user_id", "embedding IS NOT NULL"]
        params: dict[str, object] = {
            "user_id": payload.user_id,
            "query_embedding": format_vector(query_embedding),
            "limit": payload.limit,
        }
        if payload.category:
            filters.append("category = :category")
            params["category"] = payload.category.value
        if not payload.include_archived:
            filters.append("archived = false")

        statement = text(
            f"""
            SELECT id, embedding <=> CAST(:query_embedding AS vector) AS distance
            FROM memories
            WHERE {" AND ".join(filters)}
            ORDER BY embedding <=> CAST(:query_embedding AS vector)
            LIMIT :limit
            """
        )
        rows = self.db.execute(statement, params).all()
        distances = {row.id: float(row.distance) for row in rows}
        if not distances:
            return []

        memories = self.db.query(Memory).filter(Memory.id.in_(distances.keys())).all()
        ordered = sorted(memories, key=lambda item: distances[item.id])
        return [self._hit(memory, distances[memory.id]) for memory in ordered if self._similarity(distances[memory.id]) >= payload.min_similarity]

    def _search_in_python(
        self,
        payload: MemorySearchRequest,
        query_embedding: list[float],
    ) -> list[MemorySearchHit]:
        candidates = self.list_by_user(payload.user_id, payload.category, payload.include_archived)
        ranked: list[tuple[Memory, float]] = []
        for memory in candidates:
            embedding = self._coerce_embedding(memory.embedding)
            if not embedding:
                continue
            distance = self._cosine_distance(query_embedding, embedding)
            if self._similarity(distance) >= payload.min_similarity:
                ranked.append((memory, distance))
        ranked.sort(key=lambda item: item[1])
        return [self._hit(memory, distance) for memory, distance in ranked[: payload.limit]]

    def _hit(self, memory: Memory, distance: float) -> MemorySearchHit:
        memory.last_accessed_at = datetime.utcnow()
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        return MemorySearchHit(
            memory=MemoryOut.model_validate(memory),
            similarity=self._similarity(distance),
            distance=distance,
        )

    def _ensure_inference_allowed(self, user_id: UUID, inferred: bool) -> None:
        if inferred and not self.get_preferences(user_id).enabled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Memory inference is paused for this user",
            )

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

    def _embed_payload(self, title: str, content: str, tags: list[str]) -> list[float]:
        return self._embed_text(" ".join([title, content, " ".join(tags)]))

    def _embed_text(self, text_value: str) -> list[float]:
        dimensions = settings.memory_embedding_dimensions
        vector = [0.0] * dimensions
        normalized = text_value.lower()
        tokens = re.findall(r"[a-z0-9_]+", normalized)
        cjk_chars = re.findall(r"[\u4e00-\u9fff]", normalized)
        tokens.extend(cjk_chars)
        tokens.extend("".join(cjk_chars[index : index + 2]) for index in range(len(cjk_chars) - 1))
        tokens.extend("".join(cjk_chars[index : index + 3]) for index in range(len(cjk_chars) - 2))
        if not tokens:
            tokens = [normalized.strip() or "empty"]

        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
            index = int.from_bytes(digest[:4], "big") % dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + (len(token) % 7) / 10.0
            vector[index] += sign * weight

        norm = math.sqrt(sum(item * item for item in vector))
        if norm == 0:
            return vector
        return [item / norm for item in vector]

    def _coerce_embedding(self, value: object) -> list[float] | None:
        if value is None:
            return None
        if isinstance(value, list):
            return [float(item) for item in value]
        if isinstance(value, str):
            stripped = value.strip().strip("[]")
            if not stripped:
                return None
            return [float(item) for item in stripped.split(",")]
        return [float(item) for item in value]  # type: ignore[arg-type]

    def _cosine_distance(self, left: list[float], right: list[float]) -> float:
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(item * item for item in left))
        right_norm = math.sqrt(sum(item * item for item in right))
        if left_norm == 0 or right_norm == 0:
            return 1.0
        return 1.0 - (dot / (left_norm * right_norm))

    def _similarity(self, distance: float) -> float:
        return max(0.0, min(1.0, 1.0 - distance))

    def _clean_tags(self, tags: list[str]) -> list[str]:
        return [tag.strip()[:40] for tag in tags if tag and tag.strip()][:12]

    def _clean_optional(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None
