from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel


class SkillError(Exception):
    def __init__(self, code: str, message: str, user_facing_hint: str):
        super().__init__(message)
        self.code = code
        self.message = message
        self.user_facing_hint = user_facing_hint


class SkillProgress(BaseModel):
    skill_name: str
    message: str
    percent: float


OnProgress = Callable[[SkillProgress], Awaitable[None]]
CancelToken = Any


class Skill(ABC):
    name: str = ""
    description: str = ""
    parameters: type[BaseModel] = BaseModel
    example_triggers: list[str] = []

    @abstractmethod
    async def execute(
        self,
        params: dict[str, Any],
        on_progress: OnProgress,
        timeout: float,
        cancel_token: CancelToken,
    ) -> str:
        ...
