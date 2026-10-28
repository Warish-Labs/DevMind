"""Repository for PRAnalysis persistence and project-scoped queries (docs/01 CAP-06, docs/03 §3.5)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import ForbiddenError
from app.core.ids import generate_uuid7
from app.persistence.models.pr_analysis import PRAnalysis
from app.persistence.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class PRAnalysisRepository(BaseRepository):
    """Repository managing PR analysis results, change impact, and synthesized summaries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create_analysis(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        project_id: UUID,
        pull_request_id: UUID,
        head_sha: str,
        job_id: UUID | None,
        risk_level: str,
        summary: dict[str, Any],
        impact: dict[str, Any],
    ) -> PRAnalysis:
        """Persist a new PR analysis result."""
        self._validate_context(ctx)

        if isinstance(ctx, AuthContext):
            if ctx.workspace_id and ctx.workspace_id != workspace_id:
                raise ForbiddenError(detail="Cross-workspace PR analysis creation is forbidden")
            if ctx.project_id and ctx.project_id != project_id:
                raise ForbiddenError(detail="Cross-project PR analysis creation is forbidden")

        analysis = PRAnalysis(
            id=generate_uuid7(),
            workspace_id=workspace_id,
            project_id=project_id,
            pull_request_id=pull_request_id,
            head_sha=head_sha.strip(),
            job_id=job_id,
            risk_level=risk_level.lower().strip(),
            summary=summary,
            impact=impact,
        )
        self.session.add(analysis)
        await self.session.flush()
        return analysis

    async def get_by_id(
        self,
        ctx: AuthContext | SystemContext,
        analysis_id: UUID,
    ) -> PRAnalysis | None:
        """Fetch a single PR analysis by primary key."""
        self._validate_context(ctx)

        stmt = select(PRAnalysis).where(PRAnalysis.id == analysis_id)
        if isinstance(ctx, AuthContext):
            if ctx.workspace_id:
                stmt = stmt.where(PRAnalysis.workspace_id == ctx.workspace_id)
            if ctx.project_id:
                stmt = stmt.where(PRAnalysis.project_id == ctx.project_id)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_by_pr(
        self,
        ctx: AuthContext | SystemContext,
        pull_request_id: UUID,
    ) -> PRAnalysis | None:
        """Fetch the most recent analysis record for a pull request."""
        self._validate_context(ctx)

        stmt = (
            select(PRAnalysis)
            .where(PRAnalysis.pull_request_id == pull_request_id)
            .order_by(desc(PRAnalysis.created_at))
            .limit(1)
        )
        if isinstance(ctx, AuthContext):
            if ctx.workspace_id:
                stmt = stmt.where(PRAnalysis.workspace_id == ctx.workspace_id)
            if ctx.project_id:
                stmt = stmt.where(PRAnalysis.project_id == ctx.project_id)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_pr(
        self,
        ctx: AuthContext | SystemContext,
        pull_request_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[PRAnalysis]:
        """List historical analyses for a pull request, sorted newest first."""
        self._validate_context(ctx)

        stmt = (
            select(PRAnalysis)
            .where(PRAnalysis.pull_request_id == pull_request_id)
            .order_by(desc(PRAnalysis.created_at))
            .limit(limit)
            .offset(offset)
        )
        if isinstance(ctx, AuthContext):
            if ctx.workspace_id:
                stmt = stmt.where(PRAnalysis.workspace_id == ctx.workspace_id)
            if ctx.project_id:
                stmt = stmt.where(PRAnalysis.project_id == ctx.project_id)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def delete_by_id(
        self,
        ctx: AuthContext | SystemContext,
        analysis_id: UUID,
    ) -> bool:
        """Delete an analysis record."""
        self._validate_context(ctx)

        stmt = delete(PRAnalysis).where(PRAnalysis.id == analysis_id)
        if isinstance(ctx, AuthContext):
            if ctx.workspace_id:
                stmt = stmt.where(PRAnalysis.workspace_id == ctx.workspace_id)
            if ctx.project_id:
                stmt = stmt.where(PRAnalysis.project_id == ctx.project_id)

        result = await self.session.execute(stmt)
        await self.session.flush()
        return bool(result.rowcount and result.rowcount > 0)
