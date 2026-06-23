import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.character_profile import CharacterProfile, ConversationCharacter
from app.models.conversation import Conversation
from app.schemas.character_profile import (
    CharacterProfileCreate,
    CharacterProfileOut,
    CharacterProfileUpdate,
    ConversationCharactersRequest,
    ConversationCharactersResponse,
)

logger = logging.getLogger(__name__)


class CharacterProfileService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: UUID, payload: CharacterProfileCreate) -> CharacterProfileOut:
        existing = (
            self.db.query(CharacterProfile)
            .filter(CharacterProfile.user_id == user_id, CharacterProfile.name == payload.name)
            .first()
        )
        if existing:
            raise ConflictError(f"Character profile named '{payload.name}' already exists")

        profile = CharacterProfile(
            user_id=user_id,
            name=payload.name,
            persona=payload.persona,
            avatar_url=payload.avatar_url,
            color=payload.color,
        )
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return CharacterProfileOut.model_validate(profile)

    def list_by_user(self, user_id: UUID) -> list[CharacterProfileOut]:
        rows = (
            self.db.query(CharacterProfile)
            .filter(CharacterProfile.user_id == user_id)
            .order_by(CharacterProfile.created_at.asc())
            .all()
        )
        return [CharacterProfileOut.model_validate(row) for row in rows]

    def get(self, profile_id: UUID, user_id: UUID) -> CharacterProfileOut:
        row = (
            self.db.query(CharacterProfile)
            .filter(CharacterProfile.id == profile_id, CharacterProfile.user_id == user_id)
            .first()
        )
        if row is None:
            raise NotFoundError("Character profile not found")
        return CharacterProfileOut.model_validate(row)

    def update(self, profile_id: UUID, user_id: UUID, payload: CharacterProfileUpdate) -> CharacterProfileOut:
        row = (
            self.db.query(CharacterProfile)
            .filter(CharacterProfile.id == profile_id, CharacterProfile.user_id == user_id)
            .first()
        )
        if row is None:
            raise NotFoundError("Character profile not found")

        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(row, key, value)
        self.db.commit()
        self.db.refresh(row)
        return CharacterProfileOut.model_validate(row)

    def delete(self, profile_id: UUID, user_id: UUID) -> None:
        row = (
            self.db.query(CharacterProfile)
            .filter(CharacterProfile.id == profile_id, CharacterProfile.user_id == user_id)
            .first()
        )
        if row is None:
            raise NotFoundError("Character profile not found")
        self.db.delete(row)
        self.db.commit()

    # ── Conversation-level character management ──

    def _verify_conversation_ownership(self, conversation_id: UUID, user_id: UUID) -> Conversation:
        conv = (
            self.db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .first()
        )
        if conv is None:
            raise NotFoundError("Conversation not found")
        if conv.user_id != user_id:
            raise NotFoundError("Conversation not found")
        return conv

    def set_conversation_characters(
        self, user_id: UUID, payload: ConversationCharactersRequest
    ) -> ConversationCharactersResponse:
        conversation_id = payload.conversation_id
        if conversation_id is None:
            conv = (
                self.db.query(Conversation)
                .filter(Conversation.user_id == user_id)
                .order_by(Conversation.updated_at.desc())
                .first()
            )
            if conv is None:
                raise NotFoundError("No active conversation found")
            conversation_id = conv.id
        else:
            self._verify_conversation_ownership(conversation_id, user_id)

        # Validate all character_ids belong to user
        for cid in payload.character_ids:
            profile = (
                self.db.query(CharacterProfile)
                .filter(CharacterProfile.id == cid, CharacterProfile.user_id == user_id)
                .first()
            )
            if profile is None:
                raise NotFoundError(f"Character profile {cid} not found")

        # Replace all conversation-character associations
        self.db.query(ConversationCharacter).filter(
            ConversationCharacter.conversation_id == conversation_id
        ).delete()

        for cid in payload.character_ids:
            self.db.add(
                ConversationCharacter(
                    conversation_id=conversation_id,
                    character_profile_id=cid,
                )
            )
        self.db.commit()
        return ConversationCharactersResponse(character_ids=payload.character_ids)

    def get_conversation_characters(
        self, conversation_id: UUID, user_id: UUID
    ) -> list[CharacterProfileOut]:
        self._verify_conversation_ownership(conversation_id, user_id)

        rows = (
            self.db.query(CharacterProfile)
            .join(ConversationCharacter, ConversationCharacter.character_profile_id == CharacterProfile.id)
            .filter(
                ConversationCharacter.conversation_id == conversation_id,
                CharacterProfile.user_id == user_id,
            )
            .order_by(ConversationCharacter.created_at.asc())
            .all()
        )
        return [CharacterProfileOut.model_validate(row) for row in rows]
