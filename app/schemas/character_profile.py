from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CharacterProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    persona: str = Field(min_length=1)
    avatar_url: str | None = None
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    role_type: Literal["primary", "auxiliary"] = "auxiliary"


class CharacterProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    persona: str | None = Field(default=None, min_length=1)
    avatar_url: str | None = None
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    role_type: Literal["primary", "auxiliary"] | None = None


class CharacterProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    persona: str
    avatar_url: str | None = None
    color: str | None = None
    role_type: str = "auxiliary"
    created_at: datetime


class ConversationCharactersRequest(BaseModel):
    character_ids: list[UUID]
    conversation_id: UUID | None = None


class ConversationCharactersResponse(BaseModel):
    character_ids: list[UUID]
