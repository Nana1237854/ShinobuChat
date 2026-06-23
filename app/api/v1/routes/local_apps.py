"""Routes for managing user-configured local applications (F11)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id, get_db
from app.schemas.local_app import (
    LocalAppCreate,
    LocalAppOpenRequest,
    LocalAppOpenResponse,
    LocalAppResponse,
    LocalAppTestResponse,
    LocalAppUpdate,
)
from app.domains.local_agent.local_agent_settings_service import LocalAgentSettingsService
from app.domains.local_agent.local_app_service import LocalAppService

router = APIRouter(prefix="/local-apps", tags=["local-apps"])


@router.get("", response_model=list[LocalAppResponse])
def list_local_apps(
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[LocalAppResponse]:
    svc = LocalAppService(db)
    apps = svc.list_apps(user_id)
    return [LocalAppResponse.model_validate(app) for app in apps]


@router.post("", response_model=LocalAppResponse, status_code=status.HTTP_201_CREATED)
def create_local_app(
    body: LocalAppCreate,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> LocalAppResponse:
    svc = LocalAppService(db)
    app = svc.create_app(user_id, **body.model_dump())
    return LocalAppResponse.model_validate(app)


@router.patch("/{app_id}", response_model=LocalAppResponse)
def update_local_app(
    app_id: UUID,
    body: LocalAppUpdate,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> LocalAppResponse:
    svc = LocalAppService(db)
    app = svc.update_app(app_id, user_id, **body.model_dump(exclude_unset=True))
    return LocalAppResponse.model_validate(app)


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_local_app(
    app_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> None:
    svc = LocalAppService(db)
    svc.delete_app(app_id, user_id)


@router.post("/{app_id}/test", response_model=LocalAppTestResponse)
def test_local_app(
    app_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> LocalAppTestResponse:
    LocalAgentSettingsService(db).ensure_local_launcher_enabled(user_id)
    svc = LocalAppService(db)
    app = svc.get_app(app_id, user_id)
    result = svc.open_app(
        user_id,
        app_key=app.app_key,
        intent_type=app.intent_type,
        source="test",
    )
    return LocalAppTestResponse(
        status=result["status"],
        message=result["message"],
        app_key=app.app_key,
        display_name=app.display_name,
        executable_path=app.executable_path,
    )


@router.post("/open", response_model=LocalAppOpenResponse)
def open_local_app(
    body: LocalAppOpenRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> LocalAppOpenResponse:
    LocalAgentSettingsService(db).ensure_local_launcher_enabled(user_id)
    svc = LocalAppService(db)
    result = svc.open_app(
        user_id,
        app_key=body.app_key,
        intent_type=body.intent_type,
        conversation_id=body.conversation_id,
        source="api",
    )
    return LocalAppOpenResponse(
        status=result.get("status", "failed"),
        message=result.get("message", ""),
        app_key=result.get("app_key"),
        display_name=result.get("display_name"),
        executable_path=result.get("executable_path"),
        pending_action_id=result.get("pending_action_id"),
        candidates=[
            LocalAppResponse.model_validate(c) if hasattr(c, "id") else c
            for c in result.get("candidates", [])
        ],
        error_detail=result.get("error_detail"),
    )
