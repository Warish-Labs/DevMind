"""Unit and integration tests for Cloudflare Turnstile verification and public endpoints."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.errors import TurnstileError
from app.core.settings import Settings
from app.core.turnstile import (
    CLOUDFLARE_TEST_SECRET_PASS,
    TurnstileVerifier,
)
from app.main import create_app


@pytest.fixture
def base_settings() -> Settings:
    return Settings(
        env="test",
        turnstile_secret_key=CLOUDFLARE_TEST_SECRET_PASS,
        turnstile_timeout_seconds=2.0,
    )


@pytest.mark.asyncio
async def test_turnstile_missing_token_raises_400(base_settings: Settings) -> None:
    """Missing or empty token must raise 400 with turnstile.missing_token."""
    verifier = TurnstileVerifier(settings=base_settings)
    with pytest.raises(TurnstileError) as exc_info:
        await verifier.verify("")
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "turnstile.missing_token"

    with pytest.raises(TurnstileError) as exc_info2:
        await verifier.verify(None)
    assert exc_info2.value.status_code == 400
    assert exc_info2.value.code == "turnstile.missing_token"


@pytest.mark.asyncio
async def test_turnstile_success_with_mock(
    monkeypatch: pytest.MonkeyPatch, base_settings: Settings
) -> None:
    """Successful Cloudflare response returns True."""
    verifier = TurnstileVerifier(settings=base_settings)

    async def mock_post(self: Any, url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "success": True,
                "challenge_ts": "2026-10-17T12:00:00Z",
                "hostname": "devmind.warishlabs.in",
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    result = await verifier.verify("valid-turnstile-token", remote_ip="1.2.3.4")
    assert result is True


@pytest.mark.asyncio
async def test_turnstile_invalid_token_raises_403(
    monkeypatch: pytest.MonkeyPatch, base_settings: Settings
) -> None:
    """Rejected token raises 403 with turnstile.invalid_token."""
    verifier = TurnstileVerifier(settings=base_settings)

    async def mock_post(self: Any, url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={"success": False, "error-codes": ["invalid-input-response"]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    with pytest.raises(TurnstileError) as exc_info:
        await verifier.verify("bad-token")
    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "turnstile.invalid_token"


@pytest.mark.asyncio
async def test_turnstile_duplicate_or_expired_raises_403(
    monkeypatch: pytest.MonkeyPatch, base_settings: Settings
) -> None:
    """Expired or already-used token raises 403 with turnstile.duplicate_or_expired."""
    verifier = TurnstileVerifier(settings=base_settings)

    async def mock_post(self: Any, url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={"success": False, "error-codes": ["timeout-or-duplicate"]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    with pytest.raises(TurnstileError) as exc_info:
        await verifier.verify("expired-token")
    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "turnstile.duplicate_or_expired"


@pytest.mark.asyncio
async def test_turnstile_timeout_raises_504(
    monkeypatch: pytest.MonkeyPatch, base_settings: Settings
) -> None:
    """Timeout during Cloudflare call must raise 504 and fail closed."""
    verifier = TurnstileVerifier(settings=base_settings)

    async def mock_post(self: Any, url: str, **kwargs: Any) -> httpx.Response:
        raise httpx.TimeoutException("Cloudflare verify timed out")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    with pytest.raises(TurnstileError) as exc_info:
        await verifier.verify("token")
    assert exc_info.value.status_code == 504
    assert exc_info.value.code == "turnstile.timeout"


@pytest.mark.asyncio
async def test_turnstile_connection_error_raises_502(
    monkeypatch: pytest.MonkeyPatch, base_settings: Settings
) -> None:
    """Network connection failure must raise 502 and fail closed."""
    verifier = TurnstileVerifier(settings=base_settings)

    async def mock_post(self: Any, url: str, **kwargs: Any) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    with pytest.raises(TurnstileError) as exc_info:
        await verifier.verify("token")
    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "turnstile.connection_error"


@pytest.mark.asyncio
async def test_turnstile_upstream_500_raises_502(
    monkeypatch: pytest.MonkeyPatch, base_settings: Settings
) -> None:
    """Cloudflare upstream 5xx response raises 502."""
    verifier = TurnstileVerifier(settings=base_settings)

    async def mock_post(self: Any, url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(
            status_code=500,
            text="Internal Server Error",
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    with pytest.raises(TurnstileError) as exc_info:
        await verifier.verify("token")
    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "turnstile.upstream_error"


@pytest.mark.asyncio
async def test_turnstile_unconfigured_production_raises_500() -> None:
    """Production environment with no secret key must raise 500 error."""
    prod_settings = Settings(env="production", turnstile_secret_key=None)
    verifier = TurnstileVerifier(settings=prod_settings)
    with pytest.raises(TurnstileError) as exc_info:
        await verifier.verify("any-token")
    assert exc_info.value.status_code == 500
    assert exc_info.value.code == "turnstile.not_configured"


# ---------------------------------------------------------------------------
# API Integration Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_waitlist_endpoint_success(
    monkeypatch: pytest.MonkeyPatch, base_settings: Settings
) -> None:
    """POST /api/v1/public/waitlist succeeds with valid turnstile token."""
    app = create_app(settings=base_settings)

    async def mock_verify(token: str | None, remote_ip: str | None = None, **kwargs: Any) -> bool:
        return True

    monkeypatch.setattr("app.api.public.verify_turnstile_token", mock_verify)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/public/waitlist",
            json={"email": "developer@example.com", "turnstile_token": "valid-token"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "received"
        assert data["email"] == "developer@example.com"


@pytest.mark.asyncio
async def test_public_waitlist_endpoint_invalid_token_rejected(
    monkeypatch: pytest.MonkeyPatch, base_settings: Settings
) -> None:
    """POST /api/v1/public/waitlist is rejected when turnstile token is invalid."""
    app = create_app(settings=base_settings)

    async def mock_verify_invalid(
        token: str | None, remote_ip: str | None = None, **kwargs: Any
    ) -> bool:
        raise TurnstileError(
            detail="Turnstile verification failed",
            code="turnstile.invalid_token",
            status_code=403,
        )

    monkeypatch.setattr("app.api.public.verify_turnstile_token", mock_verify_invalid)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/public/waitlist",
            json={"email": "developer@example.com", "turnstile_token": "invalid-token"},
        )
        assert res.status_code == 403
        data = res.json()
        assert data["code"] == "turnstile.invalid_token"


@pytest.mark.asyncio
async def test_public_waitlist_endpoint_missing_token_rejected(base_settings: Settings) -> None:
    """POST /api/v1/public/waitlist rejects request with missing token (validation error)."""
    app = create_app(settings=base_settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/public/waitlist",
            json={"email": "developer@example.com"},
        )
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_public_contact_endpoint_success(
    monkeypatch: pytest.MonkeyPatch, base_settings: Settings
) -> None:
    """POST /api/v1/public/contact succeeds with valid turnstile token."""
    app = create_app(settings=base_settings)

    async def mock_verify(token: str | None, remote_ip: str | None = None, **kwargs: Any) -> bool:
        return True

    monkeypatch.setattr("app.api.public.verify_turnstile_token", mock_verify)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/public/contact",
            json={
                "name": "Jane Developer",
                "email": "jane@example.com",
                "subject": "architecture inquiry",
                "message": "Interested in deploying continuous brain locally.",
                "turnstile_token": "valid-token",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "received"


@pytest.mark.asyncio
async def test_public_contact_endpoint_invalid_token_rejected(
    monkeypatch: pytest.MonkeyPatch, base_settings: Settings
) -> None:
    """POST /api/v1/public/contact fails if token verification fails."""
    app = create_app(settings=base_settings)

    async def mock_verify_duplicate(
        token: str | None, remote_ip: str | None = None, **kwargs: Any
    ) -> bool:
        raise TurnstileError(
            detail="Turnstile token expired or already used",
            code="turnstile.duplicate_or_expired",
            status_code=403,
        )

    monkeypatch.setattr("app.api.public.verify_turnstile_token", mock_verify_duplicate)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/public/contact",
            json={
                "name": "Jane Developer",
                "email": "jane@example.com",
                "subject": "architecture inquiry",
                "message": "Interested in deploying continuous brain locally.",
                "turnstile_token": "expired-token",
            },
        )
        assert res.status_code == 403
        data = res.json()
        assert data["code"] == "turnstile.duplicate_or_expired"
        assert data["code"] == "turnstile.duplicate_or_expired"
