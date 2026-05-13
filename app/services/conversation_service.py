from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.conversation import ConversationCreate


class ConversationService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: ConversationCreate) -> Conversation:
        conversation = Conversation(
            user_id=payload.user_id,
            title=payload.title or "New conversation",
            summary=payload.summary,
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def create_for_user(self, user_id: UUID, title: str | None = None, summary: str | None = None) -> Conversation:
        conversation = Conversation(
            user_id=user_id,
            title=title or "New conversation",
            summary=summary,
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def list_by_user(self, user_id: UUID) -> list[Conversation]:
        return (
            self.db.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .all()
        )

    def get(self, conversation_id: UUID) -> Conversation:
        conversation = self.db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conversation:
            raise NotFoundError("Conversation not found")
        return conversation

    def get_for_user(self, conversation_id: UUID, user_id: UUID) -> Conversation:
        conversation = self.get(conversation_id)
        if conversation.user_id != user_id:
            raise NotFoundError("Conversation not found")
        return conversation

    def list_messages(self, conversation_id: UUID, user_id: UUID) -> list[Message]:
        self.get_for_user(conversation_id, user_id)
        return (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .all()
        )

    def touch(self, conversation: Conversation, *, summary: str | None = None) -> Conversation:
        conversation.updated_at = datetime.utcnow()
        if summary is not None:
            conversation.summary = summary
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation
