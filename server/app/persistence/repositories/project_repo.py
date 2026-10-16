"""Project repository for codebase boundary and per-project access (docs/03 §3.1)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.persistence.models.project import Project, ProjectMembership
from app.persistence.repositories.base import BaseRepository


class ProjectRepository(BaseRepository):
    """Repository managing Project codebases and project-level memberships."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        include_deleted: bool = False,
    ) -> Project | None:
        """Find project by ID scoped to caller workspace."""
        self._validate_context(ctx)
        stmt = select(Project).where(Project.id == project_id)
        stmt = self._scope_workspace_query(stmt, Project.workspace_id, ctx)
        if not include_deleted:
            stmt = stmt.where(Project.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_slug(
        self,
        ctx: AuthContext | SystemContext,
        slug: str,
        workspace_id: UUID | None = None,
        include_deleted: bool = False,
    ) -> Project | None:
        """Find project by slug within a workspace."""
        self._validate_context(ctx)
        stmt = select(Project).where(Project.slug == slug)
        stmt = self._scope_workspace_query(
            stmt, Project.workspace_id, ctx, target_workspace_id=workspace_id
        )
        if not include_deleted:
            stmt = stmt.where(Project.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_for_workspace(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID | None = None,
        include_archived: bool = False,
        include_deleted: bool = False,
    ) -> list[Project]:
        """List all projects within the active workspace."""
        self._validate_context(ctx)
        stmt = select(Project)
        stmt = self._scope_workspace_query(
            stmt, Project.workspace_id, ctx, target_workspace_id=workspace_id
        )
        if not include_archived:
            stmt = stmt.where(Project.archived_at.is_(None))
        if not include_deleted:
            stmt = stmt.where(Project.deleted_at.is_(None))
        stmt = stmt.order_by(Project.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        ctx: AuthContext | SystemContext,
        *,
        name: str,
        slug: str,
        visibility: str = "workspace",
        sync_mode: str = "metadata_only",
        source_kind: str = "local",
        primary_language: str | None = None,
        default_branch: str = "main",
        workspace_id: UUID | None = None,
    ) -> Project:
        """Create a new project in the workspace."""
        self._validate_context(ctx)
        ws_id = workspace_id or (
            ctx.workspace_id if isinstance(ctx, AuthContext) else ctx.workspace_id
        )
        if ws_id is None:
            raise ValueError("workspace_id must be provided or present in AuthContext")

        project = Project(
            workspace_id=ws_id,
            name=name,
            slug=slug,
            visibility=visibility,
            sync_mode=sync_mode,
            source_kind=source_kind,
            primary_language=primary_language,
            default_branch=default_branch,
        )
        self.session.add(project)
        await self.session.flush()
        return project

    async def update(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        **updates: Any,
    ) -> Project | None:
        """Update mutable fields on a project."""
        self._validate_context(ctx)
        project = await self.get_by_id(ctx, project_id)
        if not project:
            return None

        allowed_fields = {
            "name",
            "slug",
            "visibility",
            "sync_mode",
            "primary_language",
            "default_branch",
            "archived_at",
        }
        for key, value in updates.items():
            if key in allowed_fields:
                setattr(project, key, value)
        await self.session.flush()
        await self.session.refresh(project)
        return project

    async def add_member(
        self,
        ctx: AuthContext | SystemContext,
        *,
        project_id: UUID,
        user_id: UUID,
        role: str = "contributor",
    ) -> ProjectMembership:
        """Add or override project membership for a user."""
        self._validate_context(ctx)
        membership = ProjectMembership(
            project_id=project_id,
            user_id=user_id,
            role=role,
        )
        self.session.add(membership)
        await self.session.flush()
        return membership

    async def get_membership(
        self,
        ctx: AuthContext | SystemContext,
        *,
        project_id: UUID,
        user_id: UUID,
    ) -> ProjectMembership | None:
        """Retrieve project-specific membership."""
        self._validate_context(ctx)
        stmt = select(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_members(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
    ) -> list[ProjectMembership]:
        """List all members assigned to a project."""
        self._validate_context(ctx)
        stmt = select(ProjectMembership).where(ProjectMembership.project_id == project_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def remove_member(
        self,
        ctx: AuthContext | SystemContext,
        *,
        project_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Remove explicit project membership."""
        self._validate_context(ctx)
        stmt = delete(ProjectMembership).where(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return bool(result.rowcount and result.rowcount > 0)

    async def soft_delete(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
    ) -> None:
        """Soft delete a project."""
        self._validate_context(ctx)
        project = await self.get_by_id(ctx, project_id)
        if project:
            project.deleted_at = datetime.now(UTC)
            await self.session.flush()
