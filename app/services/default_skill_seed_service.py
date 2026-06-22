"""Seed default user-level skills on first access to the skill list.

Default skills live in app/seed/default_user_skills/ — NOT in the
built-in skills/ root — so they pass through SkillManager.install_text
without triggering the builtin-name conflict check.
"""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user_skill import UserSkill
from app.services.skill_manager import SkillManager

logger = logging.getLogger(__name__)


def _seed_root() -> Path:
    return Path(__file__).resolve().parents[1] / "seed" / "default_user_skills"


def ensure_default_user_skills(
    db: Session,
    user_id: UUID,
) -> list[UserSkill]:
    """Install missing default skills for `user_id`.  Idempotent — safe to
    call on every GET /api/v1/skills/user/me."""
    seed_root = _seed_root()
    if not seed_root.exists():
        logger.warning("Default skill seed directory not found: %s", seed_root)
        return []

    manager = SkillManager(db)

    existing_names: set[str] = {
        row[0]
        for row in db.query(UserSkill.name).filter(UserSkill.user_id == user_id).all()
    }

    created: list[UserSkill] = []

    for skill_file in sorted(seed_root.glob("*/SKILL.md")):
        try:
            content = skill_file.read_text(encoding="utf-8")
            parsed = manager.parse(content)
        except Exception:
            logger.exception("Failed to parse seed skill %s — skipping", skill_file)
            continue

        if parsed.name in existing_names:
            continue

        skill = UserSkill(
            user_id=user_id,
            name=parsed.name,
            description=parsed.description,
            content=parsed.content,
            keywords=list(parsed.keywords),
            enabled=True,
            installed_from="default",
            source_url=None,
        )
        db.add(skill)
        created.append(skill)
        existing_names.add(parsed.name)

    if created:
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # Concurrent request installed the same skill — re-read what's
            # actually persisted and return that set instead of crashing.
            logger.info(
                "IntegrityError during seed install for user %s — "
                "concurrent request handled it; re-reading.",
                user_id,
            )
            created = (
                db.query(UserSkill)
                .filter(
                    UserSkill.user_id == user_id,
                    UserSkill.name.in_([skill.name for skill in created]),
                )
                .all()
            )
        else:
            for skill in created:
                db.refresh(skill)

    return created
