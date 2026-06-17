from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Iterator

from app.models.message import Message
from app.schemas.message import RouteMode
from app.services.agents.chat_agent import ChatAgent
from app.services.agents.memory_agent import MemoryAgent
from app.services.agents.router_agent import RouterAgent, RouterDecision
from app.services.agents.task_agent import TaskAgent
from app.services.stream_events import StreamEvent


@dataclass(frozen=True)
class AgentPlan:
    route_mode: RouteMode
    router_decision: RouterDecision
    memory_context: list[str]
    messages: list[dict]
    progress_events: list[StreamEvent]


class AgentCoordinator:
    def __init__(
        self,
        router_agent: RouterAgent,
        chat_agent: ChatAgent,
        task_agent: TaskAgent,
        memory_agent: MemoryAgent,
    ):
        self.router_agent = router_agent
        self.chat_agent = chat_agent
        self.task_agent = task_agent
        self.memory_agent = memory_agent

    def prepare(
        self,
        *,
        requested_route_mode: RouteMode,
        user_id: uuid.UUID,
        content: str,
        history: list[Message],
    ) -> AgentPlan:
        decision = self.resolve_route(requested_route_mode, content, history)
        memory_context = self.memory_agent.search(user_id, content)
        if decision.target is RouteMode.CHAT:
            messages = self.chat_agent.build_messages(content, history, memory_context)
            progress_events: list[StreamEvent] = []
        else:
            messages, progress_events = self.task_agent.build_messages(content, history, memory_context)
        return AgentPlan(
            route_mode=decision.target,
            router_decision=decision,
            memory_context=memory_context,
            messages=messages,
            progress_events=progress_events,
        )

    def resolve_route(
        self,
        requested_route_mode: RouteMode,
        content: str,
        history: list[Message],
    ) -> RouterDecision:
        if requested_route_mode is RouteMode.CHAT:
            return RouterDecision(RouteMode.CHAT, 1.0, "manual chat override")
        if requested_route_mode is RouteMode.AGENT:
            return RouterDecision(RouteMode.AGENT, 1.0, "manual agent override")
        continuation = self._detect_agent_continuation(content, history)
        if continuation is not None:
            return continuation
        return self.router_agent.route(content)

    def run_task(self, messages: list[dict], history: list[Message]) -> Iterator[StreamEvent | str]:
        yield from self.task_agent.run(messages, history)

    def _detect_agent_continuation(self, content: str, history: list[Message]) -> RouterDecision | None:
        text = content.strip()
        if not text or len(text) > 80:
            return None

        recent_agent_messages = [
            message for message in history
            if getattr(message, "route_mode", None) == RouteMode.AGENT.value
        ]
        if not recent_agent_messages:
            return None

        last_message = recent_agent_messages[-1]
        last_content = (getattr(last_message, "content", "") or "").strip()
        if getattr(last_message, "role", None) == "assistant" and (
            last_content.endswith("？") or last_content.endswith("?") or "哪里" in last_content or "哪个" in last_content
        ):
            return RouterDecision(RouteMode.AGENT, 0.93, "continue agent follow-up after assistant clarification")
        return None
