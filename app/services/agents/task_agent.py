from __future__ import annotations

from typing import Iterator

from app.models.message import Message
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.agent_service import AgentService
from app.services.skill_service import SkillRegistry
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
    ) -> tuple[list[dict], list[StreamEvent]]:
        progress_events: list[StreamEvent] = []
        activated_skills = self.skill_registry.match(content)
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
        )
        return messages, progress_events

    def run(self, messages: list[dict], history: list[Message]) -> Iterator[StreamEvent | str]:
        yield from self.agent_orchestrator.run(messages, history)
