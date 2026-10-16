"""Tests for configuration settings validation."""

from app.core.settings import Settings


def test_settings_default_values() -> None:
    """Verify default setting values and helpers."""
    settings = Settings(
        env="local",
        run_mode="all",
        log_level="INFO",
    )
    assert settings.is_local is True
    assert settings.is_production is False
    assert settings.is_test is False
    assert settings.redis_key_prefix == "dm:"
    assert "http://localhost:3000" in settings.cors_origins


def test_settings_cors_origins_parsing() -> None:
    """Verify comma-separated cors string parses into a list."""
    settings = Settings(
        env="production",
        cors_origins="https://devmind.warishlabs.in, https://app.devmind.warishlabs.in",  # type: ignore[arg-type]
    )
    assert settings.is_production is True
    assert settings.cors_origins == [
        "https://devmind.warishlabs.in",
        "https://app.devmind.warishlabs.in",
    ]


def test_settings_environment_modes() -> None:
    """Verify environment checks for staging and test."""
    staging = Settings(env="staging")
    assert staging.env == "staging"
    assert staging.is_production is False

    test = Settings(env="test")
    assert test.is_test is True
