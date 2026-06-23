"""Action audit schemas (Phase 2)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ActionAuditItem(BaseModel):
    id: UUID
    user_id: UUID | None = None
    conversation_id: UUID | None = None
    message_id: UUID | None = None
    source: str
    action_type: str
    target: str = ""
    status: str = "unknown"
    risk_level: str = "unknown"
    requires_confirmation: bool = False
    policy_allowed: bool = True
    verified: bool = False
    arguments_redacted: dict | None = None
    result_summary: str = ""
    reasons: list[str] | None = None
    checked_fields: dict | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class ActionAuditListResponse(BaseModel):
    items: list[ActionAuditItem]
