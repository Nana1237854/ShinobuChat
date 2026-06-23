"""Routes for managing pending user-confirmation actions (F13)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db
from app.schemas.local_app import (
    LocalAppOpenResponse,
    PendingActionResponse,
    PendingActionConfirmRequest,
)
from app.services.local_app_service import LocalAppService

router = APIRouter(prefix="/pending-actions", tags=["pending-actions"])


@router.get("/active", response_model=PendingActionResponse | None)
def get_active_pending_action(
    conversation_id: UUID = Query(default=None),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> PendingActionResponse | None:
    svc = LocalAppService(db)
    pending = svc.get_active_pending_action(user_id, conversation_id=conversation_id)
    if pending is None:
        return None
    return PendingActionResponse.model_validate(pending)


@router.post("/{pending_id}/confirm", response_model=LocalAppOpenResponse)
def confirm_pending_action(
    pending_id: UUID,
    body: PendingActionConfirmRequest | None = None,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> LocalAppOpenResponse:
    svc = LocalAppService(db)
    result = svc.execute_pending_action(pending_id, user_id)
    return LocalAppOpenResponse(
        status=result.get("status", "failed"),
        message=result.get("message", ""),
        app_key=result.get("app_key"),
        display_name=result.get("display_name"),
        executable_path=result.get("executable_path"),
        error_detail=result.get("error_detail"),
    )


@router.post("/{pending_id}/cancel", response_model=LocalAppOpenResponse)
def cancel_pending_action(
    pending_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> LocalAppOpenResponse:
    svc = LocalAppService(db)
    result = svc.cancel_pending_action(pending_id, user_id)
    return LocalAppOpenResponse(
        status=result.get("status", "failed"),
        message=result.get("message", ""),
    )
