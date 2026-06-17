from dataclasses import dataclass

import edge_tts

from app.core.exceptions import UpstreamServiceError
from app.schemas.voice import VoiceTTSRequest
from app.services.emotion_service import EmotionService


@dataclass(frozen=True)
class TTSConfig:
    voice: str
    rate: str
    volume: str


@dataclass(frozen=True)
class SynthesizedSpeech:
    audio: bytes
    media_type: str
    emotion: str
    reference_emotion: str


class TTSService:
    def __init__(self, config: TTSConfig):
        self.config = config

    async def synthesize(self, payload: VoiceTTSRequest) -> SynthesizedSpeech:
        emotion = EmotionService.normalize(payload.emotion) if payload.emotion else "neutral"

        communicate = edge_tts.Communicate(
            text=payload.text,
            voice=self.config.voice,
            rate=self.config.rate,
            volume=self.config.volume,
        )
        audio_parts: list[bytes] = []
        try:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_parts.append(chunk["data"])
        except Exception as exc:
            raise UpstreamServiceError(f"Edge-TTS request failed: {exc}") from exc

        audio = b"".join(audio_parts)
        if not audio:
            raise UpstreamServiceError("Edge-TTS returned empty audio")
        return SynthesizedSpeech(
            audio=audio,
            media_type="audio/mpeg",
            emotion=emotion,
            reference_emotion=emotion,
        )
