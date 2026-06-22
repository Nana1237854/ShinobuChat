from typing import Any, Literal

from pydantic import BaseModel, Field


class UserConfigPatch(BaseModel):
    ai_api_key: str | None = None
    ai_base_url: str | None = None
    ai_model: str | None = None
    ai_request_timeout_seconds: int | None = Field(default=None, ge=1, le=600)
    ai_supports_image_input: bool | None = None
    ai_lightweight_max_tokens: int | None = Field(default=None, ge=128, le=131072)
    roleplay_llm_model: str | None = None
    roleplay_llm_temperature: float | None = Field(default=None, ge=0, le=2)
    decision_llm_model: str | None = None
    decision_llm_temperature: float | None = Field(default=None, ge=0, le=2)
    google_search_api_key: str | None = None
    google_search_cx: str | None = None
    edge_tts_voice: str | None = None
    asr_engine: str | None = None
    whisper_api_key: str | None = None


class UserConfigFieldOut(BaseModel):
    key: str
    value: Any
    source: Literal["user", "env", "default"]
    encrypted: bool


class UserConfigOut(BaseModel):
    fields: list[UserConfigFieldOut]
