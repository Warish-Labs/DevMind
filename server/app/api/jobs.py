"""Analysis Jobs and Event Streaming API Endpoints (docs/03 §5.2, §12.2)."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    AnalysisJobCreatedResponse,
    AnalysisJobResponse,
    CreateAnalysisRequest,
)
from app.core.auth_context import AuthContext
from app.core.errors import NotFoundError
from app.domain.auth import (
    PERM_ANALYSIS_CREATE,
    PERM_PROJECT_READ,
    declare_permission,
    get_auth_context,
    get_db_session,
    require_permission,
)
from app.domain.jobs.service import JobLifecycleService

logger = logging.getLogger("devmind.api.jobs")

# Project-scoped analyses router: /projects/{pid}
project_analyses_router = APIRouter(
    prefix="/projects/{pid}",
    tags=["Analysis"],
    dependencies=[Depends(get_auth_context)],
)

# Top-level jobs router: /jobs
jobs_router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"],
    dependencies=[Depends(get_auth_context)],
)


@project_analyses_router.post(
    "/analyses",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AnalysisJobCreatedResponse,
    summary="Initiate background analysis or agent workflow",
    description="Enqueue a background agent workflow (e.g. security_review, ask_project) returning streaming links.",
)
@declare_permission(PERM_ANALYSIS_CREATE)
async def create_analysis(
    pid: UUID,
    body: CreateAnalysisRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    ctx: AuthContext = Depends(require_permission(PERM_ANALYSIS_CREATE)),
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisJobCreatedResponse:
    """Create background analysis job and return 202 Accepted with SSE event link (docs/03 §12.2)."""
    service = JobLifecycleService(session)
    job = await service.create_analysis_job(
        ctx=ctx,
        project_id=pid,
        job_type=body.type,
        params=body.params,
        idempotency_key=idempotency_key,
        consent_id=body.consent_id,
    )

    job_resp = AnalysisJobResponse.model_validate(job)
    links = {
        "self": f"/api/v1/jobs/{job.id}",
        "events": f"/api/v1/jobs/{job.id}/events",
    }
    return AnalysisJobCreatedResponse(job=job_resp, links=links)


@project_analyses_router.get(
    "/jobs",
    response_model=list[AnalysisJobResponse],
    summary="List project analysis jobs",
    description="List all background analysis jobs for the specified project.",
)
@declare_permission(PERM_PROJECT_READ)
async def list_jobs(
    pid: UUID,
    status_filter: str | None = Query(None, alias="status", description="Optional status filter"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx: AuthContext = Depends(require_permission(PERM_PROJECT_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> list[AnalysisJobResponse]:
    """List analysis jobs for project."""
    service = JobLifecycleService(session)
    jobs = await service.list_project_jobs(
        ctx=ctx,
        project_id=pid,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return [AnalysisJobResponse.model_validate(j) for j in jobs]


@jobs_router.get(
    "/{id}",
    response_model=AnalysisJobResponse,
    summary="Get background job details",
    description="Retrieve status, metadata, and result summary for a background analysis job.",
)
@declare_permission(PERM_PROJECT_READ)
async def get_job(
    id: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_PROJECT_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisJobResponse:
    """Get single job by ID."""
    service = JobLifecycleService(session)
    job = await service.get_job_by_id(ctx, id)
    if not job:
        raise NotFoundError(f"Job {id} not found", code="job.not_found")
    return AnalysisJobResponse.model_validate(job)


@jobs_router.post(
    "/{id}/cancel",
    response_model=AnalysisJobResponse,
    summary="Cancel background job",
    description="Request cooperative cancellation of a queued or running background analysis job.",
)
@declare_permission(PERM_PROJECT_READ)
async def cancel_job(
    id: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_PROJECT_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> AnalysisJobResponse:
    """Request job cancellation."""
    service = JobLifecycleService(session)
    job = await service.request_job_cancellation(ctx, id)
    return AnalysisJobResponse.model_validate(job)


@jobs_router.get(
    "/{id}/events",
    summary="Stream job milestone events (SSE)",
    description="Stream RFC 8895 Server-Sent Events with milestone progress, token counts, and terminal status.",
    response_class=StreamingResponse,
)
@declare_permission(PERM_PROJECT_READ)
async def stream_job_events(
    id: UUID,
    since_seq: int = Query(0, ge=0, description="Resume sequence number"),
    ctx: AuthContext = Depends(require_permission(PERM_PROJECT_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Stream real-time and past milestone events over SSE."""
    service = JobLifecycleService(session)

    # Validate job exists and caller has access before opening SSE stream
    job = await service.get_job_by_id(ctx, id)
    if not job:
        raise NotFoundError(f"Job {id} not found", code="job.not_found")

    async def _sse_generator() -> AsyncGenerator[str, None]:
        try:
            async for item in service.stream_job_events(ctx, id, since_seq=since_seq):
                evt_name = item.get("event", "milestone")
                data_val = item.get("data", {})
                yield f"event: {evt_name}\ndata: {json.dumps(data_val)}\n\n"
        except Exception as exc:
            logger.debug("SSE stream disconnected for job %s: %s", id, exc)

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
