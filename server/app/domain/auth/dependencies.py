"""Authentication and tenant context dependencies for FastAPI request lifecycles."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import AuthenticationError
from app.core.settings import Settings, get_settings
from app.domain.auth.policy import (
    PROJECT_ROLE_PERMISSIONS,
    WORKSPACE_ROLE_PERMISSIONS,
    compute_effective_project_role,
)
from app.integrations.clerk.verifier import ClerkClaims, ClerkTokenVerifier
from app.persistence.database import get_db_session
from app.persistence.repositories.project_repo import ProjectRepository
from app.persistence.repositories.user_repo import UserRepository
from app.persistence.repositories.workspace_repo import WorkspaceRepository

logger = logging.getLogger("devmind.domain.auth")

_verifier: ClerkTokenVerifier | None = None


def get_token_verifier(settings: Settings = Depends(get_settings)) -> ClerkTokenVerifier:
    """Return shared ClerkTokenVerifier instance."""
    global _verifier
    if _verifier is None:
        _verifier = ClerkTokenVerifier(settings=settings)
    return _verifier


async def get_current_user_claims(
    request: Request,
    verifier: ClerkTokenVerifier = Depends(get_token_verifier),
) -> ClerkClaims:
    """Extract and verify bearer JWT from Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.strip():
        raise AuthenticationError(detail="Authentication token is required")

    return verifier.verify_token(auth_header)


async def get_auth_context(
    request: Request,
    claims: ClerkClaims = Depends(get_current_user_claims),
    session: AsyncSession = Depends(get_db_session),
) -> AuthContext:
    """Resolve authenticated user, workspace, and project context with effective permissions."""
    user_repo = UserRepository(session)
    ws_repo = WorkspaceRepository(session)
    project_repo = ProjectRepository(session)
    sys_ctx = SystemContext(reason="auth_context_resolution")

    # 1. Resolve or lazily sync user record from Clerk claims
    user = await user_repo.get_by_clerk_user_id(sys_ctx, clerk_user_id=claims.sub)
    if user is None:
        user_email = claims.email or f"{claims.sub}@users.devmind.local"
        user = await user_repo.create(
            sys_ctx,
            clerk_user_id=claims.sub,
            email=user_email,
            display_name=claims.email.split("@")[0] if claims.email else claims.sub,
        )

    # 2. Extract path params for workspace_id and project_id if present
    path_params = request.path_params
    raw_ws_id: str | None = path_params.get("wid") or path_params.get("workspace_id")
    raw_pid: str | None = path_params.get("pid") or path_params.get("project_id")

    workspace_id: UUID | None = None
    project_id: UUID | None = None

    if raw_ws_id:
        try:
            workspace_id = UUID(str(raw_ws_id))
        except (ValueError, TypeError):
            pass

    if raw_pid:
        try:
            project_id = UUID(str(raw_pid))
        except (ValueError, TypeError):
            pass

    # If project_id provided without workspace_id, find project's workspace
    if project_id is not None and workspace_id is None:
        proj = await project_repo.get_by_id(sys_ctx, project_id)
        if proj is not None:
            workspace_id = proj.workspace_id

    # 3. Evaluate workspace role and project role
    workspace_role: Any = None
    project_role: Any = None
    effective_permissions: set[str] = set()

    if workspace_id is not None:
        ws_membership = await ws_repo.get_membership(
            sys_ctx, workspace_id=workspace_id, user_id=user.id
        )
        if ws_membership is not None:
            workspace_role = ws_membership.role
            effective_permissions.update(
                WORKSPACE_ROLE_PERMISSIONS.get(workspace_role, frozenset())
            )

            # Evaluate project role if within a project context
            if project_id is not None:
                proj = await project_repo.get_by_id(sys_ctx, project_id)
                if proj is not None:
                    proj_membership = await project_repo.get_membership(
                        sys_ctx, project_id=project_id, user_id=user.id
                    )
                    explicit_role = proj_membership.role if proj_membership else None
                    project_role = compute_effective_project_role(
                        workspace_role=workspace_role,
                        project_visibility=proj.visibility,
                        explicit_project_role=explicit_role,
                    )
                    if project_role is not None:
                        effective_permissions.update(
                            PROJECT_ROLE_PERMISSIONS.get(project_role, frozenset())
                        )

    req_id = getattr(request.state, "request_id", None)
    auth_ctx = AuthContext(
        user_id=user.id,
        clerk_user_id=claims.sub,
        email=user.email,
        workspace_id=workspace_id,
        workspace_role=workspace_role,
        project_id=project_id,
        project_role=project_role,
        permissions=frozenset(effective_permissions),
        request_id=req_id,
    )

    request.state.auth_context = auth_ctx
    return auth_ctx
