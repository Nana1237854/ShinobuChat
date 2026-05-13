from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ShinobuChat Core API"
    api_v1_prefix: str = "/api/v1"
    live2d_assets_dir: Path = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "shinobu-chat"
        / "public"
        / "assets"
        / "live2d"
    )

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/shinobuchat"
    )

    jwt_secret_key: str = Field(default="replace-me-in-prod")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    oauth2_device_code_ttl_seconds: int = 900
    oauth2_poll_interval_seconds: int = 5

    ai_api_key: str = Field(default="")
    ai_base_url: str = Field(default="https://api.openai.com/v1")
    ai_model: str = Field(default="gpt-4o-mini")
    ai_request_timeout_seconds: int = Field(default=60)
    ai_supports_image_input: bool = Field(default=True)
    ai_extra_body: str = Field(default="")
    ai_lightweight_max_tokens: int = Field(default=4096)

    agent_max_steps: int = Field(default=50)

    image_max_input_bytes: int = Field(default=41_943_040)
    image_max_output_bytes: int = Field(default=4_194_304)
    image_max_side: int = Field(default=3072)
    image_max_pixels: int = Field(default=24_000_000)

    file_max_input_bytes: int = Field(default=209_715_200)

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SC_", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
