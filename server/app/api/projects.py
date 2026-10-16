"""Project REST endpoints for codebase boundaries and access (docs/03 §11.1)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    AddProjectMemberRequest,
    CreateProjectRequest,
    ProjectMemberResponse,
    ProjectResponse,
    UpdateProjectRequest,
)
from app.core.auth_context import AuthContext
from app.domain.auth import (
    PERM_MEMBERS_MANAGE,
    PERM_PROJECT_DELETE,
    PERM_PROJECT_READ,
    PERM_PROJECT_UPDATE,
    PERM_WORKSPACE_MANAGE,
    PERM_WORKSPACE_READ,
    declare_permission,
    get_auth_context,
    get_db_session,
    require_permission,
)
from app.domain.projects.service import ProjectService

# Workspace-scoped projects router (/workspaces/{wid}/projects)
workspace_projects_router = APIRouter(
    prefix="/workspaces/{wid}/projects",
    tags=["Projects"],
    dependencies=[Depends(get_auth_context)],
)

# Direct project router (/projects/{pid})
projects_router = APIRouter(
    prefix="/projects/{pid}",
    tags=["Projects"],
    dependencies=[Depends(get_auth_context)],
)


@workspace_projects_router.get(
    "",
    response_model=list[ProjectResponse],
    summary="List workspace projects",
    description="List all codebase projects in the specified workspace.",
)
@declare_permission(PERM_WORKSPACE_READ)
async def list_projects(
    wid: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_WORKSPACE_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> list[ProjectResponse]:
    service = ProjectService(session)
    projects = await service.list_workspace_projects(ctx, workspace_id=wid)
    return [ProjectResponse.model_validate(p) for p in projects]


@workspace_projects_router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create project",
    description="Create a new codebase project inside the specified workspace.",
)
@declare_permission(PERM_WORKSPACE_MANAGE)
async def create_project(
    wid: UUID,
    payload: CreateProjectRequest,
    ctx: AuthContext = Depends(require_permission(PERM_WORKSPACE_MANAGE)),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    service = ProjectService(session)
    project = await service.create_project(
        ctx,
        workspace_id=wid,
        name=payload.name,
        slug=payload.slug,
        visibility=payload.visibility,
        sync_mode=payload.sync_mode,
        source_kind=payload.source_kind,
        primary_language=payload.primary_language,
        default_branch=payload.default_branch,
    )
    return ProjectResponse.model_validate(project)


@projects_router.get(
    "",
    response_model=ProjectResponse,
    summary="Get project",
    description="Retrieve codebase project details by project identifier.",
)
@declare_permission(PERM_PROJECT_READ)
async def get_project(
    pid: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_PROJECT_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    service = ProjectService(session)
    project = await service.get_project(ctx, pid)
    return ProjectResponse.model_validate(project)


@projects_router.patch(
    "",
    response_model=ProjectResponse,
    summary="Update project",
    description="Update mutable project configuration (name, slug, visibility, sync_mode).",
)
@declare_permission(PERM_PROJECT_UPDATE)
async def update_project(
    pid: UUID,
    payload: UpdateProjectRequest,
    ctx: AuthContext = Depends(require_permission(PERM_PROJECT_UPDATE)),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    service = ProjectService(session)
    project = await service.update_project(
        ctx,
        pid,
        name=payload.name,
        slug=payload.slug,
        visibility=payload.visibility,
        sync_mode=payload.sync_mode,
        primary_language=payload.primary_language,
        default_branch=payload.default_branch,
    )
    return ProjectResponse.model_validate(project)


@projects_router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete project",
    description="Soft delete a codebase project.",
)
@declare_permission(PERM_PROJECT_DELETE)
async def delete_project(
    pid: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_PROJECT_DELETE)),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    service = ProjectService(session)
    await service.delete_project(ctx, pid)


@projects_router.get(
    "/members",
    response_model=list[ProjectMemberResponse],
    summary="List project members",
    description="List all explicit members assigned to the project.",
)
@declare_permission(PERM_PROJECT_READ)
async def list_project_members(
    pid: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_PROJECT_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> list[ProjectMemberResponse]:
    service = ProjectService(session)
    memberships = await service.list_members(ctx, pid)
    return [ProjectMemberResponse.model_validate(m) for m in memberships]


@projects_router.post(
    "/members",
    response_model=ProjectMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add project member",
    description="Assign an explicit role to a user for this project.",
)
@declare_permission(PERM_MEMBERS_MANAGE)
async def add_project_member(
    pid: UUID,
    payload: AddProjectMemberRequest,
    ctx: AuthContext = Depends(require_permission(PERM_MEMBERS_MANAGE)),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectMemberResponse:
    service = ProjectService(session)
    membership = await service.add_member(
        ctx,
        project_id=pid,
        user_id=payload.user_id,
        role=payload.role,
    )
    return ProjectMemberResponse.model_validate(membership)


@projects_router.delete(
    "/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove project member",
    description="Remove explicit project membership for a user.",
)
@declare_permission(PERM_MEMBERS_MANAGE)
async def remove_project_member(
    pid: UUID,
    user_id: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_MEMBERS_MANAGE)),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    service = ProjectService(session)
    await service.remove_member(ctx, project_id=pid, user_id=user_id)
