import asyncio
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.core.config import settings
from app.events.bus import bus
from app.events.types import EventType
from app.schemas.decision import SkillCall
from app.services.memory_service import MemoryService
from app.services.todo_service import TodoService
from app.skills.base import SkillError, SkillProgress
from app.skills.registry import SkillRegistry as AppSkillRegistry


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    content: str
    keywords: tuple[str, ...] = ()


class SkillRegistry:
    """File-backed SKILL.md registry used by the tool-calling agent path."""

    def __init__(self, root: Path):
        self.root = root
        self._skills = self._load()

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def all(self) -> list[Skill]:
        return list(self._skills.values())

    def match(self, content: str) -> list[Skill]:
        normalized = content.lower()
        matches: list[Skill] = []
        for skill in self._skills.values():
            if skill.name.lower() in normalized or any(keyword in normalized for keyword in skill.keywords):
                matches.append(skill)
        return matches

    def render_catalog(self, extra_skills: list[Skill] | None = None) -> str:
        merged = {skill.name: skill for skill in self._skills.values()}
        for skill in extra_skills or []:
            merged[skill.name] = skill
        return "\n".join(
            f"- {skill.name}: {skill.description}"
            for skill in sorted(merged.values(), key=lambda item: item.name)
        )

    def _load(self) -> dict[str, Skill]:
        skills: dict[str, Skill] = {}
        if not self.root.exists():
            return skills

        for skill_file in sorted(self.root.glob("*/SKILL.md")):
            try:
                content = skill_file.read_text(encoding="utf-8")
                metadata = self._frontmatter(content)
            except (OSError, ValueError, yaml.YAMLError):
                continue
            name = str(metadata.get("name") or "").strip()
            description = str(metadata.get("description") or "").strip()
            if not name or not description:
                continue
            keywords = self._keywords(name, content, metadata.get("keywords"))
            skills[name] = Skill(
                name=name,
                description=description,
                content=content,
                keywords=keywords,
            )
        return skills

    def _frontmatter(self, content: str) -> dict:
        normalized = content.replace("\r\n", "\n")
        if not normalized.startswith("---\n"):
            raise ValueError("SKILL.md frontmatter is required")
        _, frontmatter, _ = normalized.split("---", 2)
        metadata = yaml.safe_load(frontmatter) or {}
        if not isinstance(metadata, dict):
            raise ValueError("SKILL.md frontmatter must be a mapping")
        return metadata

    def _keywords(self, name: str, content: str, declared: object = None) -> tuple[str, ...]:
        base = {name.replace("_", " "), name.replace("_", "-"), name}
        if isinstance(declared, list):
            base.update(str(item).strip().lower() for item in declared if str(item).strip())
        lowered = content.lower()
        hints = {
            "weather": ("weather", "forecast", "天气", "预报"),
            "web_search_aggregator": ("search", "web", "网页", "搜索"),
            "todo_summary": ("todo", "task", "待办", "任务"),
            "evening_review": ("review", "复盘", "总结"),
            "screen_reader": ("screen", "screenshot", "屏幕", "截图"),
            "inspiration_organizer": ("inspiration", "idea", "灵感", "想法"),
        }
        for key, values in hints.items():
            if key == name or key in lowered:
                base.update(values)
        return tuple(sorted(base))


class SkillService:
    def __init__(
        self,
        memory_service: MemoryService | None = None,
        todo_service: TodoService | None = None,
    ):
        self._active_cancel: asyncio.Event | None = None
        self.memory_service = memory_service
        self.todo_service = todo_service

    async def execute(self, skill_call: SkillCall) -> None:
        skill = AppSkillRegistry.get(skill_call.skill_name)
        if not skill:
            await bus.publish(
                EventType.SKILL_ERROR,
                {
                    "skill_name": skill_call.skill_name,
                    "code": "SKILL_NOT_FOUND",
                    "message": f"Skill '{skill_call.skill_name}' is not available",
                    "hint": "I do not have that tool available yet.",
                },
            )
            return

        setattr(skill, "_memory_service", self.memory_service)
        setattr(skill, "_todo_service", self.todo_service)
        params = dict(skill_call.skill_params)
        if "user_id" not in params and skill_call.message_id:
            params["user_id"] = skill_call.message_id

        cancel_token = asyncio.Event()
        self._active_cancel = cancel_token

        async def on_progress(progress: SkillProgress) -> None:
            await bus.publish(
                EventType.SKILL_PROGRESS,
                {
                    "skill_name": progress.skill_name,
                    "message": progress.message,
                    "percent": progress.percent,
                },
            )

        try:
            result = await asyncio.wait_for(
                skill.execute(
                    params,
                    on_progress,
                    float(settings.skill_timeout_seconds),
                    cancel_token,
                ),
                timeout=float(settings.skill_timeout_seconds),
            )
            await bus.publish(
                EventType.SKILL_DONE,
                {
                    "skill_name": skill_call.skill_name,
                    "result": result,
                },
            )
        except TimeoutError:
            await bus.publish(
                EventType.SKILL_ERROR,
                {
                    "skill_name": skill_call.skill_name,
                    "code": "TIMEOUT",
                    "message": "Skill timed out",
                    "hint": "It's taking longer than expected. Maybe try again?",
                },
            )
        except SkillError as error:
            await bus.publish(
                EventType.SKILL_ERROR,
                {
                    "skill_name": skill_call.skill_name,
                    "code": error.code,
                    "message": error.message,
                    "hint": error.user_facing_hint,
                },
            )
        except Exception as error:
            await bus.publish(
                EventType.SKILL_ERROR,
                {
                    "skill_name": skill_call.skill_name,
                    "code": "UNKNOWN",
                    "message": str(error),
                    "hint": "Something went wrong. Could you try again?",
                },
            )
        finally:
            self._active_cancel = None

    async def cancel(self) -> bool:
        if self._active_cancel and not self._active_cancel.is_set():
            self._active_cancel.set()
            return True
        return False
