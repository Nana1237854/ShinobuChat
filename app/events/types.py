from enum import StrEnum


class EventType(StrEnum):
    DECISION_MADE = "decision.made"
    SKILL_PROGRESS = "skill.progress"
    SKILL_DONE = "skill.done"
    SKILL_ERROR = "skill.error"
    ROLEPLAY_SPEAKING = "roleplay.speaking"
    ROLEPLAY_IDLE = "roleplay.idle"
