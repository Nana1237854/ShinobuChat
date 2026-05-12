from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Intent(BaseModel):
    """识别出的意图"""

    name: str
    params: dict = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ToolResult(BaseModel):
    """单个工具的执行结果"""

    tool: str
    status: str
    entity_type: str
    entity_id: UUID | None = None
    summary: str


class AgentResult(BaseModel):
    """一次 Agent 执行的完整结果"""

    intents: list[Intent] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    reply: str
    route_used: str


class AgentStatusEvent(BaseModel):
    """SSE agent.status 事件的 payload"""

    status: str
    route_mode: str


class AgentLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    conversation_id: UUID | None
    message_id: UUID | None
    action_type: str
    route_mode: str
    input_summary: str
    output_summary: str
    tool_results: list[dict]
    status: str
    created_at: datetime
