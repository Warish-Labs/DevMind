"""Tests for /healthz and /readyz operational probes."""

from starlette.testclient import TestClient


def test_healthz_liveness(client: TestClient) -> None:
    """Assert /healthz returns 200 OK and status ok."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "ok"}
    assert "X-Request-ID" in response.headers


def test_readyz_readiness(client: TestClient) -> None:
    """Assert /readyz returns 200 OK and dependency statuses."""
    response = client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "ok"
    assert data["redis"] == "ok"
    assert "X-Request-ID" in response.headers


def test_api_v1_root(client: TestClient) -> None:
    """Assert /api/v1 returns operational information."""
    response = client.get("/api/v1")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "DevMind API"
    assert data["version"] == "v1"
    assert data["environment"] == "test"
    assert data["status"] == "operational"
