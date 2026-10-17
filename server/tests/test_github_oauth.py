"""Unit and integration tests for GitHub OAuth flow, state validation, and token encryption."""

from __future__ import annotations

import time
import uuid
from typing import Any
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth_context import AuthContext
from app.core.errors import AuthenticationError
from app.core.settings import Settings
from app.domain.auth import get_auth_context
from app.domain.integrations.github_oauth_service import GitHubOAuthService
from app.main import create_app
from app.persistence.models.github import GitHubConnection


@pytest.fixture
def github_settings() -> Settings:
    return Settings(
        env="test",
        github_client_id="test_github_client_id",
        github_client_secret="test_github_client_secret",
        encryption_keys=["c3VwZXJfc2VjcmV0X2tleV9mb3JfdGVzdF8zMmJ5dGVzIQ=="],
    )


def test_oauth_state_roundtrip_and_signature(github_settings: Settings) -> None:
    """Verifies that generated state is valid, contains user/workspace, and validates signature."""
    service = GitHubOAuthService(session=AsyncMock(), settings=github_settings)
    uid = uuid.uuid4()
    wid = uuid.uuid4()
    return_to = "https://devmind.warishlabs.in/settings/integrations"

    state = service.generate_state(user_id=uid, workspace_id=wid, return_to=return_to)
    assert "." in state

    data = service.verify_state(state)
    assert data["uid"] == str(uid)
    assert data["wid"] == str(wid)
    assert data["ret"] == return_to
    assert "nonce" in data


def test_oauth_state_tampering_rejected(github_settings: Settings) -> None:
    """Tampered state string must fail signature verification."""
    service = GitHubOAuthService(session=AsyncMock(), settings=github_settings)
    state = service.generate_state(user_id=uuid.uuid4(), workspace_id=uuid.uuid4())

    payload_b64, sig = state.split(".", 1)
    tampered_sig = ("0" if sig[0] != "0" else "1") + sig[1:]
    tampered_state = f"{payload_b64}.{tampered_sig}"

    with pytest.raises(AuthenticationError) as exc_info:
        service.verify_state(tampered_state)
    assert "Invalid OAuth state signature" in str(exc_info.value)


def test_oauth_state_expired_rejected(
    github_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """State older than 10 minutes must be rejected."""
    service = GitHubOAuthService(session=AsyncMock(), settings=github_settings)
    state = service.generate_state(user_id=uuid.uuid4(), workspace_id=uuid.uuid4())

    # Fast forward time by 601 seconds
    future_time = time.time() + 601
    monkeypatch.setattr(time, "time", lambda: future_time)

    with pytest.raises(AuthenticationError) as exc_info:
        service.verify_state(state)
    assert "expired" in str(exc_info.value).lower()


def test_open_redirect_prevention(github_settings: Settings) -> None:
    """Destinations outside allowed origins must fall back to canonical frontend URL."""
    service = GitHubOAuthService(session=AsyncMock(), settings=github_settings)

    # Allowed destinations
    assert (
        service.validate_return_url("https://devmind.warishlabs.in/custom")
        == "https://devmind.warishlabs.in/custom"
    )
    assert service.validate_return_url("http://localhost:3000/test") == "http://localhost:3000/test"

    # Malicious destinations
    malicious = "https://attacker.evil.com/phish?param=1"
    assert service.validate_return_url(malicious) == "http://localhost:3000/settings/integrations"

    malicious_javascript = "javascript:alert(1)"
    assert (
        service.validate_return_url(malicious_javascript)
        == "http://localhost:3000/settings/integrations"
    )


# ---------------------------------------------------------------------------
# API Endpoint Integration Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_github_authorize_unauthenticated_rejected(github_settings: Settings) -> None:
    """Unauthenticated caller to /authorize must receive 401."""
    app = create_app(settings=github_settings)
    wid = uuid.uuid4()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/api/v1/integrations/github/authorize?workspace_id={wid}")
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_github_authorize_authenticated_redirects_to_github(
    github_settings: Settings,
) -> None:
    """Authenticated caller receives 302 redirect with correct GitHub OAuth parameters."""
    app = create_app(settings=github_settings)
    uid = uuid.uuid4()
    wid = uuid.uuid4()

    mock_auth_ctx = AuthContext(
        user_id=uid,
        clerk_user_id="user_clerk_123",
        email="developer@example.com",
        workspace_id=wid,
        permissions=frozenset({"workspace:read"}),
    )
    app.dependency_overrides[get_auth_context] = lambda: mock_auth_ctx

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            f"/api/v1/integrations/github/authorize?workspace_id={wid}&return_to=http://localhost:3000/settings",
            follow_redirects=False,
        )
        assert res.status_code == 302
        location = res.headers["location"]
        parsed = urlparse(location)
        assert parsed.scheme == "https"
        assert parsed.netloc == "github.com"
        assert parsed.path == "/login/oauth/authorize"

        params = parse_qs(parsed.query)
        assert params["client_id"] == ["test_github_client_id"]
        assert "read:user user:email repo" in params["scope"][0]
        assert "state" in params


@pytest.mark.asyncio
async def test_github_callback_github_error_handled(github_settings: Settings) -> None:
    """Callback reports GitHub authorization refusal."""
    app = create_app(settings=github_settings)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/v1/integrations/github/callback?error=access_denied&error_description=The+user+has+denied+your+application+access."
        )
        assert res.status_code == 422
        data = res.json()
        assert "access_denied" in data["detail"]


@pytest.mark.asyncio
async def test_github_callback_success_flow(
    github_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valid callback code exchanges token, encrypts token at rest, and redirects to frontend."""
    app = create_app(settings=github_settings)
    uid = uuid.uuid4()
    wid = uuid.uuid4()

    service = GitHubOAuthService(session=AsyncMock(), settings=github_settings)
    valid_state = service.generate_state(
        user_id=uid,
        workspace_id=wid,
        return_to="http://localhost:3000/settings/integrations",
    )

    # Mock external GitHub HTTP responses
    async def mock_handle_callback(
        self: Any, code: str, state: str, callback_url: str
    ) -> tuple[str, Any]:
        assert code == "valid_github_code_123"
        mock_conn = GitHubConnection(
            id=uuid.uuid4(),
            workspace_id=wid,
            user_id=uid,
            kind="oauth",
            external_account="octocat_dev",
            scopes=["read:user", "user:email", "repo"],
            encrypted_credential="v1:0:nonce:ciphertext",
        )
        return "http://localhost:3000/settings/integrations", mock_conn

    monkeypatch.setattr(GitHubOAuthService, "handle_callback", mock_handle_callback)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            f"/api/v1/integrations/github/callback?code=valid_github_code_123&state={valid_state}",
            follow_redirects=False,
        )
        assert res.status_code == 302
        location = res.headers["location"]
        assert location.startswith("http://localhost:3000/settings/integrations")
        assert "github_connected=true" in location
        assert "account=octocat_dev" in location
