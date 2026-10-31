"""Project Evaluation repository for release-readiness and multidimensional health (docs/01 CAP-09, docs/03 §3.7)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth_context import AuthContext, SystemContext
from app.persistence.models.mentor import ProjectEvaluation
from app.persistence.repositories.base import BaseRepository


class ProjectEvaluationRepository(BaseRepository):
    """Repository managing ProjectEvaluation records and release-readiness verdicts."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create_evaluation(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        project_id: UUID,
        overall_score: float,
        dimension_scores: dict[str, Any],
        verdict: str,
        blockers: list[dict[str, Any]] | None = None,
        warnings: list[dict[str, Any]] | None = None,
        positive_indicators: list[str] | None = None,
        snapshot_id: UUID | None = None,
        rubric_version: str = "1.0",
        evaluated_by: UUID | None = None,
    ) -> ProjectEvaluation:
        """Persist a new multidimensional project evaluation record."""
        self._validate_context(ctx)
        eval_record = ProjectEvaluation(
            workspace_id=workspace_id,
            project_id=project_id,
            snapshot_id=snapshot_id,
            overall_score=overall_score,
            dimension_scores=dimension_scores,
            verdict=verdict,
            blockers=blockers or [],
            warnings=warnings or [],
            positive_indicators=positive_indicators or [],
            rubric_version=rubric_version,
            evaluated_by=evaluated_by,
        )
        self.session.add(eval_record)
        await self.session.flush()
        return await self.get_by_id(ctx, eval_record.id) or eval_record

    async def get_by_id(
        self,
        ctx: AuthContext | SystemContext,
        evaluation_id: UUID,
    ) -> ProjectEvaluation | None:
        """Retrieve evaluation by ID with tenant scoping."""
        self._validate_context(ctx)
        stmt = (
            select(ProjectEvaluation)
            .where(ProjectEvaluation.id == evaluation_id)
            .options(
                selectinload(ProjectEvaluation.snapshot),
                selectinload(ProjectEvaluation.evaluator),
            )
        )
        stmt = self._scope_workspace_query(stmt, ProjectEvaluation.workspace_id, ctx)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_latest_by_project(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
    ) -> ProjectEvaluation | None:
        """Retrieve the most recent health evaluation for a project."""
        self._validate_context(ctx)
        stmt = (
            select(ProjectEvaluation)
            .where(ProjectEvaluation.project_id == project_id)
            .options(
                selectinload(ProjectEvaluation.snapshot),
                selectinload(ProjectEvaluation.evaluator),
            )
            .order_by(desc(ProjectEvaluation.created_at))
            .limit(1)
        )
        stmt = self._scope_workspace_query(stmt, ProjectEvaluation.workspace_id, ctx)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_project(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ProjectEvaluation]:
        """List historical evaluations for a project in reverse chronological order."""
        self._validate_context(ctx)
        stmt = (
            select(ProjectEvaluation)
            .where(ProjectEvaluation.project_id == project_id)
            .options(
                selectinload(ProjectEvaluation.snapshot),
                selectinload(ProjectEvaluation.evaluator),
            )
            .order_by(desc(ProjectEvaluation.created_at))
            .limit(limit)
            .offset(offset)
        )
        stmt = self._scope_workspace_query(stmt, ProjectEvaluation.workspace_id, ctx)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
