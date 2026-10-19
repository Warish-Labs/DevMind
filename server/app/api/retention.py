"""Retention policies and cleanup sweep REST API endpoints (docs/03 §3.1, docs/07 §9, ADR-026)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.api.schemas import (
    EffectiveRetentionCategory,
    EffectiveRetentionResponse,
    RetentionPolicyResponse,
    RetentionSweepResponse,
    UpdateRetentionPolicyRequest,
)
from app.core.auth_context import AuthContext
from app.domain.auth import (
    PERM_PROJECT_READ,
    PERM_PROJECT_UPDATE,
    PERM_WORKSPACE_MANAGE,
    PERM_WORKSPACE_READ,
    declare_permission,
    require_permission,
)
from app.domain.retention.retention_service import RetentionService

workspace_retention_router = APIRouter(prefix="/workspaces/{wid}/retention", tags=["Retention"])
project_retention_router = APIRouter(prefix="/projects/{pid}/retention", tags=["Retention"])

_service = RetentionService()


@workspace_retention_router.get("", response_model=EffectiveRetentionResponse)
@declare_permission(PERM_WORKSPACE_READ)
async def get_workspace_retention(
    wid: uuid.UUID,
    ctx: AuthContext = Depends(require_permission(PERM_WORKSPACE_READ)),
) -> EffectiveRetentionResponse:
    """Retrieve workspace retention windows and defaults."""
    summary = await _service.get_workspace_retention(ctx, wid)
    return EffectiveRetentionResponse(
        workspace_id=summary.workspace_id,
        project_id=summary.project_id,
        backup_retention_notice=summary.backup_retention_notice,
        categories=[
            EffectiveRetentionCategory(
                kind=c.kind,
                days=c.days,
                default_days=c.default_days,
                description=c.description,
                is_custom=c.is_custom,
                source=c.source,
            )
            for c in summary.categories
        ],
    )


@workspace_retention_router.put("/{kind}", response_model=RetentionPolicyResponse)
@declare_permission(PERM_WORKSPACE_MANAGE)
async def update_workspace_retention(
    wid: uuid.UUID,
    kind: str,
    payload: UpdateRetentionPolicyRequest,
    ctx: AuthContext = Depends(require_permission(PERM_WORKSPACE_MANAGE)),
) -> RetentionPolicyResponse:
    """Configure retention window for a specific category at workspace level."""
    item = await _service.update_workspace_retention(ctx, wid, kind, payload.days)
    return RetentionPolicyResponse(
        id=item.id,
        workspace_id=item.workspace_id,
        project_id=item.project_id,
        kind=item.kind,
        days=item.days,
        is_override=item.is_override,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@project_retention_router.get("", response_model=EffectiveRetentionResponse)
@declare_permission(PERM_PROJECT_READ)
async def get_project_retention(
    pid: uuid.UUID,
    ctx: AuthContext = Depends(require_permission(PERM_PROJECT_READ)),
) -> EffectiveRetentionResponse:
    """Retrieve effective retention windows for a project (including project overrides)."""
    summary = await _service.get_project_retention(ctx, pid)
    return EffectiveRetentionResponse(
        workspace_id=summary.workspace_id,
        project_id=summary.project_id,
        backup_retention_notice=summary.backup_retention_notice,
        categories=[
            EffectiveRetentionCategory(
                kind=c.kind,
                days=c.days,
                default_days=c.default_days,
                description=c.description,
                is_custom=c.is_custom,
                source=c.source,
            )
            for c in summary.categories
        ],
    )


@project_retention_router.put("/{kind}", response_model=RetentionPolicyResponse)
@declare_permission(PERM_PROJECT_UPDATE)
async def update_project_retention(
    pid: uuid.UUID,
    kind: str,
    payload: UpdateRetentionPolicyRequest,
    ctx: AuthContext = Depends(require_permission(PERM_PROJECT_UPDATE)),
) -> RetentionPolicyResponse:
    """Set a project-level retention override for a category."""
    item = await _service.update_project_retention(ctx, pid, kind, payload.days)
    return RetentionPolicyResponse(
        id=item.id,
        workspace_id=item.workspace_id,
        project_id=item.project_id,
        kind=item.kind,
        days=item.days,
        is_override=item.is_override,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@project_retention_router.delete("/{kind}", status_code=status.HTTP_204_NO_CONTENT)
@declare_permission(PERM_PROJECT_UPDATE)
async def reset_project_retention(
    pid: uuid.UUID,
    kind: str,
    ctx: AuthContext = Depends(require_permission(PERM_PROJECT_UPDATE)),
) -> None:
    """Reset a project-level retention override back to workspace default."""
    await _service.reset_project_retention(ctx, pid, kind)


@project_retention_router.post("/sweep", response_model=RetentionSweepResponse)
@declare_permission(PERM_PROJECT_UPDATE)
async def trigger_project_retention_sweep(
    pid: uuid.UUID,
    ctx: AuthContext = Depends(require_permission(PERM_PROJECT_UPDATE)),
) -> RetentionSweepResponse:
    """Trigger an on-demand retention cleanup sweep for this project."""
    reports = await _service.execute_retention_sweep(ctx, project_id=pid)
    if not reports:
        return RetentionSweepResponse(
            project_id=str(pid),
            swept_at="",
            purged_counts={},
            effective_windows={},
        )
    rep = reports[0]
    return RetentionSweepResponse(
        project_id=rep.project_id,
        swept_at=rep.swept_at,
        purged_counts=rep.purged_counts,
        effective_windows=rep.effective_windows,
    )
