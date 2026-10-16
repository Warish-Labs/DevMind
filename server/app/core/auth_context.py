"""Authentication and authorization context.

Carries verified identity, memberships, and effective permissions for every request.
Required by every repository function (docs/03 §4, docs/07 §3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

WorkspaceRole = Literal["owner", "admin", "member", "viewer"]
ProjectRole = Literal["maintainer", "contributor", "viewer"]

# Role hierarchy weights for comparison
WORKSPACE_ROLE_WEIGHTS: dict[WorkspaceRole, int] = {
    "owner": 4,
    "admin": 3,
    "member": 2,
    "viewer": 1,
}

PROJECT_ROLE_WEIGHTS: dict[ProjectRole, int] = {
    "maintainer": 3,
    "contributor": 2,
    "viewer": 1,
}


@dataclass(frozen=True)
class AuthContext:
    """Verified caller context for tenant-scoped operations.

    Every repository function requires either an AuthContext or a SystemContext.
    Cross-tenant queries are prevented by automatically attaching workspace_id
    and project_id predicates.
    """

    user_id: UUID
    clerk_user_id: str
    email: str
    workspace_id: UUID
    workspace_role: WorkspaceRole
    project_id: UUID | None = None
    project_role: ProjectRole | None = None
    permissions: frozenset[str] = field(default_factory=frozenset)
    request_id: str | None = None
    ip_hash: str | None = None

    @property
    def is_system(self) -> bool:
        return False

    def has_permission(self, permission: str) -> bool:
        """Check whether the context holds a specific permission."""
        return permission in self.permissions

    def is_workspace_admin_or_owner(self) -> bool:
        """Check if caller has administrative privileges over the workspace."""
        return self.workspace_role in ("owner", "admin")

    def has_workspace_role(self, minimum_role: WorkspaceRole) -> bool:
        """Check if caller meets or exceeds a minimum workspace role."""
        return WORKSPACE_ROLE_WEIGHTS.get(self.workspace_role, 0) >= WORKSPACE_ROLE_WEIGHTS.get(
            minimum_role, 0
        )

    def has_project_role(self, minimum_role: ProjectRole) -> bool:
        """Check if caller meets or exceeds a minimum project role."""
        if self.project_role is None:
            return False
        return PROJECT_ROLE_WEIGHTS.get(self.project_role, 0) >= PROJECT_ROLE_WEIGHTS.get(
            minimum_role, 0
        )


@dataclass(frozen=True)
class SystemContext:
    """Explicit context for system/background tasks that act on behalf of a recorded actor or system.

    Never used implicitly; must be passed deliberately where tenant context is not tied to an active HTTP session.
    """

    reason: str
    workspace_id: UUID | None = None
    project_id: UUID | None = None
    actor_id: UUID | None = None
    actor_kind: str = "system"
    request_id: str | None = None

    @property
    def is_system(self) -> bool:
        return True

    def has_permission(self, permission: str) -> bool:
        # System tasks running with SystemContext are granted operational access
        return True
