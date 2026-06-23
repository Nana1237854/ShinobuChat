from __future__ import annotations

from typing import Iterator
from uuid import UUID

from app.core.config import settings
from app.models.message import Message
from app.schemas.message import RouteMode
from app.services.agents.coordinator import AgentCoordinator
from app.services.ai_client import AIClient
from app.services.skill_manager import SkillManager
from app.services.skill_service import Skill
from app.services.stream_events import StreamEvent
from app.services.turn.turn_state import MessageTurnState


class ReplyGenerationService:
    def __init__(
        self,
        ai_client: AIClient,
        agent_coordinator: AgentCoordinator | None = None,
        skill_manager: SkillManager | None = None,
    ):
        self.ai_client = ai_client
        self.agent_coordinator = agent_coordinator
        self.skill_manager = skill_manager

    def generate(
        self,
        *,
        state: MessageTurnState,
        messages: list[dict],
        history: list[Message],
        user_id: UUID,
        ai_config: dict | None,
        max_tokens: int,
    ) -> Iterator[StreamEvent | str]:
        if state.route_mode is RouteMode.CHAT:
            full_reply = ""
            for chunk in self.ai_client.stream_chat(
                messages, max_tokens=max_tokens, runtime_config=ai_config,
            ):
                full_reply += chunk
            yield full_reply
            return

        for event in state.progress_events:
            yield event

        user_skills = self._runtime_skills(user_id)

        yield from self.agent_coordinator.run_task(
            messages,
            history,
            user_skills=user_skills,
            ai_config=ai_config,
            conversation_mode=state.conversation_mode,
            route_mode="agent",
            user_id=user_id,
            conversation_id=state.conversation.id,
        )

    def _runtime_skills(self, user_id: UUID) -> list[Skill]:
        if self.skill_manager is None:
            return []
        return self.skill_manager.runtime_skills(user_id)
