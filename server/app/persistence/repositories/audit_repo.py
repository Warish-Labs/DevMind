"""Audit event repository for append-only security logs (docs/03 §3.5)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
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
        limit: int = 25,
    ) -> list[AuditEvent]:
        """List recent audit events for the active workspace."""
        self._validate_context(ctx)
        capped_limit = min(max(limit, 1), 100)
        stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(capped_limit)
        stmt = self._scope_workspace_query(
            stmt, AuditEvent.workspace_id, ctx, target_workspace_id=workspace_id
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
