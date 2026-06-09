from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = ""

    @field_validator("bot_token", mode="before")
    @classmethod
    def strip_token(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().strip('"').strip("'")
        return v
    webhook_url: str = ""
    webhook_secret: str = ""

    database_url: str = "postgresql+asyncpg://finances:finances@localhost:5432/finances"
    redis_url: str = "redis://localhost:6379/0"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False

    @property
    def use_webhook(self) -> bool:
        return bool(self.webhook_url)

    @property
    def redis_is_local(self) -> bool:
        return "localhost" in self.redis_url or "127.0.0.1" in self.redis_url


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_production_config(settings: Settings | None = None) -> None:
    """Fail fast with an actionable message when Railway env is misconfigured."""
    settings = settings or get_settings()
    if settings.use_webhook and settings.redis_is_local:
        raise RuntimeError(
            "REDIS_URL points to localhost, but WEBHOOK_URL is set. "
            "Redis is required for bot FSM state in webhook mode. "
            "In Railway Variables set REDIS_URL=${{Redis.REDIS_URL}} "
            "on both web and worker services (Redis plugin must be added to the project)."
        )
