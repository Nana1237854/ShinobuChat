from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.message import RouteMode
from app.services.agents.coordinator import DirectActionPlan
from app.services.stream_events import StreamEvent


@dataclass
class MessageTurnState:
    conversation: Conversation
    user_message: Message
    route_mode: RouteMode
    router_reason: str
    progress_events: list[StreamEvent]
    reply_text: str = ""
    conversation_mode: str = "companion"
    direct_action: Optional[DirectActionPlan] = None

    @property
    def conversation_id(self):
        return self.conversation.id

    @property
    def user_message_id(self):
        return self.user_message.id
