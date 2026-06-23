"""Prompt trace service (Phase 2).

Records per-message context metadata. See app/models/prompt_trace.py for
the data model. This service is intentionally lightweight — the trace is
written once at turn preparation and never mutated.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.prompt_trace import PromptTrace

logger = logging.getLogger(__name__)


class PromptTraceService:
    def __init__(self, db: Session):
        self.db = db

    def create_trace(
        self,
        *,
        user_id: UUID,
        conversation_id: UUID,
        message_id: UUID,
        route_mode: str,
        conversation_mode: str,
        router_reason: str = "",
        pinned_prefix_sha: str = "",
        character_card_sha: str = "",
        tool_catalog_sha: str = "",
        skill_catalog_sha: str = "",
        memory_ids: list[str] | None = None,
        activated_skill_names: list[str] | None = None,
        tool_names_available: list[str] | None = None,
        vision_context_used: bool = False,
        persona_context_used: bool = False,
        emotion_context_used: bool = False,
        browser_context_used: bool = False,
        mcp_context_used: bool = False,
        context_summary: dict | None = None,
    ):
        trace = PromptTrace(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            route_mode=route_mode,
            conversation_mode=conversation_mode,
            router_reason=router_reason,
            pinned_prefix_sha=pinned_prefix_sha,
            character_card_sha=character_card_sha,
            tool_catalog_sha=tool_catalog_sha,
            skill_catalog_sha=skill_catalog_sha,
            memory_ids=memory_ids or [],
            activated_skill_names=activated_skill_names or [],
            tool_names_available=tool_names_available or [],
            vision_context_used=vision_context_used,
            persona_context_used=persona_context_used,
            emotion_context_used=emotion_context_used,
            browser_context_used=browser_context_used,
            mcp_context_used=mcp_context_used,
            context_summary=context_summary or {},
        )
        self.db.add(trace)
        self.db.commit()
        self.db.refresh(trace)
        return trace

    def list_for_conversation(self, user_id: UUID, conversation_id: UUID, limit: int = 50):
        return (
            self.db.query(PromptTrace)
            .filter(
                PromptTrace.user_id == user_id,
                PromptTrace.conversation_id == conversation_id,
            )
            .order_by(PromptTrace.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_for_message(self, user_id: UUID, message_id: UUID):
        return (
            self.db.query(PromptTrace)
            .filter(
                PromptTrace.user_id == user_id,
                PromptTrace.message_id == message_id,
            )
            .first()
        )
