import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.context_manager import ContextManager
from app.events.bus import bus
from app.events.types import EventType
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageCreate, MessageRole, RouteMode
from app.services.character_service import CharacterService
from app.services.decision_service import DecisionService
from app.services.memory_service import MemoryService
from app.services.pipeline import ChatPipeline
from app.services.realtime_sync_service import realtime_sync_service
from app.services.roleplay_service import RoleplayService
from app.services.skill_service import SkillService
from app.services.sync_service import SyncService
from app.services.todo_service import TodoService
from app.skills.base import SkillError


@dataclass
class MessageStreamState:
    conversation: Conversation
    user_message: Message
    route_mode: RouteMode


class MessageService:
    def __init__(self, db: Session):
        self.db = db
        self.sync = SyncService(db)

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
        self._record_message_change(user.id, user_message)
        return MessageStreamState(conversation=conversation, user_message=user_message, route_mode=payload.route_mode)

    async def sse_event_stream(self, state: MessageStreamState, payload: MessageCreate):
        char_svc = CharacterService()
        roleplay_svc = RoleplayService()
        memory_svc = MemoryService(self.db, self.sync)
        todo_svc = TodoService(self.db, self.sync)
        pipeline = ChatPipeline(
            user_id=str(payload.user_id),
            character_service=char_svc,
            decision_service=DecisionService(),
            roleplay_service=roleplay_svc,
            skill_service=SkillService(memory_svc, todo_svc),
            memory_service=memory_svc,
        )

        subscriptions = [
            (EventType.ROLEPLAY_SPEAKING, bus.subscribe(EventType.ROLEPLAY_SPEAKING)),
            (EventType.ROLEPLAY_IDLE, bus.subscribe(EventType.ROLEPLAY_IDLE)),
            (EventType.SKILL_PROGRESS, bus.subscribe(EventType.SKILL_PROGRESS)),
            (EventType.SKILL_DONE, bus.subscribe(EventType.SKILL_DONE)),
            (EventType.SKILL_ERROR, bus.subscribe(EventType.SKILL_ERROR)),
        ]
        queues = [queue for _, queue in subscriptions]

        try:
            yield self._format_event(
                "conversation",
                {
                    "conversation_id": str(state.conversation.id),
                    "route_mode": state.route_mode.value,
                    "title": state.conversation.title,
                    "user_message": self._serialize_message(state.user_message),
                },
            )

            pipeline_task = asyncio.create_task(pipeline.process(state.user_message, state.route_mode))
            assistant_text = ""

            while not pipeline_task.done() or any(not queue.empty() for queue in queues):
                for queue in queues:
                    while not queue.empty():
                        event = queue.get_nowait()
                        event_type = event["type"]
                        event_payload = event["payload"]

                        if event_type == EventType.ROLEPLAY_SPEAKING:
                            text = event_payload.get("text", "")
                            assistant_text += text
                            for chunk in self.stream_chunks(text):
                                yield self._format_event("chunk", {"delta": chunk})
                                await asyncio.sleep(0.02)
                            yield self._format_event("emotion", {"emotion": event_payload.get("emotion", "neutral")})

                        elif event_type == EventType.SKILL_PROGRESS:
                            yield self._format_event(
                                "progress",
                                {
                                    "skill_name": event_payload["skill_name"],
                                    "message": event_payload["message"],
                                    "percent": event_payload["percent"],
                                },
                            )

                        elif event_type == EventType.SKILL_DONE:
                            card = char_svc.load_for_user(str(payload.user_id))
                            context = ContextManager(messages=[], character_card=card)
                            reply = await roleplay_svc.format_skill_result(
                                event_payload["skill_name"],
                                event_payload["result"],
                                context,
                                card.tone,
                            )
                            text = reply.get("text", "")
                            assistant_text += text
                            for chunk in self.stream_chunks(text):
                                yield self._format_event("chunk", {"delta": chunk})
                                await asyncio.sleep(0.02)
                            yield self._format_event("emotion", {"emotion": reply.get("emotion", "neutral")})

                        elif event_type == EventType.SKILL_ERROR:
                            card = char_svc.load_for_user(str(payload.user_id))
                            context = ContextManager(messages=[], character_card=card)
                            error = SkillError(event_payload["code"], event_payload["message"], event_payload["hint"])
                            reply = await roleplay_svc.format_skill_error(error, card.tone, context)
                            text = reply.get("text", "")
                            assistant_text += text
                            for chunk in self.stream_chunks(text):
                                yield self._format_event("chunk", {"delta": chunk})
                                await asyncio.sleep(0.02)
                            yield self._format_event("emotion", {"emotion": reply.get("emotion", "worried")})

                await asyncio.sleep(0.05)

            await pipeline_task

            if assistant_text:
                assistant_message = Message(
                    conversation_id=state.conversation.id,
                    role=MessageRole.ASSISTANT.value,
                    content=assistant_text,
                    route_mode=state.route_mode.value,
                )
                state.conversation.updated_at = datetime.utcnow()
                state.conversation.summary = self._build_summary(assistant_text)
                self.db.add(assistant_message)
                self.db.add(state.conversation)
                self.db.commit()
                self.db.refresh(state.conversation)
                self.db.refresh(assistant_message)
                self._record_message_change(state.conversation.user_id, assistant_message)
                yield self._format_event(
                    "done",
                    {
                        "conversation_id": str(state.conversation.id),
                        "assistant_message": self._serialize_message(assistant_message),
                    },
                )
        finally:
            for event_type, queue in subscriptions:
                bus.unsubscribe(event_type, queue)

    def stream_chunks(self, text: str) -> list[str]:
        normalized = text.strip()
        if len(normalized) <= 24:
            return [normalized]
        chunk_size = 18
        return [normalized[index : index + chunk_size] for index in range(0, len(normalized), chunk_size)]

    def _resolve_conversation(self, payload: MessageCreate) -> Conversation:
        if payload.conversation_id:
            conversation = (
                self.db.query(Conversation)
                .filter(Conversation.id == payload.conversation_id, Conversation.user_id == payload.user_id)
                .first()
            )
            if not conversation:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
            return conversation
        conversation = Conversation(user_id=payload.user_id, title=self._build_title(payload.content))
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def _record_message_change(self, user_id: UUID, message: Message) -> None:
        payload = self._serialize_message(message)
        self.sync.record_server_change(user_id, "messages", message.id, "upsert", payload, message.created_at)
        realtime_sync_service.publish_message(user_id, message)

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
