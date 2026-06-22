from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

GoalStatus = Literal["active", "paused", "completed"]


class GoalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, max_length=50)
    cadence_days: int = Field(default=7, ge=1, le=365)
    reminder_enabled: bool = True


class GoalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, max_length=50)
    status: GoalStatus | None = None
    cadence_days: int | None = Field(default=None, ge=1, le=365)
    reminder_enabled: bool | None = None


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    title: str
    description: str | None
    category: str | None
    status: GoalStatus
    cadence_days: int
    last_checked_at: datetime | None
    next_check_at: datetime | None
    reminder_enabled: bool
    completed_at: datetime | None
    paused_at: datetime | None
    created_at: datetime
    updated_at: datetime


class GoalCheckinOut(BaseModel):
    goal_id: UUID
    user_id: UUID
    title: str
    category: str | None
    status: GoalStatus
    checked: bool
    next_check_at: datetime | None
    message: str
