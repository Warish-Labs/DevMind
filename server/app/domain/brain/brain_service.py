"""Project Brain query domain service and response schemas (docs/03 §11.1)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import NotFoundError
from app.domain.brain.context import resolve_project_context
from app.domain.brain.scan_service import ScanRunItem
from app.domain.brain.snapshot_service import SnapshotItem
from app.persistence.models.brain import ProjectSnapshot, ScanRun
from app.persistence.repositories.brain_repo import BrainRepository


class BrainFileVersionItem(BaseModel):
    """Historical file version record."""

    id: UUID
    file_id: UUID
    content_hash: str
    size_bytes: int
    line_count: int
    scan_run_id: UUID | None = None
    origin: str = "extension"
    created_at: datetime

    model_config = {"from_attributes": True}


class BrainFileItem(BaseModel):
    """Active file summary in project brain."""

    id: UUID
    project_id: UUID
    path: str
    language: str
    tier: int
    current_version_id: UUID | None = None
    size_bytes: int | None = None
    line_count: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BrainFileDetail(BrainFileItem):
    """File detail including historical versions."""

    versions: list[BrainFileVersionItem] = Field(default_factory=list)


class BrainSummaryResponse(BaseModel):
    """Aggregated metrics and health overview for Project Brain."""

    project_id: UUID
    total_files: int
    languages: dict[str, int]
    total_versions: int
    total_snapshots: int
    total_symbols: int
    total_relationships: int
    findings_summary: dict[str, int]
    latest_snapshot: SnapshotItem | None = None
    latest_scan: ScanRunItem | None = None


class BrainService:
    """Manages high-level queries and aggregated views for Project Brain."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = BrainRepository(session)

    async def resolve_project_context(
        self, ctx: AuthContext | SystemContext, project_id: UUID
    ) -> AuthContext | SystemContext:
        """Resolve and verify tenant authorization context for project."""
        return await resolve_project_context(self.session, ctx, project_id)

    async def get_summary(
        self, ctx: AuthContext | SystemContext, project_id: UUID
    ) -> BrainSummaryResponse:
        """Retrieve aggregated counts and metrics for the project brain."""
        raw_stats = await self.repo.get_brain_summary_stats(ctx, project_id)
        now = datetime.now(UTC)

        latest_snap: SnapshotItem | None = None
        if raw_stats.get("latest_snapshot"):
            snap: ProjectSnapshot = raw_stats["latest_snapshot"]
            count = await self.repo.count_snapshot_files(ctx, project_id, snap.id)
            latest_snap = SnapshotItem(
                id=snap.id,
                project_id=snap.project_id,
                kind=snap.kind,
                ref=snap.ref,
                label=snap.label,
                created_at=snap.created_at or now,
                file_count=count,
            )

        latest_scan_item: ScanRunItem | None = None
        if raw_stats.get("latest_scan"):
            scan: ScanRun = raw_stats["latest_scan"]
            latest_scan_item = ScanRunItem(
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

        return BrainSummaryResponse(
            project_id=project_id,
            total_files=raw_stats["total_files"],
            languages=raw_stats["languages"],
            total_versions=raw_stats["total_versions"],
            total_snapshots=raw_stats["total_snapshots"],
            total_symbols=raw_stats["total_symbols"],
            total_relationships=raw_stats["total_relationships"],
            findings_summary=raw_stats["findings_summary"],
            latest_snapshot=latest_snap,
            latest_scan=latest_scan_item,
        )

    async def list_files(
        self, ctx: AuthContext | SystemContext, project_id: UUID
    ) -> list[BrainFileItem]:
        """List all active non-removed files with their current content metrics."""
        files = await self.repo.list_active_files(ctx, project_id)
        now = datetime.now(UTC)
        items: list[BrainFileItem] = []
        for f in files:
            size_b = f.current_version.size_bytes if f.current_version else None
            lines = f.current_version.line_count if f.current_version else None
            items.append(
                BrainFileItem(
                    id=f.id,
                    project_id=f.project_id,
                    path=f.path,
                    language=f.language,
                    tier=f.tier,
                    current_version_id=f.current_version_id,
                    size_bytes=size_b,
                    line_count=lines,
                    created_at=f.created_at or now,
                    updated_at=f.updated_at or now,
                )
            )
        return items

    async def get_file_detail(
        self, ctx: AuthContext | SystemContext, project_id: UUID, file_id: UUID
    ) -> BrainFileDetail:
        """Retrieve detailed file metadata and all historical versions."""
        file = await self.repo.get_file_by_id(ctx, project_id, file_id)
        if not file or file.removed_at is not None:
            raise NotFoundError(
                code="file.not_found",
                detail=f"File '{file_id}' not found in project '{project_id}'",
            )

        now = datetime.now(UTC)
        size_b = file.current_version.size_bytes if file.current_version else None
        lines = file.current_version.line_count if file.current_version else None

        versions_list: list[BrainFileVersionItem] = []
        if file.versions:
            for v in sorted(file.versions, key=lambda x: x.created_at or now, reverse=True):
                versions_list.append(
                    BrainFileVersionItem(
                        id=v.id,
                        file_id=v.file_id,
                        content_hash=v.content_hash,
                        size_bytes=v.size_bytes,
                        line_count=v.line_count,
                        scan_run_id=v.scan_run_id,
                        origin=v.origin or "extension",
                        created_at=v.created_at or now,
                    )
                )

        return BrainFileDetail(
            id=file.id,
            project_id=file.project_id,
            path=file.path,
            language=file.language,
            tier=file.tier,
            current_version_id=file.current_version_id,
            size_bytes=size_b,
            line_count=lines,
            created_at=file.created_at or now,
            updated_at=file.updated_at or now,
            versions=versions_list,
        )
