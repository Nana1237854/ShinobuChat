"""Prompt trace model (Phase 2).

Records per-message context metadata for explainability:
- What memories, skills, tools were available?
- What route/mode was active?
- What context types were injected?
- SHA hashes for cache zones (not the content itself).

Never stores: system prompt, tool schemas, web page content, API keys.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import local_now
from app.db.session import Base


class PromptTrace(Base):
    __tablename__ = "prompt_traces"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("messages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    route_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    conversation_mode: Mapped[str] = mapped_column(String(32), nullable=False)

    # SHA-256 hashes of cache zones (not the content)
    pinned_prefix_sha: Mapped[str] = mapped_column(String(128), default="")
    character_card_sha: Mapped[str] = mapped_column(String(128), default="")
    tool_catalog_sha: Mapped[str] = mapped_column(String(128), default="")
    skill_catalog_sha: Mapped[str] = mapped_column(String(128), default="")

    # IDs of memory records retrieved for this turn
    memory_ids: Mapped[list] = mapped_column(JSON, default=list)
    activated_skill_names: Mapped[list] = mapped_column(JSON, default=list)
    tool_names_available: Mapped[list] = mapped_column(JSON, default=list)

    # Context injection flags
    vision_context_used: Mapped[bool] = mapped_column(Boolean, default=False)
    persona_context_used: Mapped[bool] = mapped_column(Boolean, default=False)
    emotion_context_used: Mapped[bool] = mapped_column(Boolean, default=False)
    browser_context_used: Mapped[bool] = mapped_column(Boolean, default=False)
    mcp_context_used: Mapped[bool] = mapped_column(Boolean, default=False)

    router_reason: Mapped[str] = mapped_column(Text, default="")
    context_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=local_now, nullable=False
    )
