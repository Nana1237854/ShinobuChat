from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError, UpstreamServiceError
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageCreate, MessageRole, RouteMode
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.agent_service import AgentService
from app.services.ai_client import AIClient
from app.services.conversation_service import ConversationService
from app.services.emotion_service import EmotionService
from app.services.skill_service import SkillRegistry
from app.services.stream_events import SseEncoder, StreamEvent


@dataclass
class MessageStreamState:
    conversation: Conversation
    user_message: Message
    route_mode: RouteMode
    reply_text: str


class MessageService:
    def __init__(
        self,
        db: Session,
        skill_registry: SkillRegistry,
        agent: AgentService,
        agent_orchestrator: AgentOrchestrator,
        ai_client: AIClient,
        sse: SseEncoder,
    ):
        self.db = db
        self.conversations = ConversationService(db)
        self.skill_registry = skill_registry
        self.agent = agent
        self.agent_orchestrator = agent_orchestrator
        self.ai_client = ai_client
        self.emotions = EmotionService()
        self.sse = sse

    def prepare_stream(self, payload: MessageCreate) -> tuple[MessageStreamState, list[dict[str, str]]]:
        user = self.db.query(User).filter(User.id == payload.user_id).first()
        if not user:
            raise NotFoundError("User not found")

        conversation = self._resolve_conversation(payload)
        user_message = Message(
            conversation_id=conversation.id,
            role=MessageRole.USER.value,
            content=payload.content.strip(),
            route_mode=payload.route_mode.value,
        )
        self.db.add(user_message)
        conversation.updated_at = datetime.utcnow()
        if conversation.title == "New conversation":
            conversation.title = self._build_title(payload.content)
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        self.db.refresh(user_message)

        history = self.conversations.list_messages(conversation.id, payload.user_id)
        messages = self._build_ai_messages(payload.content.strip(), payload.route_mode, history[:-1])

        state = MessageStreamState(
            conversation=conversation,
            user_message=user_message,
            route_mode=payload.route_mode,
            reply_text="",
        )
        return state, messages

    def save_assistant_message(self, state: MessageStreamState) -> Message:
        assistant_message = Message(
            conversation_id=state.conversation.id,
            role=MessageRole.ASSISTANT.value,
            content=state.reply_text,
            route_mode=state.route_mode.value,
        )
        state.conversation.updated_at = datetime.utcnow()
        state.conversation.summary = self._build_summary(state.reply_text)
        self.db.add(assistant_message)
        self.db.add(state.conversation)
        self.db.commit()
        self.db.refresh(state.conversation)
        self.db.refresh(assistant_message)
        return assistant_message

    def create_streaming_response(self, payload: MessageCreate):
        state, messages = self.prepare_stream(payload)
        max_tokens = settings.ai_lightweight_max_tokens

        def event_stream():
            yield self._format_event(
                StreamEvent(
                    "conversation",
                    {
                        "conversation_id": str(state.conversation.id),
                        "route_mode": state.route_mode.value,
                        "title": state.conversation.title,
                        "user_message": self._serialize_message(
                            state.user_message,
                            emotion=self.emotions.detect(state.user_message.content),
                        ),
                    },
                )
            )

            history = self.conversations.list_messages(state.conversation.id, payload.user_id)
            full_reply = ""
            if state.route_mode is RouteMode.CHAT:
                for chunk in self.ai_client.stream_chat(messages, max_tokens=max_tokens):
                    full_reply += chunk
                    yield self._format_event(StreamEvent("chunk", {"delta": chunk}))
            else:
                activated_skills = self.skill_registry.match(payload.content)
                if activated_skills:
                    yield self._format_event(
                        StreamEvent(
                            "progress",
                            {
                                "skill_name": ",".join(skill.name for skill in activated_skills),
                                "message": "Loaded SKILL.md",
                                "percent": 0.15,
                            },
                        )
                    )
                agent_messages = self.agent.build_messages(payload.content.strip(), history[:-1], activated_skills)
                for item in self.agent_orchestrator.run(agent_messages, history[:-1]):
                    if isinstance(item, StreamEvent):
                        yield self._format_event(item)
                    else:
                        full_reply = item

            if not full_reply:
                raise UpstreamServiceError("AI API returned an empty response")

            state.reply_text = full_reply
            assistant_emotion = self.emotions.detect(full_reply, [payload.content])
            yield self._format_event(StreamEvent("emotion", {"emotion": assistant_emotion}))
            assistant_message = self.save_assistant_message(state)
            yield self._format_event(
                StreamEvent(
                    "done",
                    {
                        "conversation_id": str(state.conversation.id),
                        "assistant_message": self._serialize_message(
                            assistant_message,
                            emotion=assistant_emotion,
                        ),
                    },
                )
            )

        return event_stream()

    def _build_ai_messages(
        self,
        content: str,
        route_mode: RouteMode,
        history: list[Message],
    ) -> list[dict[str, str]]:
        if route_mode is RouteMode.CHAT:
            mode_instruction = "当前是纯聊天模式，优先自然陪伴、澄清想法，用 1-3 句话简短回复。"
        elif route_mode is RouteMode.AGENT:
            mode_instruction = "当前是 Agent 模式，优先把用户意图整理成可执行动作，并明确下一步。"
        else:
            mode_instruction = "当前是自动决策模式，先自然回应，再判断是否需要推进成任务流。"

        messages: list[dict[str, str]] = [
            {
                "role": MessageRole.SYSTEM.value,
                "content": (
                    "你是 ShinobuChat 的 AI 伙伴。用简洁、温暖、可靠的中文回复用户。"
                    f"{mode_instruction}"
                ),
            }
        ]
        for message in history[-12:]:
            if message.role in {MessageRole.USER.value, MessageRole.ASSISTANT.value}:
                messages.append({"role": message.role, "content": message.content})
        messages.append({"role": MessageRole.USER.value, "content": content})
        return messages

    def _resolve_conversation(self, payload: MessageCreate) -> Conversation:
        if payload.conversation_id:
            return self.conversations.get_for_user(payload.conversation_id, payload.user_id)
        return self.conversations.create_for_user(
            payload.user_id,
            title=self._build_title(payload.content),
        )

    def _build_title(self, content: str) -> str:
        flattened = " ".join(content.strip().split())
        if not flattened:
            return "New conversation"
        return flattened[:36]

    def _build_summary(self, content: str) -> str:
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
