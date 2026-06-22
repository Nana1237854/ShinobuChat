import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import local_now
from app.db.session import Base


class UserPersonaSettings(Base):
    __tablename__ = "user_persona_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    verbosity: Mapped[str] = mapped_column(String(20), nullable=False, default="balanced")
    warmth: Mapped[str] = mapped_column(String(20), nullable=False, default="warm")
    initiative: Mapped[str] = mapped_column(String(20), nullable=False, default="balanced")
    work_style: Mapped[str] = mapped_column(String(20), nullable=False, default="casual")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=local_now, onupdate=local_now, nullable=False
    )

    user = relationship("User")
