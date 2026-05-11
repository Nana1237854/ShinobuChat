from pydantic import BaseModel, Field


class Live2DEmotionMappingItem(BaseModel):
    expression: str | None = Field(default=None, min_length=1)
    motion: str | None = Field(default=None, min_length=1)


Live2DEmotionMapping = dict[str, Live2DEmotionMappingItem]


class Live2DModelItem(BaseModel):
    id: str
    name: str
    entry: str
    thumbnail: str | None = None
    defaultScale: float | None = None
    defaultX: float | None = None
    defaultY: float | None = None
    emotionMapping: Live2DEmotionMapping | None = None


class Live2DModelsResponse(BaseModel):
    models: list[Live2DModelItem]
