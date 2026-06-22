from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user_id, get_skill_manager
from app.schemas.user_skill import MarketSkillOut, SkillDetailOut
from app.services.skill_manager import SkillManager

router = APIRouter(prefix="/skills/market", tags=["skill-market"])

_market_path = Path(__file__).resolve().parents[4] / "app" / "skills" / "market.json"


def _load_market() -> list[dict]:
    import json

    return json.loads(_market_path.read_text(encoding="utf-8"))


def _find_market_skill(name: str) -> dict | None:
    for item in _load_market():
        if item["name"] == name:
            return item
    return None


@router.get("", response_model=list[MarketSkillOut])
def list_market_skills() -> list[MarketSkillOut]:
    items = _load_market()
    return [
        MarketSkillOut(
            name=item["name"],
            description=item["description"],
            tags=item.get("tags") or [],
            version=item.get("version", "1.0.0"),
            author=item.get("author", ""),
            official=item.get("official", True),
        )
        for item in items
    ]


@router.post("/{name}/install", response_model=SkillDetailOut, status_code=status.HTTP_201_CREATED)
def install_market_skill(
    name: str,
    user_id: UUID = Depends(get_current_user_id),
    manager: SkillManager = Depends(get_skill_manager),
) -> SkillDetailOut:
    item = _find_market_skill(name)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Market skill '{name}' not found.",
        )
    content = str(item.get("content") or "")
    if not content:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Market skill '{name}' has no content.",
        )
    try:
        skill = manager.install_text(user_id, content, installed_from="market")
    except Exception as exc:
        detail = str(exc)
        if "already installed" in detail.lower() or "conflict" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )
    return SkillDetailOut.model_validate(skill)
