import json
import time
from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageCreate, MessageRole, RouteMode
from app.services.conversation_service import ConversationService
from app.services.realtime_sync_service import realtime_sync_service
from app.services.sync_service import SyncService


@dataclass
class MessageStreamState:
    conversation: Conversation
    user_message: Message
    route_mode: RouteMode
    reply_text: str


class MessageService:
    def __init__(self, db: Session):
        self.db = db
        self.conversations = ConversationService(db)

    def prepare_stream(self, payload: MessageCreate) -> MessageStreamState:
        user = self.db.query(User).filter(User.id == payload.user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

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
        SyncService(self.db).record_server_change(
            user.id,
            "messages",
            user_message.id,
            "upsert",
            self._serialize_message(user_message),
            user_message.created_at,
        )
        realtime_sync_service.publish_message(user.id, user_message)

        history = self.conversations.list_messages(conversation.id, payload.user_id)
        reply_text = self._build_reply(payload.content.strip(), payload.route_mode, history[:-1])
        return MessageStreamState(
            conversation=conversation,
            user_message=user_message,
            route_mode=payload.route_mode,
            reply_text=reply_text,
        )

    def stream_chunks(self, text: str) -> list[str]:
        normalized = text.strip()
        if len(normalized) <= 24:
            return [normalized]
        chunk_size = 18
        return [normalized[index : index + chunk_size] for index in range(0, len(normalized), chunk_size)]

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
        SyncService(self.db).record_server_change(
            state.conversation.user_id,
            "messages",
            assistant_message.id,
            "upsert",
            self._serialize_message(assistant_message),
            assistant_message.created_at,
        )
        realtime_sync_service.publish_message(state.conversation.user_id, assistant_message)
        return assistant_message

    def create_streaming_response(self, payload: MessageCreate):
        state = self.prepare_stream(payload)

        def event_stream():
            yield self._format_event(
                "conversation",
                {
                    "conversation_id": str(state.conversation.id),
                    "route_mode": state.route_mode.value,
                    "title": state.conversation.title,
                    "user_message": self._serialize_message(state.user_message),
                },
            )

            for chunk in self.stream_chunks(state.reply_text):
                yield self._format_event("chunk", {"delta": chunk})
                time.sleep(0.04)

            assistant_message = self.save_assistant_message(state)
            yield self._format_event(
                "done",
                {
                    "conversation_id": str(state.conversation.id),
                    "assistant_message": self._serialize_message(assistant_message),
                },
            )

        return event_stream()

    def _resolve_conversation(self, payload: MessageCreate) -> Conversation:
        if payload.conversation_id:
            return self.conversations.get_for_user(payload.conversation_id, payload.user_id)
        return self.conversations.create_for_user(
            payload.user_id,
            title=self._build_title(payload.content),
        )

    def _build_reply(self, content: str, route_mode: RouteMode, history: list[Message]) -> str:
        history_prefix = "这是这段对话的第一轮，" if not history else f"我接着前面 {len(history)} 条上下文继续，"
        if route_mode is RouteMode.CHAT:
            mode_prefix = "现在是纯聊天模式，我先陪你把想法说清楚。"
        elif route_mode is RouteMode.AGENT:
            mode_prefix = "现在按 Agent 模式处理，我先把它整理成可执行动作。"
        else:
            mode_prefix = "现在是自动决策模式，我会先接住消息，再判断是否需要升级成任务流。"

        focus = content.replace("\r", " ").replace("\n", " ").strip()
        if len(focus) > 80:
            focus = f"{focus[:77]}..."

        return (
            f"{mode_prefix}{history_prefix}"
            f"你刚刚提到“{focus}”。"
            " 我建议下一步继续补充目标、约束和时间点，这样我们就能稳定地走成单轮确认或多轮推进。"
        )

    def _build_title(self, content: str) -> str:
        flattened = " ".join(content.strip().split())
        if not flattened:
            return "New conversation"
        return flattened[:36]

    def _build_summary(self, content: str) -> str:
        flattened = " ".join(content.strip().split())
        return flattened[:140] if flattened else ""

    def _serialize_message(self, message: Message) -> dict[str, str]:
        return {
            "id": str(message.id),
            "conversation_id": str(message.conversation_id),
            "role": message.role,
            "content": message.content,
            "route_mode": message.route_mode,
            "created_at": message.created_at.isoformat(),
        }

    def _format_event(self, event: str, payload: dict[str, object]) -> str:
        data = json.dumps(payload, ensure_ascii=False)
        return f"event: {event}\ndata: {data}\n\n"
