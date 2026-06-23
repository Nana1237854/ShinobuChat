from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DiaryCreate(BaseModel):
    date: date
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1)
    content: str = Field(min_length=1)
    mood: str | None = None
    tags: list[str] = Field(default_factory=list)
    privacy: str = "private"


class DiaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID = Field(validation_alias="id", serialization_alias="diary_id")
    date: date
    title: str
    summary: str
    mood: str | None = None
    created_at: datetime


class DiaryDetail(DiaryOut):
    content: str
    tags: list[str]
    source_conversation_ids: list[str]


class DiaryGenerateRequest(BaseModel):
    date: str | None = None
    style: str | None = None
    force: bool = False


class DiaryGenerateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID = Field(validation_alias="id", serialization_alias="diary_id")
    date: date
    title: str
    summary: str
    content: str
    mood: str | None = None
    tags: list[str]
