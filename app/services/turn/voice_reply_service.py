from __future__ import annotations

import asyncio
import logging

from app.services.sentence_splitter import split_long_sentence, split_sentences
from app.services.stream_events import SseEncoder, StreamEvent
from app.services.text_cleaner import clean_tts_text
from app.services.tts_pipeline import StreamProcessor
from app.services.voice_service import VoiceService

logger = logging.getLogger(__name__)


class VoiceReplyService:
    def __init__(self, voice_service: VoiceService | None, sse: SseEncoder):
        self.voice_service = voice_service
        self.sse = sse

    @staticmethod
    def split_for_voice(text: str) -> list[str]:
        tts_text = clean_tts_text(text)
        raw_sentences, remaining = split_sentences(tts_text)

        if remaining.strip():
            raw_sentences.append(remaining.strip())

        sentences: list[str] = []
        for s in raw_sentences:
            if len(s) > 40:
                sentences.extend(split_long_sentence(s))
            elif len(s) >= 2:
                sentences.append(s)

        return [s for s in sentences if len(s) >= 6]

    async def stream_reply(
        self, *, text: str, emotion: str, context_content: str,
    ):
        sentences = self.split_for_voice(text)

        if self.voice_service is None or not sentences:
            for sentence in sentences:
                yield StreamEvent("chunk", {"delta": sentence})
            return

        processor = StreamProcessor(
            voice_service=self.voice_service,
            emotion=emotion,
            context=[context_content],
            sse=self.sse,
        )

        for sentence in sentences:
            processor.res_queue.put_nowait(sentence)

        processor.finish_text()
        tts_task = asyncio.create_task(processor.run_tts())

        try:
            while True:
                item = await processor.audio_queue.get()
                if item == "__DONE__":
                    break
                if isinstance(item, dict):
                    yield StreamEvent("audio", item)
        finally:
            processor.cancel()
            await tts_task

    def stream_chunks(self, text: str) -> list[StreamEvent]:
        """Return chunk events for text without voice synthesis."""
        sentences = self.split_for_voice(text)
        return [StreamEvent("chunk", {"delta": s}) for s in sentences]
