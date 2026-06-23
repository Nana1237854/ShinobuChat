from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id, get_live2d_interaction_service
from app.schemas.live2d_interaction import Live2DInteractionCreate, Live2DInteractionOut
from app.services.live2d_interaction_service import Live2DInteractionService

router = APIRouter(prefix="/interactions", tags=["interactions"])


@router.post("/live2d", response_model=Live2DInteractionOut)
def record_live2d_interaction(
    payload: Live2DInteractionCreate,
    user_id: UUID = Depends(get_current_user_id),
    interaction_service: Live2DInteractionService = Depends(get_live2d_interaction_service),
) -> Live2DInteractionOut:
    return interaction_service.record(user_id, payload)
