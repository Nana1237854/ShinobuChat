import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import UpstreamServiceError


def _friendly_ai_error_hint(message: str) -> str:
    lower = message.lower()

    if "insufficient balance" in lower or "payment required" in lower or "402" in lower:
        return "当前 AI 服务余额不足，暂时无法生成回复。请检查模型服务余额或更换可用 API Key。"

    if "unauthorized" in lower or "invalid api key" in lower or "401" in lower:
        return "当前 AI API Key 无效，请检查模型与服务配置。"

    if "rate limit" in lower or "429" in lower:
        return "当前 AI 服务请求过于频繁，请稍后再试。"

    return "AI 服务暂时不可用，请稍后再试。"
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.message import MessageCreate, MessageRole, RouteMode
from app.services.agent_service import AgentService
from app.services.agents import AgentCoordinator, MemoryAgent
from app.services.ai_client import AIClient
from app.services.config_service import ConfigService
from app.services.conversation_service import ConversationService
from app.services.emotion_parser import parse_emotion_tag, resolve_emotion
from app.services.skill_manager import SkillManager
from app.services.skill_service import SkillRegistry
from app.services.stream_events import SseEncoder, StreamEvent
from app.services.turn.conversation_turn_service import ConversationTurnService
from app.services.turn.action_reply_generation_service import ActionReplyGenerationService
from app.services.turn.direct_action_runner import DirectActionRunner
from app.services.turn.memory_write_scheduler import MemoryWriteScheduler
from app.services.turn.reply_generation_service import ReplyGenerationService
from app.services.turn.stream_event_service import StreamEventService
from app.services.turn.turn_state import MessageTurnState
from app.services.turn.voice_reply_service import VoiceReplyService
from app.services.voice_service import VoiceService

# Legacy alias — keep backward compatibility
MessageStreamState = MessageTurnState


class MessageService:
    def __init__(
        self,
        db: Session,
        skill_registry: SkillRegistry,
        agent: AgentService,
        agent_orchestrator,  # AgentOrchestrator — kept for legacy run_task path
        ai_client: AIClient,
        sse: SseEncoder,
        voice_service: VoiceService | None = None,
        agent_coordinator: AgentCoordinator | None = None,
        memory_agent: MemoryAgent | None = None,
        config_service: ConfigService | None = None,
        skill_manager: SkillManager | None = None,
        memory_service=None,
        diary_service=None,
    ):
        self.db = db
        self.conversations = ConversationService(db)
        self.skill_registry = skill_registry
        self.agent = agent
        self.agent_orchestrator = agent_orchestrator
        self.ai_client = ai_client
        self.sse = sse
        self.voice_service = voice_service
        self.agent_coordinator = agent_coordinator
        self.memory_agent = memory_agent
        self.config_service = config_service
        self.skill_manager = skill_manager

        # Turn services
        self.turn_service = ConversationTurnService(
            db=db,
            conversations=self.conversations,
            agent_coordinator=agent_coordinator,
            skill_manager=skill_manager,
        )
        self.event_service = StreamEventService(sse)
        self.reply_generation_service = ReplyGenerationService(
            ai_client=ai_client,
            agent_coordinator=agent_coordinator,
            skill_manager=skill_manager,
        )
        self.direct_action_runner = DirectActionRunner()
        self.voice_reply_service = VoiceReplyService(voice_service, sse)
        self.memory_write_scheduler = MemoryWriteScheduler(memory_agent)
        self.action_reply_generation_service = ActionReplyGenerationService(
            ai_client=ai_client,
            config_service=config_service,
            memory_service=memory_service,
            diary_service=diary_service,
        )

    async def create_streaming_response(self, payload: MessageCreate):
        state, messages = await asyncio.to_thread(self.turn_service.prepare_turn, payload)

        ai_config = self._resolve_ai_config(payload.user_id)
        max_tokens = self._resolve_max_tokens(ai_config)

        yield self.event_service.format(
            self.event_service.conversation_started(
                state,
                self.event_service.serialize_message(state.user_message, emotion="neutral"),
            )
        )

        try:
            # ── Direct action path (F12) ──
            if state.direct_action is not None:
                async for event in self._handle_direct_action(payload.user_id, state):
                    yield self.event_service.format(event)
                return

            history = await asyncio.to_thread(
                self.conversations.list_messages,
                state.conversation.id,
                payload.user_id,
            )

            full_reply = ""
            agent_pending_action = None
            for item in self.reply_generation_service.generate(
                state=state,
                messages=messages,
                history=history[:-1],
                user_id=payload.user_id,
                ai_config=ai_config,
                max_tokens=max_tokens,
            ):
                if isinstance(item, StreamEvent):
                    if item.event == "pending_action" and item.payload:
                        agent_pending_action = item.payload
                    yield self.event_service.format(item)
                else:
                    full_reply = item

            if not full_reply:
                raise UpstreamServiceError("AI API returned an empty response")

            parsed_emotion, display_text = parse_emotion_tag(full_reply)
            assistant_emotion = resolve_emotion(parsed_emotion)
            state.reply_text = display_text

            yield self.event_service.format(
                self.event_service.emotion(assistant_emotion)
            )

            async for event in self.voice_reply_service.stream_reply(
                text=display_text,
                emotion=assistant_emotion,
                context_content=payload.content,
            ):
                yield self.event_service.format(event)

            sentences = self.voice_reply_service.split_for_voice(display_text)

            assistant_messages = await asyncio.to_thread(
                self.turn_service.save_assistant_sentences,
                state,
                sentences,
            )

            yield self.event_service.format(
                self.event_service.done(state, assistant_messages, assistant_emotion,
                                        pending_action=agent_pending_action)
            )

            self.memory_write_scheduler.schedule_after_turn(payload, state)

        except UpstreamServiceError as exc:
            logger.warning("AI upstream failed during streaming response", exc_info=True)
            yield self.event_service.format(
                self.event_service.error(
                    code="ai_upstream_error",
                    hint=_friendly_ai_error_hint(str(exc)),
                )
            )

        except Exception as exc:
            logger.exception("Unexpected error during streaming response")
            yield self.event_service.format(
                self.event_service.error(
                    code="stream_error",
                    hint="回复生成时出了点问题，请稍后再试。",
                )
            )

    # ------------------------------------------------------------------
    # Direct action path
    # ------------------------------------------------------------------

    async def _handle_direct_action(self, user_id, state: MessageTurnState):
        result = await asyncio.to_thread(
            self.direct_action_runner.run,
            user_id,
            state,
        )

        yield self.event_service.action(result.action_result, state.direct_action)

        if result.pending_info:
            yield self.event_service.pending_action(result.pending_info)

        # Generate companion-style reply via LLM, fall back to template on error
        raw_reply = result.assistant_reply
        display_reply = await asyncio.to_thread(
            self.action_reply_generation_service.generate,
            user_id=user_id,
            user_text=state.user_message.content or "",
            status=result.action_result.get("status", "failed"),
            action_type=getattr(state.direct_action, "action", "open_local_app"),
            intent_type=getattr(state.direct_action, "intent_type", None),
            app_key=result.action_result.get("app_key"),
            display_name=result.action_result.get("display_name"),
            result_message=result.action_result.get("message"),
            conversation_mode=getattr(state, "conversation_mode", "companion"),
            selected_by=result.action_result.get("selected_by"),
            selection_message=result.action_result.get("selection_message"),
            candidates=result.action_result.get("candidates"),
            requires_confirmation=result.action_result.get("status") == "requires_confirmation",
            error_detail=result.action_result.get("error_detail"),
        )
        full_reply = display_reply or raw_reply
        parsed_emotion, display_text = parse_emotion_tag(full_reply)
        assistant_emotion = resolve_emotion(parsed_emotion)
        state.reply_text = display_text

        yield self.event_service.emotion(assistant_emotion)

        async for event in self.voice_reply_service.stream_reply(
            text=display_text,
            emotion=assistant_emotion,
            context_content="",
        ):
            yield event

        sentences = self.voice_reply_service.split_for_voice(display_text)

        assistant_messages = await asyncio.to_thread(
            self.turn_service.save_assistant_sentences,
            state,
            sentences,
        )

        done_payload = self.event_service.done(
            state, assistant_messages, assistant_emotion,
            pending_action=result.pending_info,
        )
        yield done_payload

        self.memory_write_scheduler.schedule_after_turn_text(
            user_id=user_id,
            user_text=state.user_message.content,
            state=state,
        )

    # ------------------------------------------------------------------
    # Legacy methods — preserved for backward compatibility
    # ------------------------------------------------------------------

    def prepare_stream(self, payload: MessageCreate):
        """Legacy entry point. Delegates to ConversationTurnService."""
        state, messages = self.turn_service.prepare_turn(payload)
        return state, messages

    def save_sentences(self, state: MessageTurnState, sentences: list[str]) -> list[Message]:
        """Legacy entry point. Delegates to ConversationTurnService."""
        return self.turn_service.save_assistant_sentences(state, sentences)

    def _build_ai_messages(self, content: str, route_mode: RouteMode, history: list[Message]) -> list[dict[str, str]]:
        """Legacy entry point. Delegates to ConversationTurnService."""
        return self.turn_service._build_ai_messages(content, route_mode, history)

    def _prepare_agent_plan(self, payload: MessageCreate, history: list[Message]):
        """Legacy entry point. Delegates to ConversationTurnService."""
        from types import SimpleNamespace

        from app.services.skill_service import Skill

        user_skills = (
            self.skill_manager.runtime_skills(payload.user_id)
            if self.skill_manager is not None
            else []
        )
        if self.agent_coordinator is not None:
            return self.agent_coordinator.prepare(
                requested_route_mode=payload.route_mode,
                user_id=payload.user_id,
                content=payload.content.strip(),
                history=history,
                user_skills=user_skills,
                vision_context=payload.vision_context,
            )

        messages = self._build_ai_messages(payload.content.strip(), payload.route_mode, history)
        return SimpleNamespace(
            route_mode=payload.route_mode,
            router_decision=SimpleNamespace(reason="legacy message service routing"),
            progress_events=[],
            messages=messages,
            conversation_mode="companion",
            direct_action=None,
        )

    def _run_task_agent(
        self,
        messages: list[dict],
        history: list[Message],
        user_id,
        ai_config,
        conversation_mode: str = "companion",
        conversation_id=None,
    ):
        """Legacy agent loop entry point."""
        user_skills = (
            self.skill_manager.runtime_skills(user_id)
            if self.skill_manager is not None
            else []
        )
        if self.agent_coordinator is not None:
            yield from self.agent_coordinator.run_task(
                messages,
                history,
                user_skills=user_skills,
                ai_config=ai_config,
                conversation_mode=conversation_mode,
                route_mode="agent",
                user_id=user_id,
                conversation_id=conversation_id,
            )
            return

        activated_skills = self.skill_registry.match(messages[-1].get("content", ""))
        if activated_skills:
            yield StreamEvent("progress", {
                "skill_name": ",".join(skill.name for skill in activated_skills),
                "message": "Loaded SKILL.md",
                "percent": 0.15,
            })
        agent_messages = self.agent.build_messages(
            messages[-1].get("content", ""),
            history,
            activated_skills,
            user_skills=user_skills,
            tool_catalog=self.agent_orchestrator.tool_registry.render_catalog(),
        )
        yield from self.agent_orchestrator.run(
            agent_messages,
            history,
            user_skills=user_skills,
            ai_config=ai_config,
            user_id=user_id,
            conversation_id=conversation_id,
        )

    def _schedule_memory_write(self, payload: MessageCreate, state: MessageTurnState) -> None:
        self.memory_write_scheduler.schedule_after_turn(payload, state)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_ai_config(self, user_id) -> dict | None:
        if self.config_service is not None:
            return self.config_service.resolve_runtime(user_id)
        return None

    def _resolve_max_tokens(self, ai_config: dict | None) -> int:
        return int(
            (ai_config or {}).get(
                "ai_lightweight_max_tokens", settings.ai_lightweight_max_tokens
            )
        )

    def _resolve_conversation(self, payload: MessageCreate) -> Conversation:
        if payload.conversation_id:
            return self.conversations.get_for_user(payload.conversation_id, payload.user_id)
        return self.conversations.create_for_user(
            payload.user_id, title=self._build_title(payload.content),
        )

    @staticmethod
    def _build_title(content: str) -> str:
        flattened = " ".join(content.strip().split())
        return flattened[:36] if flattened else "New conversation"

    @staticmethod
    def _build_summary(content: str) -> str:
        flattened = " ".join(content.strip().split())
        return flattened[:140] if flattened else ""

    def _serialize_message(self, message: Message, emotion: str | None = None) -> dict[str, str]:
        return {
            "id": str(message.id),
            "conversation_id": str(message.conversation_id),
            "role": message.role,
            "content": message.content,
            "route_mode": message.route_mode,
            "emotion": emotion,
            "created_at": message.created_at.isoformat(),
        }

    def _format_event(self, event: StreamEvent) -> str:
        return self.sse.encode(event)
