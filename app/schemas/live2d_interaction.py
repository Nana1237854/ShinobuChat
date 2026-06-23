from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, field_validator


class Live2DHitArea(str, Enum):
    HEAD = "head"
    BODY = "body"
    HAND = "hand"
    UNKNOWN = "unknown"


class Live2DInteractionCreate(BaseModel):
    hit_area: Live2DHitArea
    x: float
    y: float
    timestamp: datetime
    interaction_type: str = "click"
    metadata: dict[str, Any] | None = None

    @field_validator("interaction_type")
    @classmethod
    def validate_interaction_type(cls, v: str) -> str:
        if v not in ("click", "long_press"):
            raise ValueError('interaction_type must be "click" or "long_press"')
        return v


class Live2DInteractionOut(BaseModel):
    event_id: UUID
    interaction_type: str = "click"
    animation: str | None = None
    expression: str | None = None
    message: str | None = None
