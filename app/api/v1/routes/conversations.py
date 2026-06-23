from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_character_profile_service, get_chat_service, get_current_user_id
from app.core.exceptions import NotFoundError
from app.schemas.character_profile import (
    CharacterProfileOut,
    ConversationCharactersRequest,
    ConversationCharactersResponse,
)
from app.schemas.conversation import ConversationCreate, ConversationOut
from app.schemas.message import MessageOut
from app.services.character_profile_service import CharacterProfileService
from app.services.chat_service import ChatService

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    chat_service: ChatService = Depends(get_chat_service),
) -> ConversationOut:
    conversation = chat_service.create_conversation(payload.user_id, payload.title, payload.summary)
    return ConversationOut.model_validate(conversation)


@router.get("/user/{user_id}", response_model=list[ConversationOut])
def list_user_conversations(
    user_id: UUID,
    chat_service: ChatService = Depends(get_chat_service),
) -> list[ConversationOut]:
    conversations = chat_service.list_conversations(user_id)
    return [ConversationOut.model_validate(item) for item in conversations]


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
def list_conversation_messages(
    conversation_id: UUID,
    user_id: UUID,
    chat_service: ChatService = Depends(get_chat_service),
) -> list[MessageOut]:
    messages = chat_service.list_messages(conversation_id, user_id)
    return [MessageOut.model_validate(item) for item in messages]


# ── Feature 9: Conversation-level character management ──


@router.get("/{conversation_id}/characters", response_model=list[CharacterProfileOut])
def get_conversation_characters(
    conversation_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    profile_service: CharacterProfileService = Depends(get_character_profile_service),
) -> list[CharacterProfileOut]:
    try:
        return profile_service.get_conversation_characters(conversation_id, user_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("/{conversation_id}/characters", response_model=ConversationCharactersResponse)
def set_conversation_characters(
    conversation_id: UUID,
    payload: ConversationCharactersRequest,
    user_id: UUID = Depends(get_current_user_id),
    profile_service: CharacterProfileService = Depends(get_character_profile_service),
) -> ConversationCharactersResponse:
    payload.conversation_id = conversation_id
    try:
        return profile_service.set_conversation_characters(user_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
