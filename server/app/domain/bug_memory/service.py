"""Domain service for Bug Memory operations, resolution tracking, and similarity matching (docs/01 CAP-03, docs/03 §3.4)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import NotFoundError
from app.domain.bug_memory.schemas import (
    BugMatchRequest,
    BugMatchResponse,
    BugRecordCreate,
    BugRecordDetailResponse,
    BugRecordResponse,
    BugResolutionCreate,
    BugResolutionResponse,
    ResolutionProposal,
)
from app.llm.router import LLMGatewayRouter
from app.persistence.models.bug_memory import BugRecord, BugResolution
from app.persistence.repositories.bug_record_repo import BugRecordRepository
from app.persistence.repositories.project_repo import ProjectRepository

logger = logging.getLogger(__name__)


class BugMemoryService:
    """Coordinates Bug Memory CRUD, duplicate incrementing, agent matching, and resolution tracking."""

    def __init__(
        self,
        session: AsyncSession,
        router: LLMGatewayRouter | None = None,
    ) -> None:
        from app.orchestration.bug_memory import BugMemoryAgent

        self.session = session
        self.repo = BugRecordRepository(session)
        self.project_repo = ProjectRepository(session)
        self.agent = BugMemoryAgent(session=session, router=router)

    async def list_bugs(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        module_hint: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BugRecordResponse]:
        """List bug records for a project ordered by most recent occurrence."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if not project:
            raise NotFoundError(detail=f"Project {project_id} not found")

        records = await self.repo.list_by_project(
            ctx=ctx,
            project_id=project_id,
            module_hint=module_hint,
            limit=limit,
            offset=offset,
        )

        return [
            BugRecordResponse(
                id=r.id,
                workspace_id=r.workspace_id,
                project_id=r.project_id,
                fingerprint=r.fingerprint,
                error_signature=r.error_signature,
                title=r.title,
                summary=r.summary,
                module_hint=r.module_hint,
                occurrence_count=r.occurrence_count,
                resolutions_count=len(r.resolutions or []),
                first_seen_at=r.first_seen_at,
                last_seen_at=r.last_seen_at,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in records
        ]

    async def get_bug_by_id(
        self,
        ctx: AuthContext | SystemContext,
        bug_id: UUID,
    ) -> BugRecordDetailResponse:
        """Retrieve detailed bug record with resolutions by ID."""
        record = await self.repo.get_by_id(ctx, bug_id)
        if not record:
            raise NotFoundError(detail=f"Bug record {bug_id} not found")

        return self._to_detail_response(record)

    async def record_bug(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        data: BugRecordCreate,
    ) -> tuple[BugRecordDetailResponse, bool]:
        """Normalize and upsert a bug record; attach initial resolution if provided."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if not project:
            raise NotFoundError(detail=f"Project {project_id} not found")

        record, is_new = await self.repo.record_bug(
            ctx=ctx,
            workspace_id=project.workspace_id,
            project_id=project_id,
            raw_error=data.raw_error,
            title=data.title,
            summary=data.summary,
            module_hint=data.module_hint,
        )

        # Attach initial resolution if supplied
        if data.resolution:
            resolved_by = ctx.user_id if isinstance(ctx, AuthContext) else None
            await self.repo.add_resolution(
                ctx=ctx,
                bug_record_id=record.id,
                cause=data.resolution.cause,
                fix_summary=data.resolution.fix_summary,
                files=data.resolution.files,
                finding_id=data.resolution.finding_id,
                resolved_by=resolved_by,
            )
            # Re-fetch with loaded resolutions
            refreshed = await self.repo.get_by_id(ctx, record.id)
            if refreshed:
                record = refreshed

        return self._to_detail_response(record), is_new

    async def add_resolution(
        self,
        ctx: AuthContext | SystemContext,
        bug_id: UUID,
        data: BugResolutionCreate,
    ) -> BugResolutionResponse:
        """Attach a resolution to an existing bug record."""
        record = await self.repo.get_by_id(ctx, bug_id)
        if not record:
            raise NotFoundError(detail=f"Bug record {bug_id} not found")

        resolved_by = ctx.user_id if isinstance(ctx, AuthContext) else None
        res = await self.repo.add_resolution(
            ctx=ctx,
            bug_record_id=bug_id,
            cause=data.cause,
            fix_summary=data.fix_summary,
            files=data.files,
            finding_id=data.finding_id,
            resolved_by=resolved_by,
        )

        return self._to_resolution_response(res)

    async def match_bugs(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        data: BugMatchRequest,
    ) -> BugMatchResponse:
        """Match an incoming raw error against project Bug Memory and synthesize explanation."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if not project:
            raise NotFoundError(detail=f"Project {project_id} not found")

        return await self.agent.match_and_explain(
            ctx=ctx,
            project_id=project_id,
            raw_error=data.raw_error,
            module_hint=data.module_hint,
            limit=data.limit,
        )

    def propose_resolution(
        self,
        cause: str,
        fix_summary: str,
        files: list[dict[str, Any]] | None = None,
        finding_id: UUID | None = None,
    ) -> ResolutionProposal:
        """Formulate a resolution proposal via BugMemoryAgent."""
        return self.agent.propose_resolution(
            cause=cause,
            fix_summary=fix_summary,
            files=files,
            finding_id=finding_id,
        )

    @staticmethod
    def _to_resolution_response(res: BugResolution) -> BugResolutionResponse:
        now = datetime.now(UTC)
        return BugResolutionResponse(
            id=res.id,
            bug_record_id=res.bug_record_id,
            cause=res.cause,
            fix_summary=res.fix_summary,
            files=res.files or [],
            finding_id=res.finding_id,
            resolved_by=res.resolved_by,
            created_at=res.created_at or now,
            updated_at=res.updated_at or now,
        )

    def _to_detail_response(self, record: BugRecord) -> BugRecordDetailResponse:
        now = datetime.now(UTC)
        resolutions = [self._to_resolution_response(r) for r in (record.resolutions or [])]
        return BugRecordDetailResponse(
            id=record.id,
            workspace_id=record.workspace_id,
            project_id=record.project_id,
            fingerprint=record.fingerprint,
            error_signature=record.error_signature,
            title=record.title,
            summary=record.summary,
            module_hint=record.module_hint,
            occurrence_count=record.occurrence_count,
            resolutions_count=len(resolutions),
            first_seen_at=record.first_seen_at or now,
            last_seen_at=record.last_seen_at or now,
            created_at=record.created_at or now,
            updated_at=record.updated_at or now,
            raw_error=record.raw_error,
            resolutions=resolutions,
        )
