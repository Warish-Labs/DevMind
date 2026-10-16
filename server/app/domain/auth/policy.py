"""Policy service, permission evaluator, and route permission registry (docs/03 §4, docs/07 §3).

Enforces role-based permissions, computes effective project roles across workspace visibility boundaries,
and registers route permissions for automated CI verification.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Request
from fastapi.routing import APIRoute

from app.core.auth_context import (
    PROJECT_ROLE_WEIGHTS,
    AuthContext,
    ProjectRole,
    WorkspaceRole,
)
from app.core.errors import AuthenticationError, ForbiddenError

# Standard DevMind Permissions (docs/03 §4.2)
PERM_PROJECT_READ = "project:read"
PERM_BRAIN_READ = "brain:read"
PERM_FINDINGS_READ = "findings:read"
PERM_CONVERSATION_READ = "conversation:read"

PERM_PROJECT_SYNC = "project:sync"
PERM_ANALYSIS_CREATE = "analysis:create"
PERM_CONVERSATION_CREATE = "conversation:create"
PERM_FINDING_ACKNOWLEDGE = "finding:acknowledge"
PERM_FINDING_PROGRESS = "finding:progress"

PERM_FINDING_TRIAGE = "finding:triage"
PERM_CONSENT_MANAGE = "consent:manage"
PERM_PROJECT_UPDATE = "project:update"
PERM_MEMBERS_MANAGE = "members:manage"
PERM_INTEGRATIONS_MANAGE = "integrations:manage"
PERM_PROJECT_DELETE = "project:delete"

PERM_WORKSPACE_READ = "workspace:read"
PERM_WORKSPACE_MANAGE = "workspace:manage"
PERM_USAGE_READ = "usage:read"
PERM_AUDIT_READ = "audit:read"
PERM_MEMBERS_MANAGE_WORKSPACE = "members:manage_workspace"

# Special marker for unauthenticated/operational public routes (/healthz, /readyz, docs)
PERMISSION_PUBLIC = "public"
PERMISSION_AUTHENTICATED = "authenticated"
PERMISSION_WEBHOOK = "webhook"

# Project Role Permissions Mapping (docs/03 §4.2)
VIEWER_PERMISSIONS: frozenset[str] = frozenset(
    {
        PERM_PROJECT_READ,
        PERM_BRAIN_READ,
        PERM_FINDINGS_READ,
        PERM_CONVERSATION_READ,
    }
)

CONTRIBUTOR_PERMISSIONS: frozenset[str] = VIEWER_PERMISSIONS | frozenset(
    {
        PERM_PROJECT_SYNC,
        PERM_ANALYSIS_CREATE,
        PERM_CONVERSATION_CREATE,
        PERM_FINDING_ACKNOWLEDGE,
        PERM_FINDING_PROGRESS,
    }
)

MAINTAINER_PERMISSIONS: frozenset[str] = CONTRIBUTOR_PERMISSIONS | frozenset(
    {
        PERM_FINDING_TRIAGE,
        PERM_CONSENT_MANAGE,
        PERM_PROJECT_UPDATE,
        PERM_MEMBERS_MANAGE,
        PERM_INTEGRATIONS_MANAGE,
        PERM_PROJECT_DELETE,
    }
)

PROJECT_ROLE_PERMISSIONS: dict[ProjectRole, frozenset[str]] = {
    "viewer": VIEWER_PERMISSIONS,
    "contributor": CONTRIBUTOR_PERMISSIONS,
    "maintainer": MAINTAINER_PERMISSIONS,
}

# Workspace Role Permissions Mapping (docs/03 §4.2)
WORKSPACE_MEMBER_PERMISSIONS: frozenset[str] = frozenset(
    {
        PERM_WORKSPACE_READ,
    }
)

WORKSPACE_ADMIN_PERMISSIONS: frozenset[str] = WORKSPACE_MEMBER_PERMISSIONS | frozenset(
    {
        PERM_WORKSPACE_MANAGE,
        PERM_USAGE_READ,
        PERM_AUDIT_READ,
        PERM_MEMBERS_MANAGE_WORKSPACE,
    }
)

WORKSPACE_ROLE_PERMISSIONS: dict[WorkspaceRole, frozenset[str]] = {
    "viewer": WORKSPACE_MEMBER_PERMISSIONS,
    "member": WORKSPACE_MEMBER_PERMISSIONS,
    "admin": WORKSPACE_ADMIN_PERMISSIONS,
    "owner": WORKSPACE_ADMIN_PERMISSIONS,
}


def compute_effective_project_role(
    workspace_role: WorkspaceRole,
    project_visibility: str,
    explicit_project_role: ProjectRole | None = None,
) -> ProjectRole | None:
    """Compute effective project role per docs/03 §4.1.

    Rules:
    - Workspace owner/admin: maintainer regardless of project visibility.
    - Project visibility = workspace:
        - Workspace member: contributor
        - Workspace viewer: viewer
    - Project visibility = private:
        - Workspace member/viewer: None (unless explicit project membership row exists).
    - If explicit project membership exists: greater of workspace-derived and project role.
    """
    if workspace_role in ("owner", "admin"):
        return "maintainer"

    derived_role: ProjectRole | None = None
    if project_visibility == "workspace":
        if workspace_role == "member":
            derived_role = "contributor"
        elif workspace_role == "viewer":
            derived_role = "viewer"
    elif project_visibility == "private":
        derived_role = None

    if explicit_project_role is None:
        return derived_role

    if derived_role is None:
        return explicit_project_role

    derived_weight = PROJECT_ROLE_WEIGHTS.get(derived_role, 0)
    explicit_weight = PROJECT_ROLE_WEIGHTS.get(explicit_project_role, 0)
    return explicit_project_role if explicit_weight > derived_weight else derived_role


def compute_permissions(
    workspace_role: WorkspaceRole,
    project_role: ProjectRole | None = None,
) -> frozenset[str]:
    """Calculate aggregated permissions set from workspace and project roles."""
    ws_perms = WORKSPACE_ROLE_PERMISSIONS.get(workspace_role, frozenset())
    if project_role is not None:
        proj_perms = PROJECT_ROLE_PERMISSIONS.get(project_role, frozenset())
        return ws_perms | proj_perms
    return ws_perms


@dataclass(frozen=True)
class RoutePermissionEntry:
    endpoint_name: str
    path: str
    methods: frozenset[str]
    permission: str


class RoutePermissionRegistry:
    """Central registry tracking required permissions for all API routes (docs/07 §3)."""

    def __init__(self) -> None:
        self._registry: dict[str, RoutePermissionEntry] = {}

    def register(
        self,
        endpoint: Callable[..., Any],
        permission: str,
        path: str = "",
        methods: frozenset[str] = frozenset({"GET"}),
    ) -> None:
        """Register permission requirement for an endpoint."""
        key = f"{endpoint.__module__}.{endpoint.__name__}"
        self._registry[key] = RoutePermissionEntry(
            endpoint_name=key,
            path=path,
            methods=methods,
            permission=permission,
        )

    def get_permission(self, endpoint: Callable[..., Any]) -> str | None:
        """Lookup declared permission for an endpoint."""
        key = f"{endpoint.__module__}.{endpoint.__name__}"
        entry = self._registry.get(key)
        if entry:
            return entry.permission
        # Check endpoint docstring or attributes if directly tagged
        return getattr(endpoint, "__devmind_permission__", None)

    def all_entries(self) -> list[RoutePermissionEntry]:
        return list(self._registry.values())


# Global route permission registry
route_permission_registry = RoutePermissionRegistry()


def declare_permission(permission: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to declare required permission on a router endpoint.

    Used by CI to verify that every route has declared permissions.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        fn.__devmind_permission__ = permission
        route_permission_registry.register(fn, permission)
        return fn

    return decorator


def require_permission(permission: str) -> Any:
    """FastAPI dependency factory enforcing that caller AuthContext has the declared permission.

    Raises ForbiddenError (403) if authenticated caller lacks the required permission.
    """

    def dependency(request: Request) -> AuthContext:
        ctx: AuthContext | None = getattr(request.state, "auth_context", None)
        if ctx is None:
            # If no auth_context in state, fail unauthenticated
            raise AuthenticationError(detail="Authentication context is missing")

        if permission in (PERMISSION_PUBLIC, PERMISSION_AUTHENTICATED, PERMISSION_WEBHOOK):
            return ctx

        if not ctx.has_permission(permission):
            raise ForbiddenError(
                detail=f"Forbidden: caller lacks required permission '{permission}'"
            )
        return ctx

    return Depends(dependency)


def find_undeclared_routes(app_routes: list[Any]) -> list[str]:
    """Inspect all FastAPI routes and return those lacking a declared permission (docs/07 §3).

    Exemptions:
    - Built-in OpenAPI docs (/docs, /redoc, /openapi.json)
    - Head/options automatic routes
    """
    undeclared: list[str] = []

    for route in app_routes:
        if not isinstance(route, APIRoute):
            continue

        path = route.path
        if path in ("/docs", "/redoc", "/openapi.json"):
            continue

        endpoint = route.endpoint
        perm = route_permission_registry.get_permission(endpoint)
        if perm is None:
            # Check route dependencies for permission markers
            found_perm = False
            for dep in route.dependencies:
                dep_fn = dep.dependency
                if dep_fn and getattr(dep_fn, "__devmind_permission__", None):
                    found_perm = True
                    break
            if not found_perm:
                undeclared.append(f"{','.join(route.methods)} {path} ({endpoint.__name__})")

    return undeclared
