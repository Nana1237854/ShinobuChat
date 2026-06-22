from __future__ import annotations

from typing import Any, Iterator

from app.models.message import Message
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.agent_service import AgentService
from app.services.skill_service import Skill, SkillRegistry
from app.services.stream_events import StreamEvent


class TaskAgent:
    def __init__(
        self,
        skill_registry: SkillRegistry,
        agent_service: AgentService,
        agent_orchestrator: AgentOrchestrator,
    ):
        self.skill_registry = skill_registry
        self.agent_service = agent_service
        self.agent_orchestrator = agent_orchestrator

    def build_messages(
        self,
        content: str,
        history: list[Message],
        memory_context: list[str] | None = None,
        user_skills: list[Skill] | None = None,
    ) -> tuple[list[dict], list[StreamEvent]]:
        normalized = content.lower()
        database_matches = [
            skill
            for skill in user_skills or []
            if skill.name.lower() in normalized
            or any(keyword.lower() in normalized for keyword in skill.keywords)
        ]
        merged = {
            skill.name: skill
            for skill in [*self.skill_registry.match(content), *database_matches]
        }
        activated_skills = list(merged.values())
        progress_events: list[StreamEvent] = []
        if activated_skills:
            progress_events.append(
                StreamEvent(
                    "progress",
                    {
                        "skill_name": ",".join(skill.name for skill in activated_skills),
                        "message": "Loaded SKILL.md",
                        "percent": 0.15,
                    },
                )
            )
        messages = self.agent_service.build_messages(
            content.strip(),
            history,
            activated_skills,
            memory_context=memory_context or [],
            user_skills=user_skills or [],
            tool_catalog=self.agent_orchestrator.tool_registry.render_catalog(),
        )
        return messages, progress_events

    def run(
        self,
        messages: list[dict],
        history: list[Message],
        *,
        user_skills: list[Skill] | None = None,
        ai_config: dict[str, Any] | None = None,
    ) -> Iterator[StreamEvent | str]:
        yield from self.agent_orchestrator.run(
            messages,
            history,
            user_skills=user_skills,
            ai_config=ai_config,
        )
