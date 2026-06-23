from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id, get_mode_service
from app.schemas.mode import ConversationModeResponse, ConversationModeUpdate
from app.services.mode_service import ModeService

router = APIRouter(prefix="/modes", tags=["modes"])


@router.get("/conversation", response_model=ConversationModeResponse)
def get_conversation_mode(
    user_id: UUID = Depends(get_current_user_id),
    mode_service: ModeService = Depends(get_mode_service),
) -> ConversationModeResponse:
    return mode_service.get_settings(user_id)


@router.put("/conversation", response_model=ConversationModeResponse)
def update_conversation_mode(
    payload: ConversationModeUpdate,
    user_id: UUID = Depends(get_current_user_id),
    mode_service: ModeService = Depends(get_mode_service),
) -> ConversationModeResponse:
    return mode_service.update_settings(user_id, payload)
