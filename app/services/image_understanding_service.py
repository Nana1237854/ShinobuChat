from __future__ import annotations

import logging
from uuid import UUID

from fastapi import UploadFile

from app.core.exceptions import BadRequestError, UpstreamServiceError
from app.core.image_validation import validate_image_bytes
from app.services.vision_client import (
    ConfigurableVisionClient,
    VisionAnalyzeResult,
)

logger = logging.getLogger(__name__)

# Does NOT import MemoryService — image analysis never writes to long-term memory.


class ImageUnderstandingService:
    def __init__(self, vision_client: ConfigurableVisionClient | None = None):
        self.vision_client = vision_client or ConfigurableVisionClient()

    async def analyze(
        self,
        file: UploadFile,
        question: str | None,
        user_id: UUID,
        runtime_config: dict | None = None,
    ) -> VisionAnalyzeResult:
        # 1. Read
        try:
            image_bytes = await file.read()
        except Exception as exc:
            raise BadRequestError(f"Failed to read uploaded file: {exc}")

        # 2. Validate
        validated_bytes, mime_type = validate_image_bytes(image_bytes)

        # 3. Analyze
        try:
            result = await self.vision_client.analyze(
                validated_bytes,
                mime_type,
                question=question,
                user_id=user_id,
                runtime_config=runtime_config,
            )
            return result
        except UpstreamServiceError:
            raise
        except Exception as exc:
            raise UpstreamServiceError(f"Vision analysis failed: {exc}")

    def build_chat_context(self, result: VisionAnalyzeResult) -> str:
        parts = [f"【图片分析结果】（由 {result.provider} 提供）"]
        parts.append(f"概要：{result.summary}")
        if result.objects:
            parts.append(f"识别到的物体：{', '.join(result.objects)}")
        if result.scene:
            parts.append(f"场景：{result.scene}")
        if result.detected_text:
            parts.append(f"图中文字：{result.detected_text}")
        if result.suggestions:
            parts.append(f"建议：{', '.join(result.suggestions)}")
        if result.fallback_used:
            parts.append("注意：当前使用了备用识别方案，结果可能不够详细。")
        if result.confidence < 0.5:
            parts.append("置信度较低，请谨慎参考分析结果。")
        return "\n".join(parts)
