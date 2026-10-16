"""Workspace domain service implementing business logic for workspaces and memberships."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.persistence.models.workspace import Workspace, WorkspaceMembership
from app.persistence.repositories.workspace_repo import WorkspaceRepository

SLUG_REGEX = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class WorkspaceService:
    """Domain service managing workspace lifecycle and membership."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WorkspaceRepository(session)

    @staticmethod
    def validate_slug(slug: str) -> str:
        """Validate slug format."""
        slug = slug.strip().lower()
        if len(slug) < 2 or len(slug) > 64 or not SLUG_REGEX.match(slug):
            raise ValidationError(
                detail="Workspace slug must be between 2 and 64 characters, using lowercase letters, numbers, and single hyphens"
            )
        return slug

    async def create_workspace(
        self,
        ctx: AuthContext | SystemContext,
        *,
        name: str,
        slug: str,
        kind: str = "personal",
    ) -> Workspace:
        """Create a workspace and automatically assign creator as owner."""
        clean_name = name.strip()
        if not clean_name or len(clean_name) > 120:
            raise ValidationError(detail="Workspace name must be between 1 and 120 characters")

        clean_slug = self.validate_slug(slug)

        # Check slug availability
        existing = await self.repo.get_by_slug(ctx, clean_slug)
        if existing is not None:
            raise ConflictError(detail=f"Workspace with slug '{clean_slug}' already exists")

        creator_id = ctx.user_id if isinstance(ctx, AuthContext) else ctx.actor_id
        ws = await self.repo.create(
            ctx,
            name=clean_name,
            slug=clean_slug,
            kind=kind,
            created_by=creator_id,
        )

        # If created by user, assign owner membership
        if creator_id is not None:
            await self.repo.add_member(
                ctx,
                workspace_id=ws.id,
                user_id=creator_id,
                role="owner",
            )

        return ws

    async def get_workspace(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
    ) -> Workspace:
        """Find workspace by ID or raise NotFoundError."""
        ws = await self.repo.get_by_id(ctx, workspace_id)
        if ws is None:
            raise NotFoundError(detail=f"Workspace '{workspace_id}' not found")
        return ws

    async def list_user_workspaces(
        self,
        ctx: AuthContext | SystemContext,
        user_id: UUID,
    ) -> list[Workspace]:
        """List all workspaces accessible to user."""
        return await self.repo.list_for_user(ctx, user_id)

    async def update_workspace(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        *,
        name: str | None = None,
        slug: str | None = None,
        kind: str | None = None,
    ) -> Workspace:
        """Update mutable workspace fields."""
        ws = await self.get_workspace(ctx, workspace_id)

        updates: dict[str, Any] = {}
        if name is not None:
            clean_name = name.strip()
            if not clean_name or len(clean_name) > 120:
                raise ValidationError(detail="Workspace name must be between 1 and 120 characters")
            updates["name"] = clean_name

        if slug is not None:
            clean_slug = self.validate_slug(slug)
            if clean_slug != ws.slug:
                existing = await self.repo.get_by_slug(ctx, clean_slug)
                if existing is not None and existing.id != workspace_id:
                    raise ConflictError(detail=f"Workspace with slug '{clean_slug}' already exists")
                updates["slug"] = clean_slug

        if kind is not None:
            if kind not in ("personal", "team", "enterprise"):
                raise ValidationError(
                    detail="Workspace kind must be 'personal', 'team', or 'enterprise'"
                )
            updates["kind"] = kind

        updated = await self.repo.update(ctx, workspace_id, **updates)
        assert updated is not None
        return updated

    async def list_members(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
    ) -> list[WorkspaceMembership]:
        """List all members belonging to a workspace."""
        await self.get_workspace(ctx, workspace_id)
        return await self.repo.list_memberships(ctx, workspace_id)

    async def add_member(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        user_id: UUID,
        role: str = "member",
    ) -> WorkspaceMembership:
        """Add a new member to a workspace."""
        await self.get_workspace(ctx, workspace_id)

        if role not in ("owner", "admin", "member", "viewer"):
            raise ValidationError(
                detail="Invalid workspace role; expected owner, admin, member, or viewer"
            )

        existing = await self.repo.get_membership(ctx, workspace_id=workspace_id, user_id=user_id)
        if existing is not None:
            raise ConflictError(
                detail=f"User '{user_id}' is already a member of workspace '{workspace_id}'"
            )

        return await self.repo.add_member(
            ctx, workspace_id=workspace_id, user_id=user_id, role=role
        )

    async def update_member_role(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        user_id: UUID,
        role: str,
    ) -> WorkspaceMembership:
        """Update role of an existing workspace member."""
        await self.get_workspace(ctx, workspace_id)

        if role not in ("owner", "admin", "member", "viewer"):
            raise ValidationError(
                detail="Invalid workspace role; expected owner, admin, member, or viewer"
            )

        membership = await self.repo.update_member_role(
            ctx, workspace_id=workspace_id, user_id=user_id, role=role
        )
        if membership is None:
            raise NotFoundError(
                detail=f"Membership for user '{user_id}' not found in workspace '{workspace_id}'"
            )
        return membership

    async def remove_member(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Remove a member from a workspace."""
        await self.get_workspace(ctx, workspace_id)
        removed = await self.repo.remove_member(ctx, workspace_id=workspace_id, user_id=user_id)
        if not removed:
            raise NotFoundError(
                detail=f"Membership for user '{user_id}' not found in workspace '{workspace_id}'"
            )
        return True
