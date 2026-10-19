"""Audit event repository for append-only security logs (docs/03 §3.5)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.persistence.models.audit import AuditEvent
from app.persistence.repositories.base import BaseRepository


class AuditEventRepository(BaseRepository):
    """Repository handling append-only audit event persistence and listing."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def record(
        self,
        ctx: AuthContext | SystemContext,
        *,
        action: str,
        target_kind: str,
        target_id: str | None = None,
        actor_id: UUID | None = None,
        actor_kind: str = "user",
        metadata: dict[str, Any] | None = None,
        ip_hash: str | None = None,
        workspace_id: UUID | None = None,
    ) -> AuditEvent:
        """Record a new immutable audit event."""
        self._validate_context(ctx)

        ws_id = workspace_id or (
            ctx.workspace_id if isinstance(ctx, AuthContext) else ctx.workspace_id
        )
        if ws_id is None:
            raise ValueError("workspace_id must be provided or present in AuthContext")

        act_id = actor_id or (ctx.user_id if isinstance(ctx, AuthContext) else ctx.actor_id)
        ip = ip_hash or (ctx.ip_hash if isinstance(ctx, AuthContext) else None)

        event = AuditEvent(
            workspace_id=ws_id,
            actor_id=act_id,
            actor_kind=actor_kind,
            action=action,
            target_kind=target_kind,
            target_id=target_id,
            ip_hash=ip,
            metadata_json=metadata or {},
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_for_workspace(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID | None = None,
        *,
        action: str | None = None,
        target_kind: str | None = None,
        target_id: str | None = None,
        actor_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """List audit events for the active workspace with optional filters."""
        self._validate_context(ctx)
        capped_limit = min(max(limit, 1), 100)
        stmt = (
            select(AuditEvent)
            .order_by(AuditEvent.created_at.desc())
            .offset(max(offset, 0))
            .limit(capped_limit)
        )
        stmt = self._scope_workspace_query(
            stmt, AuditEvent.workspace_id, ctx, target_workspace_id=workspace_id
        )
        if action:
            stmt = stmt.where(AuditEvent.action == action)
        if target_kind:
            stmt = stmt.where(AuditEvent.target_kind == target_kind)
        if target_id:
            stmt = stmt.where(AuditEvent.target_id == target_id)
        if actor_id:
            stmt = stmt.where(AuditEvent.actor_id == actor_id)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_workspace(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID | None = None,
        *,
        action: str | None = None,
        target_kind: str | None = None,
        target_id: str | None = None,
        actor_id: UUID | None = None,
    ) -> int:
        """Count audit events for the active workspace matching filters."""
        self._validate_context(ctx)
        stmt = select(func.count()).select_from(AuditEvent)
        stmt = self._scope_workspace_query(
            stmt, AuditEvent.workspace_id, ctx, target_workspace_id=workspace_id
        )
        if action:
            stmt = stmt.where(AuditEvent.action == action)
        if target_kind:
            stmt = stmt.where(AuditEvent.target_kind == target_kind)
        if target_id:
            stmt = stmt.where(AuditEvent.target_id == target_id)
        if actor_id:
            stmt = stmt.where(AuditEvent.actor_id == actor_id)

        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def list_for_project(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        workspace_id: UUID | None = None,
        *,
        action: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEvent]:
        """List audit events associated with a specific project."""
        self._validate_context(ctx)
        capped_limit = min(max(limit, 1), 100)
        pid_str = str(project_id)

        stmt = (
            select(AuditEvent)
            .order_by(AuditEvent.created_at.desc())
            .offset(max(offset, 0))
            .limit(capped_limit)
        )
        stmt = self._scope_workspace_query(
            stmt, AuditEvent.workspace_id, ctx, target_workspace_id=workspace_id
        )
        # Match either target_id == project_id or metadata containing project_id
        stmt = stmt.where(
            or_(
                AuditEvent.target_id == pid_str,
                AuditEvent.metadata_json["project_id"].astext == pid_str,
            )
        )
        if action:
            stmt = stmt.where(AuditEvent.action == action)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_project(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        workspace_id: UUID | None = None,
        *,
        action: str | None = None,
    ) -> int:
        """Count audit events associated with a specific project."""
        self._validate_context(ctx)
        pid_str = str(project_id)
        stmt = select(func.count()).select_from(AuditEvent)
        stmt = self._scope_workspace_query(
            stmt, AuditEvent.workspace_id, ctx, target_workspace_id=workspace_id
        )
        stmt = stmt.where(
            or_(
                AuditEvent.target_id == pid_str,
                AuditEvent.metadata_json["project_id"].astext == pid_str,
            )
        )
        if action:
            stmt = stmt.where(AuditEvent.action == action)

        result = await self.session.execute(stmt)
        return result.scalar_one() or 0
