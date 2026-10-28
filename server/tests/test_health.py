"""Tests for /healthz and /readyz operational probes (docs/10 §12, §14, §18)."""

from unittest.mock import AsyncMock

from starlette.testclient import TestClient


def test_health_liveness(client: TestClient) -> None:
    """Assert /health returns 200 OK, status ok, and build SHA."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["build_sha"] == "dev"
    assert "X-Request-ID" in response.headers


def test_healthz_liveness(client: TestClient) -> None:
    """Assert /healthz returns 200 OK, status ok, and build SHA."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["build_sha"] == "dev"
    assert "X-Request-ID" in response.headers


def test_readyz_readiness(client: TestClient, monkeypatch) -> None:
    """Assert /readyz returns 200 OK when dependencies and migrations are healthy."""
    monkeypatch.setattr(
        "app.domain.auth.check_database_connectivity",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "app.core.redis.check_redis_connectivity",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "app.domain.auth.check_migrations_readiness",
        AsyncMock(return_value=(True, "ok", ["0012_review_rules"])),
    )
    response = client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "ok"
    assert data["redis"] == "ok"
    assert data["migrations"] == "ok"
    assert isinstance(data["kill_switches"], dict)
    assert "X-Request-ID" in response.headers


def test_readyz_degraded_when_database_down(client: TestClient, monkeypatch) -> None:
    """Assert /readyz returns 503 Service Unavailable when database check fails."""
    monkeypatch.setattr(
        "app.domain.auth.check_database_connectivity",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "app.core.redis.check_redis_connectivity",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "app.domain.auth.check_migrations_readiness",
        AsyncMock(return_value=(True, "ok", ["0012_review_rules"])),
    )
    response = client.get("/readyz")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"] == "unreachable"
    assert data["redis"] == "ok"


def test_readyz_degraded_when_migrations_pending(client: TestClient, monkeypatch) -> None:
    """Assert /readyz returns 503 Service Unavailable when migrations are pending."""
    monkeypatch.setattr(
        "app.domain.auth.check_database_connectivity",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "app.core.redis.check_redis_connectivity",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "app.domain.auth.check_migrations_readiness",
        AsyncMock(return_value=(False, "pending", ["0009_agent_runs"])),
    )
    response = client.get("/readyz")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert data["migrations"] == "pending"


def test_readyz_alerts_endpoint(client: TestClient) -> None:
    """Assert /readyz/alerts returns operational alerts format without secrets."""
    response = client.get("/readyz/alerts")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "warning", "critical")
    assert "alerts_count" in data
    assert isinstance(data["alerts"], list)
    assert "evaluated_at" in data


def test_api_v1_root(client: TestClient) -> None:
    """Assert /api/v1 returns operational information."""
    response = client.get("/api/v1")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "DevMind API"
    assert data["version"] == "v1"
    assert data["environment"] == "test"
    assert data["status"] == "operational"
