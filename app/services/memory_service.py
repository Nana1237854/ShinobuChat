from __future__ import annotations

import json
import logging
import math
import re
import uuid
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)
from app.core.exceptions import NotFoundError
from app.db.session import SessionLocal
from app.models.memory import Memory, Vector
from app.schemas.message import MessageRole
from app.services.ai_client import AIClient
from app.services.embedding_service import EmbeddingService


@dataclass(frozen=True)
class MemoryCandidate:
    content: str
    importance: float = 0.5


@dataclass(frozen=True)
class MemoryContextMessage:
    id: uuid.UUID
    role: str
    content: str
    created_at: object


@dataclass(frozen=True)
class SimpleMemoryContext:
    memory_id: uuid.UUID
    source_msg_id: uuid.UUID | None
    conversation_id: uuid.UUID | None
    messages: list[MemoryContextMessage]
    detail: str | None


class MemoryService:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        ai_client: AIClient,
        session_factory: Callable[[], Session] = SessionLocal,
        *,
        enabled: bool | None = None,
        max_results: int | None = None,
    ):
        self.embedding_service = embedding_service
        self.ai_client = ai_client
        self.session_factory = session_factory
        self.enabled = settings.memory_enabled if enabled is None else enabled
        self.max_results = max_results or settings.memory_max_results

    def store_memory(
        self,
        user_id: uuid.UUID,
        content: str,
        embedding: list[float] | None = None,
        *,
        source_msg_id: uuid.UUID | None = None,
        importance: float = 0.5,
    ) -> Memory | None:
        if not self.enabled:
            return None

        memory_content = " ".join(content.strip().split())
        if not memory_content:
            return None

        vector = embedding if embedding is not None else self.embedding_service.embed(memory_content)
        if not vector:
            return None

        memory = Memory(
            user_id=user_id,
            content=memory_content,
            embedding=vector,
            source_msg_id=source_msg_id,
            importance=max(0.0, min(float(importance), 1.0)),
        )
        with self.session_factory() as db:
            db.add(memory)
            db.commit()
            db.refresh(memory)
            db.expunge(memory)
        return memory

    def search_memories(
        self,
        user_id: uuid.UUID,
        query: str,
        *,
        top_k: int | None = None,
        include_archived: bool = False,
    ) -> list[Memory]:
        if not self.enabled:
            return []

        query_embedding = self.embedding_service.embed(query)
        if not query_embedding:
            return []

        limit = max(top_k or self.max_results, 1)
        with self.session_factory() as db:
            if self._can_use_pgvector(db):
                query = db.query(Memory).filter(Memory.user_id == user_id)
                if not include_archived:
                    query = query.filter(Memory.archived.is_(False))
                memories = (
                    query.order_by(Memory.embedding.cosine_distance(query_embedding))
                    .limit(limit)
                    .all()
                )
            else:
                candidates = db.query(Memory).filter(Memory.user_id == user_id).all()
                if not include_archived:
                    candidates = [c for c in candidates if not c.archived]
                memories = sorted(
                    candidates,
                    key=lambda memory: self._cosine_distance(query_embedding, self._as_vector(memory.embedding)),
                )[:limit]
            for memory in memories:
                db.expunge(memory)
            return memories

    def extract_memories(self, conversation_text: str) -> list[MemoryCandidate]:
        text = conversation_text.strip()
        if not self.enabled or not text:
            return []

        messages = [
            {
                "role": MessageRole.SYSTEM.value,
                "content": (
                    "你是 ShinobuChat 的长期记忆提取器。只提取对未来对话有帮助的稳定事实，"
                    "例如用户姓名、偏好、长期目标、重要经历、常用设置。"
                    "不要保存临时寒暄、一次性任务结果或敏感信息。"
                    "请只输出 JSON 数组，每项格式为 {\"content\": \"...\", \"importance\": 0.0-1.0}。"
                    "如果没有值得保存的内容，输出 []。"
                ),
            },
            {"role": MessageRole.USER.value, "content": text},
        ]
        response = self.ai_client.complete_chat(messages, max_tokens=512)
        content = str(response.get("content") or "").strip()
        return self._parse_candidates(content)

    def extract_and_store_after_turn(
        self,
        *,
        user_id: uuid.UUID,
        user_text: str,
        assistant_text: str,
        source_msg_id: uuid.UUID | None,
    ) -> int:
        if not self.enabled:
            return 0

        conversation_text = f"用户：{user_text.strip()}\n助手：{assistant_text.strip()}"
        stored = 0
        try:
            candidates = self.extract_memories(conversation_text)
            for candidate in candidates:
                if self.store_memory(
                    user_id,
                    candidate.content,
                    source_msg_id=source_msg_id,
                    importance=candidate.importance,
                ):
                    stored += 1
        except Exception as exc:  # Keep memory write failures off the user-visible reply path.
            logger.debug("[MEMORY] skipped memory write: %s", exc)
        return stored

    def _parse_candidates(self, content: str) -> list[MemoryCandidate]:
        if not content:
            return []

        payload = content
        fenced = re.search(r"```(?:json)?\s*(.*?)```", content, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            payload = fenced.group(1).strip()

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return []

        if not isinstance(data, list):
            return []

        candidates: list[MemoryCandidate] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            memory_content = str(item.get("content") or "").strip()
            if not memory_content:
                continue
            importance = item.get("importance", 0.5)
            try:
                score = max(0.0, min(float(importance), 1.0))
            except (TypeError, ValueError):
                score = 0.5
            candidates.append(MemoryCandidate(memory_content, score))
        return candidates

    # ---- CRUD methods for routes ----

    def create(self, user_id, payload) -> Memory:
        """Create a memory from MemoryCreate schema. user_id from JWT, not payload."""
        from app.models.memory import Memory as MemoryModel

        embedding = None
        if self.enabled:
            embedding = self.embedding_service.embed(payload.content)
            if not embedding:
                embedding = [0.0] * settings.memory_embedding_dimensions
        else:
            embedding = [0.0] * settings.memory_embedding_dimensions

        memory = MemoryModel(
            user_id=user_id,
            category=payload.category.value if hasattr(payload.category, 'value') else str(payload.category),
            title=payload.title,
            content=payload.content,
            source=payload.source,
            embedding=embedding,
            importance=float(payload.importance),
            pinned=payload.pinned,
            tags=payload.tags or [],
            emotion_label=payload.emotion_label,
            inferred=payload.inferred,
            confidence=float(payload.confidence),
        )
        with self.session_factory() as db:
            db.add(memory)
            db.commit()
            db.refresh(memory)
            db.expunge(memory)
        return memory

    def list_by_user(self, user_id, category=None, include_archived=False) -> list:
        with self.session_factory() as db:
            query = db.query(Memory).filter(Memory.user_id == user_id)
            if category is not None:
                cat_val = category.value if hasattr(category, 'value') else str(category)
                query = query.filter(Memory.category == cat_val)
            if not include_archived:
                query = query.filter(Memory.archived.is_(False))
            results = query.order_by(Memory.created_at.desc()).all()
            for item in results:
                db.expunge(item)
            return results

    def search(self, payload) -> list:
        """Search memories via embedding + optional filters."""
        embeddings = self.search_memories(
            user_id=payload.user_id,
            query=payload.query,
            top_k=payload.limit,
        )
        from app.schemas.memory import MemoryOut, MemorySearchHit

        results: list = []
        for mem in embeddings:
            if payload.category and mem.category != (payload.category.value if hasattr(payload.category, 'value') else payload.category):
                continue
            if payload.include_archived is False and mem.archived:
                continue
            results.append(MemorySearchHit(
                memory=MemoryOut.model_validate(mem),
                similarity=0.0,
                distance=0.0,
            ))
        return results[:payload.limit]

    def update(self, memory_id, user_id, payload) -> Memory:
        with self.session_factory() as db:
            mem = db.query(Memory).filter(Memory.id == memory_id, Memory.user_id == user_id).first()
            if mem is None:
                raise NotFoundError("Memory not found")
            for key, value in payload.model_dump(exclude_unset=True).items():
                if hasattr(mem, key):
                    setattr(mem, key, value)
            db.add(mem)
            db.commit()
            db.refresh(mem)
            db.expunge(mem)
        return mem

    def undo_inference(self, memory_id, user_id) -> Memory:
        with self.session_factory() as db:
            mem = db.query(Memory).filter(Memory.id == memory_id, Memory.user_id == user_id).first()
            if mem is None:
                raise NotFoundError("Memory not found")
            mem.inferred = False
            db.add(mem)
            db.commit()
            db.refresh(mem)
            db.expunge(mem)
        return mem

    def delete(self, memory_id, user_id) -> None:
        with self.session_factory() as db:
            mem = db.query(Memory).filter(Memory.id == memory_id, Memory.user_id == user_id).first()
            if mem is None:
                raise NotFoundError("Memory not found")
            db.delete(mem)
            db.commit()

    def get_preferences(self, user_id):
        from app.models.memory import MemoryPreference

        with self.session_factory() as db:
            pref = db.query(MemoryPreference).filter(MemoryPreference.user_id == user_id).first()
            if pref is None:
                pref = MemoryPreference(user_id=user_id, enabled=True)
                db.add(pref)
                db.commit()
                db.refresh(pref)
            db.expunge(pref)
            return pref

    def update_preferences(self, user_id, payload):
        from app.models.memory import MemoryPreference

        with self.session_factory() as db:
            pref = db.query(MemoryPreference).filter(MemoryPreference.user_id == user_id).first()
            if pref is None:
                pref = MemoryPreference(user_id=user_id, enabled=payload.enabled)
                db.add(pref)
            else:
                pref.enabled = payload.enabled
            db.commit()
            if hasattr(db, 'refresh'):
                db.refresh(pref)
            if hasattr(db, 'expunge'):
                db.expunge(pref)
            return pref

    # ---- Timeline / Context ----

    def list_timeline(self, user_id, limit: int = 50, offset: int = 0) -> list:
        with self.session_factory() as db:
            results = (
                db.query(Memory)
                .filter(Memory.user_id == user_id, Memory.archived.is_(False))
                .order_by(Memory.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            for item in results:
                db.expunge(item)
            return results

    def get_memory_context(self, user_id, memory_id, window: int = 3):
        window = max(1, min(window, 10))
        with self.session_factory() as db:
            mem = db.query(Memory).filter(Memory.id == memory_id, Memory.user_id == user_id).first()
            if mem is None:
                raise NotFoundError("Memory not found")

            if mem.source_msg_id is None:
                return SimpleMemoryContext(memory_id=mem.id, source_msg_id=None, conversation_id=None, messages=[], detail="source context unavailable")

            from app.models.conversation import Conversation
            from app.models.message import Message

            source_msg = db.query(Message).filter(Message.id == mem.source_msg_id).first()
            if source_msg is None:
                return SimpleMemoryContext(memory_id=mem.id, source_msg_id=mem.source_msg_id, conversation_id=None, messages=[], detail="source message not found")

            conv = db.query(Conversation).filter(Conversation.id == source_msg.conversation_id).first()
            if conv is None or conv.user_id != user_id:
                return SimpleMemoryContext(memory_id=mem.id, source_msg_id=mem.source_msg_id, conversation_id=None, messages=[], detail="source context unavailable")

            conversation_id = source_msg.conversation_id
            before = (
                db.query(Message)
                .filter(Message.conversation_id == conversation_id, Message.created_at < source_msg.created_at)
                .order_by(Message.created_at.desc())
                .limit(window)
                .all()[::-1]
            )
            after = (
                db.query(Message)
                .filter(Message.conversation_id == conversation_id, Message.created_at > source_msg.created_at)
                .order_by(Message.created_at.asc())
                .limit(window)
                .all()
            )
            all_msgs = before + [source_msg] + after
            for msg in all_msgs:
                db.expunge(msg)
            return SimpleMemoryContext(
                memory_id=mem.id,
                source_msg_id=mem.source_msg_id,
                conversation_id=conversation_id,
                messages=[
                    MemoryContextMessage(id=msg.id, role=msg.role, content=msg.content, created_at=msg.created_at)
                    for msg in all_msgs
                ],
                detail=None,
            )

    def _can_use_pgvector(self, db: Session) -> bool:
        return Vector is not None and db.bind is not None and db.bind.dialect.name == "postgresql"

    def _cosine_distance(self, left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return math.inf
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return math.inf
        return 1 - (dot / (left_norm * right_norm))

    def _as_vector(self, value: object) -> list[float]:
        if value is None:
            return []
        return [float(item) for item in value]
