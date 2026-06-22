import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.time import local_now
from app.db.session import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None


def _embedding_column_type():
    if Vector is not None:
        return Vector(settings.memory_embedding_dimensions)
    return JSON


class Memory(Base):
    __tablename__ = "conversation_memories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="long_term")
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="auto")
    embedding: Mapped[list[float]] = mapped_column(_embedding_column_type(), nullable=False)
    source_msg_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    importance: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    emotion_label: Mapped[str | None] = mapped_column(String(60), nullable=True)
    inferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    archived_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=local_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=local_now, onupdate=local_now, nullable=False
    )

    user = relationship("User")
    source_message = relationship("Message")


class MemoryPreference(Base):
    __tablename__ = "memory_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=local_now, onupdate=local_now, nullable=False
    )

    user = relationship("User")
