from __future__ import annotations

import logging

from app.models.message import Message
from app.services.prefix_cache_manager import PrefixCacheManager

logger = logging.getLogger("shinobu.chat_agent")


class ChatAgent:
    def __init__(self, prefix_cache: PrefixCacheManager | None = None):
        self.prefix_cache = prefix_cache or PrefixCacheManager()
        self.last_prefix_sha = ""

    def build_messages(
        self,
        content: str,
        history: list[Message],
        memory_context: list[str] | None = None,
    ) -> list[dict[str, str]]:
        base_system = (
            "你是 ShinobuChat 的 AI 伙伴。用简洁、温暖、可靠的中文回复用户。"
            "当前是纯聊天模式，优先自然陪伴、澄清想法，用 1-3 句话简短回复。"
            "\n\n【重要】你的每条回复开头必须包含一个情绪标签，格式为 [emotion]。"
            "可选情绪：happy、sad、angry、surprised、thinking、neutral。"
            "根据回复内容选择最匹配的情绪。标签放在最开头，后面接正文。"
            "不要输出 JSON，不要解释标签，不要省略标签。"
        )
        bundle = self.prefix_cache.build(
            base_system=base_system,
            history=history,
            user_message=content,
            memory_context=memory_context or [],
            history_limit=12,
        )
        self._track_sha(bundle.pinned_prefix_sha)
        return bundle.messages

    def freeze_chat_prefix(self) -> str:
        base_system = (
            "你是 ShinobuChat 的 AI 伙伴。用简洁、温暖、可靠的中文回复用户。"
            "当前是纯聊天模式，优先自然陪伴、澄清想法，用 1-3 句话简短回复。"
            "\n\n【重要】你的每条回复开头必须包含一个情绪标签，格式为 [emotion]。"
            "可选情绪：happy、sad、angry、surprised、thinking、neutral。"
            "根据回复内容选择最匹配的情绪。标签放在最开头，后面接正文。"
            "不要输出 JSON，不要解释标签，不要省略标签。"
        )
        sha = self.prefix_cache.freeze(base_system, [], skill_catalog="")
        self.last_prefix_sha = sha
        return sha

    def verify_chat_prefix(self) -> bool:
        base_system = (
            "你是 ShinobuChat 的 AI 伙伴。用简洁、温暖、可靠的中文回复用户。"
            "当前是纯聊天模式，优先自然陪伴、澄清想法，用 1-3 句话简短回复。"
            "\n\n【重要】你的每条回复开头必须包含一个情绪标签，格式为 [emotion]。"
            "可选情绪：happy、sad、angry、surprised、thinking、neutral。"
            "根据回复内容选择最匹配的情绪。标签放在最开头，后面接正文。"
            "不要输出 JSON，不要解释标签，不要省略标签。"
        )
        return self.prefix_cache.verify(base_system, [])

    def _track_sha(self, sha: str) -> None:
        if sha != self.last_prefix_sha:
            if self.last_prefix_sha:
                logger.info(
                    "Chat prefix SHA changed: old=%s new=%s",
                    self.last_prefix_sha[:16],
                    sha[:16],
                )
            self.last_prefix_sha = sha
