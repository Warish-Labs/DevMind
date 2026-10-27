"""Integrations API routes for GitHub OAuth and external service management (docs/03 §11.1).

Routes:
- GET /api/v1/integrations/github/authorize: Initiate GitHub OAuth linking.
- GET /api/v1/integrations/github/callback: Receive GitHub OAuth redirect and exchange code.
- GET /api/v1/workspaces/{wid}/integrations/github: Get workspace GitHub connection status.
- DELETE /api/v1/workspaces/{wid}/integrations/github: Revoke workspace GitHub connection.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext
from app.core.errors import ValidationError
from app.core.settings import Settings, get_settings
from app.domain.auth import (
    PERM_INTEGRATIONS_MANAGE,
    PERMISSION_AUTHENTICATED,
    PERMISSION_PUBLIC,
    declare_permission,
    get_auth_context,
    get_db_session,
    require_permission,
)
from app.domain.integrations.github_oauth_service import GitHubOAuthService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/integrations/github",
    tags=["Integrations"],
)

workspace_integrations_router = APIRouter(
    prefix="/workspaces/{wid}/integrations/github",
    tags=["Integrations"],
)


class GitHubConnectionSummary(BaseModel):
    """Safe public representation of a GitHub connection without credentials."""

    id: UUID
    workspace_id: UUID
    user_id: UUID
    kind: str
    external_account: str
    scopes: list[str]
    created_at: Any


class GitHubConnectionStatusSummary(BaseModel):
    """Lifecycle status, granted scopes, and analysis capability of a GitHub connection."""

    connection_id: UUID | None = None
    status: str
    kind: str | None = None
    external_account: str | None = None
    scopes: list[str] = []
    can_perform_analysis: bool = False
    missing_permissions: list[str] = []
    resolution_hint: str | None = None
    revoked_at: Any = None
    updated_at: Any = None


def _get_callback_url(request: Request, settings: Settings) -> str:
    """Resolve the canonical callback URL for GitHub OAuth."""
    if settings.is_production:
        return "https://api.devmind.warishlabs.in/api/v1/integrations/github/callback"

    # In local or test environment, construct from base URL or request URL
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}/api/v1/integrations/github/callback"


@router.get(
    "/authorize",
    status_code=status.HTTP_302_FOUND,
    summary="Initiate GitHub OAuth authorization",
)
@declare_permission(PERMISSION_AUTHENTICATED)
async def github_authorize(
    request: Request,
    workspace_id: UUID = Query(..., description="Target workspace ID for connection"),
    return_to: str | None = Query(
        default=None, description="Frontend destination after authorization"
    ),
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """Redirect user to GitHub to authorize DevMind OAuth access.

    Requires valid DevMind user authentication. State parameter is HMAC-signed
    with user/workspace binding to prevent CSRF and session fixation.
    """
    callback_url = _get_callback_url(request, settings)
    service = GitHubOAuthService(session, settings=settings)

    redirect_url = service.build_authorization_url(
        ctx=ctx,
        workspace_id=workspace_id,
        callback_url=callback_url,
        return_to=return_to,
    )
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/callback",
    status_code=status.HTTP_302_FOUND,
    summary="Receive GitHub OAuth callback",
)
@declare_permission(PERMISSION_PUBLIC)
async def github_callback(
    request: Request,
    code: str | None = Query(default=None, description="GitHub authorization code"),
    state: str | None = Query(default=None, description="HMAC-signed state token"),
    error: str | None = Query(default=None, description="Error reported by GitHub"),
    error_description: str | None = Query(default=None, description="Error explanation"),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """Handle callback redirect from GitHub after user authorization.

    Validates state signature and expiration, exchanges authorization code for an
    access token, fetches GitHub user identity, encrypts the credential at rest,
    and redirects user safely back to the allowed frontend return destination.
    """
    service = GitHubOAuthService(session, settings=settings)

    if error:
        logger.warning(
            "GitHub returned OAuth authorization error: %s (%s)", error, error_description
        )
        detail_msg = (
            f"GitHub OAuth failed: {error} - {error_description}"
            if error_description
            else f"GitHub OAuth failed: {error}"
        )
        raise ValidationError(detail=detail_msg)

    if not code or not state:
        raise ValidationError(detail="Missing required OAuth code or state parameter")

    callback_url = _get_callback_url(request, settings)
    return_to, conn = await service.handle_callback(
        code=code,
        state=state,
        callback_url=callback_url,
    )
    await session.commit()

    sep = "&" if "?" in return_to else "?"
    success_redirect = (
        f"{return_to}{sep}github_connected=true"
        f"&account={quote(conn.external_account)}"
        f"&connection_id={conn.id}"
    )
    return RedirectResponse(url=success_redirect, status_code=status.HTTP_302_FOUND)


@workspace_integrations_router.get(
    "",
    response_model=list[GitHubConnectionSummary],
    status_code=status.HTTP_200_OK,
    summary="Get GitHub connection status for workspace",
)
@declare_permission(PERM_INTEGRATIONS_MANAGE)
async def get_workspace_github_connections(
    wid: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_INTEGRATIONS_MANAGE)),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> list[GitHubConnectionSummary]:
    """List active GitHub connection records for the workspace (tokens are never returned)."""
    service = GitHubOAuthService(session, settings)
    conns = await service.list_workspace_connections(ctx, wid)
    return [
        GitHubConnectionSummary(
            id=c.id,
            workspace_id=c.workspace_id,
            user_id=c.user_id,
            kind=c.kind,
            external_account=c.external_account,
            scopes=c.scopes,
            created_at=c.created_at,
        )
        for c in conns
    ]


@workspace_integrations_router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke GitHub connection for workspace",
)
@declare_permission(PERM_INTEGRATIONS_MANAGE)
async def delete_workspace_github_connection(
    wid: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_INTEGRATIONS_MANAGE)),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> None:
    """Revoke GitHub connection for the current user in this workspace."""
    service = GitHubOAuthService(session, settings)
    await service.revoke_connection(ctx, wid, ctx.user_id, kind="oauth")
    await session.commit()


@workspace_integrations_router.get(
    "/status",
    response_model=GitHubConnectionStatusSummary,
    status_code=status.HTTP_200_OK,
    summary="Get GitHub connection lifecycle and permission health status",
)
@declare_permission(PERM_INTEGRATIONS_MANAGE)
async def get_workspace_github_connection_status(
    wid: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_INTEGRATIONS_MANAGE)),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> GitHubConnectionStatusSummary:
    """Evaluate whether the user's GitHub credential is active, degraded, expired, or unlinked."""
    service = GitHubOAuthService(session, settings)
    data = await service.get_connection_status(ctx, wid, ctx.user_id, kind="oauth")
    return GitHubConnectionStatusSummary(**data)


@workspace_integrations_router.post(
    "/rotate",
    response_model=GitHubConnectionSummary,
    status_code=status.HTTP_200_OK,
    summary="Rotate GitHub connection credential envelope encryption",
)
@declare_permission(PERM_INTEGRATIONS_MANAGE)
async def rotate_workspace_github_connection(
    wid: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_INTEGRATIONS_MANAGE)),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> GitHubConnectionSummary:
    """Re-encrypt the user's stored GitHub credential under the latest primary encryption key."""
    service = GitHubOAuthService(session, settings)
    conn = await service.rotate_connection_credential(ctx, wid, ctx.user_id, kind="oauth")
    if conn is None:
        raise ValidationError(detail="No active GitHub connection found to rotate")
    await session.commit()
    return GitHubConnectionSummary(
        id=conn.id,
        workspace_id=conn.workspace_id,
        user_id=conn.user_id,
        kind=conn.kind,
        external_account=conn.external_account,
        scopes=conn.scopes,
        created_at=conn.created_at,
    )
