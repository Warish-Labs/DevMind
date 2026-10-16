"""Tests for Me and permissions API endpoints (docs/03 §11.1)."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.requests import Request
from starlette.testclient import TestClient

from app.core.auth_context import AuthContext
from app.core.ids import generate_uuid7
from app.domain.auth import (
    get_auth_context,
    get_token_verifier,
)
from app.integrations.clerk.verifier import ClerkTokenVerifier
from app.main import create_app


@pytest.fixture(scope="module")
def rsa_key_pair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    pem_public = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_key, pem_public


def test_me_unauthenticated_request(client: TestClient) -> None:
    """Verify that /api/v1/me rejects unauthenticated callers."""
    res = client.get("/api/v1/me")
    assert res.status_code == 401
    assert res.json()["code"] == "auth.unauthenticated"


def test_me_permissions_returns_caller_context(rsa_key_pair, test_settings) -> None:
    """Verify that /api/v1/me/permissions returns the active caller permissions and roles."""
    private_key, public_key = rsa_key_pair
    app = create_app(settings=test_settings)

    verifier = ClerkTokenVerifier(settings=test_settings, static_public_key=public_key)
    app.dependency_overrides[get_token_verifier] = lambda: verifier

    user_id = generate_uuid7()
    ws_id = generate_uuid7()
    mock_ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_me_test",
        email="me@example.com",
        workspace_id=ws_id,
        workspace_role="admin",
        permissions=frozenset({"workspace:read", "workspace:manage", "project:read"}),
    )

    def override_auth(request: Request) -> AuthContext:
        request.state.auth_context = mock_ctx
        return mock_ctx

    app.dependency_overrides[get_auth_context] = override_auth

    now = int(time.time())
    token = jwt.encode(
        {"sub": "user_me_test", "iss": "https://clerk.devmind.warishlabs.in", "exp": now + 300},
        private_key,
        algorithm="RS256",
        headers={"kid": "k1"},
    )

    with TestClient(app=app) as client:
        res = client.get("/api/v1/me/permissions", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == str(user_id)
        assert data["workspace_id"] == str(ws_id)
        assert data["workspace_role"] == "admin"
        assert "workspace:manage" in data["permissions"]
