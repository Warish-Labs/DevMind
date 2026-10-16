"""Application configuration and settings using Pydantic v2 Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """DevMind server configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="DEVMIND_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["local", "test", "staging", "production"] = "local"
    run_mode: Literal["api", "worker", "scheduler", "all"] = "all"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    redis_key_prefix: str = "dm:"

    # Database URLs (Neon PostgreSQL + pgvector)
    database_url: str = Field(
        default="postgresql+psycopg://devmind_app:devmind_pass@localhost:5432/devmind"
    )
    database_url_direct: str | None = None

    # Redis URL (Render Key Value or local)
    redis_url: str = "redis://localhost:6379/0"

    # CORS origins
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def is_test(self) -> bool:
        return self.env == "test"

    @property
    def is_local(self) -> bool:
        return self.env == "local"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
