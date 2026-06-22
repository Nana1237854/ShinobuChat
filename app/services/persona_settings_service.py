from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.persona_settings import UserPersonaSettings

_VALID = {
    "verbosity": {"quiet", "balanced", "talkative"},
    "warmth": {"calm", "warm", "playful"},
    "initiative": {"passive", "balanced", "proactive"},
    "work_style": {"casual", "focused", "strict"},
}

_TONE_MAP = {
    ("verbosity", "quiet"): "回复更短，少扩展",
    ("verbosity", "balanced"): "回复适中",
    ("verbosity", "talkative"): "可以多给一点解释，但不要啰嗦",
    ("warmth", "calm"): "语气平稳克制",
    ("warmth", "warm"): "语气温柔亲近",
    ("warmth", "playful"): "语气轻松俏皮",
    ("initiative", "passive"): "少主动追问",
    ("initiative", "balanced"): "适度主动建议",
    ("initiative", "proactive"): "可以主动提醒下一步，但不能压迫",
    ("work_style", "casual"): "轻松陪伴式",
    ("work_style", "focused"): "更关注效率和任务推进",
    ("work_style", "strict"): "稍微更有执行力，但不能高压训斥",
}


class PersonaSettingsService:
    def __init__(self, db: Session):
        self.db = db

    def get_settings(self, user_id: UUID) -> UserPersonaSettings:
        row = (
            self.db.query(UserPersonaSettings)
            .filter(UserPersonaSettings.user_id == user_id)
            .first()
        )
        if row is not None:
            return row
        return UserPersonaSettings(
            user_id=user_id,
            verbosity="balanced",
            warmth="warm",
            initiative="balanced",
            work_style="casual",
        )

    def update_settings(self, user_id: UUID, payload) -> UserPersonaSettings:
        row = (
            self.db.query(UserPersonaSettings)
            .filter(UserPersonaSettings.user_id == user_id)
            .first()
        )
        if row is None:
            row = UserPersonaSettings(user_id=user_id)
            self.db.add(row)
        for key, value in payload.model_dump(exclude_unset=True).items():
            if hasattr(row, key):
                setattr(row, key, value)
        row.updated_at = datetime.now(timezone.utc)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    @staticmethod
    def build_tone_instructions(settings: UserPersonaSettings) -> str:
        lines = ["【用户偏好的交流风格】"]
        for field in ("verbosity", "warmth", "initiative", "work_style"):
            value = getattr(settings, field, None)
            if value and (_TONE_MAP.get((field, value))):
                lines.append(f"- {_TONE_MAP[(field, value)]}")
        return "\n".join(lines)
