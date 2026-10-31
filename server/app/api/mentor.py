"""Project Mentor and Evaluation REST API endpoints (docs/01 CAP-08, CAP-09, docs/03 §3.6, §3.7).

Provides endpoints for:
- Managing project backlog tasks and topological dependencies
- Querying AI-driven next task recommendations based on DAG analysis
- Triggering multidimensional project release-readiness evaluations
- Retrieving latest and historical evaluation scorecards
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
    declare_permission,
    get_auth_context,
    get_db_session,
)
from app.domain.mentor.schemas import (
    ProjectEvaluationResponse,
    ProjectEvaluationRunRequest,
    ProjectTaskCreate,
    ProjectTaskResponse,
    ProjectTaskUpdate,
    TaskDependencyCreate,
    TaskDependencyResponse,
    TaskRecommendationResponse,
)
from app.domain.mentor.service import ProjectMentorService

logger = logging.getLogger("devmind.api.mentor")

mentor_router = APIRouter(tags=["Project Mentor"])


# ---------------------------------------------------------------------------
# Project Tasks & Dependencies
# ---------------------------------------------------------------------------


@mentor_router.get(
    "/projects/{project_id}/tasks",
    response_model=list[ProjectTaskResponse],
    status_code=status.HTTP_200_OK,
    summary="List project tasks",
    description="Retrieve paginated backlog tasks for a project, optionally filtered by status and priority.",
)
@declare_permission(PERM_PROJECT_READ)
async def list_project_tasks(
    project_id: UUID,
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="Filter by task status (open, in_progress, blocked, completed, cancelled)",
    ),
    priority: str | None = Query(
        default=None,
        description="Filter by task priority (critical, high, medium, low)",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[ProjectTaskResponse]:
    """List backlog tasks for a project."""
    service = ProjectMentorService(session)
    return await service.list_tasks(
        ctx=ctx,
        project_id=project_id,
        status=status_filter,
        priority=priority,
        limit=limit,
        offset=offset,
    )


@mentor_router.post(
    "/projects/{project_id}/tasks",
    response_model=ProjectTaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create project task",
    description="Create a new task in the project backlog with optional prerequisite dependencies.",
)
@declare_permission(PERM_PROJECT_UPDATE)
async def create_project_task(
    project_id: UUID,
    payload: ProjectTaskCreate,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectTaskResponse:
    """Create a new backlog task."""
    service = ProjectMentorService(session)
    return await service.create_task(ctx=ctx, project_id=project_id, payload=payload)


@mentor_router.get(
    "/projects/{project_id}/tasks/recommend",
    response_model=TaskRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get recommended next task",
    description="Analyze the project's dependency DAG and recommend the highest-leverage unblocked task.",
)
@declare_permission(PERM_PROJECT_READ)
async def get_task_recommendation(
    project_id: UUID,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> TaskRecommendationResponse:
    """Get the next recommended backlog task."""
    service = ProjectMentorService(session)
    return await service.recommend_next_task(ctx=ctx, project_id=project_id)


@mentor_router.get(
    "/projects/{project_id}/tasks/{task_id}",
    response_model=ProjectTaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project task",
    description="Retrieve details for a single backlog task including dependencies and dependents.",
)
@declare_permission(PERM_PROJECT_READ)
async def get_project_task(
    project_id: UUID,
    task_id: UUID,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectTaskResponse:
    """Retrieve details for a specific task."""
    service = ProjectMentorService(session)
    return await service.get_task(ctx=ctx, project_id=project_id, task_id=task_id)


@mentor_router.patch(
    "/projects/{project_id}/tasks/{task_id}",
    response_model=ProjectTaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Update project task",
    description="Update mutable fields of a project backlog task.",
)
@declare_permission(PERM_PROJECT_UPDATE)
async def update_project_task(
    project_id: UUID,
    task_id: UUID,
    payload: ProjectTaskUpdate,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectTaskResponse:
    """Update task details."""
    service = ProjectMentorService(session)
    return await service.update_task(
        ctx=ctx,
        project_id=project_id,
        task_id=task_id,
        payload=payload,
    )


@mentor_router.delete(
    "/projects/{project_id}/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project task",
    description="Delete a backlog task and cascade-remove associated dependency links.",
)
@declare_permission(PERM_PROJECT_UPDATE)
async def delete_project_task(
    project_id: UUID,
    task_id: UUID,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """Delete a task from project backlog."""
    service = ProjectMentorService(session)
    await service.delete_task(ctx=ctx, project_id=project_id, task_id=task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@mentor_router.post(
    "/projects/{project_id}/tasks/{task_id}/dependencies",
    response_model=TaskDependencyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add task dependency",
    description="Declare that task_id depends on depends_on_task_id, preventing cycles.",
)
@declare_permission(PERM_PROJECT_UPDATE)
async def add_task_dependency(
    project_id: UUID,
    task_id: UUID,
    payload: TaskDependencyCreate,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> TaskDependencyResponse:
    """Add a dependency relationship between two tasks."""
    service = ProjectMentorService(session)
    return await service.add_dependency(
        ctx=ctx,
        project_id=project_id,
        task_id=task_id,
        depends_on_task_id=payload.depends_on_task_id,
    )


@mentor_router.delete(
    "/projects/{project_id}/tasks/{task_id}/dependencies/{depends_on_task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove task dependency",
    description="Remove a dependency edge between two tasks.",
)
@declare_permission(PERM_PROJECT_UPDATE)
async def remove_task_dependency(
    project_id: UUID,
    task_id: UUID,
    depends_on_task_id: UUID,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """Remove a dependency edge."""
    service = ProjectMentorService(session)
    await service.remove_dependency(
        ctx=ctx,
        project_id=project_id,
        task_id=task_id,
        depends_on_task_id=depends_on_task_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Project Evaluations & Release Readiness
# ---------------------------------------------------------------------------


@mentor_router.get(
    "/projects/{project_id}/evaluations",
    response_model=list[ProjectEvaluationResponse],
    status_code=status.HTTP_200_OK,
    summary="List project evaluations",
    description="Retrieve paginated historical multidimensional evaluations for a project.",
)
@declare_permission(PERM_PROJECT_READ)
async def list_project_evaluations(
    project_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[ProjectEvaluationResponse]:
    """List historical project evaluations."""
    service = ProjectMentorService(session)
    return await service.list_evaluations(
        ctx=ctx,
        project_id=project_id,
        limit=limit,
        offset=offset,
    )


@mentor_router.post(
    "/projects/{project_id}/evaluations/run",
    response_model=ProjectEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run project evaluation",
    description="Execute an on-demand multidimensional health evaluation and store release-readiness verdict.",
)
@declare_permission(PERM_ANALYSIS_CREATE)
async def run_project_evaluation(
    project_id: UUID,
    payload: ProjectEvaluationRunRequest,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectEvaluationResponse:
    """Trigger an on-demand project health evaluation."""
    service = ProjectMentorService(session)
    return await service.evaluate_project(ctx=ctx, project_id=project_id, payload=payload)


@mentor_router.get(
    "/projects/{project_id}/evaluations/latest",
    response_model=ProjectEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get latest project evaluation",
    description="Retrieve the most recent health scorecard and release-readiness verdict for a project.",
)
@declare_permission(PERM_PROJECT_READ)
async def get_latest_project_evaluation(
    project_id: UUID,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectEvaluationResponse:
    """Retrieve the latest evaluation record."""
    service = ProjectMentorService(session)
    return await service.get_latest_evaluation(ctx=ctx, project_id=project_id)


@mentor_router.get(
    "/projects/{project_id}/evaluations/{evaluation_id}",
    response_model=ProjectEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project evaluation detail",
    description="Retrieve detailed results for a specific evaluation by ID.",
)
@declare_permission(PERM_PROJECT_READ)
async def get_project_evaluation(
    project_id: UUID,
    evaluation_id: UUID,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectEvaluationResponse:
    """Retrieve details of a specific evaluation."""
    service = ProjectMentorService(session)
    return await service.get_evaluation(
        ctx=ctx,
        project_id=project_id,
        evaluation_id=evaluation_id,
    )
