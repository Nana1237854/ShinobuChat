from fastapi import APIRouter

from app.schemas.live2d import Live2DEmotionMapping, Live2DModelsResponse
from app.services.live2d_service import Live2DService

router = APIRouter(prefix="/live2d", tags=["live2d"])


@router.get("/models")
def list_live2d_models(simple: bool = False) -> Live2DModelsResponse | list[str]:
    models = Live2DService().list_models()
    if simple:
        return [model.name for model in models]
    return Live2DModelsResponse(models=models)


@router.get("/emotion_mapping/{model_name}")
def get_live2d_emotion_mapping(model_name: str) -> Live2DEmotionMapping:
    return Live2DService().get_emotion_mapping(model_name)


@router.post("/emotion_mapping/{model_name}")
def save_live2d_emotion_mapping(
    model_name: str,
    emotion_mapping: Live2DEmotionMapping,
) -> Live2DEmotionMapping:
    return Live2DService().save_emotion_mapping(model_name, emotion_mapping)
