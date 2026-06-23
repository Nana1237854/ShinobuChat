from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ConversationMode(str, Enum):
    COMPANION = "companion"
    WORK = "work"
    FOCUS = "focus"
    NIGHT = "night"


MODE_LABELS: dict[str, str] = {
    "companion": "陪伴",
    "work": "工作",
    "focus": "专注",
    "night": "夜间",
}

MODE_DESCRIPTIONS: dict[str, str] = {
    "companion": "保持 Shinobu 的日常陪伴感，自然闲聊与互动",
    "work": "优先整理任务、步骤和结论，回复更结构化",
    "focus": "减少闲聊，只保留必要提醒与关键回复",
    "night": "降低打扰，回复更轻柔简短",
}


class ConversationModeUpdate(BaseModel):
    mode: ConversationMode


class ModeToolPolicy(BaseModel):
    allowed_tool_groups: list[str] = Field(default_factory=list)
    blocked_tool_groups: list[str] = Field(default_factory=list)


class ModeReplyPolicy(BaseModel):
    max_sentences: int = 3
    style: str = "natural"
    prioritize_conciseness: bool = False


class ModeReminderPolicy(BaseModel):
    enabled: bool = True
    reduce_frequency: bool = False
    urgent_only: bool = False
    tone: str = "friendly"


class ModeDecisionTendency(BaseModel):
    chat_weight: float = 0.7
    agent_weight: float = 0.3
    prefer_todo_create: bool = False
    prefer_task_planning: bool = False
    suppress_idle_chat: bool = False


class ModeBehaviorOut(BaseModel):
    mode: ConversationMode
    mode_label: str
    description: str
    tool_policy: ModeToolPolicy
    reply_policy: ModeReplyPolicy
    reminder_policy: ModeReminderPolicy
    decision_tendency: ModeDecisionTendency


class ConversationModeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mode: ConversationMode
    mode_label: str
    description: str
    behavior: ModeBehaviorOut
    updated_at: datetime
