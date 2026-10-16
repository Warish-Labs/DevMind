"""Pytest fixtures for DevMind server tests."""

from collections.abc import Iterator

import pytest
from starlette.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    """Fixture returning test settings."""
    return Settings(
        env="test",
        run_mode="all",
        log_level="DEBUG",
        redis_key_prefix="test:",
        database_url="postgresql+psycopg://test_user:test_pass@localhost:5432/test_db",
        redis_url="redis://localhost:6379/15",
        cors_origins=["http://localhost:3000", "http://test.local"],
    )


@pytest.fixture
def client(test_settings: Settings) -> Iterator[TestClient]:
    """HTTP test client fixture using Starlette TestClient."""
    app = create_app(settings=test_settings)
    with TestClient(app=app, base_url="http://testserver") as test_client:
        yield test_client
