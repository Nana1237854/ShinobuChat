import json
import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user_id, get_skill_manager
from app.core.exceptions import BadRequestError, ConflictError
from app.schemas.user_skill import MarketSkillOut, SkillDetailOut
from app.services.skill_manager import SkillManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/skills/market", tags=["skill-market"])

_market_path = Path(__file__).resolve().parents[4] / "app" / "skills" / "market.json"

# Required fields for each market skill entry
_REQUIRED_FIELDS = ("name", "description", "content")


def _load_market() -> list[dict]:
    """Load the market registry. Raises HTTPException on missing/broken file."""
    if not _market_path.exists():
        logger.error("Market registry file not found: %s", _market_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Market registry is unavailable.",
        )
    try:
        raw = _market_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.error("Cannot read market registry: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Market registry is unreadable.",
        ) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Market registry has invalid JSON: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Market registry is invalid.",
        ) from exc
    if not isinstance(data, list):
        logger.error("Market registry is not a JSON array")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Market registry has an unexpected format.",
        )
    return data


def _find_market_skill(name: str) -> dict | None:
    for item in _load_market():
        if item.get("name") == name:
            return item
    return None


def _validate_market_item(item: dict, index: int) -> None:
    """Log a warning if a market entry is missing a required field."""
    for field in _REQUIRED_FIELDS:
        if not item.get(field):
            logger.warning(
                "Market skill #%d is missing required field '%s'",
                index + 1,
                field,
            )


@router.get("", response_model=list[MarketSkillOut])
def list_market_skills() -> list[MarketSkillOut]:
    items = _load_market()
    result: list[MarketSkillOut] = []
    for i, item in enumerate(items):
        if not item.get("name") or not item.get("description"):
            logger.warning("Market skill #%d skipped: missing name or description", i + 1)
            continue
        result.append(
            MarketSkillOut(
                name=item["name"],
                description=item["description"],
                tags=item.get("tags") or [],
                version=item.get("version", "1.0.0"),
                author=item.get("author", ""),
                official=item.get("official", True),
            )
        )
    return result


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
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except BadRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return SkillDetailOut.model_validate(skill)
