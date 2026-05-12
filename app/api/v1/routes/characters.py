from pathlib import Path

from fastapi import APIRouter, Depends

from app.api.deps import get_character_service
from app.schemas.character import CharacterCard, CharacterCardOverride
from app.services.character_service import CharacterService

router = APIRouter(prefix="/characters", tags=["characters"])


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
