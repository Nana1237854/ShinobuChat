import json
import time
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.db_utils import require_user
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.message import MessageCreate, MessageRole, RouteMode
from app.services.realtime_sync_service import realtime_sync_service
from app.services.sync_service import SyncService


@dataclass
class MessageStreamState:
    conversation: Conversation
    user_message: Message
    route_mode: RouteMode
    reply_text: str


class ChatService:
    def __init__(self, db: Session, sync: SyncService):
        self.db = db
        self.sync = sync

    def create_conversation(
        self,
        user_id: UUID,
        title: str | None = None,
        summary: str | None = None,
    ) -> Conversation:
        conversation = Conversation(
            user_id=user_id,
            title=title or "New conversation",
            summary=summary,
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def list_conversations(self, user_id: UUID) -> list[Conversation]:
        require_user(self.db, user_id)
        return (
            self.db.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .all()
        )

    def get_messages(self, conversation_id: UUID, user_id: UUID) -> list[Message]:
        self._get_conversation_for_user(conversation_id, user_id)
        return (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .all()
        )

    def stream_reply(self, payload: MessageCreate):
        state = self._prepare_stream(payload)

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

            for chunk in self._stream_chunks(state.reply_text):
                yield self._format_event("chunk", {"delta": chunk})
                time.sleep(0.04)

            assistant_message = self._save_assistant_message(state)
            yield self._format_event(
                "done",
                {
                    "conversation_id": str(state.conversation.id),
                    "assistant_message": self._serialize_message(assistant_message),
                },
            )

        return event_stream()

    def _prepare_stream(self, payload: MessageCreate) -> MessageStreamState:
        require_user(self.db, payload.user_id)

        conversation = self._resolve_conversation(payload)
        user_message = Message(
            conversation_id=conversation.id,
            role=MessageRole.USER.value,
            content=payload.content.strip(),
            route_mode=payload.route_mode.value,
        )
        self.db.add(user_message)
        self._touch_conversation(conversation)
        if conversation.title == "New conversation":
            conversation.title = self._build_title(payload.content)
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        self.db.refresh(user_message)
        self._record_message_change(payload.user_id, user_message)

        history = self.get_messages(conversation.id, payload.user_id)
        reply_text = self._build_reply(payload.content.strip(), payload.route_mode, history[:-1])
        return MessageStreamState(
            conversation=conversation,
            user_message=user_message,
            route_mode=payload.route_mode,
            reply_text=reply_text,
        )

    def _resolve_conversation(self, payload: MessageCreate) -> Conversation:
        if payload.conversation_id:
            return self._get_conversation_for_user(payload.conversation_id, payload.user_id)
        return self.create_conversation(
            payload.user_id,
            title=self._build_title(payload.content),
        )

    def _get_conversation_for_user(self, conversation_id: UUID, user_id: UUID) -> Conversation:
        conversation = (
            self.db.query(Conversation)
            .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
            .first()
        )
        if not conversation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        return conversation

    def _stream_chunks(self, text: str) -> list[str]:
        normalized = text.strip()
        if len(normalized) <= 24:
            return [normalized]
        chunk_size = 18
        return [normalized[index : index + chunk_size] for index in range(0, len(normalized), chunk_size)]

    def _save_assistant_message(self, state: MessageStreamState) -> Message:
        assistant_message = Message(
            conversation_id=state.conversation.id,
            role=MessageRole.ASSISTANT.value,
            content=state.reply_text,
            route_mode=state.route_mode.value,
        )
        self._touch_conversation(state.conversation, summary=self._build_summary(state.reply_text))
        self.db.add(assistant_message)
        self.db.add(state.conversation)
        self.db.commit()
        self.db.refresh(state.conversation)
        self.db.refresh(assistant_message)
        self._record_message_change(state.conversation.user_id, assistant_message)
        return assistant_message

    def _touch_conversation(self, conversation: Conversation, *, summary: str | None = None) -> None:
        conversation.updated_at = datetime.utcnow()
        if summary is not None:
            conversation.summary = summary

    def _record_message_change(self, user_id: UUID, message: Message) -> None:
        self.sync.record_server_change(
            user_id,
            "messages",
            message.id,
            "upsert",
            self._serialize_message(message),
            message.created_at,
        )
        realtime_sync_service.publish_message(user_id, message)

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
