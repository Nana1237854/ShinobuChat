from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import uuid
from dataclasses import dataclass
from typing import Protocol

from app.core.config import settings
from app.core.exceptions import ConfigurationError, UpstreamServiceError
from app.services.http_client import UrllibHttpClient

logger = logging.getLogger(__name__)

VISION_PROMPT = """Analyze this image and respond ONLY with a JSON object in this exact format:
{
  "summary": "A concise 1-2 sentence description in Chinese",
  "objects": ["object1", "object2"],
  "scene": "scene category or null",
  "text_in_image": "any visible text or null",
  "suggestions": ["suggestion1"],
  "confidence": 0.0
}
Rules:
- summary: describe what you see in natural Chinese
- objects: list distinct objects/items visible
- scene: describe the setting (e.g. "office", "outdoor", "screenshot") or null
- text_in_image: extract ALL visible text exactly as it appears, or null
- suggestions: 1-3 helpful suggestions about what the user might do with this image
- confidence: 0.0 to 1.0 reflecting how clear the image content is
Return ONLY the JSON object, no markdown fences, no extra text."""


def _extract_json_object(text: str) -> dict:
    """Robustly extract a JSON object from LLM output.

    Handles: ```json fences, leading text, trailing text.
    Falls back to returning raw text as summary if JSON parsing fails.
    """
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.MULTILINE)

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            pass

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    return {
        "summary": cleaned[:500] or text[:500],
        "objects": [],
        "scene": None,
        "text_in_image": None,
        "suggestions": [],
        "confidence": 0.3,
    }


def _coerce_str(value: object) -> str:
    if isinstance(value, str):
        return value
    return str(value) if value else ""


def _coerce_str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [_coerce_str(v) for v in value if v is not None]
    if isinstance(value, str):
        return [value] if value.strip() else []
    return []


def _coerce_float(value: object, default: float = 0.5) -> float:
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    if isinstance(value, str):
        try:
            return max(0.0, min(1.0, float(value)))
        except (ValueError, TypeError):
            return default
    return default


def _coerce_optional_str(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s and s.lower() != "null" and s.lower() != "none" else None


@dataclass(frozen=True)
class VisionAnalyzeResult:
    summary: str
    objects: list[str]
    scene: str | None
    detected_text: str | None
    suggestions: list[str]
    confidence: float
    provider: str  # "openai" | "ocr"
    fallback_used: bool
    raw_error: str | None = None  # internal only, never exposed to client


class BaseVisionClient(Protocol):
    async def analyze(
        self,
        image_bytes: bytes,
        mime_type: str,
        question: str | None = None,
        user_id: uuid.UUID | None = None,
        runtime_config: dict | None = None,
    ) -> VisionAnalyzeResult: ...


def _resolve_vision_runtime_config(runtime_config: dict | None) -> dict:
    """Resolve which provider configuration to use for vision analysis.

    Returns a dict with ``base_url``, ``api_key``, ``model``, ``source`` (``"main"``
    or ``"vision"``), and ``timeout``.

    Raises ConfigurationError when no usable vision provider is available.
    """
    cfg = runtime_config or {}

    main_base_url = cfg.get("ai_base_url") or settings.ai_base_url
    main_api_key = cfg.get("ai_api_key") or settings.ai_api_key
    main_model = cfg.get("ai_model") or settings.ai_model
    supports_image = cfg.get("ai_supports_image_input", settings.ai_supports_image_input)

    vision_base_url = cfg.get("ai_vision_base_url") or settings.ai_vision_base_url or main_base_url
    vision_api_key = cfg.get("ai_vision_api_key") or settings.ai_vision_api_key or main_api_key
    vision_model = cfg.get("ai_vision_model") or settings.ai_vision_model

    timeout = int(cfg.get("ai_request_timeout_seconds", settings.ai_request_timeout_seconds))

    # Case 1: main model declares image support
    if supports_image:
        if not main_api_key:
            raise ConfigurationError("No AI API key configured for vision analysis")
        return {
            "base_url": main_base_url,
            "api_key": main_api_key,
            "model": main_model,
            "source": "main",
            "timeout": timeout,
        }

    # Case 2: dedicated vision model configured
    if vision_model:
        if not vision_api_key:
            raise ConfigurationError(
                "Vision model is configured but no API key is available. "
                "Set ai_vision_api_key or ai_api_key."
            )
        return {
            "base_url": vision_base_url,
            "api_key": vision_api_key,
            "model": vision_model,
            "source": "vision",
            "timeout": timeout,
        }

    # Case 3: no vision capability — let ConfigurableVisionClient fall back to OCR
    raise ConfigurationError(
        "Current AI model does not support image input and no vision model is configured. "
        "Set ai_vision_model to use a dedicated vision provider."
    )


class OpenAIVisionClient:
    def __init__(self, http_client: UrllibHttpClient | None = None):
        self._http = http_client or UrllibHttpClient()

    async def analyze(
        self,
        image_bytes: bytes,
        mime_type: str,
        question: str | None = None,
        user_id: uuid.UUID | None = None,
        runtime_config: dict | None = None,
    ) -> VisionAnalyzeResult:
        resolved = _resolve_vision_runtime_config(runtime_config)
        api_key = resolved["api_key"]
        base_url = resolved["base_url"]
        model = resolved["model"]
        timeout = resolved["timeout"]

        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        data_uri = f"data:{mime_type};base64,{image_b64}"

        user_prompt = question or "请分析这张图片的内容。"
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_PROMPT + "\n\nUser question: " + user_prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            }
        ]

        body = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 1024,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        url = f"{base_url.rstrip('/')}/chat/completions"

        # Sync HTTP via to_thread — UrllibHttpClient blocks
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(
            None,
            lambda: self._http.request_json(
                url, method="POST", headers=headers, body=body, timeout=timeout
            ),
        )

        try:
            content = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise UpstreamServiceError(f"Unexpected vision API response structure: {exc}")

        parsed = _extract_json_object(content)
        return VisionAnalyzeResult(
            summary=_coerce_str(parsed.get("summary")) or content[:200],
            objects=_coerce_str_list(parsed.get("objects")),
            scene=_coerce_optional_str(parsed.get("scene")),
            detected_text=_coerce_optional_str(parsed.get("text_in_image")),
            suggestions=_coerce_str_list(parsed.get("suggestions")),
            confidence=_coerce_float(parsed.get("confidence"), 0.7),
            provider="openai",
            fallback_used=False,
        )


class OCRVisionClient:
    def __init__(self):
        self._reader = None

    def _ensure_reader(self):
        if self._reader is not None:
            return self._reader
        try:
            import easyocr
        except ModuleNotFoundError:
            raise ConfigurationError("OCR not available: easyocr is not installed")

        try:
            self._reader = easyocr.Reader(["ch_sim", "en"], gpu=False)
        except Exception as exc:
            raise ConfigurationError(f"OCR not available: failed to initialize easyocr: {exc}")
        return self._reader

    async def analyze(
        self,
        image_bytes: bytes,
        mime_type: str,
        question: str | None = None,
        user_id: uuid.UUID | None = None,
        runtime_config: dict | None = None,
    ) -> VisionAnalyzeResult:
        try:
            reader = self._ensure_reader()
        except ConfigurationError:
            raise

        # Run sync OCR in thread — easyocr.Reader.readtext blocks
        loop = asyncio.get_running_loop()
        try:
            results = await loop.run_in_executor(
                None, self._run_ocr, image_bytes, reader
            )
        except UpstreamServiceError:
            raise
        except Exception as exc:
            raise UpstreamServiceError(f"OCR processing failed: {exc}")

        if not results:
            return VisionAnalyzeResult(
                summary="未识别到明显文字。",
                objects=[],
                scene=None,
                detected_text=None,
                suggestions=[],
                confidence=0.35,
                provider="ocr",
                fallback_used=True,
            )

        detected_text = "\n".join(text for (_bbox, text, _conf) in results if text.strip())
        return VisionAnalyzeResult(
            summary="已从图片中提取到文字。" if detected_text.strip() else "未识别到明显文字。",
            objects=[],
            scene=None,
            detected_text=detected_text.strip() or None,
            suggestions=[],
            confidence=0.5,
            provider="ocr",
            fallback_used=True,
        )

    def _run_ocr(self, image_bytes: bytes, reader):
        """Synchronous OCR processing — runs in executor thread."""
        import io

        try:
            from PIL import Image
        except ModuleNotFoundError:
            raise UpstreamServiceError("OCR failed: Pillow is not installed")

        try:
            img = Image.open(io.BytesIO(image_bytes))
            img.load()
        except Exception as exc:
            raise UpstreamServiceError(f"OCR failed to open image: {exc}")

        try:
            return reader.readtext(img)
        except Exception as exc:
            raise UpstreamServiceError(f"OCR readtext failed: {exc}")


class ConfigurableVisionClient:
    def __init__(self, http_client: UrllibHttpClient | None = None):
        self._http = http_client

    async def analyze(
        self,
        image_bytes: bytes,
        mime_type: str,
        question: str | None = None,
        user_id: uuid.UUID | None = None,
        runtime_config: dict | None = None,
    ) -> VisionAnalyzeResult:
        errors: list[str] = []

        # 1. Try OpenAI vision API
        try:
            openai_client = OpenAIVisionClient(self._http)
            result = await openai_client.analyze(
                image_bytes, mime_type, question, user_id, runtime_config
            )
            return result
        except (ConfigurationError, UpstreamServiceError) as exc:
            errors.append(f"openai: {exc}")

        # 2. Fallback to OCR
        try:
            ocr_client = OCRVisionClient()
            result = await ocr_client.analyze(
                image_bytes, mime_type, question, user_id, runtime_config
            )
            return result
        except (ConfigurationError, UpstreamServiceError) as exc:
            errors.append(f"ocr: {exc}")

        # 3. Both failed — never return 200 with provider="none"
        raise UpstreamServiceError(
            "Vision analysis unavailable: no vision API key configured and OCR is not available. "
            + "; ".join(errors)
        )
