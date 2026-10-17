"""Consent management REST API endpoints (docs/03 §11.1, docs/07 §7)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, status

from app.core.auth_context import AuthContext
from app.domain.auth import (
    PERM_CONSENT_MANAGE,
    declare_permission,
    require_permission,
)
from app.domain.consent import (
    ConsentItem,
    ConsentListResponse,
    ConsentService,
    CreateConsentRequest,
)

router = APIRouter(prefix="/projects/{pid}/consents", tags=["Consent"])


@router.get("", response_model=ConsentListResponse)
@declare_permission(PERM_CONSENT_MANAGE)
async def list_project_consents(
    pid: uuid.UUID,
    active_only: bool = Query(
        False, description="Filter to only currently active (unrevoked, unexpired) consents"
    ),
    scope: str | None = Query(
        None, description="Optional scope filter (e.g. snippet_transmission, cloud_index)"
    ),
    ctx: AuthContext = Depends(require_permission(PERM_CONSENT_MANAGE)),
) -> ConsentListResponse:
    """List consent records for a project."""
    items = await ConsentService.list_consents(
        ctx=ctx,
        project_id=pid,
        active_only=active_only,
        scope=scope,
    )
    return ConsentListResponse(items=items, total=len(items))


@router.post("", response_model=ConsentItem, status_code=status.HTTP_201_CREATED)
@declare_permission(PERM_CONSENT_MANAGE)
async def create_project_consent(
    pid: uuid.UUID,
    req: CreateConsentRequest,
    ctx: AuthContext = Depends(require_permission(PERM_CONSENT_MANAGE)),
) -> ConsentItem:
    """Grant source transmission or cloud indexing consent for a project."""
    return await ConsentService.create_consent(ctx=ctx, project_id=pid, req=req)


@router.delete("/{cid}", response_model=ConsentItem)
@declare_permission(PERM_CONSENT_MANAGE)
async def revoke_project_consent(
    pid: uuid.UUID,
    cid: uuid.UUID,
    ctx: AuthContext = Depends(require_permission(PERM_CONSENT_MANAGE)),
) -> ConsentItem:
    """Revoke a previously granted consent record immediately."""
    return await ConsentService.revoke_consent(ctx=ctx, project_id=pid, consent_id=cid)


@router.get("/check", response_model=dict[str, Any])
@declare_permission(PERM_CONSENT_MANAGE)
async def check_project_consent(
    pid: uuid.UUID,
    scope: str = Query(..., description="Scope to check"),
    provider_id: str | None = Query(None, description="Optional provider ID to check"),
    ctx: AuthContext = Depends(require_permission(PERM_CONSENT_MANAGE)),
) -> dict[str, Any]:
    """Check if active consent exists for a specific scope and provider."""
    try:
        await ConsentService.verify_consent(
            ctx=ctx, project_id=pid, scope=scope, provider_id=provider_id
        )
        return {"has_consent": True, "scope": scope, "provider_id": provider_id}
    except Exception:
        return {"has_consent": False, "scope": scope, "provider_id": provider_id}
