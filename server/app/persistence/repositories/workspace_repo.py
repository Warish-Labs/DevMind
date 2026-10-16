"""Workspace repository for tenant management and memberships (docs/03 §3.1)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.persistence.models.workspace import Workspace, WorkspaceMembership
from app.persistence.repositories.base import BaseRepository


class WorkspaceRepository(BaseRepository):
    """Repository managing Workspace entities and user memberships."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        include_deleted: bool = False,
    ) -> Workspace | None:
        """Find workspace by ID, enforcing tenant boundary."""
        self._validate_context(ctx)
        stmt = select(Workspace).where(Workspace.id == workspace_id)
        stmt = self._scope_workspace_query(
            stmt, Workspace.id, ctx, target_workspace_id=workspace_id
        )
        if not include_deleted:
            stmt = stmt.where(Workspace.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_slug(
        self,
        ctx: AuthContext | SystemContext,
        slug: str,
        include_deleted: bool = False,
    ) -> Workspace | None:
        """Find workspace by slug, enforcing tenant boundary."""
        self._validate_context(ctx)
        stmt = select(Workspace).where(Workspace.slug == slug)
        stmt = self._scope_workspace_query(stmt, Workspace.id, ctx)
        if not include_deleted:
            stmt = stmt.where(Workspace.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_for_user(
        self,
        ctx: AuthContext | SystemContext,
        user_id: UUID,
    ) -> list[Workspace]:
        """List all active workspaces a given user belongs to."""
        self._validate_context(ctx)
        stmt = (
            select(Workspace)
            .join(WorkspaceMembership, Workspace.id == WorkspaceMembership.workspace_id)
            .where(
                WorkspaceMembership.user_id == user_id,
                Workspace.deleted_at.is_(None),
            )
            .order_by(Workspace.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        ctx: AuthContext | SystemContext,
        *,
        name: str,
        slug: str,
        kind: str = "personal",
        created_by: UUID | None = None,
    ) -> Workspace:
        """Create a new workspace."""
        self._validate_context(ctx)
        ws = Workspace(
            name=name,
            slug=slug,
            kind=kind,
            created_by=created_by,
        )
        self.session.add(ws)
        await self.session.flush()
        return ws

    async def add_member(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        user_id: UUID,
        role: str = "member",
    ) -> WorkspaceMembership:
        """Add a member to a workspace."""
        self._validate_context(ctx)
        membership = WorkspaceMembership(
            workspace_id=workspace_id,
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
        workspace_id: UUID,
        user_id: UUID,
    ) -> WorkspaceMembership | None:
        """Retrieve membership record for a specific user in a workspace."""
        self._validate_context(ctx)
        stmt = select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_memberships(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
    ) -> list[WorkspaceMembership]:
        """List all memberships within a workspace."""
        self._validate_context(ctx)
        stmt = select(WorkspaceMembership).where(WorkspaceMembership.workspace_id == workspace_id)
        stmt = self._scope_workspace_query(
            stmt, WorkspaceMembership.workspace_id, ctx, target_workspace_id=workspace_id
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_member_role(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        user_id: UUID,
        role: str,
    ) -> WorkspaceMembership | None:
        """Update role for a member in a workspace."""
        self._validate_context(ctx)
        membership = await self.get_membership(ctx, workspace_id=workspace_id, user_id=user_id)
        if membership:
            membership.role = role
            await self.session.flush()
        return membership

    async def remove_member(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Remove a member from a workspace."""
        self._validate_context(ctx)
        stmt = delete(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return bool(result.rowcount and result.rowcount > 0)

    async def soft_delete(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
    ) -> None:
        """Soft delete a workspace."""
        self._validate_context(ctx)
        ws = await self.get_by_id(ctx, workspace_id)
        if ws:
            ws.deleted_at = datetime.now(UTC)
            await self.session.flush()
