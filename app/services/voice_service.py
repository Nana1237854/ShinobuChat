from app.schemas.voice import VoiceTTSRequest
from app.services.asr_service import ASRConfig, ASRService
from app.services.http_client import UrllibHttpClient
from app.services.tts_service import SynthesizedSpeech, TTSConfig, TTSService


class VoiceService:
    def __init__(
        self,
        tts_config: TTSConfig,
        asr_config: ASRConfig,
        http_client: UrllibHttpClient | None = None,
    ):
        self.tts = TTSService(tts_config)
        self.asr = ASRService(asr_config, http_client)

    @property
    def asr_engine(self) -> str:
        return self.asr.config.engine

    async def synthesize(self, payload: VoiceTTSRequest) -> SynthesizedSpeech:
        return await self.tts.synthesize(payload)

    async def transcribe(self, filename: str, content_type: str | None, audio: bytes) -> str:
        return await self.asr.transcribe(filename, content_type, audio)
