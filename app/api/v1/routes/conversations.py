from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import get_chat_service
from app.schemas.conversation import ConversationCreate, ConversationOut
from app.schemas.message import MessageOut
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
    messages = chat_service.get_messages(conversation_id, user_id)
    return [MessageOut.model_validate(item) for item in messages]
