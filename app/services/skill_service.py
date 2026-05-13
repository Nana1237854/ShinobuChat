from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    content: str
    path: Path


class SkillRegistry:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._skills = self._load_skills()

    def names(self) -> list[str]:
        return sorted(self._skills)

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def match(self, user_text: str) -> list[Skill]:
        normalized = user_text.casefold()
        matches: list[Skill] = []
        for skill in self._skills.values():
            haystack = f"{skill.name}\n{skill.description}".casefold()
            if skill.name.casefold() in normalized:
                matches.append(skill)
                continue
            if any(keyword in normalized for keyword in _SKILL_KEYWORDS.get(skill.name, ())):
                matches.append(skill)
                continue
            if any(token and token in normalized for token in _tokenize_description(haystack)):
                matches.append(skill)

        deduped: dict[str, Skill] = {}
        for skill in matches:
            deduped[skill.name] = skill
        return list(deduped.values())[:3]

    def render_catalog(self) -> str:
        lines = []
        for skill in sorted(self._skills.values(), key=lambda item: item.name):
            lines.append(f"- {skill.name}: {skill.description}")
        return "\n".join(lines)

    def _load_skills(self) -> dict[str, Skill]:
        if not self.skills_dir.exists():
            return {}

        skills: dict[str, Skill] = {}
        for skill_file in sorted(self.skills_dir.glob("*/SKILL.md")):
            content = skill_file.read_text(encoding="utf-8")
            metadata = _parse_frontmatter(content)
            name = metadata.get("name") or skill_file.parent.name
            description = metadata.get("description") or ""
            skills[name] = Skill(
                name=name,
                description=description,
                content=content,
                path=skill_file,
            )
        return skills


def _parse_frontmatter(content: str) -> dict[str, str]:
    if not content.startswith("---"):
        return {}

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}

    metadata: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata


def _tokenize_description(text: str) -> list[str]:
    return [
        token
        for token in text.replace("/", " ").replace(",", " ").replace("，", " ").split()
        if len(token) >= 4
    ]


_SKILL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "weather": ("天气", "气温", "下雨", "forecast", "weather", "wttr"),
    "evening_review": ("晚间", "复盘", "今日消息", "今天聊了", "review"),
    "todo_summary": ("todo", "待办", "任务清单", "todo summary", "事项"),
    "inspiration_organizer": ("灵感", "inspiration", "点子", "想法", "标签"),
    "screen_reader": ("截图", "截屏", "ocr", "屏幕", "识别屏幕", "读屏"),
    "web_search_aggregator": ("搜索", "网页", "web search", "查资料", "汇总网页"),
}
