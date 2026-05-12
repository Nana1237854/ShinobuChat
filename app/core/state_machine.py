import asyncio
from enum import StrEnum


class SystemState(StrEnum):
    IDLE = "idle"
    DECIDING = "deciding"
    CHATTING = "chatting"
    EXECUTING = "executing"
    SPEAKING = "speaking"


class StateMachine:
    ALLOWED = {
        SystemState.IDLE: {SystemState.DECIDING},
        SystemState.DECIDING: {SystemState.CHATTING, SystemState.EXECUTING},
        SystemState.CHATTING: {SystemState.SPEAKING},
        SystemState.EXECUTING: {SystemState.SPEAKING},
        SystemState.SPEAKING: {SystemState.IDLE},
    }

    EMOTIONS = {
        SystemState.IDLE: "neutral",
        SystemState.DECIDING: "thinking",
        SystemState.CHATTING: "chatting",
        SystemState.EXECUTING: "working",
        SystemState.SPEAKING: "speaking",
    }

    def __init__(self):
        self.state = SystemState.IDLE

    def transition(self, target: SystemState) -> None:
        if target not in self.ALLOWED.get(self.state, set()):
            raise ValueError(f"Cannot transition from {self.state} to {target}")
        self.state = target

    def reset(self) -> None:
        self.state = SystemState.IDLE

    @property
    def emotion(self) -> str:
        return self.EMOTIONS.get(self.state, "neutral")

    async def debounce_deciding(self, delay_ms: int = 300) -> None:
        await asyncio.sleep(delay_ms / 1000)
