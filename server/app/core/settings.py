"""Application configuration and settings using Pydantic v2 Settings."""

import json
import os
import sys
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILES: tuple[str, ...] | None = (
    None
    if ("pytest" in sys.modules or os.getenv("DEVMIND_ENV") == "test")
    else (".env", ".env.local")
)


class Settings(BaseSettings):
    """DevMind server configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="DEVMIND_",
        env_file=_ENV_FILES,
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

    # Redis URL (Upstash Redis or local, docs/10 §11)
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("DEVMIND_REDIS_URL", "REDIS_URL", "UPSTASH_REDIS_URL"),
    )

    # Rate Limiting & Idempotency (docs/03 §10, docs/07 §11)
    rate_limit_enabled: bool = True
    rate_limit_window_seconds: int = 60
    rate_limit_read: int = 300
    rate_limit_write: int = 120
    rate_limit_job_create: int = 30
    rate_limit_ext_sync: int = 60
    rate_limit_auth: int = 20
    idempotency_ttl_seconds: int = 86400  # 24 hours (docs/03 §10)

    # CORS origins (accepts comma-separated string or list)
    cors_origins: list[str] | str = Field(
        default_factory=lambda: ["http://localhost:3000", "https://devmind.warishlabs.in"]
    )

    # Clerk Authentication (docs/07 §3, docs/10 §11)
    clerk_issuer: str | None = None
    clerk_jwks_url: str | None = None
    clerk_authorized_parties: list[str] | str = Field(
        default_factory=lambda: ["http://localhost:3000", "https://devmind.warishlabs.in"]
    )
    clerk_secret_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DEVMIND_CLERK_SECRET_KEY", "CLERK_SECRET_KEY"),
    )
    clerk_webhook_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DEVMIND_CLERK_WEBHOOK_SECRET", "CLERK_WEBHOOK_SECRET"),
    )

    # Encryption and token security (docs/07 §3, docs/10 §11)
    encryption_keys: list[str] | str = Field(default_factory=list)
    ext_token_pepper: str | None = None

    # LLM and embedding providers (docs/05, docs/10 §11)
    llm_provider: str = "fake"
    llm_api_key: str | None = None
    embed_provider: str = "fake"
    embed_api_key: str | None = None
    embed_space_id: str = "default-768"

    # GitHub integration & Resend email (docs/10 §11)
    github_client_id: str | None = None
    github_client_secret: str | None = None
    github_webhook_secret: str | None = None
    resend_api_key: str | None = None

    # Cloudflare Turnstile bot protection (docs/07 §11, docs/10 §11)
    turnstile_secret_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DEVMIND_TURNSTILE_SECRET_KEY", "TURNSTILE_SECRET_KEY"),
    )
    turnstile_verify_url: str = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    turnstile_timeout_seconds: float = 5.0

    # Subsystem kill switches (docs/07 §12, docs/10 §11)
    kill_indexing: bool = False
    kill_llm: bool = False
    kill_embed: bool = False

    # Observability, tracing, and error reporting (docs/02 §12, docs/10 §13, ADR-030, OQ-15)
    otel_enabled: bool = True
    otel_service_name: str = "devmind-api"
    otel_exporter: Literal["console", "memory", "none"] = "memory"
    sentry_dsn: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DEVMIND_SENTRY_DSN", "SENTRY_DSN"),
    )

    @field_validator("encryption_keys", mode="before")
    @classmethod
    def parse_encryption_keys(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(k).strip() for k in parsed if str(k).strip()]
                except Exception:
                    pass
            return [k.strip() for k in value.split(",") if k.strip()]
        return value

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

    @field_validator("redis_url", mode="before")
    @classmethod
    def validate_redis_url(cls, value: str | None) -> str:
        if not value:
            return "redis://localhost:6379/0"
        val = value.strip()
        if val.startswith("http://") or val.startswith("https://"):
            raise ValueError(
                "DevMind requires standard Redis protocol ('redis://' or 'rediss://' for Upstash TLS), "
                "not the Upstash HTTP REST URL. In Upstash Console, copy the 'Redis Connect' string "
                "(e.g. rediss://default:<password>@<host>.upstash.io:6379)."
            )
        return val

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
