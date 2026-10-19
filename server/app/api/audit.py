"""Audit event REST endpoints for workspace governance and security logs (docs/03 §11.1)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import AuditEventItem
from app.core.auth_context import AuthContext
from app.domain.audit.service import AuditService
from app.domain.auth import (
    PERM_AUDIT_READ,
    PERM_PROJECT_READ,
    declare_permission,
    get_auth_context,
    get_db_session,
    require_permission,
)

workspace_audit_router = APIRouter(
    prefix="/workspaces",
    tags=["Audit"],
    dependencies=[Depends(get_auth_context)],
)

project_audit_router = APIRouter(
    prefix="/projects",
    tags=["Audit"],
    dependencies=[Depends(get_auth_context)],
)


@workspace_audit_router.get(
    "/{workspace_id}/audit-events",
    response_model=list[AuditEventItem],
    summary="List workspace audit events",
    description="Retrieve append-only audit event log for the workspace. Requires workspace admin or owner.",
)
@declare_permission(PERM_AUDIT_READ)
async def list_workspace_audit_events(
    workspace_id: UUID,
    action: str | None = Query(default=None, description="Filter by event action (e.g. consent.revoked)"),
    target_kind: str | None = Query(default=None, description="Filter by target kind (e.g. project, consent)"),
    target_id: str | None = Query(default=None, description="Filter by target identifier"),
    actor_id: UUID | None = Query(default=None, description="Filter by actor user ID"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of events to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    ctx: AuthContext = Depends(require_permission(PERM_AUDIT_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> list[AuditEventItem]:
    """List audit events in the workspace with tenant isolation and optional filtering."""
    service = AuditService(session)
    events = await service.list_workspace_audit_events(
        ctx,
        workspace_id=workspace_id,
        action=action,
        target_kind=target_kind,
        target_id=target_id,
        actor_id=actor_id,
        limit=limit,
        offset=offset,
    )
    return [AuditEventItem.model_validate(e) for e in events]


@project_audit_router.get(
    "/{pid}/audit-events",
    response_model=list[AuditEventItem],
    summary="List project audit events",
    description="Retrieve append-only audit events scoped to a specific project. Requires project read permission.",
)
@declare_permission(PERM_PROJECT_READ)
async def list_project_audit_events(
    pid: UUID,
    action: str | None = Query(default=None, description="Filter by event action"),
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of events to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    ctx: AuthContext = Depends(require_permission(PERM_PROJECT_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> list[AuditEventItem]:
    """List audit events for a project with tenant isolation and optional action filtering."""
    service = AuditService(session)
    events = await service.list_project_audit_events(
        ctx,
        project_id=pid,
        action=action,
        limit=limit,
        offset=offset,
    )
    return [AuditEventItem.model_validate(e) for e in events]
