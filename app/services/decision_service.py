import json

from app.core.config import settings
from app.core.context_manager import ContextManager
from app.schemas.decision import DecisionFrame, RouteDecision
from app.schemas.message import RouteMode
from app.schemas.mode import ConversationMode
from app.skills.registry import SkillRegistry

# Mode-aware routing instruction templates
DECISION_MODE_INSTRUCTIONS: dict[str, str] = {
    "companion": (
        "Mode hint: conversation mode. Default to chat unless the user explicitly requests a task. "
        "Prefer natural, warm interaction over tool use."
    ),
    "work": (
        "Mode hint: work mode. Raise confidence for task-oriented intents (todo_create, planning, "
        "search, summarize). When a user describes anything actionable, prefer agent routing."
    ),
    "focus": (
        "Mode hint: focus mode. Avoid routing idle chat to agent. "
        "Only route when the user clearly requests a task. Conversational messages -> chat."
    ),
    "night": (
        "Mode hint: night mode. Keep interaction quiet. Route chat by default. "
        "Only trigger agent for urgent or explicitly requested tasks. Prefer shorter, gentler routing."
    ),
}


class DecisionService:
    async def decide(
        self,
        user_message: str,
        context: ContextManager,
        force_route: str | None = None,
        mode: str = "companion",
    ) -> DecisionFrame:
        if force_route == RouteMode.CHAT.value:
            return DecisionFrame(route=RouteDecision.CHAT, reasoning="Route forced by user.", confidence=1.0)
        if force_route == RouteMode.AGENT.value and not SkillRegistry.list_skills():
            return DecisionFrame(
                route=RouteDecision.CHAT,
                reasoning="Agent route requested, but no skills are available.",
                confidence=0.5,
            )

        if not settings.effective_decision_api_key:
            return self._fallback_decision(user_message, force_route, mode)

        try:
            from openai import AsyncOpenAI
        except ModuleNotFoundError:
            return self._fallback_decision(user_message, force_route, mode)

        client = AsyncOpenAI(
            api_key=settings.effective_decision_api_key,
            base_url=settings.decision_llm_base_url or settings.llm_base_url,
        )
        mode_instruction = DECISION_MODE_INSTRUCTIONS.get(mode, DECISION_MODE_INSTRUCTIONS["companion"])
        messages = [
            {
                "role": "system",
                "content": context.decision_system_prompt(
                    SkillRegistry.describe_for_llm(), mode_instruction
                ),
            },
            *context.decision_slice(),
            {"role": "user", "content": user_message},
        ]
        try:
            response = await client.chat.completions.create(
                model=settings.decision_llm_model,
                messages=messages,
                temperature=settings.decision_llm_temperature,
                max_tokens=settings.decision_llm_max_tokens,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            decision = DecisionFrame.model_validate(json.loads(content))
        except Exception:
            return self._fallback_decision(user_message, force_route, mode)

        if decision.confidence < 0.6 or not decision.skill_name:
            return DecisionFrame(
                route=RouteDecision.CHAT,
                skill_name=None,
                skill_params=None,
                reasoning=decision.reasoning,
                confidence=decision.confidence,
            )
        if not SkillRegistry.get(decision.skill_name):
            return DecisionFrame(route=RouteDecision.CHAT, reasoning="Selected skill is unavailable.", confidence=0.5)
        return decision

    def _fallback_decision(
        self, user_message: str, force_route: str | None, mode: str = "companion"
    ) -> DecisionFrame:
        if force_route == RouteMode.AGENT.value and SkillRegistry.list_skills():
            return DecisionFrame(route=RouteDecision.AGENT, reasoning="Agent route forced by user.", confidence=1.0)
        del user_message

        # Mode-aware fallback reasoning
        mode_reason: dict[str, str] = {
            "work": "LLM unavailable; work mode defaults to agent for task routing.",
            "focus": "LLM unavailable; focus mode suppresses chat fallback.",
            "night": "LLM unavailable; night mode defaults to quiet chat.",
        }
        reason = mode_reason.get(mode, "LLM unavailable; using chat fallback.")
        return DecisionFrame(route=RouteDecision.CHAT, reasoning=reason, confidence=0.5)
