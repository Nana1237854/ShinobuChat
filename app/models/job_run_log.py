"""JobRunLog model — persisted job execution records (Phase 3)."""

from __future__ import annotations

import uuid

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import local_now
from app.db.session import Base


class JobRunLog(Base):
    __tablename__ = "job_run_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    started_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

    result_summary: Mapped[str] = mapped_column(Text, default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    locked_by: Mapped[str] = mapped_column(String(128), default="")

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=local_now)
