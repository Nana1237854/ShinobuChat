import uuid

from sqlalchemy import DateTime, Float, ForeignKey, JSON, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.time import local_now
from app.db.session import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - exercised only when optional dependency is absent
    Vector = None


def _embedding_column_type():
    if Vector is not None:
        return Vector(settings.memory_embedding_dimensions)
    return JSON


class Memory(Base):
    __tablename__ = "conversation_memories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(_embedding_column_type(), nullable=False)
    source_msg_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    importance: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), default=local_now, nullable=False)

    user = relationship("User")
    source_message = relationship("Message")
