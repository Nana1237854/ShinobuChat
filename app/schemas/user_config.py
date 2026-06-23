from typing import Any, Literal

from pydantic import BaseModel, Field


class UserConfigPatch(BaseModel):
    ai_api_key: str | None = None
    ai_base_url: str | None = None
    ai_model: str | None = None
    ai_request_timeout_seconds: int | None = Field(default=None, ge=1, le=600)
    ai_supports_image_input: bool | None = None
    ai_lightweight_max_tokens: int | None = Field(default=None, ge=128, le=131072)
    ai_vision_base_url: str | None = None
    ai_vision_api_key: str | None = None
    ai_vision_model: str | None = None
    roleplay_llm_model: str | None = None
    roleplay_llm_temperature: float | None = Field(default=None, ge=0, le=2)
    decision_llm_model: str | None = None
    decision_llm_temperature: float | None = Field(default=None, ge=0, le=2)
    google_search_api_key: str | None = None
    google_search_cx: str | None = None
    edge_tts_voice: str | None = None
    asr_engine: str | None = None
    whisper_api_key: str | None = None
    diary_enabled: bool | None = None
    auto_diary_enabled: bool | None = None
    auto_diary_timezone: str | None = None
    # Embedding / memory retrieval
    embedding_provider: str | None = None
    embedding_model: str | None = None
    google_embedding_api_key: str | None = None
    google_embedding_base_url: str | None = None
    embedding_dimension: int | None = Field(default=None, ge=0, le=4096)
    embedding_timeout_seconds: int | None = Field(default=None, ge=5, le=120)
    embedding_top_k: int | None = Field(default=None, ge=1, le=10)
    # Action reply personalization
    action_reply_personalization_enabled: bool | None = None
    action_reply_use_memory: bool | None = None
    action_reply_use_diary: bool | None = None
    action_reply_model: str | None = None
    action_reply_max_tokens: int | None = Field(default=None, ge=64, le=2048)
    action_reply_temperature: float | None = Field(default=None, ge=0, le=2)


class UserConfigFieldOut(BaseModel):
    key: str
    value: Any
    source: Literal["user", "env", "default"]
    encrypted: bool


class UserConfigOut(BaseModel):
    fields: list[UserConfigFieldOut]


# Type aliases matching the user-facing naming convention
ConfigFieldOut = UserConfigFieldOut
ConfigUpdateRequest = UserConfigPatch
ConfigListResponse = UserConfigOut
