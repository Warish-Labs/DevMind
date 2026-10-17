"""Brain tenant context resolver (docs/03 §4, Rule 4)."""

from __future__ import annotations

import dataclasses
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import ForbiddenError, NotFoundError
from app.persistence.models.project import Project, ProjectMembership
from app.persistence.models.workspace import WorkspaceMembership


async def resolve_project_context(
    session: AsyncSession,
    ctx: AuthContext | SystemContext,
    project_id: UUID,
) -> AuthContext | SystemContext:
    """Resolve and verify tenant workspace context for caller on target project."""
    if isinstance(ctx, SystemContext):
        return ctx

    stmt = select(Project).where(
        Project.id == project_id,
        Project.deleted_at.is_(None),
    )
    res = await session.execute(stmt)
    project = res.scalars().first()
    if project is None:
        raise NotFoundError(detail=f"Project '{project_id}' not found")

    if ctx.workspace_id == project.workspace_id:
        return ctx

    # Check workspace membership
    ws_stmt = select(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == project.workspace_id,
        WorkspaceMembership.user_id == ctx.user_id,
    )
    ws_mem = (await session.execute(ws_stmt)).scalars().first()

    if ws_mem is None:
        # Check direct project membership
        pm_stmt = select(ProjectMembership).where(
            ProjectMembership.project_id == project.id,
            ProjectMembership.user_id == ctx.user_id,
        )
        pm = (await session.execute(pm_stmt)).scalars().first()
        if pm is None:
            raise ForbiddenError(
                detail=f"Forbidden: caller lacks membership in project '{project_id}'"
            )

    return dataclasses.replace(
        ctx,
        workspace_id=project.workspace_id,
        project_id=project.id,
        workspace_role=ws_mem.role if ws_mem else None,
    )
