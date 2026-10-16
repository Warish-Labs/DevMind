"""Tests for policy service, permission evaluator, and role inheritance (docs/03 §4)."""

import pytest
from starlette.requests import Request

from app.core.auth_context import AuthContext
from app.core.errors import AuthenticationError, ForbiddenError
from app.core.ids import generate_uuid7
from app.domain.auth.policy import (
    CONTRIBUTOR_PERMISSIONS,
    MAINTAINER_PERMISSIONS,
    PERM_AUDIT_READ,
    PERM_BRAIN_READ,
    PERM_CONSENT_MANAGE,
    PERM_FINDING_TRIAGE,
    PERM_PROJECT_DELETE,
    PERM_PROJECT_READ,
    PERM_PROJECT_SYNC,
    PERM_USAGE_READ,
    PERM_WORKSPACE_MANAGE,
    PERM_WORKSPACE_READ,
    VIEWER_PERMISSIONS,
    compute_effective_project_role,
    compute_permissions,
    require_permission,
)


def test_permission_hierarchy_and_sets() -> None:
    """Verify that role permissions strictly match the matrix from docs/03 §4.2."""
    assert PERM_PROJECT_READ in VIEWER_PERMISSIONS
    assert PERM_BRAIN_READ in VIEWER_PERMISSIONS
    assert PERM_PROJECT_SYNC not in VIEWER_PERMISSIONS

    assert PERM_PROJECT_SYNC in CONTRIBUTOR_PERMISSIONS
    assert PERM_PROJECT_READ in CONTRIBUTOR_PERMISSIONS
    assert PERM_FINDING_TRIAGE not in CONTRIBUTOR_PERMISSIONS

    assert PERM_FINDING_TRIAGE in MAINTAINER_PERMISSIONS
    assert PERM_PROJECT_DELETE in MAINTAINER_PERMISSIONS
    assert PERM_CONSENT_MANAGE in MAINTAINER_PERMISSIONS


def test_workspace_role_permissions() -> None:
    """Verify workspace role permissions for members vs administrators."""
    member_perms = compute_permissions(workspace_role="member")
    assert PERM_WORKSPACE_READ in member_perms
    assert PERM_WORKSPACE_MANAGE not in member_perms
    assert PERM_USAGE_READ not in member_perms

    admin_perms = compute_permissions(workspace_role="admin")
    assert PERM_WORKSPACE_READ in admin_perms
    assert PERM_WORKSPACE_MANAGE in admin_perms
    assert PERM_USAGE_READ in admin_perms
    assert PERM_AUDIT_READ in admin_perms


def test_effective_project_role_workspace_admin() -> None:
    """Workspace owner and admin always have effective maintainer role (docs/03 §4.1)."""
    assert compute_effective_project_role("owner", "workspace") == "maintainer"
    assert compute_effective_project_role("owner", "private") == "maintainer"
    assert compute_effective_project_role("admin", "workspace") == "maintainer"
    assert compute_effective_project_role("admin", "private") == "maintainer"


def test_effective_project_role_member_and_viewer() -> None:
    """Workspace member is contributor on workspace projects, None on private projects."""
    assert compute_effective_project_role("member", "workspace") == "contributor"
    assert compute_effective_project_role("member", "private") is None

    assert compute_effective_project_role("viewer", "workspace") == "viewer"
    assert compute_effective_project_role("viewer", "private") is None


def test_effective_project_role_explicit_override() -> None:
    """Explicit project membership takes the greater of workspace-derived and project role."""
    # Member (derived contributor) elevated to explicit maintainer
    assert (
        compute_effective_project_role(
            workspace_role="member",
            project_visibility="workspace",
            explicit_project_role="maintainer",
        )
        == "maintainer"
    )

    # Member on private project granted explicit viewer
    assert (
        compute_effective_project_role(
            workspace_role="member",
            project_visibility="private",
            explicit_project_role="viewer",
        )
        == "viewer"
    )

    # Derived contributor is not degraded by lower explicit viewer role
    assert (
        compute_effective_project_role(
            workspace_role="member",
            project_visibility="workspace",
            explicit_project_role="viewer",
        )
        == "contributor"
    )


def test_require_permission_dependency_enforcement() -> None:
    """Verify that require_permission raises ForbiddenError when caller lacks permission."""
    dep = require_permission("project:delete")

    # Mock request without auth_context
    req = Request({"type": "http"})
    with pytest.raises(AuthenticationError, match="Authentication context is missing"):
        dep.dependency(req)

    # Mock request with auth_context lacking project:delete
    ctx_viewer = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_1",
        email="viewer@example.com",
        workspace_id=generate_uuid7(),
        workspace_role="viewer",
        permissions=frozenset({"project:read"}),
    )
    req.state.auth_context = ctx_viewer
    with pytest.raises(ForbiddenError, match="caller lacks required permission 'project:delete'"):
        dep.dependency(req)

    # Mock request with auth_context having project:delete
    ctx_maintainer = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_2",
        email="maintainer@example.com",
        workspace_id=generate_uuid7(),
        workspace_role="member",
        permissions=frozenset({"project:read", "project:delete"}),
    )
    req.state.auth_context = ctx_maintainer
    result = dep.dependency(req)
    assert result == ctx_maintainer
