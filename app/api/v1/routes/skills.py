from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_current_user_id, get_skill_manager
from app.schemas.user_skill import (
    UserSkillCreate,
    UserSkillDetailOut,
    UserSkillPatch,
    UserSkillSummaryOut,
    UserSkillUpdate,
)
from app.services.skill_manager import SkillManager

router = APIRouter(prefix="/skills/user/me", tags=["skills"])


@router.get("", response_model=list[UserSkillSummaryOut])
def list_user_skills(
    user_id: UUID = Depends(get_current_user_id),
    service: SkillManager = Depends(get_skill_manager),
) -> list[UserSkillSummaryOut]:
    return [UserSkillSummaryOut.model_validate(skill) for skill in service.list(user_id)]


@router.post("", response_model=UserSkillDetailOut, status_code=status.HTTP_201_CREATED)
def install_user_skill(
    payload: UserSkillCreate,
    user_id: UUID = Depends(get_current_user_id),
    service: SkillManager = Depends(get_skill_manager),
) -> UserSkillDetailOut:
    skill = service.install_text(user_id, payload.content)
    return UserSkillDetailOut.model_validate(skill)


@router.get("/{skill_id}", response_model=UserSkillDetailOut)
def get_user_skill(
    skill_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    service: SkillManager = Depends(get_skill_manager),
) -> UserSkillDetailOut:
    return UserSkillDetailOut.model_validate(service.get(user_id, skill_id))


@router.put("/{skill_id}", response_model=UserSkillDetailOut)
def update_user_skill(
    skill_id: UUID,
    payload: UserSkillUpdate,
    user_id: UUID = Depends(get_current_user_id),
    service: SkillManager = Depends(get_skill_manager),
) -> UserSkillDetailOut:
    return UserSkillDetailOut.model_validate(service.update(user_id, skill_id, payload.content))


@router.patch("/{skill_id}", response_model=UserSkillSummaryOut)
def set_user_skill_enabled(
    skill_id: UUID,
    payload: UserSkillPatch,
    user_id: UUID = Depends(get_current_user_id),
    service: SkillManager = Depends(get_skill_manager),
) -> UserSkillSummaryOut:
    return UserSkillSummaryOut.model_validate(
        service.set_enabled(user_id, skill_id, payload.enabled)
    )


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_skill(
    skill_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    service: SkillManager = Depends(get_skill_manager),
) -> Response:
    service.delete(user_id, skill_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
