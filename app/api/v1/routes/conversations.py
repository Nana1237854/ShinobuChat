from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import get_conversation_service
from app.schemas.conversation import ConversationCreate, ConversationOut
from app.schemas.message import MessageOut
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> ConversationOut:
    conversation = conversation_service.create(payload)
    return ConversationOut.model_validate(conversation)


@router.get("/user/{user_id}", response_model=list[ConversationOut])
def list_user_conversations(
    user_id: UUID,
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> list[ConversationOut]:
    conversations = conversation_service.list_by_user(user_id)
    return [ConversationOut.model_validate(item) for item in conversations]


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
def list_conversation_messages(
    conversation_id: UUID,
    user_id: UUID,
    conversation_service: ConversationService = Depends(get_conversation_service),
) -> list[MessageOut]:
    messages = conversation_service.list_messages(conversation_id, user_id)
    return [MessageOut.model_validate(item) for item in messages]
