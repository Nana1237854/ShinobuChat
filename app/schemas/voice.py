from pydantic import BaseModel, Field


class VoiceTTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    emotion: str | None = Field(default=None, max_length=40)
    context: list[str] = Field(default_factory=list, max_length=12)
    text_lang: str | None = Field(default=None, max_length=12)
    media_type: str | None = Field(default=None, max_length=12)


class VoiceASRResponse(BaseModel):
    text: str
    engine: str

