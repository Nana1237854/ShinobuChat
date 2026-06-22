from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserSkillCreate(BaseModel):
    install_type: Literal["text"] = "text"
    content: str = Field(min_length=1, max_length=100_000)


class UserSkillUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=100_000)


class UserSkillPatch(BaseModel):
    enabled: bool


class UserSkillSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str
    keywords: list[str]
    enabled: bool
    installed_from: str
    source_url: str | None
    created_at: datetime
    updated_at: datetime


class UserSkillDetailOut(UserSkillSummaryOut):
    content: str


# Type aliases matching the requested naming convention
SkillOut = UserSkillSummaryOut
SkillDetailOut = UserSkillDetailOut
SkillInstallRequest = UserSkillCreate
SkillUpdateRequest = UserSkillUpdate
SkillToggleRequest = UserSkillPatch
