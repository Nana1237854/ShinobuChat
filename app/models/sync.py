import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class SyncRecord(Base):
    __tablename__ = "sync_records"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", name="uq_sync_records_entity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    vector_clock: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False, default=dict)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)

    user = relationship("User")


class SyncOperation(Base):
    __tablename__ = "sync_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(16), nullable=False)
    server_version: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    vector_clock: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False, default=dict)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    conflict: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_device_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)

    user = relationship("User")
