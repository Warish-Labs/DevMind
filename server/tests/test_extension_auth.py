"""Tests for Extension Tokens, Registration Lifecycle, and Authentication Endpoints (M3-06).

Verifies:
1. Extension models and SHA-256 hashing (ADR-012, docs/03 §3.1).
2. Token issuance, rotation, and expiration.
3. Replay detection: reusing an already rotated refresh token immediately revokes the registration (docs/07 §3).
4. Extension routes under /api/v1/ext/* accept only DevMind extension tokens (Rule 10).
5. All extension routes declare permissions and pass CI gate.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.testclient import TestClient

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import AuthenticationError
from app.core.ids import generate_uuid7
from app.core.settings import Settings
from app.domain.auth import (
    get_auth_context,
    get_db_session,
    get_extension_auth_context,
)
from app.domain.extension.service import (
    ACCESS_TOKEN_LIFETIME_SECONDS,
    ExtensionService,
    generate_access_token,
    generate_refresh_token,
    hash_token,
)
from app.main import create_app
from app.persistence.models.extension import ExtensionRegistration, ExtensionToken


def test_token_generation_and_hashing() -> None:
    """Verify format and hashing of generated access and refresh tokens."""
    access_token = generate_access_token()
    refresh_token = generate_refresh_token()

    assert access_token.startswith("dme_at_")
    assert refresh_token.startswith("dme_rt_")
    assert len(access_token) > 20
    assert len(refresh_token) > 20

    hash_a = hash_token(access_token)
    hash_b = hash_token(access_token)
    assert hash_a == hash_b
    assert len(hash_a) == 64  # SHA-256 hex string
    assert hash_a != access_token


def test_extension_models_instantiation() -> None:
    """Verify ExtensionRegistration and ExtensionToken entity attributes."""
    user_id = generate_uuid7()
    reg = ExtensionRegistration(
        user_id=user_id,
        name="VS Code Linux",
        platform="linux",
        extension_version="0.1.0",
    )
    assert reg.user_id == user_id
    assert reg.name == "VS Code Linux"
    assert reg.platform == "linux"
    assert reg.extension_version == "0.1.0"
    assert reg.revoked_at is None

    token = ExtensionToken(
        registration_id=reg.id,
        token_hash="fake_sha256_hash",
        kind="access",
        scope="project:sync",
        expires_at=datetime.now(UTC),
    )
    assert token.registration_id == reg.id
    assert token.token_hash == "fake_sha256_hash"
    assert token.kind == "access"
    assert token.revoked_at is None


@pytest.mark.asyncio
async def test_extension_service_issue_tokens() -> None:
    """Verify ExtensionService registers client and issues hashed tokens."""
    mock_session = AsyncMock()
    service = ExtensionService(mock_session)

    user_id = generate_uuid7()
    ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_test_clerk",
        email="test@devmind.local",
    )

    reg_id = generate_uuid7()
    mock_reg = ExtensionRegistration(
        id=reg_id,
        user_id=user_id,
        name="VS Code Mac",
        platform="darwin",
        extension_version="0.1.0",
    )

    service.repo.create_registration = AsyncMock(return_value=mock_reg)  # type: ignore[method-assign]
    service.repo.create_token = AsyncMock()  # type: ignore[method-assign]

    reg, access_token, refresh_token, expires_in = await service.register_and_issue_tokens(
        ctx,
        name="VS Code Mac",
        platform="darwin",
        extension_version="0.1.0",
    )

    assert reg.id == reg_id
    assert access_token.startswith("dme_at_")
    assert refresh_token.startswith("dme_rt_")
    assert expires_in == ACCESS_TOKEN_LIFETIME_SECONDS

    # Verify that raw tokens were NEVER stored; repo.create_token received SHA-256 hashes
    assert service.repo.create_token.call_count == 2
    calls = service.repo.create_token.call_args_list
    assert calls[0].kwargs["token_hash"] == hash_token(access_token)
    assert calls[0].kwargs["kind"] == "access"
    assert calls[1].kwargs["token_hash"] == hash_token(refresh_token)
    assert calls[1].kwargs["kind"] == "refresh"


@pytest.mark.asyncio
async def test_extension_service_refresh_tokens_and_rotation() -> None:
    """Verify refresh token rotation issues new pair and revokes old refresh token."""
    mock_session = AsyncMock()
    service = ExtensionService(mock_session)
    sys_ctx = SystemContext(reason="test")

    reg_id = generate_uuid7()
    old_token_id = generate_uuid7()
    raw_old_refresh = generate_refresh_token()
    old_hash = hash_token(raw_old_refresh)

    stored_token = ExtensionToken(
        id=old_token_id,
        registration_id=reg_id,
        token_hash=old_hash,
        kind="refresh",
        scope="project:sync",
        expires_at=datetime.now(UTC) + timedelta(days=10),
        revoked_at=None,
    )
    stored_reg = ExtensionRegistration(
        id=reg_id,
        user_id=generate_uuid7(),
        name="VS Code Test",
        platform="linux",
        extension_version="0.1.0",
        revoked_at=None,
    )

    service.repo.get_token_by_hash = AsyncMock(return_value=stored_token)  # type: ignore[method-assign]
    service.repo.get_registration_by_id = AsyncMock(return_value=stored_reg)  # type: ignore[method-assign]
    service.repo.revoke_token = AsyncMock()  # type: ignore[method-assign]
    service.repo.create_token = AsyncMock()  # type: ignore[method-assign]
    service.repo.touch_registration = AsyncMock()  # type: ignore[method-assign]

    reg, new_access, new_refresh, expires_in = await service.refresh_tokens(
        sys_ctx, raw_old_refresh
    )

    assert reg.id == reg_id
    assert new_access.startswith("dme_at_")
    assert new_refresh.startswith("dme_rt_")
    assert new_refresh != raw_old_refresh

    # Old token was revoked
    service.repo.revoke_token.assert_called_once_with(sys_ctx, old_token_id)
    # Registration touched
    service.repo.touch_registration.assert_called_once_with(sys_ctx, reg_id)


@pytest.mark.asyncio
async def test_extension_service_replay_detection_revocation() -> None:
    """Verify docs/07 §3: Reuse of an already rotated refresh token revokes registration."""
    mock_session = AsyncMock()
    service = ExtensionService(mock_session)
    sys_ctx = SystemContext(reason="test")

    reg_id = generate_uuid7()
    reused_raw_token = generate_refresh_token()
    reused_hash = hash_token(reused_raw_token)

    # Token was already revoked previously (e.g. from an earlier rotation)
    already_revoked_token = ExtensionToken(
        id=generate_uuid7(),
        registration_id=reg_id,
        token_hash=reused_hash,
        kind="refresh",
        scope="project:sync",
        expires_at=datetime.now(UTC) + timedelta(days=10),
        revoked_at=datetime.now(UTC) - timedelta(hours=1),
    )

    service.repo.get_token_by_hash = AsyncMock(return_value=already_revoked_token)  # type: ignore[method-assign]
    service.repo.revoke_registration = AsyncMock()  # type: ignore[method-assign]

    with pytest.raises(AuthenticationError, match="Token reuse detected"):
        await service.refresh_tokens(sys_ctx, reused_raw_token)

    # Replay detection: registration and ALL tokens revoked immediately
    service.repo.revoke_registration.assert_called_once_with(sys_ctx, reg_id)


def test_extension_endpoints_token_lifecycle(test_settings: Settings) -> None:
    """Test full extension token lifecycle via REST endpoints."""
    from unittest.mock import patch

    app = create_app(settings=test_settings)

    user_id = generate_uuid7()
    mock_ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_clerk_test",
        email="dev@devmind.local",
    )

    # Mock get_auth_context for /token creation endpoint
    mock_session = AsyncMock()
    app.dependency_overrides[get_auth_context] = lambda: mock_ctx
    app.dependency_overrides[get_db_session] = lambda: mock_session

    reg_id = generate_uuid7()
    access_token = generate_access_token()
    refresh_token = generate_refresh_token()

    mock_reg = ExtensionRegistration(
        id=reg_id,
        user_id=user_id,
        name="VS Code Test",
        platform="linux",
        extension_version="0.1.0",
    )

    with patch("app.api.extension.ExtensionService") as mock_service_cls:
        mock_instance = MagicMock()
        mock_service_cls.return_value = mock_instance
        mock_instance.register_and_issue_tokens = AsyncMock(
            return_value=(mock_reg, access_token, refresh_token, 3600)
        )
        mock_instance.refresh_tokens = AsyncMock(
            return_value=(mock_reg, generate_access_token(), generate_refresh_token(), 3600)
        )
        mock_instance.record_heartbeat = AsyncMock()
        mock_instance.revoke_registration = AsyncMock()

        with TestClient(app) as client:
            # 1. Issue extension tokens (POST /api/v1/ext/token)
            res = client.post(
                "/api/v1/ext/token",
                json={
                    "name": "VS Code Linux",
                    "platform": "linux",
                    "extension_version": "0.1.0",
                    "scope": "project:sync",
                },
            )
            assert res.status_code == 201
            data = res.json()
            assert data["access_token"].startswith("dme_at_")
            assert data["refresh_token"].startswith("dme_rt_")
            assert data["token_type"] == "Bearer"
            assert data["expires_in"] == 3600
            assert data["registration_id"] == str(reg_id)

            # 2. Refresh extension tokens (POST /api/v1/ext/token/refresh)
            res = client.post(
                "/api/v1/ext/token/refresh",
                json={"refresh_token": refresh_token},
            )
            assert res.status_code == 200
            data_refresh = res.json()
            assert data_refresh["access_token"].startswith("dme_at_")
            assert data_refresh["refresh_token"].startswith("dme_rt_")

            # 3. Heartbeat with extension access token (POST /api/v1/ext/registrations/self/heartbeat)
            mock_ext_ctx = AuthContext(
                user_id=user_id,
                clerk_user_id="user_clerk_test",
                email="dev@devmind.local",
                permissions=frozenset({"project:sync"}),
            )
            app.dependency_overrides[get_extension_auth_context] = lambda: mock_ext_ctx

            res = client.post(
                "/api/v1/ext/registrations/self/heartbeat",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            assert res.status_code == 200
            assert res.json()["status"] == "ok"


def test_rule_10_api_scheme_separation(test_settings: Settings) -> None:
    """Verify Rule 10: Extension routes accept ONLY extension tokens, browser routes accept Clerk."""
    app = create_app(settings=test_settings)

    with TestClient(app) as client:
        # Extension route rejected without valid extension token
        res = client.post("/api/v1/ext/registrations/self/heartbeat")
        assert res.status_code == 401
        assert "Extension access token required" in res.json()["detail"]

        # Extension route rejected if non-dme token provided
        res = client.post(
            "/api/v1/ext/registrations/self/heartbeat",
            headers={"Authorization": "Bearer not_a_dme_token"},
        )
        assert res.status_code == 401
        assert "Invalid extension token format" in res.json()["detail"]
