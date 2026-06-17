from __future__ import annotations

import json
import math
import re
import uuid
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.memory import Memory, Vector
from app.schemas.message import MessageRole
from app.services.ai_client import AIClient
from app.services.embedding_service import EmbeddingService


@dataclass(frozen=True)
class MemoryCandidate:
    content: str
    importance: float = 0.5


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
        self.enabled = settings.memory_pgvector_enabled if enabled is None else enabled
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
    ) -> list[Memory]:
        if not self.enabled:
            return []

        query_embedding = self.embedding_service.embed(query)
        if not query_embedding:
            return []

        limit = max(top_k or self.max_results, 1)
        with self.session_factory() as db:
            if self._can_use_pgvector(db):
                memories = (
                    db.query(Memory)
                    .filter(Memory.user_id == user_id)
                    .order_by(Memory.embedding.cosine_distance(query_embedding))
                    .limit(limit)
                    .all()
                )
            else:
                candidates = db.query(Memory).filter(Memory.user_id == user_id).all()
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
            print(f"[MEMORY] skipped memory write: {exc}")
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
