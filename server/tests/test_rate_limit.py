"""Unit and integration tests for Redis-backed sliding-window rate limiting (docs/03 §10)."""

import uuid

import pytest
from starlette.testclient import TestClient

from app.core.settings import Settings
from app.domain.auth import (
    PERMISSION_PUBLIC,
    declare_permission,
)
from app.main import create_app
from app.middleware.rate_limit import _in_memory_windows


@pytest.fixture(autouse=True)
def reset_rate_limit_windows() -> None:
    _in_memory_windows.clear()
    yield
    _in_memory_windows.clear()


def test_rate_limit_headers_on_allowed_requests() -> None:
    """Verify RateLimit-* headers are injected on successful responses."""
    settings = Settings(
        rate_limit_enabled=True,
        rate_limit_read=50,
        rate_limit_window_seconds=60,
        redis_key_prefix=f"test_{uuid.uuid4().hex[:6]}:",
    )
    app = create_app(settings=settings)


    with TestClient(app) as client:
        response = client.get("/api/v1")
        assert response.status_code == 200
        assert "RateLimit-Limit" in response.headers
        assert response.headers["RateLimit-Limit"] == "50"
        assert "RateLimit-Remaining" in response.headers
        assert "RateLimit-Reset" in response.headers


def test_rate_limit_exceeded_returns_429_problem_details() -> None:
    """Verify HTTP 429 and RFC 9457 Problem Details when rate limit is exceeded."""
    _in_memory_windows.clear()
    settings = Settings(
        rate_limit_enabled=True,
        rate_limit_read=3,
        rate_limit_window_seconds=60,
        redis_key_prefix=f"test_{uuid.uuid4().hex[:6]}:",
    )
    app = create_app(settings=settings)

    with TestClient(app) as client:
        # First 3 requests should succeed
        for i in range(3):
            res = client.get("/api/v1")
            assert res.status_code == 200, f"Request {i + 1} failed"
            assert int(res.headers["RateLimit-Remaining"]) == 3 - (i + 1)

        # 4th request must be rejected with 429
        rejected = client.get("/api/v1")
        assert rejected.status_code == 429
        data = rejected.json()
        assert data["code"] == "rate_limit.exceeded"
        assert data["status"] == 429
        assert "Retry-After" in rejected.headers
        assert int(rejected.headers["Retry-After"]) >= 1
        assert rejected.headers["RateLimit-Remaining"] == "0"


def test_rate_limit_per_principal_isolation() -> None:
    """Verify that one principal's rate limit exhaustion does not affect another."""
    _in_memory_windows.clear()
    settings = Settings(
        rate_limit_enabled=True,
        rate_limit_read=2,
        rate_limit_window_seconds=60,
        redis_key_prefix=f"test_{uuid.uuid4().hex[:6]}:",
    )
    app = create_app(settings=settings)

    with TestClient(app) as client:
        # User A makes 2 requests and exhausts limit
        headers_a = {"Authorization": "Bearer token_user_a"}
        res1 = client.get("/api/v1", headers=headers_a)
        assert res1.status_code == 200
        res2 = client.get("/api/v1", headers=headers_a)
        assert res2.status_code == 200
        res3 = client.get("/api/v1", headers=headers_a)
        assert res3.status_code == 429

        # User B makes requests and succeeds
        headers_b = {"Authorization": "Bearer token_user_b"}
        res_b1 = client.get("/api/v1", headers=headers_b)
        assert res_b1.status_code == 200
        assert res_b1.headers["RateLimit-Remaining"] == "1"


def test_rate_limit_exempt_paths() -> None:
    """Verify that health checks and system probes are never rate limited."""
    _in_memory_windows.clear()
    settings = Settings(
        rate_limit_enabled=True,
        rate_limit_read=1,
        rate_limit_window_seconds=60,
        redis_key_prefix=f"test_{uuid.uuid4().hex[:6]}:",
    )
    app = create_app(settings=settings)

    with TestClient(app) as client:
        # Exhaust read limit on /api/v1
        res1 = client.get("/api/v1")
        assert res1.status_code == 200
        res2 = client.get("/api/v1")
        assert res2.status_code == 429

        # /healthz and /readyz should still succeed
        h_res1 = client.get("/healthz")
        assert h_res1.status_code == 200
        h_res2 = client.get("/healthz")
        assert h_res2.status_code == 200


def test_rate_limit_route_classes_distinction() -> None:
    """Verify that distinct route classes (read vs write) have separate rate limits."""
    _in_memory_windows.clear()
    settings = Settings(
        rate_limit_enabled=True,
        rate_limit_read=2,
        rate_limit_write=10,
        rate_limit_window_seconds=60,
        redis_key_prefix=f"test_{uuid.uuid4().hex[:6]}:",
    )
    app = create_app(settings=settings)

    @app.post("/api/v1/test-write")
    @declare_permission(PERMISSION_PUBLIC)
    async def sample_write_route() -> dict[str, str]:
        return {"status": "ok"}

    with TestClient(app) as client:
        # Read route reaches limit
        assert client.get("/api/v1").status_code == 200
        assert client.get("/api/v1").status_code == 200
        assert client.get("/api/v1").status_code == 429

        # Write route (POST) should have separate write quota (limit 10)
        res_post = client.post("/api/v1/test-write")
        assert res_post.status_code == 200
        assert res_post.headers.get("RateLimit-Limit") == "10"
        assert res_post.headers.get("RateLimit-Remaining") == "9"
