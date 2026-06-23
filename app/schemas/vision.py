from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VisionConfidence(BaseModel):
    score: float
    label: str


class VisionAnalyzeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    analysis_id: UUID
    summary: str
    objects: list[str]
    scene: str | None = None
    text_in_image: str | None = None
    confidence: VisionConfidence
    created_at: datetime
    provider: str
    fallback_used: bool
