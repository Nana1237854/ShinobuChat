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
from app.services.behavior_engine import BehaviorEngine, BehaviorContext
from app.services.capabilities.capability_policy_service import CapabilityPolicyService
from app.services.capabilities.capability_registry import CapabilityRegistry
from app.services.local_agent_settings_service import LocalAgentSettingsService
from app.services.prompt_trace_service import PromptTraceService
from app.services.skill_run_log_service import SkillRunLogService
from app.services.tasks.task_run_service import TaskRunService
from app.services.tasks.task_event_service import TaskEventService
from app.services.tasks.task_event_store import TaskEventStore
from app.services.jobs.job_run_log_service import JobRunLogService

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


# ── Phase 3: Job Runs ──


@router.get("/jobs/runs")
def list_job_runs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = JobRunLogService(db).list_all(limit=limit)
    return [
        {
            "id": str(r.id),
            "job_name": r.job_name,
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "duration_ms": r.duration_ms,
            "result_summary": r.result_summary,
            "error_message": r.error_message,
        }
        for r in rows
    ]


@router.get("/jobs/runs/{run_id}")
def get_job_run(
    run_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    row = JobRunLogService(db).get(run_id)
    if row is None:
        raise NotFoundError("JobRunLog not found")
    return {
        "id": str(row.id),
        "job_name": row.job_name,
        "status": row.status,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "duration_ms": row.duration_ms,
        "result_summary": row.result_summary,
        "error_message": row.error_message,
    }


# ── Phase 3: Task Runs (debug view) ──

_debug_task_store = TaskEventStore()
_debug_task_event_service = TaskEventService(_debug_task_store)


@router.get("/tasks")
def list_debug_tasks(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    rows = TaskRunService(db, _debug_task_event_service).list_for_user(
        current_user_id, limit=limit, offset=offset,
    )
    return {
        "tasks": [
            {
                "id": r.id,
                "task_type": r.task_type,
                "status": r.status,
                "title": r.title,
                "progress": r.progress,
            }
            for r in rows
        ]
    }


@router.get("/tasks/{task_id}")
def get_debug_task(
    task_id: str,
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    r = TaskRunService(db, _debug_task_event_service).get_for_user(task_id, current_user_id)
    return {
        "id": r.id,
        "task_type": r.task_type,
        "status": r.status,
        "title": r.title,
        "progress": r.progress,
        "message": r.message,
        "result_summary": r.result_summary,
        "error_message": r.error_message,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
    }


# ── Phase 3: Skill Runs ──


@router.get("/skills/runs")
def list_skill_runs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = SkillRunLogService(db).list_for_user(current_user_id, limit=limit, offset=offset)
    return [
        {
            "id": str(r.id),
            "skill_name": r.skill_name,
            "trigger_source": r.trigger_source,
            "matched": r.matched,
            "activated": r.activated,
            "input_summary": r.input_summary,
            "output_summary": r.output_summary,
            "error_message": r.error_message,
            "duration_ms": r.duration_ms,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/skills/runs/{run_id}")
def get_skill_run(
    run_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    row = SkillRunLogService(db).get_for_user(run_id, current_user_id)
    if row is None:
        raise NotFoundError("SkillRunLog not found")
    return {
        "id": str(row.id),
        "skill_name": row.skill_name,
        "trigger_source": row.trigger_source,
        "matched": row.matched,
        "activated": row.activated,
        "input_summary": row.input_summary,
        "output_summary": row.output_summary,
        "error_message": row.error_message,
        "duration_ms": row.duration_ms,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


# ── Phase 3: Capabilities ──


def _serialize_capability_decision(decision) -> dict:
    """Explicitly serialize CapabilityDecision to JSON-safe dict."""
    return {
        "enabled": decision.enabled,
        "requires_confirmation": decision.requires_confirmation,
        "reason": decision.reason,
    }


@router.get("/capabilities")
def list_capabilities(
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    registry = CapabilityRegistry()
    policy = CapabilityPolicyService(db)

    return {
        "capabilities": [
            {
                "key": c.key,
                "label": c.label,
                "description": c.description,
                "risk_level": c.risk_level,
                "decision": _serialize_capability_decision(
                    policy.check(current_user_id, c.key)
                ),
            }
            for c in registry.list()
        ]
    }


# ── Phase 3: Behavior Preview ──


@router.get("/behavior/preview")
def preview_behavior(
    mode: str = Query(default="companion"),
    current_user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    settings = LocalAgentSettingsService(db).get_settings(current_user_id)

    decision = BehaviorEngine().decide(
        BehaviorContext(
            user_id=str(current_user_id),
            conversation_mode=mode,
            local_agent_settings=settings,
        )
    )

    return {
        "conversation_mode": decision.conversation_mode,
        "reply_length": decision.reply_length,
        "proactive_level": decision.proactive_level,
        "allowed_tool_groups": decision.allowed_tool_groups,
        "blocked_tool_groups": decision.blocked_tool_groups,
        "reminder_style": decision.reminder_style,
        "memory_write_policy": decision.memory_write_policy,
        "tts_style": decision.tts_style,
        "should_suppress_idle_chat": decision.should_suppress_idle_chat,
        "should_prefer_todo": decision.should_prefer_todo,
        "should_prefer_goal": decision.should_prefer_goal,
        "should_prefer_task_planning": decision.should_prefer_task_planning,
        "prompt_hints": decision.prompt_hints,
        "debug_reasons": decision.debug_reasons,
    }
