"""Usage record repository for token metering and quota accounting (docs/03 §3.5)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.persistence.models.usage import UsageRecord
from app.persistence.repositories.base import BaseRepository


class UsageRecordRepository(BaseRepository):
    """Repository managing inference usage records and accounting."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def record(
        self,
        ctx: AuthContext | SystemContext,
        *,
        llm_task: str,
        provider_id: str,
        model_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_units: int = 0,
        latency_ms: int = 0,
        outcome: str = "success",
        project_id: UUID | None = None,
        job_id: UUID | None = None,
        workspace_id: UUID | None = None,
    ) -> UsageRecord:
        """Record an inference usage metering entry."""
        self._validate_context(ctx)

        ws_id = workspace_id or (
            ctx.workspace_id if isinstance(ctx, AuthContext) else ctx.workspace_id
        )
        if ws_id is None:
            raise ValueError("workspace_id must be provided or present in AuthContext")

        record = UsageRecord(
            workspace_id=ws_id,
            project_id=project_id or (ctx.project_id if isinstance(ctx, AuthContext) else None),
            job_id=job_id,
            llm_task=llm_task,
            provider_id=provider_id,
            model_id=model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_units=cost_units,
            latency_ms=latency_ms,
            outcome=outcome,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def list_for_workspace(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID | None = None,
        limit: int = 25,
    ) -> list[UsageRecord]:
        """List recent usage records for the workspace."""
        self._validate_context(ctx)
        capped_limit = min(max(limit, 1), 100)
        stmt = select(UsageRecord).order_by(UsageRecord.created_at.desc()).limit(capped_limit)
        stmt = self._scope_workspace_query(
            stmt, UsageRecord.workspace_id, ctx, target_workspace_id=workspace_id
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_token_totals(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID | None = None,
    ) -> dict[str, int]:
        """Aggregate total input and output tokens consumed by the workspace."""
        self._validate_context(ctx)
        stmt = select(
            func.coalesce(func.sum(UsageRecord.input_tokens), 0).label("total_input"),
            func.coalesce(func.sum(UsageRecord.output_tokens), 0).label("total_output"),
        )
        stmt = self._scope_workspace_query(
            stmt, UsageRecord.workspace_id, ctx, target_workspace_id=workspace_id
        )
        result = await self.session.execute(stmt)
        row = result.first()
        if row:
            return {"input_tokens": int(row[0]), "output_tokens": int(row[1])}
        return {"input_tokens": 0, "output_tokens": 0}
