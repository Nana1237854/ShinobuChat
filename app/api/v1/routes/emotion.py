from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id, get_user_emotion_service
from app.schemas.emotion import EmotionAnalyzeRequest, EmotionAnalyzeResponse
from app.services.user_emotion_service import UserEmotionService

router = APIRouter(prefix="/emotion", tags=["emotion"])


@router.post("/analyze", response_model=EmotionAnalyzeResponse)
def analyze_emotion(
    payload: EmotionAnalyzeRequest,
    user_id: UUID = Depends(get_current_user_id),
    service: UserEmotionService = Depends(get_user_emotion_service),
) -> EmotionAnalyzeResponse:
    truncated_recent = [m[:500] for m in payload.recent_user_messages[-10:]]
    result = service.analyze(
        user_message=payload.message,
        recent_user_messages=truncated_recent,
        local_hour=payload.local_hour,
    )
    return result.model_dump()
