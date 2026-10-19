"""Tests for Projects REST API endpoints (docs/03 §11.1, docs/07 §3)."""

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
    PERM_PROJECT_DELETE,
    PERM_PROJECT_READ,
    PERM_PROJECT_UPDATE,
    PERM_WORKSPACE_MANAGE,
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


def make_test_token(private_key, sub: str = "user_proj_test") -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "iss": "https://clerk.devmind.warishlabs.in",
        "exp": now + 3600,
        "iat": now,
        "azp": "http://localhost:3000",
    }
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "test-kid"})


def test_projects_unauthenticated_requests(client: TestClient) -> None:
    """Verify that unauthenticated project requests receive 401 Problem Details."""
    wid = generate_uuid7()
    pid = generate_uuid7()

    res = client.get(f"/api/v1/workspaces/{wid}/projects")
    assert res.status_code == 401
    assert res.json()["code"] == "auth.unauthenticated"

    res = client.get(f"/api/v1/projects/{pid}")
    assert res.status_code == 401
    assert res.json()["code"] == "auth.unauthenticated"


def test_projects_validation_errors(rsa_key_pair, test_settings) -> None:
    """Verify that invalid project creation requests return 422 Problem Details."""
    private_key, public_key = rsa_key_pair
    app = create_app(settings=test_settings)

    verifier = ClerkTokenVerifier(settings=test_settings, static_public_key=public_key)
    app.dependency_overrides[get_token_verifier] = lambda: verifier

    wid = generate_uuid7()
    mock_ctx = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_proj_val",
        email="proj_val@example.com",
        workspace_id=wid,
        workspace_role="admin",
        permissions=frozenset(
            {PERMISSION_AUTHENTICATED, PERM_WORKSPACE_READ, PERM_WORKSPACE_MANAGE}
        ),
    )
    app.dependency_overrides[get_auth_context] = lambda: mock_ctx

    with TestClient(app=app) as client:
        token = make_test_token(private_key, sub="user_proj_val")
        headers = {"Authorization": f"Bearer {token}"}

        # Empty project name
        res = client.post(
            f"/api/v1/workspaces/{wid}/projects",
            json={"name": "", "slug": "valid-slug"},
            headers=headers,
        )
        assert res.status_code == 422
        assert res.json()["code"] == "validation.failed"

        # Invalid slug format
        res = client.post(
            f"/api/v1/workspaces/{wid}/projects",
            json={"name": "Valid Name", "slug": "UPPERCASE_AND_SPACES"},
            headers=headers,
        )
        assert res.status_code == 422
        assert res.json()["code"] == "validation.failed"


def test_projects_forbidden_without_project_role(rsa_key_pair, test_settings) -> None:
    """Verify that contributor lacking maintainer permissions cannot delete project."""
    private_key, public_key = rsa_key_pair
    app = create_app(settings=test_settings)

    verifier = ClerkTokenVerifier(settings=test_settings, static_public_key=public_key)
    app.dependency_overrides[get_token_verifier] = lambda: verifier

    wid = generate_uuid7()
    pid = generate_uuid7()
    # Contributor has project:read, project:sync, but lacks project:delete and members:manage
    mock_ctx = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_contrib",
        email="contrib@example.com",
        workspace_id=wid,
        workspace_role="member",
        project_id=pid,
        project_role="contributor",
        permissions=frozenset({PERMISSION_AUTHENTICATED, PERM_PROJECT_READ}),
    )
    app.dependency_overrides[get_auth_context] = lambda: mock_ctx

    with TestClient(app=app) as client:
        token = make_test_token(private_key, sub="user_contrib")
        headers = {"Authorization": f"Bearer {token}"}

        # Attempt to delete project (requires PERM_PROJECT_DELETE)
        res = client.delete(f"/api/v1/projects/{pid}", headers=headers)
        assert res.status_code == 403
        assert res.json()["code"] == "auth.forbidden"

        # Attempt to add project member (requires PERM_MEMBERS_MANAGE)
        res = client.post(
            f"/api/v1/projects/{pid}/members",
            json={"user_id": str(generate_uuid7()), "role": "viewer"},
            headers=headers,
        )
        assert res.status_code == 403
        assert res.json()["code"] == "auth.forbidden"


def test_sync_mode_forbidden_without_update_role(rsa_key_pair, test_settings) -> None:
    """Verify that a client lacking project:update receives 403 on PATCH /sync-mode."""
    private_key, public_key = rsa_key_pair
    app = create_app(settings=test_settings)

    verifier = ClerkTokenVerifier(settings=test_settings, static_public_key=public_key)
    app.dependency_overrides[get_token_verifier] = lambda: verifier

    wid = generate_uuid7()
    pid = generate_uuid7()
    mock_ctx = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_viewer",
        email="viewer@example.com",
        workspace_id=wid,
        workspace_role="member",
        project_id=pid,
        project_role="viewer",
        permissions=frozenset({PERMISSION_AUTHENTICATED, PERM_PROJECT_READ}),
    )
    app.dependency_overrides[get_auth_context] = lambda: mock_ctx

    with TestClient(app=app) as client:
        token = make_test_token(private_key, sub="user_viewer")
        headers = {"Authorization": f"Bearer {token}"}

        res = client.patch(
            f"/api/v1/projects/{pid}/sync-mode",
            json={"sync_mode": "indexed"},
            headers=headers,
        )
        assert res.status_code == 403
        assert res.json()["code"] == "auth.forbidden"


@pytest.mark.asyncio
async def test_project_service_sync_mode_transition_and_purge() -> None:
    """Verify ProjectService purge consequences and audit event creation during sync-mode transition."""
    from unittest.mock import AsyncMock, MagicMock

    from app.core.errors import ValidationError
    from app.domain.projects.service import ProjectService
    from app.persistence.models.project import Project

    session = AsyncMock()
    service = ProjectService(session)

    pid = generate_uuid7()
    wid = generate_uuid7()
    mock_project = MagicMock(spec=Project)
    mock_project.id = pid
    mock_project.workspace_id = wid
    mock_project.sync_mode = "indexed"

    service.repo.get_by_id = AsyncMock(return_value=mock_project)
    service.repo.update = AsyncMock(return_value=mock_project)
    service.brain_repo.purge_project_chunks = AsyncMock(
        return_value={"code_chunks": 42, "embeddings": 42}
    )
    service.audit_repo.record = AsyncMock()

    ctx = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_admin",
        email="admin@example.com",
        workspace_id=wid,
        workspace_role="admin",
        project_id=pid,
        project_role="maintainer",
        permissions=frozenset({PERMISSION_AUTHENTICATED, PERM_PROJECT_READ, PERM_PROJECT_UPDATE}),
    )

    # 1. Transition indexed -> metadata_only triggers purge of chunks and embeddings
    res = await service.update_sync_mode(ctx, pid, "metadata_only")
    assert res["project_id"] == pid
    assert res["previous_sync_mode"] == "indexed"
    assert res["new_sync_mode"] == "metadata_only"
    assert res["purged_counts"] == {"code_chunks": 42, "embeddings": 42}

    service.brain_repo.purge_project_chunks.assert_awaited_once_with(ctx, pid)
    service.repo.update.assert_awaited_once_with(ctx, pid, sync_mode="metadata_only")
    service.audit_repo.record.assert_awaited_once()
    audit_call_kwargs = service.audit_repo.record.await_args.kwargs
    assert audit_call_kwargs["action"] == "project.sync_mode_updated"
    assert audit_call_kwargs["metadata"]["purged_counts"] == {
        "code_chunks": 42,
        "embeddings": 42,
    }

    # 2. Transition metadata_only -> indexed does not purge
    mock_project.sync_mode = "metadata_only"
    service.brain_repo.purge_project_chunks.reset_mock()
    service.audit_repo.record.reset_mock()

    res2 = await service.update_sync_mode(ctx, pid, "indexed")
    assert res2["previous_sync_mode"] == "metadata_only"
    assert res2["new_sync_mode"] == "indexed"
    assert res2["purged_counts"] == {"code_chunks": 0, "embeddings": 0}
    service.brain_repo.purge_project_chunks.assert_not_awaited()

    # 3. Invalid sync mode raises ValidationError
    with pytest.raises(ValidationError):
        await service.update_sync_mode(ctx, pid, "invalid_mode")


def test_project_purge_forbidden_without_delete_role(rsa_key_pair) -> None:
    """Verify that project data purge endpoint rejects callers lacking PERM_PROJECT_DELETE."""
    private_key, public_key = rsa_key_pair
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:", env="test")
    app = create_app(settings=settings)

    verifier = ClerkTokenVerifier(settings=settings, static_public_key=public_key)
    app.dependency_overrides[get_token_verifier] = lambda: verifier

    pid = generate_uuid7()
    wid = generate_uuid7()
    mock_ctx = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_viewer",
        email="viewer@example.com",
        workspace_id=wid,
        workspace_role="viewer",
        project_id=pid,
        project_role="viewer",
        permissions=frozenset({PERMISSION_AUTHENTICATED, PERM_PROJECT_READ}),
    )
    app.dependency_overrides[get_auth_context] = lambda: mock_ctx

    with TestClient(app=app) as client:
        token = make_test_token(private_key, sub="user_viewer")
        headers = {"Authorization": f"Bearer {token}"}

        res = client.post(
            f"/api/v1/projects/{pid}/purge",
            json={"scope": "all"},
            headers=headers,
        )
        assert res.status_code == 403
        assert res.json()["code"] == "auth.forbidden"


@pytest.mark.asyncio
async def test_project_service_purge_project_data_and_verification_report() -> None:
    """Verify ProjectService purge across stores, verification report, and audit recording."""
    from unittest.mock import AsyncMock, MagicMock

    from app.core.errors import ValidationError
    from app.domain.projects.service import ProjectService
    from app.persistence.models.project import Project

    session = AsyncMock()
    service = ProjectService(session)

    pid = generate_uuid7()
    wid = generate_uuid7()
    user_id = generate_uuid7()
    mock_project = MagicMock(spec=Project)
    mock_project.id = pid
    mock_project.workspace_id = wid
    mock_project.slug = "demo-repo"
    mock_project.sync_mode = "indexed"

    service.repo.get_by_id = AsyncMock(return_value=mock_project)
    service.repo.update = AsyncMock(return_value=mock_project)
    service.brain_repo.purge_project_data = AsyncMock(
        return_value={
            "postgres": {
                "code_chunks": 50,
                "chunk_embeddings": 50,
                "evidence_snippets": 5,
                "job_events": 12,
            },
            "redis": {"cache_keys_purged": 6},
            "checkpoints": {"threads_purged": 2},
        }
    )
    service.audit_repo.record = AsyncMock()

    ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_admin",
        email="admin@example.com",
        workspace_id=wid,
        workspace_role="admin",
        project_id=pid,
        project_role="maintainer",
        permissions=frozenset({PERMISSION_AUTHENTICATED, PERM_PROJECT_READ, PERM_PROJECT_DELETE}),
    )

    # 1. Mismatched confirmation slug raises ValidationError
    with pytest.raises(ValidationError):
        await service.purge_project_data(ctx, pid, scope="all", confirmation_slug="wrong-slug")

    # 2. Matching confirmation slug executes purge and generates verification report
    report = await service.purge_project_data(ctx, pid, scope="all", confirmation_slug="demo-repo")

    assert report["project_id"] == str(pid)
    assert report["workspace_id"] == str(wid)
    assert report["requested_by"] == str(user_id)
    assert report["scope"] == "all"
    assert report["sync_mode"] == "metadata_only"
    assert report["status"] == "completed"
    assert report["verification_hash"].startswith("sha256:")
    assert len(report["verification_hash"]) == 71  # "sha256:" + 64 hex chars

    # Verify per-store counts
    assert report["stores"]["postgres"]["code_chunks"] == 50
    assert report["stores"]["postgres"]["chunk_embeddings"] == 50
    assert report["stores"]["redis"]["cache_keys_purged"] == 6
    assert report["stores"]["checkpoints"]["threads_purged"] == 2

    # Verify project sync_mode updated to metadata_only
    service.repo.update.assert_awaited_once_with(ctx, pid, sync_mode="metadata_only")

    # Verify audit event emitted with verification hash and counts, no source code
    service.audit_repo.record.assert_awaited_once()
    audit_kwargs = service.audit_repo.record.await_args.kwargs
    assert audit_kwargs["action"] == "project.data_purged"
    assert audit_kwargs["target_id"] == str(pid)
    assert audit_kwargs["metadata"]["verification_hash"] == report["verification_hash"]
    assert audit_kwargs["metadata"]["stores"]["postgres"]["code_chunks"] == 50


def test_projects_crud_lifecycle_live_db(rsa_key_pair) -> None:
    """End-to-end functional test of project CRUD endpoints against live DB."""
    import os

    db_url = os.getenv("DEVMIND_DATABASE_URL")
    if not db_url:
        pytest.skip("DEVMIND_DATABASE_URL not set; skipping live DB test")

    private_key, public_key = rsa_key_pair
    settings = Settings(database_url=db_url, env="test")
    app = create_app(settings=settings)

    verifier = ClerkTokenVerifier(settings=settings, static_public_key=public_key)
    app.dependency_overrides[get_token_verifier] = lambda: verifier

    test_sub = f"user_proj_live_{generate_uuid7().hex[:8]}"
    token = make_test_token(private_key, sub=test_sub)
    headers = {"Authorization": f"Bearer {token}"}

    with TestClient(app=app) as client:
        # 1. Create a workspace first
        ws_slug = f"ws-proj-{generate_uuid7().hex[:8]}"
        res = client.post(
            "/api/v1/workspaces",
            json={"name": "Project Parent WS", "slug": ws_slug, "kind": "personal"},
            headers=headers,
        )
        assert res.status_code == 201, res.text
        ws_id = res.json()["id"]

        # 2. Create project in workspace
        proj_slug = f"proj-api-{generate_uuid7().hex[:8]}"
        res = client.post(
            f"/api/v1/workspaces/{ws_id}/projects",
            json={
                "name": "Live Project",
                "slug": proj_slug,
                "visibility": "workspace",
                "sync_mode": "metadata_only",
                "primary_language": "typescript",
            },
            headers=headers,
        )
        assert res.status_code == 201, res.text
        proj_data = res.json()
        pid = proj_data["id"]
        assert proj_data["slug"] == proj_slug
        assert proj_data["workspace_id"] == ws_id

        # 3. Get project
        res = client.get(f"/api/v1/projects/{pid}", headers=headers)
        assert res.status_code == 200
        assert res.json()["name"] == "Live Project"

        # 4. Patch project
        res = client.patch(
            f"/api/v1/projects/{pid}",
            json={"name": "Renamed Live Project"},
            headers=headers,
        )
        assert res.status_code == 200
        assert res.json()["name"] == "Renamed Live Project"

        # 5. List projects in workspace
        res = client.get(f"/api/v1/workspaces/{ws_id}/projects", headers=headers)
        assert res.status_code == 200
        items = res.json()
        assert any(item["id"] == pid for item in items)

        # 6. Delete project
        res = client.delete(f"/api/v1/projects/{pid}", headers=headers)
        assert res.status_code == 204
