import json
import mimetypes
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import BadRequestError, ConfigurationError, UpstreamServiceError
from app.schemas.voice import VoiceReferencePresetOut, VoiceTTSRequest
from app.services.emotion_service import EmotionService
from app.services.http_client import HttpClientError, UrllibHttpClient


@dataclass(frozen=True)
class ReferenceAudioPreset:
    emotion: str
    ref_audio_path: str
    prompt_text: str = ""
    prompt_lang: str = "zh"
    text_lang: str = "zh"
    aux_ref_audio_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class SynthesizedSpeech:
    audio: bytes
    media_type: str
    emotion: str
    reference_emotion: str


class VoiceService:
    def __init__(self, http_client: UrllibHttpClient | None = None):
        self.http_client = http_client or UrllibHttpClient()

    def synthesize(self, payload: VoiceTTSRequest) -> SynthesizedSpeech:
        emotion = EmotionService.normalize(payload.emotion) if payload.emotion else EmotionService.detect(
            payload.text,
            payload.context,
        )
        preset = self._select_reference_audio(emotion)
        media_type = payload.media_type or settings.gpt_sovits_media_type

        body = {
            "text": payload.text,
            "text_lang": payload.text_lang or preset.text_lang or settings.gpt_sovits_text_lang,
            "ref_audio_path": preset.ref_audio_path,
            "aux_ref_audio_paths": list(preset.aux_ref_audio_paths),
            "prompt_text": preset.prompt_text,
            "prompt_lang": preset.prompt_lang or settings.gpt_sovits_prompt_lang,
            "text_split_method": settings.gpt_sovits_text_split_method,
            "batch_size": settings.gpt_sovits_batch_size,
            "media_type": media_type,
            "streaming_mode": settings.gpt_sovits_streaming_mode,
        }
        endpoint = f"{settings.gpt_sovits_base_url.rstrip('/')}/tts"
        try:
            response = self.http_client.request_bytes(
                endpoint,
                headers={"Content-Type": "application/json"},
                method="POST",
                body=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                timeout=settings.gpt_sovits_timeout_seconds,
            )
            audio = response.body
            response_media_type = response.media_type or f"audio/{media_type}"
        except HttpClientError as exc:
            raise UpstreamServiceError(f"GPT-SoVITS request failed: {exc}") from exc

        if not audio:
            raise UpstreamServiceError("GPT-SoVITS returned an empty audio response")
        return SynthesizedSpeech(
            audio=audio,
            media_type=response_media_type,
            emotion=emotion,
            reference_emotion=preset.emotion,
        )

    def transcribe(self, filename: str, content_type: str | None, audio: bytes) -> str:
        if not audio:
            raise BadRequestError("Audio file is empty")

        engine = settings.asr_engine.strip().lower()
        if engine == "funasr":
            return self._transcribe_with_funasr(filename, content_type, audio)
        if engine == "whisper":
            return self._transcribe_with_whisper(filename, content_type, audio)
        raise BadRequestError("SC_ASR_ENGINE must be either 'funasr' or 'whisper'")

    def list_reference_presets(self) -> list[VoiceReferencePresetOut]:
        return [
            VoiceReferencePresetOut(
                emotion=preset.emotion,
                prompt_text=preset.prompt_text,
                prompt_lang=preset.prompt_lang,
                text_lang=preset.text_lang,
                has_ref_audio=bool(preset.ref_audio_path),
            )
            for preset in self._load_reference_presets().values()
        ]

    def _transcribe_with_whisper(self, filename: str, content_type: str | None, audio: bytes) -> str:
        api_key = settings.whisper_api_key or settings.ai_api_key
        if not api_key:
            raise ConfigurationError("Whisper API key is not configured")

        endpoint = settings.whisper_api_url or f"{settings.ai_base_url.rstrip('/')}/audio/transcriptions"
        fields = {"model": settings.whisper_model}
        if settings.whisper_language:
            fields["language"] = settings.whisper_language
        body, boundary = self._encode_multipart(
            fields=fields,
            files={
                "file": (
                    filename,
                    content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
                    audio,
                )
            },
        )
        return self._read_transcription_response(
            endpoint,
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            body,
            "Whisper",
        )

    def _transcribe_with_funasr(self, filename: str, content_type: str | None, audio: bytes) -> str:
        if not settings.funasr_api_url:
            raise ConfigurationError("FunASR API URL is not configured")

        body, boundary = self._encode_multipart(
            fields={},
            files={
                "file": (
                    filename,
                    content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
                    audio,
                )
            },
        )
        return self._read_transcription_response(
            settings.funasr_api_url,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            body=body,
            engine_name="FunASR",
        )

    def _read_transcription_response(
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
                timeout=settings.asr_timeout_seconds,
            )
            data = json.loads(response.body.decode("utf-8"))
        except (HttpClientError, json.JSONDecodeError) as exc:
            raise UpstreamServiceError(f"{engine_name} ASR request failed: {exc}") from exc

        text = self._extract_text(data)
        if not text:
            raise UpstreamServiceError(f"{engine_name} ASR returned no text")
        return text

    def _select_reference_audio(self, emotion: str) -> ReferenceAudioPreset:
        presets = self._load_reference_presets()
        for key in (emotion, "neutral", "default"):
            if key in presets and presets[key].ref_audio_path:
                return presets[key]
        raise ConfigurationError(
            "No GPT-SoVITS reference audio is configured. "
            "Set SC_VOICE_REFERENCE_PRESETS or create voice_reference_audio.json."
        )

    def _load_reference_presets(self) -> dict[str, ReferenceAudioPreset]:
        raw = self._read_reference_config()
        presets: dict[str, ReferenceAudioPreset] = {}
        for emotion, record in raw.items():
            if not isinstance(record, dict):
                continue
            normalized = EmotionService.normalize(emotion)
            aux_paths = record.get("aux_ref_audio_paths") or []
            presets[normalized] = ReferenceAudioPreset(
                emotion=normalized,
                ref_audio_path=str(record.get("ref_audio_path") or ""),
                prompt_text=str(record.get("prompt_text") or ""),
                prompt_lang=str(record.get("prompt_lang") or settings.gpt_sovits_prompt_lang),
                text_lang=str(record.get("text_lang") or settings.gpt_sovits_text_lang),
                aux_ref_audio_paths=tuple(str(path) for path in aux_paths if path),
            )
        return presets

    def _read_reference_config(self) -> dict:
        if settings.voice_reference_presets:
            try:
                data = json.loads(settings.voice_reference_presets)
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError as exc:
                raise ConfigurationError(f"SC_VOICE_REFERENCE_PRESETS is not valid JSON: {exc}") from exc

        path = Path(settings.voice_reference_manifest_path)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"Failed to read voice reference manifest: {exc}") from exc

    @staticmethod
    def _extract_text(data: object) -> str:
        if isinstance(data, dict):
            for key in ("text", "result", "transcript", "sentence"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
                if isinstance(value, (dict, list)):
                    text = VoiceService._extract_text(value)
                    if text:
                        return text
            for value in data.values():
                text = VoiceService._extract_text(value)
                if text:
                    return text
        if isinstance(data, list):
            return " ".join(filter(None, (VoiceService._extract_text(item) for item in data))).strip()
        return ""

    @staticmethod
    def _encode_multipart(
        fields: dict[str, str],
        files: dict[str, tuple[str, str, bytes]],
    ) -> tuple[bytes, str]:
        boundary = f"----ShinobuChat{uuid.uuid4().hex}"
        chunks: list[bytes] = []
        for name, value in fields.items():
            chunks.extend([
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                str(value).encode("utf-8"),
                b"\r\n",
            ])
        for name, (filename, content_type, content) in files.items():
            chunks.extend([
                f"--{boundary}\r\n".encode("utf-8"),
                (
                    f'Content-Disposition: form-data; name="{name}"; '
                    f'filename="{filename}"\r\n'
                ).encode("utf-8"),
                f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
                content,
                b"\r\n",
            ])
        chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
        return b"".join(chunks), boundary
