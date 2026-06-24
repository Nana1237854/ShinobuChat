"""Context pack and intent result schemas.

ContextPack is assembled by ContextPackBuilder and consumed by
ContextIntentResolver. ContextIntentResult is the validated LLM output.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ContextPack(BaseModel):
    """Structured context assembled before intent resolution."""

    recent_messages: list[dict[str, Any]] = Field(default_factory=list)
    conversation_summary: str | None = None
    relevant_memories: list[dict[str, Any]] = Field(default_factory=list)
    diary_summaries: list[dict[str, Any]] = Field(default_factory=list)
    pending_conversation_intent: dict[str, Any] | None = None
    available_tools: list[dict[str, Any]] = Field(default_factory=list)
    available_local_apps: list[dict[str, Any]] = Field(default_factory=list)
    conversation_mode: str = "companion"


class ContextIntentResult(BaseModel):
    """Validated intent result from ContextIntentResolver.

    v1: force_relaunch / bring_to_front are NOT execution facts.
    They are not passed to LocalAppService.open_app().
    """

    action: Literal["open_local_app", "clarify", "chat", "none"] = "chat"
    intent_type: str | None = None
    app_name: str | None = None
    app_key: str | None = None
    query: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_clarification: bool = False
    clarification_question: str | None = None
    should_save_pending_intent: bool = False
    pending_intent: dict[str, Any] | None = None
    reason: str | None = None
