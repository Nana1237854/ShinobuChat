"""Debug API routes (Phase 2).

Authorized endpoints for inspecting PromptTrace and ActionAudit records.
Users can only see their own data. Never exposes system prompts, tool
schemas, web page content, or API keys.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.schemas.action_audit import ActionAuditItem, ActionAuditListResponse
from app.schemas.debug_trace import PromptTraceItem
from app.services.action_audit_service import ActionAuditService
from app.services.prompt_trace_service import PromptTraceService

router = APIRouter(prefix="/debug", tags=["debug"])


# ── Prompt Traces ──

@router.get("/prompt-traces/conversations/{conversation_id}")
def list_prompt_traces(
    conversation_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[PromptTraceItem]:
    traces = PromptTraceService(db).list_for_conversation(current_user_id, conversation_id)
    return [PromptTraceItem.model_validate(t) for t in traces]


@router.get("/prompt-traces/messages/{message_id}")
def get_prompt_trace(
    message_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> PromptTraceItem | None:
    trace = PromptTraceService(db).get_for_message(current_user_id, message_id)
    if trace is None:
        raise NotFoundError("PromptTrace not found")
    return PromptTraceItem.model_validate(trace)


# ── Action Audits ──

@router.get("/action-audits", response_model=ActionAuditListResponse)
def list_action_audits(
    source: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ActionAuditListResponse:
    items = ActionAuditService(db).list_for_user(
        current_user_id,
        source=source,
        limit=limit,
        offset=offset,
    )
    return ActionAuditListResponse(
        items=[ActionAuditItem.model_validate(item) for item in items]
    )


@router.get("/action-audits/{audit_id}", response_model=ActionAuditItem)
def get_action_audit(
    audit_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ActionAuditItem:
    item = ActionAuditService(db).get(audit_id, current_user_id)
    if item is None:
        raise NotFoundError("ActionAudit not found")
    return ActionAuditItem.model_validate(item)


@router.get("/action-audits/conversations/{conversation_id}")
def list_action_audits_by_conversation(
    conversation_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[ActionAuditItem]:
    items = ActionAuditService(db).list_for_conversation(current_user_id, conversation_id)
    return [ActionAuditItem.model_validate(item) for item in items]


@router.get("/action-audits/messages/{message_id}")
def list_action_audits_by_message(
    message_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[ActionAuditItem]:
    items = ActionAuditService(db).list_for_message(current_user_id, message_id)
    return [ActionAuditItem.model_validate(item) for item in items]
