"""TaskRun model — persisted task execution metadata (Phase 3).

Complements the in-memory TaskEventStore with a durable record of
each long-running task, its progress, and final outcome.
"""

from __future__ import annotations

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import local_now
from app.db.session import Base


class TaskRun(Base):
    __tablename__ = "task_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[object] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )

    task_type: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")

    title: Mapped[str] = mapped_column(String(255), default="")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str] = mapped_column(Text, default="")
    result_summary: Mapped[str] = mapped_column(Text, default="")
    error_message: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=local_now)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=local_now)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
