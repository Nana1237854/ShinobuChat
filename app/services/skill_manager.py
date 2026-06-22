from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

import yaml
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.time import local_now
from app.models.user_skill import UserSkill
from app.services.skill_service import Skill

_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")


@dataclass(frozen=True)
class ParsedSkill:
    name: str
    description: str
    keywords: tuple[str, ...]
    content: str


class SkillManager:
    def __init__(self, db: Session):
        self.db = db

    def list(self, user_id: UUID) -> list[UserSkill]:
        return (
            self.db.query(UserSkill)
            .filter(UserSkill.user_id == user_id)
            .order_by(UserSkill.name.asc())
            .all()
        )

    def get(self, user_id: UUID, skill_id: UUID) -> UserSkill:
        skill = (
            self.db.query(UserSkill)
            .filter(UserSkill.user_id == user_id, UserSkill.id == skill_id)
            .first()
        )
        if skill is None:
            raise NotFoundError("Skill not found")
        return skill

    def install_text(self, user_id: UUID, content: str) -> UserSkill:
        parsed = self.parse(content)
        skill = UserSkill(
            user_id=user_id,
            name=parsed.name,
            description=parsed.description,
            content=parsed.content,
            keywords=list(parsed.keywords),
            installed_from="text",
        )
        self.db.add(skill)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(f"Skill '{parsed.name}' is already installed") from exc
        self.db.refresh(skill)
        return skill

    def update(self, user_id: UUID, skill_id: UUID, content: str) -> UserSkill:
        skill = self.get(user_id, skill_id)
        parsed = self.parse(content)
        skill.name = parsed.name
        skill.description = parsed.description
        skill.content = parsed.content
        skill.keywords = list(parsed.keywords)
        skill.updated_at = local_now()
        self.db.add(skill)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(f"Skill '{parsed.name}' is already installed") from exc
        self.db.refresh(skill)
        return skill

    def set_enabled(self, user_id: UUID, skill_id: UUID, enabled: bool) -> UserSkill:
        skill = self.get(user_id, skill_id)
        skill.enabled = enabled
        skill.updated_at = local_now()
        self.db.add(skill)
        self.db.commit()
        self.db.refresh(skill)
        return skill

    def delete(self, user_id: UUID, skill_id: UUID) -> None:
        self.db.delete(self.get(user_id, skill_id))
        self.db.commit()

    def runtime_skills(self, user_id: UUID) -> list[Skill]:
        return [
            Skill(
                name=skill.name,
                description=skill.description,
                content=skill.content,
                keywords=tuple(skill.keywords or ()),
            )
            for skill in self.list(user_id)
            if skill.enabled
        ]

    def parse(self, content: str) -> ParsedSkill:
        normalized = content.replace("\r\n", "\n").strip()
        if not normalized.startswith("---\n"):
            raise BadRequestError("SKILL.md must start with YAML frontmatter")
        try:
            _, frontmatter, _ = normalized.split("---", 2)
        except ValueError as exc:
            raise BadRequestError("SKILL.md frontmatter is not closed") from exc
        try:
            metadata = yaml.safe_load(frontmatter) or {}
        except yaml.YAMLError as exc:
            raise BadRequestError("SKILL.md frontmatter is invalid YAML") from exc
        if not isinstance(metadata, dict):
            raise BadRequestError("SKILL.md frontmatter must be a mapping")
        name = str(metadata.get("name") or "").strip()
        description = str(metadata.get("description") or "").strip()
        if not name or not description:
            raise BadRequestError("SKILL.md requires name and description")
        if not _NAME_PATTERN.fullmatch(name):
            raise BadRequestError(
                "Skill name must be 2-64 lowercase letters, numbers, hyphens, or underscores"
            )
        raw_keywords = metadata.get("keywords") or []
        if not isinstance(raw_keywords, list):
            raise BadRequestError("Skill keywords must be a list")
        keywords = tuple(
            dict.fromkeys(str(keyword).strip().lower() for keyword in raw_keywords if str(keyword).strip())
        )
        return ParsedSkill(name=name, description=description, keywords=keywords, content=normalized + "\n")
