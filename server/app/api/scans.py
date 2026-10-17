"""Scans REST endpoints for browser and API clients (docs/03 §11.1)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ScanRunItem
from app.core.auth_context import AuthContext
from app.domain.auth import (
    PERM_PROJECT_READ,
    declare_permission,
    get_auth_context,
    get_db_session,
    require_permission,
)
from app.domain.brain import ScanService

router = APIRouter(
    prefix="/projects/{pid}/scans",
    tags=["Scans"],
    dependencies=[Depends(get_auth_context)],
)


@router.get(
    "",
    response_model=list[ScanRunItem],
    summary="List project scan runs",
)
@declare_permission(PERM_PROJECT_READ)
async def list_scans(
    pid: UUID,
    status: str | None = Query(
        default=None, description="Filter by status (running, completed, failed, cancelled)"
    ),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    ctx: AuthContext = Depends(require_permission(PERM_PROJECT_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> list[ScanRunItem]:
    """List recent scan runs for a project ordered by start time descending."""
    service = ScanService(session)
    scoped_ctx = await service.resolve_project_context(ctx, pid)
    return await service.list_scans(
        scoped_ctx, pid, status_filter=status, limit=limit, offset=offset
    )


@router.get(
    "/{sid}",
    response_model=ScanRunItem,
    summary="Get scan run details and statistics",
)
@declare_permission(PERM_PROJECT_READ)
async def get_scan_detail(
    pid: UUID,
    sid: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_PROJECT_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> ScanRunItem:
    """Retrieve details and statistics of a specific scan run."""
    service = ScanService(session)
    scoped_ctx = await service.resolve_project_context(ctx, pid)
    return await service.get_scan(scoped_ctx, pid, sid)
