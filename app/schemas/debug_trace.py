"""Debug trace schemas (Phase 2).

Never expose: system prompt, tool schemas, web page content, API keys.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PromptTraceItem(BaseModel):
    id: UUID
    user_id: UUID
    conversation_id: UUID
    message_id: UUID
    route_mode: str
    conversation_mode: str
    pinned_prefix_sha: str = ""
    character_card_sha: str = ""
    tool_catalog_sha: str = ""
    skill_catalog_sha: str = ""
    memory_ids: list[str] | None = None
    activated_skill_names: list[str] | None = None
    tool_names_available: list[str] | None = None
    vision_context_used: bool = False
    persona_context_used: bool = False
    emotion_context_used: bool = False
    browser_context_used: bool = False
    mcp_context_used: bool = False
    router_reason: str = ""
    context_summary: dict | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
