"""Tests for Audit Event REST API endpoints and append-only governance logs (M9-06, docs/03 §3.5 & §11.1, docs/07 §16)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from starlette.testclient import TestClient

from app.core.auth_context import AuthContext
from app.core.ids import generate_uuid7
from app.domain.auth import (
    PERM_AUDIT_READ,
    PERM_PROJECT_READ,
    PERM_WORKSPACE_READ,
    get_auth_context,
    get_db_session,
)
from app.main import create_app
from app.persistence.models.audit import AuditEvent


def _make_auth_ctx(
    workspace_id: UUID | None = None,
    user_id: UUID | None = None,
    role: str = "admin",
    permissions: frozenset[str] | None = None,
) -> AuthContext:
    perms = permissions if permissions is not None else frozenset({PERM_AUDIT_READ, PERM_WORKSPACE_READ, PERM_PROJECT_READ})
    return AuthContext(
        user_id=user_id or generate_uuid7(),
        clerk_user_id="user_clerk_audit_test",
        email="audit_test@example.com",
        workspace_id=workspace_id or generate_uuid7(),
        workspace_role=role,
        permissions=perms,
    )


def test_list_workspace_audit_events_as_admin() -> None:
    """Workspace admin can list audit events with metadata and timestamps."""
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()
    client = TestClient(app)

    wid = generate_uuid7()
    actor_id = generate_uuid7()
    event_id = generate_uuid7()
    now = datetime.now(UTC)

    mock_event = AuditEvent(
        id=event_id,
        workspace_id=wid,
        actor_id=actor_id,
        actor_kind="user",
        action="project.sync_mode_updated",
        target_kind="project",
        target_id=str(generate_uuid7()),
        ip_hash="abc123hash",
        metadata_json={"previous_sync_mode": "indexed", "new_sync_mode": "metadata_only"},
        created_at=now,
    )

    admin_ctx = _make_auth_ctx(workspace_id=wid, role="admin", permissions=frozenset({PERM_AUDIT_READ, PERM_WORKSPACE_READ}))
    app.dependency_overrides[get_auth_context] = lambda: admin_ctx

    with (
        patch("app.domain.audit.service.WorkspaceRepository.get_by_id", new_callable=AsyncMock) as mock_get_ws,
        patch("app.domain.audit.service.AuditEventRepository.list_for_workspace", new_callable=AsyncMock) as mock_list,
    ):
        mock_get_ws.return_value = MagicMock()
        mock_list.return_value = [mock_event]

        resp = client.get(f"/api/v1/workspaces/{wid}/audit-events?limit=25&offset=0")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == str(event_id)
        assert data[0]["workspace_id"] == str(wid)
        assert data[0]["action"] == "project.sync_mode_updated"
        assert data[0]["target_kind"] == "project"
        assert data[0]["metadata"]["new_sync_mode"] == "metadata_only"


def test_list_workspace_audit_events_requires_audit_read_permission() -> None:
    """Workspace member without PERM_AUDIT_READ is rejected with 403 Forbidden."""
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()
    client = TestClient(app)

    wid = generate_uuid7()
    member_ctx = _make_auth_ctx(workspace_id=wid, role="member", permissions=frozenset({PERM_WORKSPACE_READ}))
    app.dependency_overrides[get_auth_context] = lambda: member_ctx

    resp = client.get(f"/api/v1/workspaces/{wid}/audit-events")
    assert resp.status_code == 403
    assert resp.headers.get("content-type") == "application/problem+json"


def test_list_workspace_audit_events_cross_tenant_isolation() -> None:
    """Admin of Workspace A cannot access audit events of Workspace B."""
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()
    client = TestClient(app)

    ws_a = generate_uuid7()
    ws_b = generate_uuid7()

    admin_a_ctx = _make_auth_ctx(workspace_id=ws_a, role="admin", permissions=frozenset({PERM_AUDIT_READ, PERM_WORKSPACE_READ}))
    app.dependency_overrides[get_auth_context] = lambda: admin_a_ctx

    resp = client.get(f"/api/v1/workspaces/{ws_b}/audit-events")
    assert resp.status_code == 403
    assert resp.headers.get("content-type") == "application/problem+json"


def test_list_workspace_audit_events_with_filters() -> None:
    """Filters by action, target_kind, and pagination are forwarded to repository."""
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()
    client = TestClient(app)

    wid = generate_uuid7()
    admin_ctx = _make_auth_ctx(workspace_id=wid, role="admin", permissions=frozenset({PERM_AUDIT_READ, PERM_WORKSPACE_READ}))
    app.dependency_overrides[get_auth_context] = lambda: admin_ctx

    with (
        patch("app.domain.audit.service.WorkspaceRepository.get_by_id", new_callable=AsyncMock) as mock_get_ws,
        patch("app.domain.audit.service.AuditEventRepository.list_for_workspace", new_callable=AsyncMock) as mock_list,
    ):
        mock_get_ws.return_value = MagicMock()
        mock_list.return_value = []

        resp = client.get(
            f"/api/v1/workspaces/{wid}/audit-events?action=consent.revoked&target_kind=consent&limit=20&offset=5"
        )
        assert resp.status_code == 200
        mock_list.assert_called_once_with(
            admin_ctx,
            workspace_id=wid,
            action="consent.revoked",
            target_kind="consent",
            target_id=None,
            actor_id=None,
            limit=20,
            offset=5,
        )


def test_list_project_audit_events() -> None:
    """Project reader can access audit events scoped to a project."""
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()
    client = TestClient(app)

    wid = generate_uuid7()
    pid = generate_uuid7()
    event_id = generate_uuid7()

    mock_event = AuditEvent(
        id=event_id,
        workspace_id=wid,
        actor_id=generate_uuid7(),
        actor_kind="user",
        action="project.data_purged",
        target_kind="project",
        target_id=str(pid),
        ip_hash="hash123",
        metadata_json={"verification_hash": "sha256abc", "scope": "all"},
        created_at=datetime.now(UTC),
    )

    proj_ctx = _make_auth_ctx(workspace_id=wid, role="contributor", permissions=frozenset({PERM_PROJECT_READ}))
    app.dependency_overrides[get_auth_context] = lambda: proj_ctx

    with (
        patch("app.domain.audit.service.ProjectRepository.get_by_id", new_callable=AsyncMock) as mock_get_proj,
        patch("app.domain.audit.service.AuditEventRepository.list_for_project", new_callable=AsyncMock) as mock_list,
    ):
        mock_proj = MagicMock(workspace_id=wid)
        mock_get_proj.return_value = mock_proj
        mock_list.return_value = [mock_event]

        resp = client.get(f"/api/v1/projects/{pid}/audit-events?action=project.data_purged")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data) == 1
        assert data[0]["action"] == "project.data_purged"
        assert data[0]["metadata"]["verification_hash"] == "sha256abc"


def test_list_project_audit_events_cross_tenant_isolation() -> None:
    """User in Workspace A cannot access audit events of project in Workspace B."""
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()
    client = TestClient(app)

    ws_a = generate_uuid7()
    ws_b = generate_uuid7()
    pid = generate_uuid7()

    ctx = _make_auth_ctx(workspace_id=ws_a, role="admin", permissions=frozenset({PERM_PROJECT_READ}))
    app.dependency_overrides[get_auth_context] = lambda: ctx

    with patch("app.domain.audit.service.ProjectRepository.get_by_id", new_callable=AsyncMock) as mock_get_proj:
        mock_proj = MagicMock(workspace_id=ws_b)
        mock_get_proj.return_value = mock_proj

        resp = client.get(f"/api/v1/projects/{pid}/audit-events")
        assert resp.status_code == 403
        assert resp.headers.get("content-type") == "application/problem+json"

