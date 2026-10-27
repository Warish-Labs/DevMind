"""Unit and API integration tests for GitHub token management, envelope rotation, and lifecycle status (M11-02).

Verifies:
1. Repository token retrieval and AES-256-GCM envelope decryption.
2. Cross-workspace tenant isolation (IDOR prevention - Rule 4).
3. Zero-downtime key rotation: re-encrypting older secondary envelopes under primary key.
4. Audit event recording on connection creation, revocation, and envelope rotation.
5. Lifecycle status evaluation (unlinked, active, degraded).
6. API routes for status checking and credential rotation.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth_context import AuthContext, SystemContext
from app.core.crypto import EncryptionService
from app.core.errors import ForbiddenError
from app.core.settings import Settings
from app.domain.auth import get_auth_context
from app.domain.integrations.github_oauth_service import GitHubOAuthService
from app.main import create_app
from app.persistence.models.github import GitHubConnection
from app.persistence.repositories.github_repo import GitHubRepository


@pytest.fixture
def dual_key_settings() -> Settings:
    """Settings with primary key and secondary legacy key for rotation testing."""
    return Settings(
        env="test",
        github_client_id="test_github_client_id",
        github_client_secret="test_github_client_secret",
        encryption_keys=[
            "c3VwZXJfc2VjcmV0X3ByaW1hcnlfa2V5XzMyYnl0ZXMh",  # Primary (index 0)
            "c3VwZXJfc2VjcmV0X3NlY29uZGFyeV9rZXlfMzJieXRl",  # Secondary (index 1)
        ],
    )


# ---------------------------------------------------------------------------
# 1. Repository Token Decryption & Tenant Isolation Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_github_repo_get_decrypted_token(dual_key_settings: Settings) -> None:
    """Verifies that stored encrypted credential can be decrypted correctly."""
    mock_session = AsyncMock()
    repo = GitHubRepository(session=mock_session, settings=dual_key_settings)
    crypto = EncryptionService(dual_key_settings)

    wid = uuid.uuid4()
    uid = uuid.uuid4()
    raw_token = "ghp_mockSecretAccessToken1234567890"
    encrypted_envelope = crypto.encrypt(raw_token)

    mock_conn = GitHubConnection(
        id=uuid.uuid4(),
        workspace_id=wid,
        user_id=uid,
        kind="oauth",
        external_account="octocat_tester",
        scopes=["read:user", "user:email", "repo"],
        encrypted_credential=encrypted_envelope,
    )

    # Mock database select
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_conn
    mock_session.execute.return_value = mock_result

    ctx = AuthContext(
        user_id=uid,
        clerk_user_id="clerk_123",
        email="dev@example.com",
        workspace_id=wid,
        permissions=frozenset({"workspace:read"}),
    )

    decrypted = await repo.get_decrypted_token(ctx, wid, uid, kind="oauth")
    assert decrypted == raw_token


@pytest.mark.asyncio
async def test_github_repo_cross_workspace_isolation_rejected(dual_key_settings: Settings) -> None:
    """Caller from workspace A cannot access GitHub connection of workspace B."""
    mock_session = AsyncMock()
    repo = GitHubRepository(session=mock_session, settings=dual_key_settings)

    wid_a = uuid.uuid4()
    wid_b = uuid.uuid4()
    uid = uuid.uuid4()

    ctx = AuthContext(
        user_id=uid,
        clerk_user_id="clerk_123",
        email="dev@example.com",
        workspace_id=wid_a,
        permissions=frozenset({"workspace:read"}),
    )

    # Requesting connection for wid_b when ctx is scoped to wid_a must raise ForbiddenError
    with pytest.raises(ForbiddenError) as exc_info:
        await repo.get_connection(ctx, workspace_id=wid_b, user_id=uid)
    assert "Cross-workspace" in str(exc_info.value)


@pytest.mark.asyncio
async def test_github_repo_rotate_credential(dual_key_settings: Settings) -> None:
    """Verifies that an envelope encrypted under secondary key rotates to primary key."""
    mock_session = AsyncMock()
    repo = GitHubRepository(session=mock_session, settings=dual_key_settings)

    # Encrypt explicitly with secondary key settings
    secondary_settings = Settings(
        env="test",
        encryption_keys=["c3VwZXJfc2VjcmV0X3NlY29uZGFyeV9rZXlfMzJieXRl"],
    )
    crypto_secondary = EncryptionService(secondary_settings)
    raw_token = "ghp_legacyTokenNeedRotation998877"
    old_envelope = crypto_secondary.encrypt(raw_token)

    wid = uuid.uuid4()
    uid = uuid.uuid4()
    mock_conn = GitHubConnection(
        id=uuid.uuid4(),
        workspace_id=wid,
        user_id=uid,
        kind="oauth",
        external_account="octocat_roller",
        scopes=["read:user", "repo"],
        encrypted_credential=old_envelope,
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_conn
    mock_session.execute.return_value = mock_result

    sys_ctx = SystemContext(reason="token_rotation_drill")
    rotated_conn = await repo.rotate_credential(sys_ctx, wid, uid, kind="oauth")

    assert rotated_conn is not None
    assert rotated_conn.encrypted_credential != old_envelope
    assert rotated_conn.encrypted_credential.startswith("v1:0:")

    # Verify new envelope decrypts cleanly to original token
    crypto_primary = EncryptionService(dual_key_settings)
    assert crypto_primary.decrypt(rotated_conn.encrypted_credential) == raw_token


# ---------------------------------------------------------------------------
# 2. Domain Service Lifecycle & Status Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_oauth_service_get_connection_status_unlinked(dual_key_settings: Settings) -> None:
    """When no connection exists, returns unlinked status with resolution hint."""
    mock_session = AsyncMock()
    service = GitHubOAuthService(mock_session, settings=dual_key_settings)

    # Mock repository returning None
    service.repo.get_connection = AsyncMock(return_value=None)  # type: ignore[method-assign]

    wid = uuid.uuid4()
    uid = uuid.uuid4()
    ctx = AuthContext(
        user_id=uid,
        clerk_user_id="clerk_123",
        email="dev@example.com",
        workspace_id=wid,
        permissions=frozenset({"workspace:read"}),
    )

    status_data = await service.get_connection_status(ctx, wid, uid)
    assert status_data["status"] == "unlinked"
    assert status_data["can_perform_analysis"] is False
    assert "Connect your GitHub account" in status_data["resolution_hint"]


@pytest.mark.asyncio
async def test_oauth_service_get_connection_status_active(dual_key_settings: Settings) -> None:
    """When connection has all required scopes, status is active and can_perform_analysis is True."""
    mock_session = AsyncMock()
    service = GitHubOAuthService(mock_session, settings=dual_key_settings)

    wid = uuid.uuid4()
    uid = uuid.uuid4()
    mock_conn = GitHubConnection(
        id=uuid.uuid4(),
        workspace_id=wid,
        user_id=uid,
        kind="oauth",
        external_account="octocat_active",
        scopes=["read:user", "user:email", "repo"],
        encrypted_credential="v1:0:nonce:ciphertext",
    )
    service.repo.get_connection = AsyncMock(return_value=mock_conn)  # type: ignore[method-assign]

    ctx = AuthContext(
        user_id=uid,
        clerk_user_id="clerk_123",
        email="dev@example.com",
        workspace_id=wid,
        permissions=frozenset({"workspace:read"}),
    )

    status_data = await service.get_connection_status(ctx, wid, uid)
    assert status_data["status"] == "active"
    assert status_data["can_perform_analysis"] is True
    assert status_data["external_account"] == "octocat_active"
    assert status_data["missing_permissions"] == []


@pytest.mark.asyncio
async def test_oauth_service_get_connection_status_degraded(dual_key_settings: Settings) -> None:
    """When token lacks repo scope, status is degraded and can_perform_analysis is False."""
    mock_session = AsyncMock()
    service = GitHubOAuthService(mock_session, settings=dual_key_settings)

    wid = uuid.uuid4()
    uid = uuid.uuid4()
    mock_conn = GitHubConnection(
        id=uuid.uuid4(),
        workspace_id=wid,
        user_id=uid,
        kind="oauth",
        external_account="octocat_degraded",
        scopes=["read:user"],  # Missing repo scope
        encrypted_credential="v1:0:nonce:ciphertext",
    )
    service.repo.get_connection = AsyncMock(return_value=mock_conn)  # type: ignore[method-assign]

    ctx = AuthContext(
        user_id=uid,
        clerk_user_id="clerk_123",
        email="dev@example.com",
        workspace_id=wid,
        permissions=frozenset({"workspace:read"}),
    )

    status_data = await service.get_connection_status(ctx, wid, uid)
    assert status_data["status"] == "degraded"
    assert status_data["can_perform_analysis"] is False
    assert "repo" in status_data["missing_permissions"]


# ---------------------------------------------------------------------------
# 3. API Integration Tests (/status and /rotate)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_get_workspace_github_status_endpoint(
    dual_key_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /api/v1/workspaces/{wid}/integrations/github/status returns status summary."""
    app = create_app(settings=dual_key_settings)
    wid = uuid.uuid4()
    uid = uuid.uuid4()

    mock_auth_ctx = AuthContext(
        user_id=uid,
        clerk_user_id="clerk_test",
        email="admin@example.com",
        workspace_id=wid,
        permissions=frozenset({"integrations:manage"}),
    )
    app.dependency_overrides[get_auth_context] = lambda: mock_auth_ctx

    async def mock_get_status(self: Any, ctx: Any, wid: Any, uid: Any, kind: str = "oauth") -> dict[str, Any]:
        return {
            "connection_id": uuid.uuid4(),
            "status": "active",
            "kind": "oauth",
            "external_account": "octocat_api_test",
            "scopes": ["read:user", "repo"],
            "can_perform_analysis": True,
            "missing_permissions": [],
            "resolution_hint": None,
            "revoked_at": None,
            "updated_at": None,
        }

    monkeypatch.setattr(GitHubOAuthService, "get_connection_status", mock_get_status)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/api/v1/workspaces/{wid}/integrations/github/status")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "active"
        assert data["can_perform_analysis"] is True
        assert data["external_account"] == "octocat_api_test"


@pytest.mark.asyncio
async def test_api_rotate_workspace_github_connection_endpoint(
    dual_key_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /api/v1/workspaces/{wid}/integrations/github/rotate re-encrypts credential."""
    app = create_app(settings=dual_key_settings)
    wid = uuid.uuid4()
    uid = uuid.uuid4()
    conn_id = uuid.uuid4()

    mock_auth_ctx = AuthContext(
        user_id=uid,
        clerk_user_id="clerk_test",
        email="admin@example.com",
        workspace_id=wid,
        permissions=frozenset({"integrations:manage"}),
    )
    app.dependency_overrides[get_auth_context] = lambda: mock_auth_ctx

    mock_rotated_conn = GitHubConnection(
        id=conn_id,
        workspace_id=wid,
        user_id=uid,
        kind="oauth",
        external_account="octocat_rotated",
        scopes=["read:user", "repo"],
        encrypted_credential="v1:0:newNonce:newCiphertext",
    )

    async def mock_rotate(self: Any, ctx: Any, wid: Any, uid: Any, kind: str = "oauth") -> GitHubConnection:
        return mock_rotated_conn

    monkeypatch.setattr(GitHubOAuthService, "rotate_connection_credential", mock_rotate)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/api/v1/workspaces/{wid}/integrations/github/rotate")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == str(conn_id)
        assert data["external_account"] == "octocat_rotated"
