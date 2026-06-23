"""Pydantic schemas for browser automation (F15 skeleton)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BrowserReadRequest(BaseModel):
    url: str
    max_chars: int = Field(default=10000, ge=500, le=50000)


class BrowserReadResponse(BaseModel):
    status: str  # "not_implemented"
    message: str


class BrowserActionRequest(BaseModel):
    action: str
    target_url: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class BrowserActionResponse(BaseModel):
    status: str
    message: str
    action_log_id: UUID | None = None
