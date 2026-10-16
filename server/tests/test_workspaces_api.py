"""Tests for Workspaces REST API endpoints (docs/03 §11.1, docs/07 §3)."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.testclient import TestClient

from app.core.auth_context import AuthContext
from app.core.ids import generate_uuid7
from app.core.settings import Settings
from app.domain.auth import (
    PERM_WORKSPACE_READ,
    PERMISSION_AUTHENTICATED,
    get_auth_context,
    get_token_verifier,
)
from app.integrations.clerk.verifier import ClerkTokenVerifier
from app.main import create_app


@pytest.fixture(scope="module")
def rsa_key_pair():
    """Generate RSA key pair for testing token signing and verification."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    pem_public = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_key, pem_public


def make_test_token(private_key, sub: str = "user_test_1", email: str = "test@example.com") -> str:
    """Generate a signed test JWT."""
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "iss": "https://clerk.devmind.warishlabs.in",
        "exp": now + 3600,
        "iat": now,
        "azp": "http://localhost:3000",
    }
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "test-kid"})


def test_workspaces_unauthenticated_requests(client: TestClient) -> None:
    """Verify that requests without Authorization header receive 401 Problem Details."""
    # List workspaces
    res = client.get("/api/v1/workspaces")
    assert res.status_code == 401
    problem = res.json()
    assert problem["code"] == "auth.unauthenticated"
    assert problem["status"] == 401

    # Create workspace
    res = client.post("/api/v1/workspaces", json={"name": "Test", "slug": "test"})
    assert res.status_code == 401
    assert res.json()["code"] == "auth.unauthenticated"


def test_workspaces_validation_errors(rsa_key_pair, test_settings) -> None:
    """Verify that malformed workspace requests return 422 Problem Details."""
    private_key, public_key = rsa_key_pair
    app = create_app(settings=test_settings)

    # Mock verifier to trust our public key
    verifier = ClerkTokenVerifier(settings=test_settings, static_public_key=public_key)
    app.dependency_overrides[get_token_verifier] = lambda: verifier

    # Mock auth context to bypass DB lookup for validation test
    mock_ctx = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_val",
        email="val@example.com",
        permissions=frozenset({PERMISSION_AUTHENTICATED}),
    )
    app.dependency_overrides[get_auth_context] = lambda: mock_ctx

    with TestClient(app=app) as client:
        token = make_test_token(private_key, sub="user_val")
        headers = {"Authorization": f"Bearer {token}"}

        # Empty name
        res = client.post(
            "/api/v1/workspaces", json={"name": "", "slug": "valid-slug"}, headers=headers
        )
        assert res.status_code == 422
        assert res.json()["code"] == "validation.failed"

        # Invalid slug (uppercase and symbols)
        res = client.post(
            "/api/v1/workspaces", json={"name": "Valid", "slug": "Invalid_Slug!"}, headers=headers
        )
        assert res.status_code == 422
        assert res.json()["code"] == "validation.failed"


def test_workspaces_forbidden_without_permission(rsa_key_pair, test_settings) -> None:
    """Verify that caller lacking required workspace permission receives 403 Problem Details."""
    private_key, public_key = rsa_key_pair
    app = create_app(settings=test_settings)

    verifier = ClerkTokenVerifier(settings=test_settings, static_public_key=public_key)
    app.dependency_overrides[get_token_verifier] = lambda: verifier

    # Caller has viewer role (workspace:read only), lacks workspace:manage
    ws_id = generate_uuid7()
    mock_ctx = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_viewer",
        email="viewer@example.com",
        workspace_id=ws_id,
        workspace_role="viewer",
        permissions=frozenset({PERMISSION_AUTHENTICATED, PERM_WORKSPACE_READ}),
    )
    app.dependency_overrides[get_auth_context] = lambda: mock_ctx

    with TestClient(app=app) as client:
        token = make_test_token(private_key, sub="user_viewer")
        headers = {"Authorization": f"Bearer {token}"}

        # Attempt to patch workspace (requires PERM_WORKSPACE_MANAGE)
        res = client.patch(
            f"/api/v1/workspaces/{ws_id}", json={"name": "New Name"}, headers=headers
        )
        assert res.status_code == 403
        assert res.json()["code"] == "auth.forbidden"

        # Attempt to add member (requires PERM_MEMBERS_MANAGE_WORKSPACE)
        res = client.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"user_id": str(generate_uuid7()), "role": "member"},
            headers=headers,
        )
        assert res.status_code == 403
        assert res.json()["code"] == "auth.forbidden"


def test_workspaces_crud_lifecycle_live_db(rsa_key_pair) -> None:
    """End-to-end functional test of workspace CRUD endpoints against live DB."""
    import os

    db_url = os.getenv("DEVMIND_DATABASE_URL")
    if not db_url:
        pytest.skip("DEVMIND_DATABASE_URL not set; skipping live DB test")

    private_key, public_key = rsa_key_pair
    settings = Settings(database_url=db_url, env="test")
    app = create_app(settings=settings)

    verifier = ClerkTokenVerifier(settings=settings, static_public_key=public_key)
    app.dependency_overrides[get_token_verifier] = lambda: verifier

    test_sub = f"user_ws_live_{generate_uuid7().hex[:8]}"
    test_email = f"{test_sub}@example.com"
    token = make_test_token(private_key, sub=test_sub, email=test_email)
    headers = {"Authorization": f"Bearer {token}"}

    with TestClient(app=app) as client:
        # 1. Create workspace
        ws_slug = f"ws-api-{generate_uuid7().hex[:8]}"
        res = client.post(
            "/api/v1/workspaces",
            json={"name": "Live Test Workspace", "slug": ws_slug, "kind": "personal"},
            headers=headers,
        )
        assert res.status_code == 201, res.text
        ws_data = res.json()
        ws_id = ws_data["id"]
        assert ws_data["slug"] == ws_slug

        # 2. Get workspace
        res = client.get(f"/api/v1/workspaces/{ws_id}", headers=headers)
        assert res.status_code == 200
        assert res.json()["name"] == "Live Test Workspace"

        # 3. Patch workspace
        res = client.patch(
            f"/api/v1/workspaces/{ws_id}",
            json={"name": "Updated Live Workspace"},
            headers=headers,
        )
        assert res.status_code == 200
        assert res.json()["name"] == "Updated Live Workspace"

        # 4. List workspaces
        res = client.get("/api/v1/workspaces", headers=headers)
        assert res.status_code == 200
        items = res.json()
        assert any(item["id"] == ws_id for item in items)
