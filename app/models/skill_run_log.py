"""SkillRunLog model — skill activation/execution records (Phase 3)."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import local_now
from app.db.session import Base


class SkillRunLog(Base):
    __tablename__ = "skill_run_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    user_id: Mapped[object | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=True
    )
    conversation_id: Mapped[object | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), index=True, nullable=True
    )
    message_id: Mapped[object | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), index=True, nullable=True
    )

    skill_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    trigger_source: Mapped[str] = mapped_column(String(64), default="auto_match")

    matched: Mapped[bool] = mapped_column(Boolean, default=False)
    activated: Mapped[bool] = mapped_column(Boolean, default=False)

    input_summary: Mapped[str] = mapped_column(Text, default="")
    output_summary: Mapped[str] = mapped_column(Text, default="")
    error_message: Mapped[str] = mapped_column(Text, default="")

    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=local_now)
