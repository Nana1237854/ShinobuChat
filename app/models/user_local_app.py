"""User-configured local application shortcuts (F11)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import local_now
from app.db.session import Base


class UserLocalApp(Base):
    __tablename__ = "user_local_apps"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    app_key: Mapped[str] = mapped_column(String(64), nullable=False)
    intent_type: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    executable_path: Mapped[str] = mapped_column(String(512), nullable=False)
    working_dir: Mapped[str | None] = mapped_column(String(512), nullable=True)
    args_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    keywords_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default_for_intent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confirm_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=local_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=local_now, onupdate=local_now, nullable=False
    )

    user = relationship("User")
