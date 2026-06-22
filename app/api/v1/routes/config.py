from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_config_service, get_current_user_id
from app.schemas.user_config import UserConfigOut, UserConfigPatch
from app.services.config_service import ConfigService

router = APIRouter(prefix="/config/user/me", tags=["config"])


@router.get("", response_model=UserConfigOut)
def get_user_config(
    user_id: UUID = Depends(get_current_user_id),
    service: ConfigService = Depends(get_config_service),
) -> UserConfigOut:
    return service.list_fields(user_id)


@router.patch("", response_model=UserConfigOut)
def update_user_config(
    payload: UserConfigPatch,
    user_id: UUID = Depends(get_current_user_id),
    service: ConfigService = Depends(get_config_service),
) -> UserConfigOut:
    return service.update(user_id, payload)


@router.put("/reset", response_model=UserConfigOut)
def reset_user_config(
    user_id: UUID = Depends(get_current_user_id),
    service: ConfigService = Depends(get_config_service),
) -> UserConfigOut:
    return service.reset(user_id)
