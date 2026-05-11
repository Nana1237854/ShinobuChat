from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ShinobuChat Core API"
    api_v1_prefix: str = "/api/v1"

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/shinobuchat"
    )

    jwt_secret_key: str = Field(default="replace-me-in-prod")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    oauth2_device_code_ttl_seconds: int = 900
    oauth2_poll_interval_seconds: int = 5
    sync_heartbeat_seconds: int = 20

    apns_offline_fallback_enabled: bool = True
    apns_sandbox: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SC_")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
