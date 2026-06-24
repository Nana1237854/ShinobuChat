from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.time import local_now
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageCreate, MessageRole
from app.services.agents.coordinator import AgentCoordinator
from app.services.conversation_service import ConversationService
from app.services.skill_manager import SkillManager
from app.services.turn.turn_state import MessageTurnState

logger = logging.getLogger(__name__)


class ConversationTurnService:
    def __init__(
        self,
        db: Session,
        conversations: ConversationService,
        agent_coordinator: AgentCoordinator | None = None,
        skill_manager: SkillManager | None = None,
    ):
        self.db = db
        self.conversations = conversations
        self.agent_coordinator = agent_coordinator
        self.skill_manager = skill_manager

    def prepare_turn(self, payload: MessageCreate, enable_quick_intent: bool = True) -> tuple[MessageTurnState, list[dict]]:
        user = self.db.query(User).filter(User.id == payload.user_id).first()
        if not user:
            raise NotFoundError("User not found")

        conversation = self._resolve_conversation(payload)
        history = self.conversations.list_messages(conversation.id, payload.user_id)
        user_skills = self._runtime_skills(payload.user_id)

        agent_plan = self._prepare_agent_plan(payload, history, user_skills, enable_quick_intent=enable_quick_intent)
        user_message = Message(
            conversation_id=conversation.id,
            role=MessageRole.USER.value,
            content=payload.content.strip(),
            route_mode=agent_plan.route_mode.value,
        )

        self.db.add(user_message)
        conversation.updated_at = local_now()

        if conversation.title == "New conversation":
            conversation.title = self._build_title(payload.content)

        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        self.db.refresh(user_message)

        # ── Phase 2: PromptTrace ──
        try:
            from app.domains.observability.prompt_trace_service import PromptTraceService

            trace_ctx = getattr(agent_plan, "trace_context", {}) or {}
            PromptTraceService(self.db).create_trace(
                user_id=payload.user_id,
                conversation_id=conversation.id,
                message_id=user_message.id,
                route_mode=agent_plan.route_mode.value,
                conversation_mode=agent_plan.conversation_mode,
                router_reason=agent_plan.router_decision.reason,
                memory_ids=trace_ctx.get("memory_ids", []),
                activated_skill_names=trace_ctx.get("activated_skill_names", []),
                vision_context_used=trace_ctx.get("vision_context_used", False),
                persona_context_used=trace_ctx.get("persona_context_used", False),
                emotion_context_used=trace_ctx.get("emotion_context_used", False),
                browser_context_used=trace_ctx.get("browser_context_used", False),
                mcp_context_used=trace_ctx.get("mcp_context_used", False),
                context_summary=trace_ctx.get("context_summary", {}),
            )
        except Exception:
            logger.warning("PromptTrace creation failed", exc_info=True)

        state = MessageTurnState(
            conversation=conversation,
            user_message=user_message,
            route_mode=agent_plan.route_mode,
            router_reason=agent_plan.router_decision.reason,
            progress_events=agent_plan.progress_events,
            conversation_mode=agent_plan.conversation_mode,
            direct_action=getattr(agent_plan, "direct_action", None),
        )

        return state, agent_plan.messages

    def save_assistant_sentences(self, state: MessageTurnState, sentences: list[str]) -> list[Message]:
        messages: list[Message] = []

        for sentence in sentences:
            msg = Message(
                conversation_id=state.conversation.id,
                role=MessageRole.ASSISTANT.value,
                content=sentence,
                route_mode=state.route_mode.value,
            )
            self.db.add(msg)
            messages.append(msg)

        state.conversation.updated_at = local_now()
        state.conversation.summary = self._build_summary(state.reply_text)
        self.db.add(state.conversation)
        self.db.commit()

        for msg in messages:
            self.db.refresh(msg)

        self.db.refresh(state.conversation)
        return messages

    def _runtime_skills(self, user_id: UUID):
        if self.skill_manager is None:
            return []
        return self.skill_manager.runtime_skills(user_id)

    def _prepare_agent_plan(self, payload: MessageCreate, history: list[Message], user_skills, enable_quick_intent: bool = True):
        if self.agent_coordinator is not None:
            return self.agent_coordinator.prepare(
                requested_route_mode=payload.route_mode,
                user_id=payload.user_id,
                content=payload.content.strip(),
                history=history,
                user_skills=user_skills,
                vision_context=payload.vision_context,
                enable_quick_intent=enable_quick_intent,
                conversation_id=payload.conversation_id,
            )

        from types import SimpleNamespace

        from app.services.ai_client import AIClient

        messages = self._build_ai_messages(payload.content.strip(), payload.route_mode, history)
        return SimpleNamespace(
            route_mode=payload.route_mode,
            router_decision=SimpleNamespace(reason="legacy message service routing"),
            progress_events=[],
            messages=messages,
            conversation_mode="companion",
            direct_action=None,
        )

    def _build_ai_messages(self, content: str, route_mode, history: list[Message]) -> list[dict]:
        if route_mode.value == "chat":
            mode_instruction = "当前是纯聊天模式，优先自然陪伴、澄清想法，用 1-3 句话简短回复。"
        elif route_mode.value == "agent":
            mode_instruction = "当前是 Agent 模式，优先把用户意图整理成可执行动作，并明确下一步。"
        else:
            mode_instruction = "当前是自动决策模式，先自然回应，再判断是否需要推进成任务流。"

        messages: list[dict] = [{
            "role": MessageRole.SYSTEM.value,
            "content": (
                f"你是 ShinobuChat 的 AI 伙伴。用简洁、温暖、可靠的中文回复用户。{mode_instruction}"
                "\n\n【重要】你的每条回复开头必须包含一个情绪标签，格式为 [emotion]。"
                "可选情绪：happy、sad、angry、surprised、thinking、neutral。"
                "根据你的回复内容选择最匹配的情绪。标签放在回复的最开头，后面接正文。"
                "不要输出 JSON，不要解释标签，不要省略标签。"
                "\n示例：[happy]今天天气真好！\n[sad]抱歉让你失望了..."
            ),
        }]
        for msg in history[-12:]:
            if msg.role in {MessageRole.USER.value, MessageRole.ASSISTANT.value}:
                messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": MessageRole.USER.value, "content": content})
        return messages

    def _resolve_conversation(self, payload: MessageCreate) -> Conversation:
        if payload.conversation_id:
            return self.conversations.get_for_user(payload.conversation_id, payload.user_id)
        return self.conversations.create_for_user(
            payload.user_id,
            title=self._build_title(payload.content),
        )

    @staticmethod
    def _build_title(content: str) -> str:
        flattened = " ".join(content.strip().split())
        return flattened[:36] if flattened else "New conversation"

    @staticmethod
    def _build_summary(content: str) -> str:
        flattened = " ".join(content.strip().split())
        return flattened[:140] if flattened else ""
