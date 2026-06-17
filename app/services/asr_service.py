import json
import mimetypes
from dataclasses import dataclass

from app.core.exceptions import BadRequestError, ConfigurationError, UpstreamServiceError
from app.services.http_client import UrllibHttpClient, encode_multipart, extract_text


@dataclass(frozen=True)
class ASRConfig:
    engine: str
    timeout_seconds: int
    funasr_api_url: str
    whisper_api_url: str
    whisper_api_key: str
    whisper_fallback_api_key: str
    whisper_base_url: str
    whisper_model: str
    whisper_language: str


class ASRService:
    def __init__(self, config: ASRConfig, http_client: UrllibHttpClient | None = None):
        self.config = config
        self.http_client = http_client or UrllibHttpClient()

    async def transcribe(self, filename: str, content_type: str | None, audio: bytes) -> str:
        if not audio:
            raise BadRequestError("Audio file is empty")
        engine = self.config.engine.strip().lower()
        if engine == "funasr":
            return await self._transcribe_with_funasr(filename, content_type, audio)
        if engine == "whisper":
            return await self._transcribe_with_whisper(filename, content_type, audio)
        raise BadRequestError("SC_ASR_ENGINE must be either 'funasr' or 'whisper'")

    async def _transcribe_with_whisper(self, filename: str, content_type: str | None, audio: bytes) -> str:
        api_key = self.config.whisper_api_key or self.config.whisper_fallback_api_key
        if not api_key:
            raise ConfigurationError("Whisper API key is not configured")
        endpoint = self.config.whisper_api_url or f"{self.config.whisper_base_url.rstrip('/')}/audio/transcriptions"
        fields = {"model": self.config.whisper_model}
        if self.config.whisper_language:
            fields["language"] = self.config.whisper_language
        body, boundary = encode_multipart(
            fields=fields,
            files={
                "file": (
                    filename,
                    content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
                    audio,
                )
            },
        )
        return await self._read_transcription_response(
            endpoint,
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            body,
            "Whisper",
        )

    async def _transcribe_with_funasr(self, filename: str, content_type: str | None, audio: bytes) -> str:
        if not self.config.funasr_api_url:
            raise ConfigurationError("FunASR API URL is not configured")
        body, boundary = encode_multipart(
            fields={},
            files={
                "file": (
                    filename,
                    content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
                    audio,
                )
            },
        )
        return await self._read_transcription_response(
            self.config.funasr_api_url,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            body=body,
            engine_name="FunASR",
        )

    async def _read_transcription_response(
        self,
        endpoint: str,
        headers: dict[str, str],
        body: bytes,
        engine_name: str,
    ) -> str:
        try:
            response = self.http_client.request_bytes(
                endpoint,
                method="POST",
                headers=headers,
                body=body,
                timeout=self.config.timeout_seconds,
            )
            data = json.loads(response.body.decode("utf-8"))
        except Exception as exc:
            raise UpstreamServiceError(f"{engine_name} ASR request failed: {exc}") from exc
        text = extract_text(data)
        if not text:
            raise UpstreamServiceError(f"{engine_name} ASR returned no text")
        return text
