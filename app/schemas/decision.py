from enum import Enum

from pydantic import BaseModel, Field


class RouteDecision(str, Enum):
    CHAT = "chat"
    AGENT = "agent"


class DecisionFrame(BaseModel):
    route: RouteDecision
    skill_name: str | None = None
    skill_params: dict | None = None
    reasoning: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class SkillCall(BaseModel):
    skill_name: str
    skill_params: dict = Field(default_factory=dict)
    message_id: str = ""
    decision_frame: DecisionFrame | None = None
