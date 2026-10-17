"""Scan domain service and response schemas for browser and client queries (docs/03 §11.1)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import NotFoundError
from app.domain.brain.context import resolve_project_context
from app.persistence.models.brain import ScanRun
from app.persistence.repositories.brain_repo import BrainRepository


class ScanRunItem(BaseModel):
    """Serialized summary of a scan run."""

    id: UUID
    project_id: UUID
    origin: str
    registration_id: UUID | None = None
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    rules_version: str | None = None
    stats: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScanService:
    """Manages queries and lifecycle views for scan runs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = BrainRepository(session)

    async def resolve_project_context(
        self, ctx: AuthContext | SystemContext, project_id: UUID
    ) -> AuthContext | SystemContext:
        """Resolve and verify tenant authorization context for project."""
        return await resolve_project_context(self.session, ctx, project_id)

    async def list_scans(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        status_filter: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ScanRunItem]:
        """List scan runs for a project ordered by creation time descending."""
        scans = await self.repo.list_scan_runs(
            ctx,
            project_id=project_id,
            status=status_filter,
            limit=limit,
            offset=offset,
        )
        return [self._to_item(s) for s in scans]

    async def get_scan(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        scan_run_id: UUID,
    ) -> ScanRunItem:
        """Retrieve details of a single scan run."""
        scan = await self.repo.get_scan_run(ctx, project_id, scan_run_id)
        if not scan:
            raise NotFoundError(
                code="scan.not_found",
                detail=f"Scan run '{scan_run_id}' not found for project '{project_id}'",
            )
        return self._to_item(scan)

    def _to_item(self, scan: ScanRun) -> ScanRunItem:
        now = datetime.now(UTC)
        return ScanRunItem(
            id=scan.id,
            project_id=scan.project_id,
            origin=scan.origin,
            registration_id=scan.registration_id,
            status=scan.status,
            started_at=scan.started_at,
            finished_at=scan.finished_at,
            rules_version=scan.rules_version,
            stats=scan.stats or {},
            created_at=scan.created_at or now,
            updated_at=scan.updated_at or now,
        )
