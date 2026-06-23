"""Local Agent settings and action logs routes (F16)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.models.local_action_log import LocalActionLog
from app.schemas.local_agent_settings import (
    LocalAgentSettingsOut,
    LocalAgentSettingsPatch,
)
from app.services.local_agent_settings_service import LocalAgentSettingsService

router = APIRouter(prefix="/local-agent", tags=["local-agent"])


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@router.get("/settings", response_model=LocalAgentSettingsOut)
def get_local_agent_settings(
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> LocalAgentSettingsOut:
    return LocalAgentSettingsOut(**LocalAgentSettingsService(db).get_settings(user_id))


@router.patch("/settings", response_model=LocalAgentSettingsOut)
def patch_local_agent_settings(
    patch: LocalAgentSettingsPatch,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> LocalAgentSettingsOut:
    data = LocalAgentSettingsService(db).save_settings(
        user_id,
        patch.model_dump(exclude_unset=True),
    )
    return LocalAgentSettingsOut(**data)


# ---------------------------------------------------------------------------
# Action Logs
# ---------------------------------------------------------------------------

@router.get("/actions/logs")
def get_local_action_logs(
    user_id: UUID = Depends(get_current_user_id),
    action_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    q = (
        db.query(LocalActionLog)
        .filter(LocalActionLog.user_id == user_id)
    )
    if action_type:
        q = q.filter(LocalActionLog.action_type == action_type)
    if status:
        q = q.filter(LocalActionLog.status == status)
    q = q.order_by(LocalActionLog.created_at.desc()).offset(offset).limit(limit)
    rows = q.all()
    return {
        "logs": [
            {
                "id": str(r.id),
                "user_id": str(r.user_id),
                "conversation_id": str(r.conversation_id) if r.conversation_id else None,
                "action_type": r.action_type,
                "target": r.target,
                "status": r.status,
                "message": r.message,
                "error_detail": r.error_detail,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in rows
        ]
    }
