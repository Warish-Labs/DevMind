"""Bug Memory REST API endpoints (docs/01 CAP-03, docs/03 §3.4, §11.1).

Provides endpoints for:
- Listing and creating project bug memory records
- Hybrid similarity matching against past incidents and resolutions
- Retrieving single bug record details and resolutions
- Documenting resolutions for resolved bugs
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
    PERMISSION_AUTHENTICATED,
    declare_permission,
    get_auth_context,
    get_db_session,
)
from app.domain.bug_memory import (
    BugMatchRequest,
    BugMatchResponse,
    BugMemoryService,
    BugRecordCreate,
    BugRecordDetailResponse,
    BugRecordResponse,
    BugResolutionCreate,
    BugResolutionResponse,
)

logger = logging.getLogger(__name__)

bug_memory_router = APIRouter(tags=["Bug Memory"])


@bug_memory_router.get(
    "/projects/{project_id}/bugs",
    response_model=list[BugRecordResponse],
    status_code=status.HTTP_200_OK,
    summary="List project bug records",
    description="Retrieve paginated bug records tracked for a project, optionally filtered by module hint.",
)
@declare_permission(PERM_PROJECT_READ)
async def list_project_bugs(
    project_id: UUID,
    module_hint: str | None = Query(
        default=None, description="Optional module or subsystem hint filter"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[BugRecordResponse]:
    """List historical bug records for a project."""
    service = BugMemoryService(session)
    return await service.list_bugs(
        ctx=ctx,
        project_id=project_id,
        module_hint=module_hint,
        limit=limit,
        offset=offset,
    )


@bug_memory_router.post(
    "/projects/{project_id}/bugs",
    response_model=BugRecordDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log or upsert a project bug record",
    description="Normalize an error trace, deduplicate by signature fingerprint, and record occurrence count.",
)
@declare_permission(PERM_ANALYSIS_CREATE)
async def create_project_bug(
    project_id: UUID,
    payload: BugRecordCreate,
    response: Response,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> BugRecordDetailResponse:
    """Normalize and record a bug occurrence, attaching initial resolution if provided."""
    service = BugMemoryService(session)
    record, is_new = await service.record_bug(
        ctx=ctx,
        project_id=project_id,
        data=payload,
    )
    if not is_new:
        response.status_code = status.HTTP_200_OK
    return record


@bug_memory_router.post(
    "/projects/{project_id}/bugs/match",
    response_model=BugMatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Match error trace against Bug Memory",
    description="Find similar historical bugs using hybrid fingerprint, token, and module similarity, with AI synthesis.",
)
@declare_permission(PERM_PROJECT_READ)
async def match_project_bugs(
    project_id: UUID,
    payload: BugMatchRequest,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> BugMatchResponse:
    """Perform hybrid similarity search and comparison for an observed error trace."""
    service = BugMemoryService(session)
    return await service.match_bugs(
        ctx=ctx,
        project_id=project_id,
        data=payload,
    )


@bug_memory_router.get(
    "/bugs/{bug_id}",
    response_model=BugRecordDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get bug record detail with resolutions",
    description="Retrieve a single bug record by ID, including its full resolution history.",
)
@declare_permission(PERMISSION_AUTHENTICATED)
async def get_bug_record(
    bug_id: UUID,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> BugRecordDetailResponse:
    """Retrieve bug record detail within authorized workspace."""
    service = BugMemoryService(session)
    return await service.get_bug_by_id(ctx=ctx, bug_id=bug_id)


@bug_memory_router.post(
    "/bugs/{bug_id}/resolutions",
    response_model=BugResolutionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add resolution to a bug record",
    description="Document root cause, code fix, and affected files for a resolved bug record.",
)
@declare_permission(PERMISSION_AUTHENTICATED)
async def add_bug_resolution(
    bug_id: UUID,
    payload: BugResolutionCreate,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> BugResolutionResponse:
    """Attach a verified resolution to an existing bug record."""
    service = BugMemoryService(session)
    return await service.add_resolution(
        ctx=ctx,
        bug_id=bug_id,
        data=payload,
    )
