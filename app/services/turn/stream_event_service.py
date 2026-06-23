from __future__ import annotations

from app.models.message import Message
from app.services.stream_events import SseEncoder, StreamEvent
from app.services.turn.turn_state import MessageTurnState


class StreamEventService:
    def __init__(self, sse: SseEncoder):
        self.sse = sse

    def format(self, event: StreamEvent) -> str:
        return self.sse.encode(event)

    @staticmethod
    def conversation_started(state: MessageTurnState, user_message: dict) -> StreamEvent:
        return StreamEvent("conversation", {
            "conversation_id": str(state.conversation.id),
            "route_mode": state.route_mode.value,
            "title": state.conversation.title,
            "user_message": user_message,
        })

    @staticmethod
    def emotion(emotion: str) -> StreamEvent:
        return StreamEvent("emotion", {"emotion": emotion})

    @staticmethod
    def chunk(delta: str) -> StreamEvent:
        return StreamEvent("chunk", {"delta": delta})

    @staticmethod
    def progress(skill_name: str, message: str, percent: float, state: str | None = None) -> StreamEvent:
        payload: dict = {
            "skill_name": skill_name,
            "message": message,
            "percent": percent,
        }
        if state:
            payload["state"] = state
        return StreamEvent("progress", payload)

    @staticmethod
    def action(action_result: dict, direct_action) -> StreamEvent:
        if direct_action is None:
            return StreamEvent("action", action_result)
        return StreamEvent("action", {
            "action": direct_action.action,
            "intent_type": direct_action.intent_type,
            "status": action_result.get("status", "unknown"),
            "message": action_result.get("message", ""),
            "app_key": action_result.get("app_key"),
            "display_name": action_result.get("display_name"),
        })

    @staticmethod
    def pending_action(payload: dict) -> StreamEvent:
        return StreamEvent("pending_action", payload)

    @staticmethod
    def error(code: str, hint: str, **extra) -> StreamEvent:
        payload: dict = {"code": code, "hint": hint}
        payload.update(extra)
        return StreamEvent("error", payload)

    @staticmethod
    def done(
        state: MessageTurnState,
        assistant_messages: list[Message],
        emotion: str,
        pending_action: dict | None = None,
    ) -> StreamEvent:
        payload: dict = {
            "conversation_id": str(state.conversation.id),
            "assistant_messages": [
                StreamEventService.serialize_message(m, emotion=emotion)
                for m in assistant_messages
            ],
        }
        if pending_action:
            payload["pending_action"] = pending_action
        return StreamEvent("done", payload)

    @staticmethod
    def serialize_message(message: Message, emotion: str | None = None) -> dict:
        return {
            "id": str(message.id),
            "conversation_id": str(message.conversation_id),
            "role": message.role,
            "content": message.content,
            "route_mode": message.route_mode,
            "emotion": emotion,
            "created_at": message.created_at.isoformat(),
        }
