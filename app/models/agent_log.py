import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    route_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    input_summary: Mapped[str] = mapped_column(Text, nullable=False)
    output_summary: Mapped[str] = mapped_column(Text, nullable=False)
    tool_results: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    user = relationship("User")
