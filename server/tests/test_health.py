"""Tests for /healthz and /readyz operational probes."""

from starlette.testclient import TestClient


def test_health_liveness(client: TestClient) -> None:
    """Assert /health returns 200 OK and status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok"}
    assert "X-Request-ID" in response.headers


def test_healthz_liveness(client: TestClient) -> None:
    """Assert /healthz returns 200 OK and status ok."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok"}
    assert "X-Request-ID" in response.headers


def test_readyz_readiness(client: TestClient, monkeypatch) -> None:
    """Assert /readyz returns 200 OK when dependencies are healthy."""
    from unittest.mock import AsyncMock

    monkeypatch.setattr(
        "app.domain.auth.check_database_connectivity",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "app.core.redis.check_redis_connectivity",
        AsyncMock(return_value=True),
    )
    response = client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "ok"
    assert data["redis"] == "ok"
    assert "X-Request-ID" in response.headers


def test_readyz_degraded_when_database_down(client: TestClient, monkeypatch) -> None:
    """Assert /readyz returns 503 Service Unavailable when database check fails."""
    from unittest.mock import AsyncMock

    monkeypatch.setattr(
        "app.domain.auth.check_database_connectivity",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "app.core.redis.check_redis_connectivity",
        AsyncMock(return_value=True),
    )
    response = client.get("/readyz")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"] == "unreachable"
    assert data["redis"] == "ok"


def test_api_v1_root(client: TestClient) -> None:
    """Assert /api/v1 returns operational information."""
    response = client.get("/api/v1")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "DevMind API"
    assert data["version"] == "v1"
    assert data["environment"] == "test"
    assert data["status"] == "operational"
