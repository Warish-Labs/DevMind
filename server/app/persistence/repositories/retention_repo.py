"""Retention repository managing data-retention window configurations (docs/03 §3.1, docs/07 §9)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.ids import generate_uuid7
from app.persistence.models.project import Project
from app.persistence.models.retention import RetentionPolicy
from app.persistence.repositories.base import BaseRepository


class RetentionRepository(BaseRepository):
    """Repository managing retention policies for workspaces and projects.

    Enforces workspace-level and project-level isolation via AuthContext on every operation.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def _verify_workspace_access(
        self, ctx: AuthContext | SystemContext, workspace_id: UUID
    ) -> None:
        """Verify that caller has access to workspace."""
        self._validate_context(ctx)
        if isinstance(ctx, AuthContext):
            if ctx.workspace_id != workspace_id:
                raise PermissionError(
                    f"Access denied: caller workspace '{ctx.workspace_id}' cannot access '{workspace_id}'"
                )

    async def _verify_project_access(
        self, ctx: AuthContext | SystemContext, workspace_id: UUID, project_id: UUID
    ) -> Project:
        """Verify that caller has access to project within the workspace."""
        self._validate_context(ctx)
        await self._verify_workspace_access(ctx, workspace_id)
        stmt = select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
        result = await self.session.execute(stmt)
        project = result.scalars().first()
        if not project:
            raise ValueError(f"Project '{project_id}' not found in workspace '{workspace_id}'")
        return project

    async def list_workspace_policies(
        self, ctx: AuthContext | SystemContext, workspace_id: UUID
    ) -> list[RetentionPolicy]:
        """List all workspace-level retention policies."""
        await self._verify_workspace_access(ctx, workspace_id)
        stmt = select(RetentionPolicy).where(
            RetentionPolicy.workspace_id == workspace_id,
            RetentionPolicy.project_id.is_(None),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_project_policies(
        self, ctx: AuthContext | SystemContext, workspace_id: UUID, project_id: UUID
    ) -> list[RetentionPolicy]:
        """List project-level retention policy overrides."""
        await self._verify_project_access(ctx, workspace_id, project_id)
        stmt = select(RetentionPolicy).where(
            RetentionPolicy.workspace_id == workspace_id,
            RetentionPolicy.project_id == project_id,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_policy(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        kind: str,
        project_id: UUID | None = None,
    ) -> RetentionPolicy | None:
        """Get a specific retention policy."""
        if project_id is not None:
            await self._verify_project_access(ctx, workspace_id, project_id)
        else:
            await self._verify_workspace_access(ctx, workspace_id)

        stmt = select(RetentionPolicy).where(
            RetentionPolicy.workspace_id == workspace_id,
            RetentionPolicy.kind == kind,
        )
        if project_id is not None:
            stmt = stmt.where(RetentionPolicy.project_id == project_id)
        else:
            stmt = stmt.where(RetentionPolicy.project_id.is_(None))

        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def upsert_policy(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        kind: str,
        days: int,
        project_id: UUID | None = None,
    ) -> RetentionPolicy:
        """Create or update a retention policy for workspace or project override."""
        if days < 1:
            raise ValueError("Retention period must be at least 1 day")

        existing = await self.get_policy(ctx, workspace_id, kind, project_id)
        now = datetime.now(UTC)

        if existing:
            existing.days = days
            existing.updated_at = now
            await self.session.flush()
            return existing

        policy = RetentionPolicy(
            id=generate_uuid7(),
            workspace_id=workspace_id,
            project_id=project_id,
            kind=kind,
            days=days,
            created_at=now,
            updated_at=now,
        )
        self.session.add(policy)
        await self.session.flush()
        return policy

    async def delete_policy(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        kind: str,
        project_id: UUID | None = None,
    ) -> bool:
        """Delete a retention policy override (falls back to workspace default or interim default)."""
        if project_id is not None:
            await self._verify_project_access(ctx, workspace_id, project_id)
        else:
            await self._verify_workspace_access(ctx, workspace_id)

        stmt = delete(RetentionPolicy).where(
            RetentionPolicy.workspace_id == workspace_id,
            RetentionPolicy.kind == kind,
        )
        if project_id is not None:
            stmt = stmt.where(RetentionPolicy.project_id == project_id)
        else:
            stmt = stmt.where(RetentionPolicy.project_id.is_(None))

        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0
