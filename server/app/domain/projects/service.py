"""Project domain service implementing business logic for codebases and project access."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.persistence.models.project import Project, ProjectMembership
from app.persistence.repositories.project_repo import ProjectRepository

SLUG_REGEX = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ProjectService:
    """Domain service managing codebase project lifecycle and members."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ProjectRepository(session)

    @staticmethod
    def validate_slug(slug: str) -> str:
        """Validate project slug format."""
        slug = slug.strip().lower()
        if len(slug) < 2 or len(slug) > 64 or not SLUG_REGEX.match(slug):
            raise ValidationError(
                detail="Project slug must be between 2 and 64 characters, using lowercase letters, numbers, and single hyphens"
            )
        return slug

    async def create_project(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        name: str,
        slug: str,
        visibility: str = "workspace",
        sync_mode: str = "metadata_only",
        source_kind: str = "local",
        primary_language: str | None = None,
        default_branch: str = "main",
    ) -> Project:
        """Create a new codebase project inside a workspace."""
        clean_name = name.strip()
        if not clean_name or len(clean_name) > 120:
            raise ValidationError(detail="Project name must be between 1 and 120 characters")

        clean_slug = self.validate_slug(slug)

        if visibility not in ("private", "workspace"):
            raise ValidationError(detail="Project visibility must be 'private' or 'workspace'")

        if sync_mode not in ("metadata_only", "indexed"):
            raise ValidationError(detail="Project sync_mode must be 'metadata_only' or 'indexed'")

        if source_kind not in ("local", "github", "gitlab", "bitbucket"):
            raise ValidationError(detail="Invalid source_kind")

        # Check slug availability in workspace
        existing = await self.repo.get_by_slug(ctx, clean_slug, workspace_id=workspace_id)
        if existing is not None:
            raise ConflictError(
                detail=f"Project with slug '{clean_slug}' already exists in workspace"
            )

        return await self.repo.create(
            ctx,
            workspace_id=workspace_id,
            name=clean_name,
            slug=clean_slug,
            visibility=visibility,
            sync_mode=sync_mode,
            source_kind=source_kind,
            primary_language=primary_language,
            default_branch=default_branch,
        )

    async def get_project(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
    ) -> Project:
        """Find project by ID or raise NotFoundError."""
        project = await self.repo.get_by_id(ctx, project_id)
        if project is None:
            raise NotFoundError(detail=f"Project '{project_id}' not found")
        return project

    async def list_workspace_projects(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        include_archived: bool = False,
    ) -> list[Project]:
        """List all projects in workspace."""
        return await self.repo.list_for_workspace(
            ctx, workspace_id=workspace_id, include_archived=include_archived
        )

    async def update_project(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        *,
        name: str | None = None,
        slug: str | None = None,
        visibility: str | None = None,
        sync_mode: str | None = None,
        primary_language: str | None = None,
        default_branch: str | None = None,
    ) -> Project:
        """Update mutable project settings."""
        project = await self.get_project(ctx, project_id)

        updates: dict[str, Any] = {}
        if name is not None:
            clean_name = name.strip()
            if not clean_name or len(clean_name) > 120:
                raise ValidationError(detail="Project name must be between 1 and 120 characters")
            updates["name"] = clean_name

        if slug is not None:
            clean_slug = self.validate_slug(slug)
            if clean_slug != project.slug:
                existing = await self.repo.get_by_slug(
                    ctx, clean_slug, workspace_id=project.workspace_id
                )
                if existing is not None and existing.id != project_id:
                    raise ConflictError(
                        detail=f"Project with slug '{clean_slug}' already exists in workspace"
                    )
                updates["slug"] = clean_slug

        if visibility is not None:
            if visibility not in ("private", "workspace"):
                raise ValidationError(detail="Project visibility must be 'private' or 'workspace'")
            updates["visibility"] = visibility

        if sync_mode is not None:
            if sync_mode not in ("metadata_only", "indexed"):
                raise ValidationError(
                    detail="Project sync_mode must be 'metadata_only' or 'indexed'"
                )
            updates["sync_mode"] = sync_mode

        if primary_language is not None:
            updates["primary_language"] = primary_language.strip().lower()

        if default_branch is not None:
            updates["default_branch"] = default_branch.strip()

        updated = await self.repo.update(ctx, project_id, **updates)
        assert updated is not None
        return updated

    async def delete_project(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
    ) -> bool:
        """Soft delete a project."""
        await self.get_project(ctx, project_id)
        await self.repo.soft_delete(ctx, project_id)
        return True

    async def list_members(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
    ) -> list[ProjectMembership]:
        """List all explicit members of a project."""
        await self.get_project(ctx, project_id)
        return await self.repo.list_members(ctx, project_id)

    async def add_member(
        self,
        ctx: AuthContext | SystemContext,
        *,
        project_id: UUID,
        user_id: UUID,
        role: str = "contributor",
    ) -> ProjectMembership:
        """Add or elevate project membership."""
        await self.get_project(ctx, project_id)

        if role not in ("maintainer", "contributor", "viewer"):
            raise ValidationError(
                detail="Invalid project role; expected maintainer, contributor, or viewer"
            )

        existing = await self.repo.get_membership(ctx, project_id=project_id, user_id=user_id)
        if existing is not None:
            raise ConflictError(
                detail=f"User '{user_id}' already has an explicit membership in project '{project_id}'"
            )

        return await self.repo.add_member(ctx, project_id=project_id, user_id=user_id, role=role)

    async def remove_member(
        self,
        ctx: AuthContext | SystemContext,
        *,
        project_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Remove explicit project membership."""
        await self.get_project(ctx, project_id)
        removed = await self.repo.remove_member(ctx, project_id=project_id, user_id=user_id)
        if not removed:
            raise NotFoundError(
                detail=f"Membership for user '{user_id}' not found in project '{project_id}'"
            )
        return True
