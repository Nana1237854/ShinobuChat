import asyncio

from app.core.config import settings
from app.events.bus import bus
from app.events.types import EventType
from app.schemas.decision import SkillCall
from app.skills.base import SkillError, SkillProgress
from app.skills.registry import SkillRegistry


class SkillService:
    def __init__(self):
        self._active_cancel: asyncio.Event | None = None

    async def execute(self, skill_call: SkillCall) -> None:
        skill = SkillRegistry.get(skill_call.skill_name)
        if not skill:
            await bus.publish(
                EventType.SKILL_ERROR,
                {
                    "skill_name": skill_call.skill_name,
                    "code": "SKILL_NOT_FOUND",
                    "message": f"Skill '{skill_call.skill_name}' is not available",
                    "hint": "I do not have that tool available yet.",
                },
            )
            return

        cancel_token = asyncio.Event()
        self._active_cancel = cancel_token

        async def on_progress(progress: SkillProgress) -> None:
            await bus.publish(
                EventType.SKILL_PROGRESS,
                {
                    "skill_name": progress.skill_name,
                    "message": progress.message,
                    "percent": progress.percent,
                },
            )

        try:
            result = await asyncio.wait_for(
                skill.execute(
                    skill_call.skill_params,
                    on_progress,
                    float(settings.skill_timeout_seconds),
                    cancel_token,
                ),
                timeout=float(settings.skill_timeout_seconds),
            )
            await bus.publish(
                EventType.SKILL_DONE,
                {
                    "skill_name": skill_call.skill_name,
                    "result": result,
                },
            )
        except TimeoutError:
            await bus.publish(
                EventType.SKILL_ERROR,
                {
                    "skill_name": skill_call.skill_name,
                    "code": "TIMEOUT",
                    "message": "Skill timed out",
                    "hint": "It's taking longer than expected. Maybe try again?",
                },
            )
        except SkillError as error:
            await bus.publish(
                EventType.SKILL_ERROR,
                {
                    "skill_name": skill_call.skill_name,
                    "code": error.code,
                    "message": error.message,
                    "hint": error.user_facing_hint,
                },
            )
        except Exception as error:
            await bus.publish(
                EventType.SKILL_ERROR,
                {
                    "skill_name": skill_call.skill_name,
                    "code": "UNKNOWN",
                    "message": str(error),
                    "hint": "Something went wrong. Could you try again?",
                },
            )
        finally:
            self._active_cancel = None

    async def cancel(self) -> bool:
        if self._active_cancel and not self._active_cancel.is_set():
            self._active_cancel.set()
            return True
        return False
