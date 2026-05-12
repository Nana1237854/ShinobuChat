from pydantic import BaseModel, Field


class ToneSettings(BaseModel):
    warmth: float = Field(default=0.7, ge=0.0, le=1.0)
    sharpness: float = Field(default=0.3, ge=0.0, le=1.0)
    formality: float = Field(default=0.5, ge=0.0, le=1.0)


class CharacterCard(BaseModel):
    name: str = "Shinobu"
    persona: str = ""
    tone: ToneSettings = Field(default_factory=ToneSettings)
    example_dialogue: list[str] = Field(default_factory=list)
    visual: dict = Field(default_factory=lambda: {"default_emotion": "neutral", "default_motion": "idle"})
    system_prompt_extra: str = ""


class CharacterCardOverride(BaseModel):
    tone: ToneSettings | None = None
    system_prompt_extra: str | None = None
