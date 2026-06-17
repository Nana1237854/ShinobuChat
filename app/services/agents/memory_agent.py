from __future__ import annotations

import uuid

from app.services.memory_service import MemoryCandidate, MemoryService


class MemoryAgent:
    def __init__(self, memory_service: MemoryService):
        self.memory_service = memory_service

    def search(self, user_id: uuid.UUID, query: str) -> list[str]:
        return [memory.content for memory in self.memory_service.search_memories(user_id, query)]

    def extract(self, conversation_text: str) -> list[MemoryCandidate]:
        return self.memory_service.extract_memories(conversation_text)

    def extract_and_store_after_turn(
        self,
        *,
        user_id: uuid.UUID,
        user_text: str,
        assistant_text: str,
        source_msg_id: uuid.UUID | None,
    ) -> int:
        return self.memory_service.extract_and_store_after_turn(
            user_id=user_id,
            user_text=user_text,
            assistant_text=assistant_text,
            source_msg_id=source_msg_id,
        )
