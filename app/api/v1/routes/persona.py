from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id, get_persona_service
from app.schemas.persona import PersonaSettingsOut, PersonaSettingsUpdate
from app.services.persona_settings_service import PersonaSettingsService

router = APIRouter(prefix="/persona", tags=["persona"])


@router.get("/settings", response_model=PersonaSettingsOut)
def get_settings(
    user_id: UUID = Depends(get_current_user_id),
    service: PersonaSettingsService = Depends(get_persona_service),
) -> PersonaSettingsOut:
    return PersonaSettingsOut.model_validate(service.get_settings(user_id))


@router.put("/settings", response_model=PersonaSettingsOut)
def update_settings(
    payload: PersonaSettingsUpdate,
    user_id: UUID = Depends(get_current_user_id),
    service: PersonaSettingsService = Depends(get_persona_service),
) -> PersonaSettingsOut:
    return PersonaSettingsOut.model_validate(service.update_settings(user_id, payload))
