from __future__ import annotations

import asyncio

from app.schemas.message import MessageCreate
from app.services.agents.memory_agent import MemoryAgent
from app.services.turn.turn_state import MessageTurnState


class MemoryWriteScheduler:
    def __init__(self, memory_agent: MemoryAgent | None = None):
        self.memory_agent = memory_agent

    def schedule_after_turn(self, payload: MessageCreate, state: MessageTurnState) -> None:
        if self.memory_agent is None:
            return

        asyncio.create_task(
            asyncio.to_thread(
                self.memory_agent.extract_and_store_after_turn,
                user_id=payload.user_id,
                user_text=payload.content,
                assistant_text=state.reply_text,
                source_msg_id=state.user_message.id,
            )
        )
