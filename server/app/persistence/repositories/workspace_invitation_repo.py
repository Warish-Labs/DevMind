"""Workspace invitation repository for team membership management (docs/01 FR-PLT-05, docs/03 §3.1)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.persistence.models.workspace_invitation import WorkspaceInvitation
from app.persistence.repositories.base import BaseRepository


class WorkspaceInvitationRepository(BaseRepository):
    """Repository managing WorkspaceInvitation persistence with tenant scoping."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create_invitation(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        email: str,
        role: str,
        token_hash: str,
        invited_by: UUID | None,
        expires_at: datetime,
    ) -> WorkspaceInvitation:
        """Create a new workspace invitation record."""
        self._validate_context(ctx)
        self._scope_workspace_query(
            select(WorkspaceInvitation),
            WorkspaceInvitation.workspace_id,
            ctx,
            target_workspace_id=workspace_id,
        )

        invitation = WorkspaceInvitation(
            workspace_id=workspace_id,
            email=email.strip().lower(),
            role=role,
            token_hash=token_hash,
            invited_by=invited_by,
            expires_at=expires_at,
        )
        self.session.add(invitation)
        await self.session.flush()
        return invitation

    async def get_by_id(
        self,
        ctx: AuthContext | SystemContext,
        invitation_id: UUID,
    ) -> WorkspaceInvitation | None:
        """Retrieve an invitation by ID within authorized workspace."""
        self._validate_context(ctx)
        stmt = select(WorkspaceInvitation).where(WorkspaceInvitation.id == invitation_id)
        stmt = self._scope_workspace_query(stmt, WorkspaceInvitation.workspace_id, ctx)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_token_hash(
        self,
        token_hash: str,
    ) -> WorkspaceInvitation | None:
        """Retrieve an invitation by its token hash for verification or acceptance."""
        stmt = select(WorkspaceInvitation).where(WorkspaceInvitation.token_hash == token_hash)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_active_by_email(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        email: str,
    ) -> WorkspaceInvitation | None:
        """Find pending, non-expired invitation for an email in a workspace."""
        self._validate_context(ctx)
        now = datetime.now(UTC)
        stmt = (
            select(WorkspaceInvitation)
            .where(
                WorkspaceInvitation.workspace_id == workspace_id,
                WorkspaceInvitation.email == email.strip().lower(),
                WorkspaceInvitation.accepted_at.is_(None),
                WorkspaceInvitation.expires_at > now,
            )
        )
        stmt = self._scope_workspace_query(
            stmt, WorkspaceInvitation.workspace_id, ctx, target_workspace_id=workspace_id
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_for_workspace(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        *,
        pending_only: bool = True,
    ) -> list[WorkspaceInvitation]:
        """List invitations for a workspace."""
        self._validate_context(ctx)
        stmt = (
            select(WorkspaceInvitation)
            .where(WorkspaceInvitation.workspace_id == workspace_id)
            .order_by(WorkspaceInvitation.created_at.desc())
        )
        if pending_only:
            now = datetime.now(UTC)
            stmt = stmt.where(
                WorkspaceInvitation.accepted_at.is_(None),
                WorkspaceInvitation.expires_at > now,
            )
        stmt = self._scope_workspace_query(
            stmt, WorkspaceInvitation.workspace_id, ctx, target_workspace_id=workspace_id
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_accepted(
        self,
        invitation: WorkspaceInvitation,
        accepted_at: datetime | None = None,
    ) -> WorkspaceInvitation:
        """Mark invitation as accepted."""
        invitation.accepted_at = accepted_at or datetime.now(UTC)
        await self.session.flush()
        return invitation

    async def delete(
        self,
        ctx: AuthContext | SystemContext,
        invitation_id: UUID,
    ) -> bool:
        """Revoke / delete an invitation."""
        self._validate_context(ctx)
        invitation = await self.get_by_id(ctx, invitation_id)
        if invitation is None:
            return False
        stmt = delete(WorkspaceInvitation).where(WorkspaceInvitation.id == invitation_id)
        stmt = self._scope_workspace_query(stmt, WorkspaceInvitation.workspace_id, ctx)
        await self.session.execute(stmt)
        await self.session.flush()
        return True
