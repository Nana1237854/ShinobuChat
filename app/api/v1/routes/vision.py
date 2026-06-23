from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.deps import get_config_service, get_current_user_id, get_image_understanding_service
from app.schemas.vision import VisionAnalyzeResponse, VisionConfidence
from app.services.config_service import ConfigService
from app.services.image_understanding_service import ImageUnderstandingService

router = APIRouter(prefix="/vision", tags=["vision"])


@router.post("/analyze", response_model=VisionAnalyzeResponse)
async def analyze_image(
    file: UploadFile = File(...),
    question: str | None = Form(None),
    user_id: UUID = Depends(get_current_user_id),
    service: ImageUnderstandingService = Depends(get_image_understanding_service),
    config_service: ConfigService = Depends(get_config_service),
) -> VisionAnalyzeResponse:
    runtime_config = config_service.resolve_runtime(user_id)
    result = await service.analyze(file, question, user_id, runtime_config)
    return VisionAnalyzeResponse(
        analysis_id=uuid4(),
        summary=result.summary,
        objects=result.objects,
        scene=result.scene,
        text_in_image=result.detected_text,
        confidence=VisionConfidence(score=result.confidence, label=result.provider),
        created_at=datetime.now(timezone.utc),
        provider=result.provider,
        fallback_used=result.fallback_used,
    )
