from __future__ import annotations

import uuid

from app.services.memory_service import MemoryCandidate, MemoryService

_RECALL_PATTERNS = [
    "上次聊到什么",
    "我们之前说过什么",
    "我以前提过什么",
    "之前那个",
    "还记得我上次",
    "我们聊到一半",
    "上次说的",
    "之前说过",
    "你还记得",
    "之前聊过",
    "以前说过",
    "之前提到过",
    "上次讨论",
    "之前讨论",
    "上次那个",
    "之前那个",
]


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

    @staticmethod
    def is_recall_question(content: str) -> bool:
        """Return True if the message looks like a memory recall question."""
        return any(pattern in content for pattern in _RECALL_PATTERNS)

    def search_for_recall(self, user_id: uuid.UUID, content: str, top_k: int = 5) -> list[str]:
        """Search memories for recall context. Returns empty list if no matches."""
        results = self.search(user_id, content)
        return results[:top_k]

    def build_recall_context(self, memories: list[str]) -> str:
        """Build a prompt-safe context string from memory search results."""
        if not memories:
            return "未找到相关长期记忆。"
        lines = ["以下是与用户问题相关的长期记忆："]
        for i, mem in enumerate(memories, 1):
            lines.append(f"{i}. {mem}")
        return "\n".join(lines)
