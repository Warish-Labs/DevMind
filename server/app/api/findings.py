"""Findings REST endpoints for browser and API clients (docs/03 §11.1).

Adheres to:
- docs/03 §4.2: Role-based permissions (findings:read, finding:progress, finding:triage).
- docs/03 §5.1: Lifecycle state machine transitions and audit history.
- RFC 9457: Problem Details on all failure paths.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    FindingDetailItem,
    FindingItem,
    FindingStatusTransitionRequest,
)
from app.core.auth_context import AuthContext
from app.core.errors import ForbiddenError
from app.domain.auth import (
    PERM_FINDING_PROGRESS,
    PERM_FINDING_TRIAGE,
    PERM_FINDINGS_READ,
    declare_permission,
    get_auth_context,
    get_db_session,
    require_permission,
)
from app.domain.brain import FindingsService

router = APIRouter(
    prefix="/projects/{pid}/findings",
    tags=["Findings"],
    dependencies=[Depends(get_auth_context)],
)


@router.get(
    "",
    response_model=list[FindingItem],
    summary="List project findings with optional filters",
)
@declare_permission(PERM_FINDINGS_READ)
async def list_findings(
    pid: UUID,
    status: str | None = Query(default=None, description="Filter by status (open, stale, etc.)"),
    severity: str | None = Query(
        default=None, description="Filter by severity (critical, high, etc.)"
    ),
    category: str | None = Query(
        default=None, description="Filter by category (authorization, etc.)"
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    ctx: AuthContext = Depends(require_permission(PERM_FINDINGS_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> list[FindingItem]:
    """List findings for a project filtered by status, severity, and category."""
    service = FindingsService(session)
    scoped_ctx = await service.resolve_project_context(ctx, pid)
    return await service.list_findings(
        scoped_ctx,
        pid,
        status_filter=status,
        severity_filter=severity,
        category_filter=category,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{fid}",
    response_model=FindingDetailItem,
    summary="Get finding detail with evidence and status history",
)
@declare_permission(PERM_FINDINGS_READ)
async def get_finding_detail(
    pid: UUID,
    fid: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_FINDINGS_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> FindingDetailItem:
    """Retrieve full finding detail including machine-checkable evidence and status history."""
    service = FindingsService(session)
    scoped_ctx = await service.resolve_project_context(ctx, pid)
    return await service.get_finding_detail(scoped_ctx, pid, fid)


@router.post(
    "/{fid}/transitions",
    response_model=FindingDetailItem,
    status_code=status.HTTP_200_OK,
    summary="Transition finding lifecycle status",
)
@declare_permission(PERM_FINDING_PROGRESS)
async def transition_finding_status(
    pid: UUID,
    fid: UUID,
    payload: FindingStatusTransitionRequest,
    ctx: AuthContext = Depends(require_permission(PERM_FINDING_PROGRESS)),
    session: AsyncSession = Depends(get_db_session),
) -> FindingDetailItem:
    """Transition finding status through lifecycle state machine (docs/03 §5.1).

    Permissions:
    - Triage transitions (dismissed, accepted_risk) strictly require finding:triage (maintainer).
    - Progress transitions require finding:progress (contributor+).
    """
    target = payload.to_status.lower()
    if target in ("dismissed", "accepted_risk") and not ctx.has_permission(PERM_FINDING_TRIAGE):
        raise ForbiddenError(
            code="auth.forbidden",
            message=f"Transitioning to '{target}' requires maintainer permission '{PERM_FINDING_TRIAGE}'.",
        )

    service = FindingsService(session)
    scoped_ctx = await service.resolve_project_context(ctx, pid)
    return await service.transition_status(scoped_ctx, pid, fid, payload)
