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

    # CORS origins (accepts comma-separated string or list)
    cors_origins: list[str] | str = Field(default_factory=lambda: ["http://localhost:3000"])

    # Clerk Authentication (docs/07 §3, docs/10 §11)
    clerk_issuer: str | None = None
    clerk_jwks_url: str | None = None
    clerk_authorized_parties: list[str] | str = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    clerk_secret_key: str | None = None
    clerk_webhook_secret: str | None = None

    @field_validator("clerk_authorized_parties", mode="before")
    @classmethod
    def parse_authorized_parties(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return ["http://localhost:3000"]
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                import json

                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
            return [party.strip() for party in value.split(",") if party.strip()]
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                import json

                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass
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
