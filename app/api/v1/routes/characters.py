from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_character_profile_service, get_character_service, get_current_user_id
from app.core.exceptions import ConflictError, NotFoundError
from app.schemas.character import CharacterCard, CharacterCardOverride
from app.schemas.character_profile import (
    CharacterProfileCreate,
    CharacterProfileOut,
    CharacterProfileUpdate,
    ConversationCharactersRequest,
    ConversationCharactersResponse,
)
from app.services.character_profile_service import CharacterProfileService
from app.services.character_service import CharacterService

router = APIRouter(prefix="/characters", tags=["characters"])


# ── Existing YAML-based character endpoints (unchanged) ──


@router.get("", response_model=list[str])
def list_characters(
    character_service: CharacterService = Depends(get_character_service),
) -> list[str]:
    try:
        import yaml
    except ModuleNotFoundError:
        return ["Shinobu"]

    directory = Path(character_service.characters_dir)
    if not directory.exists():
        return ["Shinobu"]

    names = set()
    for path in directory.glob("*.yaml"):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if isinstance(data, dict) and isinstance(data.get("name"), str):
            names.add(data["name"])
    return sorted(names) if names else ["Shinobu"]


@router.get("/active", response_model=CharacterCard)
def get_active_character(
    user_id: str,
    character_service: CharacterService = Depends(get_character_service),
) -> CharacterCard:
    return character_service.load_for_user(user_id)


@router.put("/active", response_model=CharacterCard)
def update_active_character(
    user_id: str,
    override: CharacterCardOverride,
    character_service: CharacterService = Depends(get_character_service),
) -> CharacterCard:
    character_service.save_user_override(user_id, override)
    return character_service.load_for_user(user_id)


# ── Feature 9: DB-backed CharacterProfile CRUD ──


@router.post("/profiles", response_model=CharacterProfileOut, status_code=status.HTTP_201_CREATED)
def create_character_profile(
    payload: CharacterProfileCreate,
    user_id: UUID = Depends(get_current_user_id),
    profile_service: CharacterProfileService = Depends(get_character_profile_service),
) -> CharacterProfileOut:
    try:
        return profile_service.create(user_id, payload)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/profiles", response_model=list[CharacterProfileOut])
def list_character_profiles(
    user_id: UUID = Depends(get_current_user_id),
    profile_service: CharacterProfileService = Depends(get_character_profile_service),
) -> list[CharacterProfileOut]:
    return profile_service.list_by_user(user_id)


@router.get("/profiles/{profile_id}", response_model=CharacterProfileOut)
def get_character_profile(
    profile_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    profile_service: CharacterProfileService = Depends(get_character_profile_service),
) -> CharacterProfileOut:
    try:
        return profile_service.get(profile_id, user_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/profiles/{profile_id}", response_model=CharacterProfileOut)
def update_character_profile(
    profile_id: UUID,
    payload: CharacterProfileUpdate,
    user_id: UUID = Depends(get_current_user_id),
    profile_service: CharacterProfileService = Depends(get_character_profile_service),
) -> CharacterProfileOut:
    try:
        return profile_service.update(profile_id, user_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_character_profile(
    profile_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    profile_service: CharacterProfileService = Depends(get_character_profile_service),
) -> Response:
    try:
        profile_service.delete(profile_id, user_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Feature 9: Conversation-level character assignment ──


@router.put("/conversation", response_model=ConversationCharactersResponse)
def set_conversation_characters(
    payload: ConversationCharactersRequest,
    user_id: UUID = Depends(get_current_user_id),
    profile_service: CharacterProfileService = Depends(get_character_profile_service),
) -> ConversationCharactersResponse:
    try:
        return profile_service.set_conversation_characters(user_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
