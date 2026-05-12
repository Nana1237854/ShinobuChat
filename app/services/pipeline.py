from uuid import UUID

from app.core.config import settings
from app.core.context_manager import ContextManager
from app.core.state_machine import StateMachine, SystemState
from app.events.bus import bus
from app.events.types import EventType
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.decision import DecisionFrame, RouteDecision, SkillCall
from app.schemas.message import RouteMode
from app.services.character_service import CharacterService
from app.services.decision_service import DecisionService
from app.services.memory_service import MemoryService
from app.services.roleplay_service import RoleplayService
from app.services.skill_service import SkillService


class ChatPipeline:
    def __init__(
        self,
        user_id: str,
        character_service: CharacterService,
        decision_service: DecisionService,
        roleplay_service: RoleplayService,
        skill_service: SkillService,
        memory_service: MemoryService,
    ):
        self.user_id = user_id
        self.character_service = character_service
        self.decision_service = decision_service
        self.roleplay_service = roleplay_service
        self.skill_service = skill_service
        self.memory_service = memory_service
        self.state_machine = StateMachine()

    async def process(self, user_message: Message, route_mode: RouteMode) -> None:
        try:
            self.state_machine.transition(SystemState.DECIDING)
            await self.state_machine.debounce_deciding(settings.decision_debounce_ms)

            card = self.character_service.load_for_user(self.user_id)
            history = self._get_history()
            context = ContextManager(messages=history, character_card=card)

            force = None if route_mode == RouteMode.AUTO else route_mode.value
            decision = await self.decision_service.decide(user_message.content, context, force)
            await bus.publish(
                EventType.DECISION_MADE,
                {
                    "route": decision.route.value,
                    "skill_name": decision.skill_name,
                    "confidence": decision.confidence,
                    "reasoning": decision.reasoning,
                    "message_id": str(user_message.id),
                },
            )

            if decision.route == RouteDecision.CHAT or not decision.skill_name:
                await self._handle_chat(user_message.content, context, card.tone, card.system_prompt_extra)
            else:
                await self._handle_agent(decision)
        except Exception as error:
            await bus.publish(
                EventType.SKILL_ERROR,
                {
                    "skill_name": "pipeline",
                    "code": "PIPELINE_ERROR",
                    "message": str(error) or "Pipeline failed",
                    "hint": "Something went wrong on my end.",
                },
            )
        finally:
            self.state_machine.reset()

    def _get_history(self) -> list[Message]:
        try:
            user_uuid = UUID(self.user_id)
        except ValueError:
            return []
        return (
            self.memory_service.db.query(Message)
            .join(Conversation)
            .filter(Conversation.user_id == user_uuid)
            .order_by(Message.created_at.desc())
            .limit(30)
            .all()[::-1]
        )

    async def _handle_chat(self, content: str, context: ContextManager, tone, extra: str) -> None:
        self.state_machine.transition(SystemState.CHATTING)
        reply = await self.roleplay_service.generate_reply(content, context, tone, extra)
        self.state_machine.transition(SystemState.SPEAKING)
        await bus.publish(
            EventType.ROLEPLAY_SPEAKING,
            {
                "text": reply.get("text", ""),
                "emotion": reply.get("emotion", "neutral"),
            },
        )
        await bus.publish(EventType.ROLEPLAY_IDLE, {})

    async def _handle_agent(self, decision: DecisionFrame) -> None:
        self.state_machine.transition(SystemState.EXECUTING)
        skill_call = SkillCall(
            skill_name=decision.skill_name or "",
            skill_params=decision.skill_params or {},
            decision_frame=decision,
        )
        await self.skill_service.execute(skill_call)
