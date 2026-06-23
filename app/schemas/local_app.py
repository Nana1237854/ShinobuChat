"""Pydantic schemas for local app management (F11-F13)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# LocalApp
# ---------------------------------------------------------------------------


class LocalAppCreate(BaseModel):
    app_key: str = Field(min_length=1, max_length=64)
    intent_type: str = Field(min_length=1, max_length=32)
    display_name: str = Field(min_length=1, max_length=128)
    executable_path: str = Field(min_length=1, max_length=512)
    working_dir: str | None = Field(default=None, max_length=512)
    args_json: list[str] = Field(default_factory=list)
    keywords_json: list[str] = Field(default_factory=list)
    enabled: bool = True
    is_default_for_intent: bool = False
    confirm_required: bool = False


class LocalAppUpdate(BaseModel):
    intent_type: str | None = Field(default=None, min_length=1, max_length=32)
    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    executable_path: str | None = Field(default=None, min_length=1, max_length=512)
    working_dir: str | None = Field(default=None, max_length=512)
    args_json: list[str] | None = None
    keywords_json: list[str] | None = None
    enabled: bool | None = None
    is_default_for_intent: bool | None = None
    confirm_required: bool | None = None


class LocalAppResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    app_key: str
    intent_type: str
    display_name: str
    executable_path: str
    working_dir: str | None = None
    args_json: list[str]
    keywords_json: list[str]
    enabled: bool
    is_default_for_intent: bool
    confirm_required: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Open / test
# ---------------------------------------------------------------------------


class LocalAppOpenRequest(BaseModel):
    """Open a local app by app_key or intent_type.

    At least one of *app_key* or *intent_type* must be provided.
    *app_key* takes priority when both are given.
    """

    app_key: str | None = Field(default=None, max_length=64)
    intent_type: str | None = Field(default=None, max_length=32)
    conversation_id: UUID | None = None


class LocalAppTestResponse(BaseModel):
    """Result of testing a local app launch."""

    status: str  # opened | failed
    message: str
    app_key: str
    display_name: str
    executable_path: str


class LocalAppOpenResponse(BaseModel):
    """Result of opening a local app via open endpoint.

    ``status`` is one of:
    - ``opened``: App was launched successfully.
    - ``requires_confirmation``: A pending_action was created; user must confirm.
    - ``not_configured``: No app found for the given app_key/intent_type.
    - ``requires_selection``: Multiple apps match; user must pick one.
    - ``failed``: An error occurred during launch.
    """

    status: str
    message: str
    app_key: str | None = None
    display_name: str | None = None
    executable_path: str | None = None
    pending_action_id: UUID | None = None
    candidates: list[LocalAppResponse] = Field(default_factory=list)
    error_detail: str | None = None


# ---------------------------------------------------------------------------
# Pending Action
# ---------------------------------------------------------------------------


class PendingActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    conversation_id: UUID
    action_type: str
    payload_json: dict[str, Any]
    status: str
    created_at: datetime
    expires_at: datetime | None = None
    executed_at: datetime | None = None
    cancelled_at: datetime | None = None
    source_message_id: UUID | None = None
    assistant_message_id: UUID | None = None


class PendingActionConfirmRequest(BaseModel):
    """Optional override when confirming a pending action."""

    override_args: dict[str, Any] | None = None
