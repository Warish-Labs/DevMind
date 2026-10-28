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
from app.core.errors import NotFoundError, ValidationError
from app.core.settings import Settings, get_settings
from app.domain.auth import (
    PERM_INTEGRATIONS_MANAGE,
    PERM_PROJECT_READ,
    PERM_PROJECT_UPDATE,
    PERMISSION_AUTHENTICATED,
    PERMISSION_PUBLIC,
    declare_permission,
    get_auth_context,
    get_db_session,
    require_permission,
)
from app.domain.integrations.github_ingest_service import GitHubIngestService
from app.domain.integrations.github_oauth_service import GitHubOAuthService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/integrations/github",
    tags=["Integrations"],
)
integrations_router = router

workspace_integrations_router = APIRouter(
    prefix="/workspaces/{wid}/integrations/github",
    tags=["Integrations"],
)

project_github_router = APIRouter(
    prefix="/projects/{pid}",
    tags=["GitHub"],
)

pull_requests_router = APIRouter(
    prefix="/pull-requests",
    tags=["Pull Requests"],
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


class GitHubLinkRequest(BaseModel):
    """Payload to bind a project to a GitHub repository."""

    full_name: str
    default_branch: str = "main"


class GitHubRepositorySummary(BaseModel):
    """Summary of a linked GitHub repository."""

    id: UUID
    project_id: UUID
    connection_id: UUID
    full_name: str
    default_branch: str
    is_active: bool
    last_synced_at: Any = None
    created_at: Any


class PullRequestSummary(BaseModel):
    """Mirrored pull request summary model."""

    id: UUID
    repository_id: UUID
    number: int
    title: str
    author_login: str
    state: str
    head_sha: str
    base_sha: str
    head_ref: str | None = None
    base_ref: str | None = None
    diff_url: str | None = None
    merged_at: Any = None
    closed_at: Any = None
    created_at: Any
    updated_at: Any


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


# ---------------------------------------------------------------------------
# Project Repository & Pull Request Routes (FR-BRN-07, CAP-06)
# ---------------------------------------------------------------------------


@project_github_router.post(
    "/github/link",
    response_model=GitHubRepositorySummary,
    status_code=status.HTTP_200_OK,
    summary="Link project to a GitHub repository",
)
@declare_permission(PERM_PROJECT_UPDATE)
async def link_project_github_repository(
    pid: UUID,
    payload: GitHubLinkRequest,
    ctx: AuthContext = Depends(require_permission(PERM_PROJECT_UPDATE)),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> GitHubRepositorySummary:
    """Link project to a GitHub repository using the active connection."""
    service = GitHubIngestService(session, settings)
    binding = await service.link_project_repository(
        ctx=ctx,
        project_id=pid,
        full_name=payload.full_name,
        default_branch=payload.default_branch,
    )
    await session.commit()
    return GitHubRepositorySummary(
        id=binding.id,
        project_id=binding.project_id,
        connection_id=binding.connection_id,
        full_name=binding.full_name,
        default_branch=binding.default_branch,
        is_active=binding.is_active,
        last_synced_at=binding.last_synced_at,
        created_at=binding.created_at,
    )


@project_github_router.delete(
    "/github/unlink",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unlink project from GitHub repository",
)
@declare_permission(PERM_PROJECT_UPDATE)
async def unlink_project_github_repository(
    pid: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_PROJECT_UPDATE)),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> None:
    """Unlink repository binding from project."""
    service = GitHubIngestService(session, settings)
    await service.unlink_project_repository(ctx, pid)
    await session.commit()


@project_github_router.get(
    "/github/repository",
    response_model=GitHubRepositorySummary,
    status_code=status.HTTP_200_OK,
    summary="Get linked GitHub repository for project",
)
@declare_permission(PERM_PROJECT_READ)
async def get_project_github_repository(
    pid: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_PROJECT_READ)),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> GitHubRepositorySummary:
    """Retrieve linked repository details for project."""
    service = GitHubIngestService(session, settings)
    binding = await service.get_project_repository(ctx, pid)
    if binding is None:
        raise NotFoundError(detail=f"Project {pid} does not have a linked GitHub repository")
    return GitHubRepositorySummary(
        id=binding.id,
        project_id=binding.project_id,
        connection_id=binding.connection_id,
        full_name=binding.full_name,
        default_branch=binding.default_branch,
        is_active=binding.is_active,
        last_synced_at=binding.last_synced_at,
        created_at=binding.created_at,
    )


@project_github_router.get(
    "/pull-requests",
    response_model=list[PullRequestSummary],
    status_code=status.HTTP_200_OK,
    summary="List mirrored pull requests for project",
)
@declare_permission(PERM_PROJECT_READ)
async def list_project_pull_requests(
    pid: UUID,
    state: str | None = Query(default=None, description="Filter by state (open, closed, merged)"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    ctx: AuthContext = Depends(require_permission(PERM_PROJECT_READ)),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> list[PullRequestSummary]:
    """List mirrored PRs for the linked repository."""
    service = GitHubIngestService(session, settings)
    prs = await service.list_project_pull_requests(
        ctx, pid, state=state, limit=limit, offset=offset
    )
    return [
        PullRequestSummary(
            id=pr.id,
            repository_id=pr.repository_id,
            number=pr.number,
            title=pr.title,
            author_login=pr.author_login,
            state=pr.state,
            head_sha=pr.head_sha,
            base_sha=pr.base_sha,
            head_ref=pr.head_ref,
            base_ref=pr.base_ref,
            diff_url=pr.diff_url,
            merged_at=pr.merged_at,
            closed_at=pr.closed_at,
            created_at=pr.created_at,
            updated_at=pr.updated_at,
        )
        for pr in prs
    ]


@project_github_router.post(
    "/pull-requests/sync",
    response_model=list[PullRequestSummary],
    status_code=status.HTTP_200_OK,
    summary="Sync pull requests from GitHub REST API",
)
@declare_permission(PERM_PROJECT_UPDATE)
async def sync_project_pull_requests(
    pid: UUID,
    state: str = Query(default="open", description="PR state to sync (open, closed, all)"),
    ctx: AuthContext = Depends(require_permission(PERM_PROJECT_UPDATE)),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> list[PullRequestSummary]:
    """Fetch recent PRs from GitHub and mirror them locally."""
    service = GitHubIngestService(session, settings)
    prs = await service.sync_pull_requests_from_github(ctx, pid, state=state)
    await session.commit()
    return [
        PullRequestSummary(
            id=pr.id,
            repository_id=pr.repository_id,
            number=pr.number,
            title=pr.title,
            author_login=pr.author_login,
            state=pr.state,
            head_sha=pr.head_sha,
            base_sha=pr.base_sha,
            head_ref=pr.head_ref,
            base_ref=pr.base_ref,
            diff_url=pr.diff_url,
            merged_at=pr.merged_at,
            closed_at=pr.closed_at,
            created_at=pr.created_at,
            updated_at=pr.updated_at,
        )
        for pr in prs
    ]


@pull_requests_router.get(
    "/{id}",
    response_model=PullRequestSummary,
    status_code=status.HTTP_200_OK,
    summary="Get mirrored pull request by ID",
)
@declare_permission(PERMISSION_AUTHENTICATED)
async def get_pull_request_by_id(
    id: UUID,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> PullRequestSummary:
    """Retrieve PR mirror record by ID."""
    service = GitHubIngestService(session, settings)
    pr = await service.get_pull_request_by_id(ctx, id)
    if pr is None:
        raise NotFoundError(detail=f"Pull request {id} not found")
    return PullRequestSummary(
        id=pr.id,
        repository_id=pr.repository_id,
        number=pr.number,
        title=pr.title,
        author_login=pr.author_login,
        state=pr.state,
        head_sha=pr.head_sha,
        base_sha=pr.base_sha,
        head_ref=pr.head_ref,
        base_ref=pr.base_ref,
        diff_url=pr.diff_url,
        merged_at=pr.merged_at,
        closed_at=pr.closed_at,
        created_at=pr.created_at,
        updated_at=pr.updated_at,
    )
