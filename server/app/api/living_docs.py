"""Living Documentation REST API endpoints (docs/01 CAP-04, docs/03 §3.4, §11.2).

Provides endpoints for:
- Listing and registering tracked project documentation files
- Deterministic and agent-assisted documentation drift detection
- Reviewing drift items and patch proposal diffs
- Human approval gate (approve / reject proposal)
- Applying approved documentation patches
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext
from app.domain.auth import (
    PERM_ANALYSIS_CREATE,
    PERM_PROJECT_READ,
    PERM_PROJECT_UPDATE,
    PERMISSION_AUTHENTICATED,
    declare_permission,
    get_auth_context,
    get_db_session,
)
from app.domain.living_docs import (
    DocDriftDetectRequest,
    DocDriftDetectResponse,
    DocDriftItemResponse,
    DocRecordCreate,
    DocRecordDetailResponse,
    DocRecordResponse,
    DriftActionResponse,
    DriftApprovalRequest,
    LivingDocService,
)

logger = logging.getLogger(__name__)

living_docs_router = APIRouter(tags=["Living Documentation"])


@living_docs_router.get(
    "/projects/{project_id}/docs",
    response_model=list[DocRecordResponse],
    status_code=status.HTTP_200_OK,
    summary="List project documentation records",
    description="Retrieve tracked documentation files for a project, optionally filtered by kind.",
)
@declare_permission(PERM_PROJECT_READ)
async def list_project_docs(
    project_id: UUID,
    kind: str | None = Query(
        default=None, description="Optional kind filter (readme, api, architecture)"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[DocRecordResponse]:
    """List tracked documentation records for caller's authorized project."""
    service = LivingDocService(session=session)
    return await service.list_documents(
        ctx=ctx,
        project_id=project_id,
        kind=kind,
        limit=limit,
        offset=offset,
    )


@living_docs_router.post(
    "/projects/{project_id}/docs",
    response_model=DocRecordDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register or update project documentation",
    description="Register or update a documentation file, parse sections and code mentions.",
)
@declare_permission(PERM_PROJECT_UPDATE)
async def register_project_doc(
    project_id: UUID,
    payload: DocRecordCreate,
    response: Response,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> DocRecordDetailResponse:
    """Register or update a documentation record and extract symbols."""
    service = LivingDocService(session=session)
    result = await service.register_document(ctx=ctx, project_id=project_id, data=payload)
    response.headers["Location"] = f"/api/v1/projects/{project_id}/docs/{result.id}"
    return result


@living_docs_router.post(
    "/projects/{project_id}/docs/detect-drift",
    response_model=DocDriftDetectResponse,
    status_code=status.HTTP_200_OK,
    summary="Detect documentation drift and synthesize patch proposals",
    description="Runs DocsAlive drift detection against ground-truth code symbols and routes.",
)
@declare_permission(PERM_ANALYSIS_CREATE)
async def detect_doc_drift(
    project_id: UUID,
    payload: DocDriftDetectRequest,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> DocDriftDetectResponse:
    """Run DocsAlive drift analysis and generate patch proposals."""
    service = LivingDocService(session=session)
    return await service.detect_drift(ctx=ctx, project_id=project_id, req=payload)


@living_docs_router.get(
    "/projects/{project_id}/docs/drift",
    response_model=list[DocDriftItemResponse],
    status_code=status.HTTP_200_OK,
    summary="List documentation drift items",
    description="Retrieve tracked documentation drift items, filtered by status or kind.",
)
@declare_permission(PERM_PROJECT_READ)
async def list_project_drift_items(
    project_id: UUID,
    status: str | None = Query(
        default=None, description="Optional status filter (detected, approved, rejected, applied)"
    ),
    kind: str | None = Query(
        default=None,
        description="Optional drift kind filter (undocumented_route, removed_route, missing_symbol)",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[DocDriftItemResponse]:
    """List tracked drift items for a project."""
    service = LivingDocService(session=session)
    return await service.list_drift_items(
        ctx=ctx,
        project_id=project_id,
        status=status,
        kind=kind,
        limit=limit,
        offset=offset,
    )


@living_docs_router.get(
    "/projects/{project_id}/docs/{doc_id}",
    response_model=DocRecordDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get documentation record detail",
    description="Retrieve a documentation record with cached snapshot and extracted symbol metadata.",
)
@declare_permission(PERM_PROJECT_READ)
async def get_project_doc(
    project_id: UUID,
    doc_id: UUID,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> DocRecordDetailResponse:
    """Get documentation record detail."""
    service = LivingDocService(session=session)
    return await service.get_document(ctx=ctx, doc_id=doc_id)


@living_docs_router.get(
    "/docs/drift/{drift_id}",
    response_model=DocDriftItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Get drift item and patch proposal",
    description="Retrieve a single drift item with its proposed unified diff patch.",
)
@declare_permission(PERMISSION_AUTHENTICATED)
async def get_drift_item(
    drift_id: UUID,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> DocDriftItemResponse:
    """Get single drift item and proposed patch."""
    service = LivingDocService(session=session)
    return await service.get_drift_item(ctx=ctx, drift_id=drift_id)


@living_docs_router.post(
    "/docs/drift/{drift_id}/approve",
    response_model=DriftActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve documentation patch proposal",
    description="Human approval gate: maintainer marks patch proposal as approved for application.",
)
@declare_permission(PERMISSION_AUTHENTICATED)
async def approve_drift_proposal(
    drift_id: UUID,
    payload: DriftApprovalRequest,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> DriftActionResponse:
    """Maintainer approves a proposed patch."""
    service = LivingDocService(session=session)
    return await service.approve_drift_item(ctx=ctx, drift_id=drift_id, req=payload)


@living_docs_router.post(
    "/docs/drift/{drift_id}/reject",
    response_model=DriftActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject documentation patch proposal",
    description="Maintainer rejects a proposed documentation patch.",
)
@declare_permission(PERMISSION_AUTHENTICATED)
async def reject_drift_proposal(
    drift_id: UUID,
    payload: DriftApprovalRequest,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> DriftActionResponse:
    """Maintainer rejects a proposed patch."""
    service = LivingDocService(session=session)
    return await service.reject_drift_item(ctx=ctx, drift_id=drift_id, req=payload)


@living_docs_router.post(
    "/docs/drift/{drift_id}/apply",
    response_model=DriftActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Apply approved documentation patch",
    description="Apply approved patch to documentation record. Fails with 409 if not approved.",
)
@declare_permission(PERMISSION_AUTHENTICATED)
async def apply_drift_patch(
    drift_id: UUID,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> DriftActionResponse:
    """Apply approved documentation patch."""
    service = LivingDocService(session=session)
    return await service.apply_drift_patch(ctx=ctx, drift_id=drift_id)
