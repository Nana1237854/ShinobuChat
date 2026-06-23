from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RouteMode(str, Enum):
    AUTO = "auto"
    CHAT = "chat"
    AGENT = "agent"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageCreate(BaseModel):
    user_id: UUID
    content: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None
    route_mode: RouteMode = RouteMode.AUTO
    vision_context: str | None = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    route_mode: RouteMode | None = None
    created_at: datetime
