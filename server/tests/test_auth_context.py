"""Tests for AuthContext, SystemContext, role evaluation, and permissions."""

from app.core.auth_context import AuthContext, SystemContext
from app.core.ids import generate_uuid7


def test_auth_context_creation_and_attributes() -> None:
    """Verify standard AuthContext attributes and properties."""
    user_id = generate_uuid7()
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()

    ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_clerk_123",
        email="dev@example.com",
        workspace_id=workspace_id,
        workspace_role="admin",
        project_id=project_id,
        project_role="maintainer",
        permissions=frozenset(["project:read", "project:sync", "finding:triage"]),
        request_id="req-test-99",
        ip_hash="abc123sha256",
    )

    assert ctx.is_system is False
    assert ctx.is_workspace_admin_or_owner() is True
    assert ctx.has_workspace_role("member") is True
    assert ctx.has_workspace_role("owner") is False
    assert ctx.has_project_role("contributor") is True
    assert ctx.has_project_role("maintainer") is True
    assert ctx.has_permission("project:read") is True
    assert ctx.has_permission("audit:read") is False


def test_system_context() -> None:
    """Verify SystemContext initialization and attributes."""
    workspace_id = generate_uuid7()
    ctx = SystemContext(
        reason="background_reindex_job",
        workspace_id=workspace_id,
    )

    assert ctx.is_system is True
    assert ctx.reason == "background_reindex_job"
    assert ctx.workspace_id == workspace_id
    assert ctx.has_permission("any:action") is True
