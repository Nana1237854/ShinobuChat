import hashlib
import math
import re
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.vector import format_vector
from app.models.memory import Memory
from app.schemas.memory import MemoryCategory, MemoryOut, MemorySearchHit


class EmbeddingService:
    def __init__(self, db: Session):
        self.db = db

    def embed(self, text: str) -> list[float]:
        dimensions = settings.memory_embedding_dimensions
        vector = [0.0] * dimensions
        tokens = self._tokenize(text)

        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
            index = int.from_bytes(digest[:4], "big") % dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + (len(token) % 7) / 10.0
            vector[index] += sign * weight

        return self._normalize(vector)

    def search(
        self,
        user_id: UUID,
        query_embedding: list[float],
        *,
        category: MemoryCategory | None = None,
        limit: int = 8,
        min_similarity: float = 0.0,
        include_archived: bool = False,
    ) -> list[MemorySearchHit]:
        if (
            settings.memory_pgvector_enabled
            and self.db.bind
            and self.db.bind.dialect.name == "postgresql"
        ):
            return self._search_pgvector(
                user_id,
                query_embedding,
                category=category,
                limit=limit,
                min_similarity=min_similarity,
                include_archived=include_archived,
            )
        return self._search_in_python(
            user_id,
            query_embedding,
            category=category,
            limit=limit,
            min_similarity=min_similarity,
            include_archived=include_archived,
        )

    def _tokenize(self, text_value: str) -> list[str]:
        normalized = text_value.lower()
        tokens = re.findall(r"[a-z0-9_]+", normalized)
        cjk_chars = re.findall(r"[\u4e00-\u9fff]", normalized)
        tokens.extend(cjk_chars)
        tokens.extend("".join(cjk_chars[index : index + 2]) for index in range(len(cjk_chars) - 1))
        tokens.extend("".join(cjk_chars[index : index + 3]) for index in range(len(cjk_chars) - 2))
        if not tokens:
            tokens = [normalized.strip() or "empty"]
        return tokens

    def _normalize(self, vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(item * item for item in vector))
        if norm == 0:
            return vector
        return [item / norm for item in vector]

    def _search_pgvector(
        self,
        user_id: UUID,
        query_embedding: list[float],
        *,
        category: MemoryCategory | None = None,
        limit: int = 8,
        min_similarity: float = 0.0,
        include_archived: bool = False,
    ) -> list[MemorySearchHit]:
        filters = ["user_id = :user_id", "embedding IS NOT NULL"]
        params: dict[str, object] = {
            "user_id": user_id,
            "query_embedding": format_vector(query_embedding),
            "limit": limit,
        }
        if category:
            filters.append("category = :category")
            params["category"] = category.value
        if not include_archived:
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
        return [
            self._hit(memory, distances[memory.id])
            for memory in ordered
            if self._similarity(distances[memory.id]) >= min_similarity
        ]

    def _search_in_python(
        self,
        user_id: UUID,
        query_embedding: list[float],
        *,
        category: MemoryCategory | None = None,
        limit: int = 8,
        min_similarity: float = 0.0,
        include_archived: bool = False,
    ) -> list[MemorySearchHit]:
        query = self.db.query(Memory).filter(Memory.user_id == user_id)
        if category:
            query = query.filter(Memory.category == category.value)
        if not include_archived:
            query = query.filter(Memory.archived.is_(False))

        ranked: list[tuple[Memory, float]] = []
        for memory in query.all():
            embedding = self._coerce_embedding(memory.embedding)
            if not embedding:
                continue
            distance = self._cosine_distance(query_embedding, embedding)
            if self._similarity(distance) >= min_similarity:
                ranked.append((memory, distance))
        ranked.sort(key=lambda item: item[1])
        return [self._hit(memory, distance) for memory, distance in ranked[:limit]]

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
