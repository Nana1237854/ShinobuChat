from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

Verbosity = Literal["quiet", "balanced", "talkative"]
Warmth = Literal["calm", "warm", "playful"]
Initiative = Literal["passive", "balanced", "proactive"]
WorkStyle = Literal["casual", "focused", "strict"]


class PersonaSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    verbosity: Verbosity = "balanced"
    warmth: Warmth = "warm"
    initiative: Initiative = "balanced"
    work_style: WorkStyle = "casual"
    updated_at: datetime


class PersonaSettingsUpdate(BaseModel):
    verbosity: Verbosity | None = None
    warmth: Warmth | None = None
    initiative: Initiative | None = None
    work_style: WorkStyle | None = None
