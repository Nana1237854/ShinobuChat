import asyncio
import base64
import logging
from dataclasses import dataclass, field

from app.schemas.voice import VoiceTTSRequest
from app.services.stream_events import SseEncoder
from app.services.text_cleaner import strip_tts_punctuation
from app.services.voice_service import VoiceService

logger = logging.getLogger(__name__)


@dataclass
class StreamProcessor:
    voice_service: VoiceService
    emotion: str
    context: list[str]
    sse: SseEncoder

    audio_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    res_queue: asyncio.Queue[str] = field(default_factory=asyncio.Queue)
    tts_done: bool = False
    cancelled: bool = False
    _seq: int = 0

    def cancel(self):
        self.cancelled = True
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        while not self.res_queue.empty():
            try:
                self.res_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def finish_text(self):
        self.res_queue.put_nowait("__DONE__")

    async def run_tts(self):
        try:
            while True:
                text = await self.res_queue.get()
                if text == "__DONE__" or self.cancelled:
                    break
                self._seq += 1
                spoken_text = strip_tts_punctuation(text)
                if not spoken_text:
                    continue
                try:
                    speech = await self.voice_service.synthesize(
                        VoiceTTSRequest(text=spoken_text, emotion=self.emotion, context=self.context)
                    )
                    logger.debug("[TTS] OK (%dB)", len(speech.audio))
                    if len(speech.audio) >= 100:
                        b64 = base64.b64encode(speech.audio).decode("ascii")
                        self.audio_queue.put_nowait({
                            "text": text,
                            "audio": b64,
                            "emotion": speech.emotion,
                        })
                except Exception as e:
                    logger.debug("[TTS] FAIL: %s", e)
        finally:
            self.tts_done = True
            self.audio_queue.put_nowait("__DONE__")
