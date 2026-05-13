from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response

from app.api.deps import get_voice_service
from app.core.config import settings
from app.schemas.voice import VoiceASRResponse, VoiceReferencePresetOut, VoiceTTSRequest
from app.services.voice_service import VoiceService

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/tts")
def synthesize_voice(
    payload: VoiceTTSRequest,
    voice_service: VoiceService = Depends(get_voice_service),
) -> Response:
    speech = voice_service.synthesize(payload)
    return Response(
        content=speech.audio,
        media_type=speech.media_type,
        headers={
            "X-Shinobu-Voice-Emotion": speech.emotion,
            "X-Shinobu-Voice-Reference": speech.reference_emotion,
        },
    )


@router.post("/asr")
async def transcribe_voice(
    file: UploadFile = File(...),
    voice_service: VoiceService = Depends(get_voice_service),
) -> VoiceASRResponse:
    audio = await file.read()
    text = voice_service.transcribe(file.filename or "speech.webm", file.content_type, audio)
    return VoiceASRResponse(text=text, engine=settings.asr_engine)


@router.get("/reference-audio")
def list_reference_audio(
    voice_service: VoiceService = Depends(get_voice_service),
) -> list[VoiceReferencePresetOut]:
    return voice_service.list_reference_presets()
