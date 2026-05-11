from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MemoryCreate(BaseModel):
    user_id: UUID
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=4000)
    source: str = Field(default="manual", min_length=1, max_length=50)
    importance: int = Field(default=2, ge=1, le=5)
    pinned: bool = False


class MemoryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    content: str | None = Field(default=None, min_length=1, max_length=4000)
    source: str | None = Field(default=None, min_length=1, max_length=50)
    importance: int | None = Field(default=None, ge=1, le=5)
    pinned: bool | None = None


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    title: str
    content: str
    source: str
    importance: int
    pinned: bool
    created_at: datetime
    updated_at: datetime
