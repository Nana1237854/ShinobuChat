from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings


class MemoryCategory(str, Enum):
    LONG_TERM = "long_term"
    EMOTION_PROFILE = "emotion_profile"
    INSPIRATION = "inspiration"


class MemoryCreate(BaseModel):
    user_id: UUID
    category: MemoryCategory = MemoryCategory.LONG_TERM
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=4000)
    source: str = Field(default="manual", min_length=1, max_length=50)
    importance: int = Field(default=2, ge=1, le=5)
    pinned: bool = False
    tags: list[str] = Field(default_factory=list, max_length=12)
    emotion_label: str | None = Field(default=None, max_length=60)
    inferred: bool = False
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class MemoryUpdate(BaseModel):
    category: MemoryCategory | None = None
    title: str | None = Field(default=None, min_length=1, max_length=120)
    content: str | None = Field(default=None, min_length=1, max_length=4000)
    source: str | None = Field(default=None, min_length=1, max_length=50)
    importance: int | None = Field(default=None, ge=1, le=5)
    pinned: bool | None = None
    tags: list[str] | None = Field(default=None, max_length=12)
    emotion_label: str | None = Field(default=None, max_length=60)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    archived: bool | None = None


class MemorySearchRequest(BaseModel):
    user_id: UUID
    query: str = Field(min_length=1, max_length=1000)
    category: MemoryCategory | None = None
    limit: int = Field(default=settings.memory_search_default_limit, ge=1, le=30)
    min_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    include_archived: bool = False


class MemoryPreferenceUpdate(BaseModel):
    enabled: bool


class MemoryPreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    enabled: bool
    updated_at: datetime


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    category: MemoryCategory
    title: str
    content: str
    source: str
    importance: int
    pinned: bool
    tags: list[str]
    emotion_label: str | None
    inferred: bool
    confidence: float
    archived: bool
    archived_reason: str | None
    archived_at: datetime | None
    embedding_model: str | None
    last_accessed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MemorySearchHit(BaseModel):
    memory: MemoryOut
    similarity: float
    distance: float
