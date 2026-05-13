from fastapi import APIRouter, Depends

from app.api.deps import get_live2d_service
from app.schemas.live2d import Live2DEmotionMapping, Live2DModelsResponse
from app.services.live2d_service import Live2DService

router = APIRouter(prefix="/live2d", tags=["live2d"])


@router.get("/models")
def list_live2d_models(
    simple: bool = False,
    live2d_service: Live2DService = Depends(get_live2d_service),
) -> Live2DModelsResponse | list[str]:
    models = live2d_service.list_models()
    if simple:
        return [model.name for model in models]
    return Live2DModelsResponse(models=models)


@router.get("/emotion_mapping/{model_name}")
def get_live2d_emotion_mapping(
    model_name: str,
    live2d_service: Live2DService = Depends(get_live2d_service),
) -> Live2DEmotionMapping:
    return live2d_service.get_emotion_mapping(model_name)


@router.post("/emotion_mapping/{model_name}")
def save_live2d_emotion_mapping(
    model_name: str,
    emotion_mapping: Live2DEmotionMapping,
    live2d_service: Live2DService = Depends(get_live2d_service),
) -> Live2DEmotionMapping:
    return live2d_service.save_emotion_mapping(model_name, emotion_mapping)
