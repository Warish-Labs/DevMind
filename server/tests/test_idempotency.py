"""Unit and integration tests for Idempotency middleware (docs/03 §10)."""

import uuid
from typing import Any

from fastapi import Request
from starlette.testclient import TestClient

from app.core.settings import Settings
from app.domain.auth import PERMISSION_PUBLIC, declare_permission
from app.main import create_app
from app.middleware.idempotency import require_idempotency_key


def test_missing_idempotency_key_on_required_route() -> None:
    """POST to scans/jobs/analyses/snippets/consents without Idempotency-Key returns 422."""
    settings = Settings(
        redis_key_prefix=f"test_{uuid.uuid4().hex[:6]}:",
    )
    app = create_app(settings=settings)

    # Register sample job route matching required pattern
    @app.post("/api/v1/projects/{pid}/analyses")
    @declare_permission(PERMISSION_PUBLIC)
    async def create_analysis(pid: str) -> dict[str, Any]:
        return {"job_id": str(uuid.uuid4()), "status": "queued"}

    with TestClient(app) as client:
        # Request WITHOUT Idempotency-Key header
        res = client.post("/api/v1/projects/proj-123/analyses", json={"type": "security"})
        assert res.status_code == 422
        data = res.json()
        assert data["code"] == "validation.failed"
        assert "Idempotency-Key" in data["detail"]


def test_idempotent_replay_returns_cached_response() -> None:
    """Same Idempotency-Key and payload returns original response with Idempotent-Replay: true."""
    settings = Settings(
        redis_key_prefix=f"test_{uuid.uuid4().hex[:6]}:",
    )
    app = create_app(settings=settings)
    call_count = 0

    @app.post("/api/v1/projects/{pid}/analyses")
    @declare_permission(PERMISSION_PUBLIC)
    async def create_analysis(pid: str) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        return {"job_id": f"job-{call_count}", "status": "queued"}

    with TestClient(app) as client:
        key = f"key-{uuid.uuid4()}"
        headers = {"Idempotency-Key": key}
        payload = {"type": "architecture", "scope": "full"}

        # First execution
        res1 = client.post("/api/v1/projects/proj-1/analyses", json=payload, headers=headers)
        assert res1.status_code == 200
        assert res1.headers.get("Idempotent-Replay") == "false"
        assert res1.json()["job_id"] == "job-1"
        assert call_count == 1

        # Second execution with same key and payload
        res2 = client.post("/api/v1/projects/proj-1/analyses", json=payload, headers=headers)
        assert res2.status_code == 200
        assert res2.headers.get("Idempotent-Replay") == "true"
        # Handler must NOT have been called again
        assert res2.json()["job_id"] == "job-1"
        assert call_count == 1


def test_idempotency_mismatch_returns_422() -> None:
    """Same Idempotency-Key with different payload returns 422 idempotency.mismatch."""
    settings = Settings(
        redis_key_prefix=f"test_{uuid.uuid4().hex[:6]}:",
    )
    app = create_app(settings=settings)

    @app.post("/api/v1/projects/{pid}/analyses")
    @declare_permission(PERMISSION_PUBLIC)
    async def create_analysis(pid: str, req: Request) -> dict[str, Any]:
        data = await req.json()
        return {"job_id": str(uuid.uuid4()), "type": data.get("type")}

    with TestClient(app) as client:
        key = f"key-{uuid.uuid4()}"
        headers = {"Idempotency-Key": key}

        # First request
        res1 = client.post(
            "/api/v1/projects/proj-1/analyses",
            json={"type": "first_type"},
            headers=headers,
        )
        assert res1.status_code == 200

        # Second request with SAME key but DIFFERENT body
        res2 = client.post(
            "/api/v1/projects/proj-1/analyses",
            json={"type": "different_type"},
            headers=headers,
        )
        assert res2.status_code == 422
        data = res2.json()
        assert data["code"] == "idempotency.mismatch"
        assert data["status"] == 422


def test_explicit_require_idempotency_key_decorator() -> None:
    """Endpoints decorated with @require_idempotency_key enforce header."""
    settings = Settings(
        redis_key_prefix=f"test_{uuid.uuid4().hex[:6]}:",
    )
    app = create_app(settings=settings)

    @app.post("/api/v1/custom-operation")
    @declare_permission(PERMISSION_PUBLIC)
    @require_idempotency_key
    async def custom_op() -> dict[str, str]:
        return {"status": "created"}

    with TestClient(app) as client:
        # Fails without header
        res_fail = client.post("/api/v1/custom-operation")
        assert res_fail.status_code == 422
        assert res_fail.json()["code"] == "validation.failed"

        # Succeeds with header
        key = f"key-{uuid.uuid4()}"
        res_ok = client.post("/api/v1/custom-operation", headers={"Idempotency-Key": key})
        assert res_ok.status_code == 200
        assert res_ok.json()["status"] == "created"


def test_get_requests_ignore_idempotency_key() -> None:
    """Safe read requests (GET) ignore Idempotency-Key and are not cached."""
    settings = Settings(
        redis_key_prefix=f"test_{uuid.uuid4().hex[:6]}:",
    )
    app = create_app(settings=settings)
    counter = 0

    @app.get("/api/v1/counter")
    @declare_permission(PERMISSION_PUBLIC)
    async def get_counter() -> dict[str, int]:
        nonlocal counter
        counter += 1
        return {"count": counter}

    with TestClient(app) as client:
        key = "get-key-1"
        res1 = client.get("/api/v1/counter", headers={"Idempotency-Key": key})
        assert res1.status_code == 200
        assert res1.json()["count"] == 1

        res2 = client.get("/api/v1/counter", headers={"Idempotency-Key": key})
        assert res2.status_code == 200
        assert res2.json()["count"] == 2  # Handled fresh, not replayed
        assert "Idempotent-Replay" not in res2.headers


def test_downstream_error_not_cached_as_idempotent() -> None:
    """If downstream returns 4xx/5xx, subsequent request with same key is executed fresh."""
    settings = Settings(
        redis_key_prefix=f"test_{uuid.uuid4().hex[:6]}:",
    )
    app = create_app(settings=settings)
    fail = True

    @app.post("/api/v1/flaky")
    @declare_permission(PERMISSION_PUBLIC)
    async def flaky_route() -> dict[str, str]:
        nonlocal fail
        if fail:
            from fastapi import HTTPException

            raise HTTPException(status_code=400, detail="Temporary bad input")
        return {"status": "recovered"}

    with TestClient(app) as client:
        key = f"flaky-key-{uuid.uuid4()}"
        headers = {"Idempotency-Key": key}

        # First request fails (400)
        res1 = client.post("/api/v1/flaky", headers=headers)
        assert res1.status_code == 400

        # Change state so next request succeeds
        fail = False
        res2 = client.post("/api/v1/flaky", headers=headers)
        assert res2.status_code == 200
        assert res2.json()["status"] == "recovered"
        assert res2.headers.get("Idempotent-Replay") == "false"
