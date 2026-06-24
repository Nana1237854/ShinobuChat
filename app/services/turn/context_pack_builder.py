"""Context pack builder.

Assembles a structured ContextPack for each turn from:
- Recent messages (current conversation)
- Conversation summary
- Relevant long-term memories
- Recent diary summaries
- Pending conversation intent
- Available tools (filtered by mode)
- Available local apps (safe DTO — no paths exposed)
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from app.models.user_local_app import UserLocalApp
from app.schemas.context_intent import ContextPack
from app.schemas.message import MessageRole

logger = logging.getLogger(__name__)


class ContextPackBuilder:
    """Build a ContextPack for intent resolution.

    NOT a global singleton — created per-request with a session_factory
    so that DB sessions are properly scoped.
    """

    def __init__(
        self,
        session_factory,
        memory_service=None,
        diary_service=None,
        pending_conversation_intent_service=None,
        config_service=None,
    ):
        self.session_factory = session_factory
        self.memory_service = memory_service
        self.diary_service = diary_service
        self.pending_conversation_intent_service = pending_conversation_intent_service
        self.config_service = config_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(
        self,
        *,
        user_id: UUID,
        conversation_id: UUID,
        current_user_text: str,
        conversation_mode: str = "companion",
    ) -> ContextPack:
        return ContextPack(
            recent_messages=self._recent_messages(conversation_id, user_id),
            conversation_summary=self._conversation_summary(conversation_id, user_id),
            relevant_memories=self._relevant_memories(user_id, current_user_text, conversation_mode),
            diary_summaries=self._diary_summaries(user_id),
            pending_conversation_intent=self._pending_intent(user_id, conversation_id),
            available_tools=self._available_tools(conversation_mode),
            available_local_apps=self._available_local_apps(user_id),
            conversation_mode=conversation_mode,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _recent_messages(self, conversation_id: UUID, user_id: UUID) -> list[dict[str, Any]]:
        """Return the last 8 user/assistant messages, filtering tool/trace."""
        try:
            db = self.session_factory()
            try:
                from app.models.message import Message

                rows = (
                    db.query(Message)
                    .filter(
                        Message.conversation_id == conversation_id,
                        Message.role.in_([MessageRole.USER.value, MessageRole.ASSISTANT.value]),
                    )
                    .order_by(Message.created_at.desc())
                    .limit(8)
                    .all()
                )
                rows = list(reversed(rows))
                result: list[dict[str, Any]] = []
                for msg in rows:
                    content = (msg.content or "").strip()
                    if not content:
                        continue
                    if self._is_tool_or_trace(content):
                        continue
                    result.append({
                        "role": msg.role,
                        "content": content[:300],
                        "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    })
                return result
            finally:
                db.close()
        except Exception:
            logger.debug("Failed to load recent messages", exc_info=True)
            return []

    def _conversation_summary(self, conversation_id: UUID, user_id: UUID) -> str | None:
        """Return the conversation summary, if any."""
        try:
            db = self.session_factory()
            try:
                from app.models.conversation import Conversation

                conv = (
                    db.query(Conversation)
                    .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
                    .first()
                )
                if conv and conv.summary:
                    return conv.summary[:500]
                return None
            finally:
                db.close()
        except Exception:
            logger.debug("Failed to load conversation summary", exc_info=True)
            return None

    def _relevant_memories(
        self, user_id: UUID, user_text: str, conversation_mode: str
    ) -> list[dict[str, Any]]:
        """Return up to 3 relevant long-term memories, each truncated to 80 chars."""
        if not self.memory_service:
            return []
        try:
            query = f"{user_text} {conversation_mode}".strip()
            results = self.memory_service.search_memories(
                user_id=user_id,
                query=query,
                top_k=3,
            )
            memories: list[dict[str, Any]] = []
            for r in (results or [])[:3]:
                content = getattr(r, "content", "") or ""
                tags = getattr(r, "tags", None) or []
                confidence = getattr(r, "confidence", 1.0) or 1.0
                memories.append({
                    "content": (content[:80] + "…") if len(content) > 80 else content,
                    "tags": tags,
                    "confidence": float(confidence),
                })
            return memories
        except Exception:
            logger.debug("Memory retrieval failed in context pack builder", exc_info=True)
            return []

    def _diary_summaries(self, user_id: UUID) -> list[dict[str, Any]]:
        """Return up to 2 most recent diary summaries, each truncated to 100 chars."""
        if not self.diary_service:
            return []
        try:
            today = date.today()
            start = today - timedelta(days=30)
            diaries = self.diary_service.list_diaries_in_range(user_id, start, today)
            recent = list(reversed(diaries or []))[:2]
            summaries: list[dict[str, Any]] = []
            for d in recent:
                summary = getattr(d, "summary", None) or getattr(d, "title", None) or ""
                date_val = getattr(d, "date", None)
                summaries.append({
                    "summary": str(summary)[:100],
                    "date": date_val.isoformat() if date_val else None,
                })
            return summaries
        except Exception:
            logger.debug("Diary retrieval failed in context pack builder", exc_info=True)
            return []

    def _pending_intent(self, user_id: UUID, conversation_id: UUID) -> dict[str, Any] | None:
        """Return active pending conversation intent, if any."""
        if not self.pending_conversation_intent_service:
            return None
        try:
            return self.pending_conversation_intent_service.get_active(user_id, conversation_id)
        except Exception:
            return None

    def _available_tools(self, conversation_mode: str) -> list[dict[str, Any]]:
        """Return filtered tool list based on conversation mode."""
        all_tools: list[dict[str, Any]] = [
            {"name": "open_local_app", "description": "打开或唤醒用户已配置的本地应用", "capability": "local_agent"},
        ]
        return all_tools

    def _available_local_apps(self, user_id: UUID) -> list[dict[str, Any]]:
        """Return safe DTO for user's enabled local apps — NO executable_path exposed."""
        try:
            db = self.session_factory()
            try:
                apps = (
                    db.query(UserLocalApp)
                    .filter(UserLocalApp.user_id == user_id, UserLocalApp.enabled.is_(True))
                    .all()
                )
                safe: list[dict[str, Any]] = []
                for app in apps:
                    safe.append({
                        "app_key": app.app_key,
                        "display_name": app.display_name,
                        "intent_type": app.intent_type,
                        "keywords": app.keywords_json or [],
                        "is_default_for_intent": bool(app.is_default_for_intent),
                    })
                return safe
            finally:
                db.close()
        except Exception:
            logger.debug("Failed to load local apps for context pack", exc_info=True)
            return []

    @staticmethod
    def _is_tool_or_trace(content: str) -> bool:
        """Heuristic: skip messages that look like tool results or traces."""
        if content.startswith("[tool_") or content.startswith("[trace]"):
            return True
        if content.startswith("Tool result:") or content.startswith("Reasoning:"):
            return True
        if len(content) > 2000:
            return True
        return False
