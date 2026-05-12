from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.message import MessageRole


@dataclass
class CompactResult:
    messages: list[Message]
    summary: str
    was_compacted: bool
    synthetic_message: Message | None = None

    def __iter__(self):
        return (message for message in self.messages if message is not self.synthetic_message)


class ConversationCompactor:
    def __init__(self, max_messages: int = 30, keep_recent: int = 15):
        self.max_messages = max_messages
        self.keep_recent = keep_recent

    def accumulate(
        self,
        conversation: Conversation,
        user_message: Message,
        assistant_message: Message,
        tool_results: list,
        route_mode: str,
    ) -> str:
        """Append a one-line summary of this turn to conversation.summary."""
        now = conversation.updated_at or datetime.utcnow()
        timestamp = now.strftime("%H:%M")

        user_preview = user_message.content.strip()[:80]
        if len(user_message.content.strip()) > 80:
            user_preview = f"{user_preview}..."

        if route_mode == "chat":
            reply_preview = assistant_message.content.strip()[:60]
            if len(assistant_message.content.strip()) > 60:
                reply_preview = f"{reply_preview}..."
            line = f"[{timestamp}] CHAT: 「{user_preview}」→ {reply_preview}"
        else:
            tools = []
            for tr in tool_results:
                if getattr(tr, "status", "") == "ok":
                    tool_name = getattr(tr, "tool", "unknown")
                    label = {"write_memory": "记", "create_todo": "待办", "set_reminder": "提醒"}.get(
                        tool_name, tool_name
                    )
                    tools.append(label)
            tool_str = "+".join(tools) if tools else "分析"
            line = f"[{timestamp}] {route_mode.upper()}: 「{user_preview}」→ {tool_str}"

        old = conversation.summary or ""
        conversation.summary = f"{old}\n{line}".strip() if old else line
        return conversation.summary

    def compact(
        self,
        messages: list[Message],
        summary: str,
        conversation_id: UUID | None = None,
    ) -> CompactResult:
        """If messages exceed max_messages, keep only recent ones + inject summary."""
        if len(messages) <= self.max_messages or not summary:
            return CompactResult(messages=messages, summary=summary, was_compacted=False)

        kept = messages[-self.keep_recent :]
        synthetic = Message(
            conversation_id=conversation_id or (kept[0].conversation_id if kept else None),
            role=MessageRole.SYSTEM.value,
            content=f"[会话摘要]\n{summary}",
        )
        return CompactResult(
            messages=[synthetic] + kept,
            summary=summary,
            was_compacted=True,
            synthetic_message=synthetic,
        )
