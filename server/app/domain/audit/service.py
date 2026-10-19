"""Audit domain service for querying immutable audit logs (docs/03 §3.5, docs/07 §16)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import ForbiddenError, NotFoundError
from app.persistence.models.audit import AuditEvent
from app.persistence.repositories.audit_repo import AuditEventRepository
from app.persistence.repositories.project_repo import ProjectRepository
from app.persistence.repositories.workspace_repo import WorkspaceRepository


class AuditService:
    """Domain service managing retrieval and filtering of security and governance audit logs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit_repo = AuditEventRepository(session)
        self.workspace_repo = WorkspaceRepository(session)
        self.project_repo = ProjectRepository(session)

    async def list_workspace_audit_events(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        *,
        action: str | None = None,
        target_kind: str | None = None,
        target_id: str | None = None,
        actor_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """List audit events for a target workspace with optional filtering."""
        if isinstance(ctx, AuthContext) and ctx.workspace_id != workspace_id:
            raise ForbiddenError(detail="Cross-tenant workspace access denied")

        ws = await self.workspace_repo.get_by_id(ctx, workspace_id)
        if ws is None:
            raise NotFoundError(detail=f"Workspace '{workspace_id}' not found")

        return await self.audit_repo.list_for_workspace(
            ctx,
            workspace_id=workspace_id,
            action=action,
            target_kind=target_kind,
            target_id=target_id,
            actor_id=actor_id,
            limit=limit,
            offset=offset,
        )

    async def count_workspace_audit_events(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        *,
        action: str | None = None,
        target_kind: str | None = None,
        target_id: str | None = None,
        actor_id: UUID | None = None,
    ) -> int:
        """Count total audit events for a workspace matching specified filters."""
        ws = await self.workspace_repo.get_by_id(ctx, workspace_id)
        if ws is None:
            raise NotFoundError(detail=f"Workspace '{workspace_id}' not found")

        return await self.audit_repo.count_for_workspace(
            ctx,
            workspace_id=workspace_id,
            action=action,
            target_kind=target_kind,
            target_id=target_id,
            actor_id=actor_id,
        )

    async def list_project_audit_events(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        *,
        action: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """List audit events associated with a specific project."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if project is None:
            raise NotFoundError(detail=f"Project '{project_id}' not found")

        if isinstance(ctx, AuthContext) and project.workspace_id != ctx.workspace_id:
            raise ForbiddenError(detail="Cross-tenant project access denied")

        return await self.audit_repo.list_for_project(
            ctx,
            project_id=project_id,
            workspace_id=project.workspace_id,
            action=action,
            limit=limit,
            offset=offset,
        )

    async def count_project_audit_events(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        *,
        action: str | None = None,
    ) -> int:
        """Count audit events associated with a specific project matching filters."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if project is None:
            raise NotFoundError(detail=f"Project '{project_id}' not found")

        if isinstance(ctx, AuthContext) and project.workspace_id != ctx.workspace_id:
            raise ForbiddenError(detail="Cross-tenant project access denied")

        return await self.audit_repo.count_for_project(
            ctx,
            project_id=project_id,
            workspace_id=project.workspace_id,
            action=action,
        )
