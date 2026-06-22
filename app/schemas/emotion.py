from pydantic import BaseModel, Field

EMOTION_LABELS = [
    "neutral",
    "happy",
    "worried",
    "stressed",
    "tired",
    "lonely",
    "frustrated",
    "sad",
    "confused",
    "crisis",
]


class UserEmotionResult(BaseModel):
    emotion_label: str
    confidence: float
    intensity: float
    reply_style_hint: str
    source: str
    should_adjust_reply: bool


class EmotionAnalyzeRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    recent_user_messages: list[str] = Field(default_factory=list, max_length=10)
    local_hour: int | None = Field(default=None, ge=0, le=23)


class EmotionAnalyzeResponse(UserEmotionResult):
    pass
