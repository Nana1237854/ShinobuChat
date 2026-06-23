from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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


class Live2DInteractionOut(BaseModel):
    event_id: UUID
    animation: str | None = None
    expression: str | None = None
    message: str | None = None
