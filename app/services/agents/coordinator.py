from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Iterator

from app.models.message import Message
from app.schemas.message import RouteMode
from app.services.agents.chat_agent import ChatAgent
from app.services.agents.memory_agent import MemoryAgent
from app.services.agents.router_agent import RouterAgent, RouterDecision
from app.services.agents.task_agent import TaskAgent
from app.services.skill_service import Skill
from app.services.stream_events import StreamEvent
from app.services.user_emotion_service import UserEmotionService


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
        user_emotion_service: UserEmotionService | None = None,
    ):
        self.router_agent = router_agent
        self.chat_agent = chat_agent
        self.task_agent = task_agent
        self.memory_agent = memory_agent
        self.user_emotion_service = user_emotion_service

    def prepare(
        self,
        *,
        requested_route_mode: RouteMode,
        user_id: uuid.UUID,
        content: str,
        history: list[Message],
        user_skills: list[Skill] | None = None,
    ) -> AgentPlan:
        decision = self.resolve_route(requested_route_mode, content, history)
        memory_context = self.memory_agent.search(user_id, content)

        # Persona tone instructions — injected as dynamic context, NOT base_system
        persona_context = self._persona_tone_context(user_id)
        if persona_context:
            memory_context = [persona_context, *memory_context]

        # User emotion perception — temporary turn-level hint, NOT persisted
        if self.user_emotion_service is not None:
            emotion_context = self._user_emotion_context(content, history)
            if emotion_context:
                memory_context = [emotion_context, *memory_context]

        # Goal candidate detection — prompt to ask, never auto-create
        from app.services.goal_service import GoalService

        if GoalService.is_goal_candidate(content):
            memory_context = [GoalService.build_goal_candidate_prompt(content), *memory_context]

        # Recall detection: inject memory search results + honesty instruction
        if self.memory_agent.is_recall_question(content):
            recall_results = self.memory_agent.search_for_recall(user_id, content, top_k=5)
            if recall_results:
                memory_context = [self.memory_agent.build_recall_context(recall_results), *memory_context]
            else:
                memory_context = ["用户询问了之前的记忆，但未找到相关长期记忆。请诚实说明没有找到，不要编造。", *memory_context]

        if decision.target is RouteMode.CHAT:
            messages = self.chat_agent.build_messages(content, history, memory_context)
            progress_events: list[StreamEvent] = []
        else:
            if user_skills:
                messages, progress_events = self.task_agent.build_messages(
                    content,
                    history,
                    memory_context,
                    user_skills=user_skills,
                )
            else:
                messages, progress_events = self.task_agent.build_messages(
                    content, history, memory_context
                )
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

    def run_task(
        self,
        messages: list[dict],
        history: list[Message],
        *,
        user_skills: list[Skill] | None = None,
        ai_config: dict[str, Any] | None = None,
    ) -> Iterator[StreamEvent | str]:
        yield from self.task_agent.run(
            messages,
            history,
            user_skills=user_skills,
            ai_config=ai_config,
        )

    @staticmethod
    def _persona_tone_context(user_id: uuid.UUID) -> str:
        try:
            from app.db.session import SessionLocal
            from app.services.persona_settings_service import PersonaSettingsService

            db = SessionLocal()
            try:
                svc = PersonaSettingsService(db)
                settings = svc.get_settings(user_id)
                return svc.build_tone_instructions(settings)
            finally:
                db.close()
        except Exception:
            return ""

    def _user_emotion_context(self, content: str, history: list[Message]) -> str:
        recent = [
            m.content for m in history
            if getattr(m, "role", None) == "user"
        ][-5:]
        result = self.user_emotion_service.analyze(
            user_message=content,
            recent_user_messages=recent,
        )
        if result.should_adjust_reply and result.reply_style_hint:
            return f"【用户当前情绪回应提示】\n{result.reply_style_hint}"
        return ""

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
