from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    app_name: str = "SmartRoute AI Backend"
    app_env: str = "development"
    app_version: str = "0.2.0"
    debug: bool = False
    log_level: str = "INFO"

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "smartroute"

    # CORS – comma-separated origins
    allowed_origins: str = "http://localhost:5173"

    # Firebase Cloud Messaging (optional – supplied at deployment)
    fcm_server_key: str = ""

    # Server-side, OpenAI-compatible LLM gateway. Never expose these to Vite.
    ai_api_key: str = ""
    ai_model: str = "gpt-4o-mini"
    ai_base_url: str = "https://api.openai.com/v1"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
