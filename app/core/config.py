from functools import lru_cache
from pathlib import Path

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

    memory_embedding_dimensions: int = 384
    memory_embedding_model: str = "local-hash-v1"
    memory_search_default_limit: int = 8
    memory_pgvector_enabled: bool = False

    live2d_assets_dir: Path = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "shinobu-chat"
        / "dist"
        / "assets"
        / "live2d"
    )

    decision_llm_api_key: str = ""
    decision_llm_base_url: str = "https://api.deepseek.com/v1"
    decision_llm_model: str = "deepseek-chat"
    decision_llm_temperature: float = 0.1
    decision_llm_max_tokens: int = 512

    roleplay_llm_api_key: str = ""
    roleplay_llm_base_url: str = "https://api.deepseek.com/v1"
    roleplay_llm_model: str = "deepseek-chat"
    roleplay_llm_temperature: float = 0.8
    roleplay_llm_max_tokens: int = 2048

    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"

    characters_dir: Path = Path(__file__).resolve().parents[2] / "characters"
    skill_timeout_seconds: int = 120
    decision_debounce_ms: int = 300
    google_search_api_key: str = ""
    google_search_cx: str = ""

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

    gpt_sovits_base_url: str = Field(default="http://127.0.0.1:9880")
    gpt_sovits_timeout_seconds: int = Field(default=120)
    gpt_sovits_text_lang: str = Field(default="zh")
    gpt_sovits_prompt_lang: str = Field(default="zh")
    gpt_sovits_media_type: str = Field(default="wav")
    gpt_sovits_text_split_method: str = Field(default="cut5")
    gpt_sovits_batch_size: int = Field(default=1)
    gpt_sovits_streaming_mode: bool = Field(default=False)

    voice_reference_manifest_path: Path = (
        Path(__file__).resolve().parents[2] / "voice_reference_audio.json"
    )
    voice_reference_presets: str = Field(default="")

    asr_engine: str = Field(default="whisper")
    asr_timeout_seconds: int = Field(default=90)
    funasr_api_url: str = Field(default="")
    whisper_api_url: str = Field(default="https://api.openai.com/v1/audio/transcriptions")
    whisper_api_key: str = Field(default="")
    whisper_model: str = Field(default="whisper-1")
    whisper_language: str = Field(default="")

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SC_", extra="ignore")

    @property
    def effective_decision_api_key(self) -> str:
        return self.decision_llm_api_key or self.llm_api_key

    @property
    def effective_roleplay_api_key(self) -> str:
        return self.roleplay_llm_api_key or self.llm_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
