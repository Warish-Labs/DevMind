"""Project Brain Snapshot and File Versioning Domain Service (docs/03 §3.2, docs/04 §11).

Provides:
1. Point-in-time immutable snapshot creation capturing current file versions.
2. Historical snapshot retrieval and file membership inspection.
3. Snapshot diffing and comparison (snapshot-to-snapshot and snapshot-to-current).
4. Tenant isolation enforced on all snapshot queries and mutations.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import NotFoundError, ValidationError
from app.domain.brain.context import resolve_project_context
from app.persistence.repositories.brain_repo import BrainRepository


class CreateSnapshotRequest(BaseModel):
    """Payload for capturing a point-in-time project snapshot."""

    kind: str = Field(
        default="scan",
        description="Snapshot trigger origin: scan | commit | manual",
    )
    ref: str = Field(
        default="",
        max_length=255,
        description="External reference (e.g. commit SHA or scan run ID)",
    )
    label: str | None = Field(
        default=None,
        max_length=255,
        description="Optional human-readable label",
    )


class SnapshotFileItem(BaseModel):
    """File version metadata linked to a snapshot."""

    file_id: UUID
    file_version_id: UUID
    path: str
    language: str
    tier: int
    content_hash: str
    size_bytes: int
    line_count: int


class SnapshotItem(BaseModel):
    """Serialized summary of a project snapshot."""

    id: UUID
    project_id: UUID
    kind: str
    ref: str
    label: str | None = None
    created_at: datetime
    file_count: int = 0


class SnapshotDetail(BaseModel):
    """Full snapshot details including file composition."""

    snapshot: SnapshotItem
    files: list[SnapshotFileItem] = Field(default_factory=list)


class SnapshotDiffItem(BaseModel):
    """Comparison item for a single file between two snapshots."""

    path: str
    status: str = Field(description="added | removed | modified | unchanged")
    base_version_id: UUID | None = None
    base_content_hash: str | None = None
    target_version_id: UUID | None = None
    target_content_hash: str | None = None


class SnapshotDiffResponse(BaseModel):
    """Complete diff report between two snapshots or against active state."""

    base_snapshot_id: UUID
    target_snapshot_id: UUID | None = None
    added: int
    removed: int
    modified: int
    unchanged: int
    differences: list[SnapshotDiffItem] = Field(default_factory=list)


class SnapshotService:
    """Domain service orchestrating point-in-time project snapshots and version diffs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = BrainRepository(session)

    async def resolve_project_context(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
    ) -> AuthContext | SystemContext:
        """Resolve and verify tenant workspace context for caller on target project."""
        return await resolve_project_context(self.session, ctx, project_id)

    async def create_snapshot(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        payload: CreateSnapshotRequest,
    ) -> SnapshotItem:
        """Capture an immutable point-in-time snapshot of all currently active files."""
        if payload.kind not in ("scan", "commit", "manual"):
            raise ValidationError(detail="Snapshot kind must be 'scan', 'commit', or 'manual'")

        snapshot = await self.repo.create_snapshot_from_active_files(
            ctx,
            project_id=project_id,
            kind=payload.kind,
            ref=payload.ref,
            label=payload.label,
        )

        file_count = await self.repo.count_snapshot_files(ctx, project_id, snapshot.id)

        return SnapshotItem(
            id=snapshot.id,
            project_id=snapshot.project_id,
            kind=snapshot.kind,
            ref=snapshot.ref,
            label=snapshot.label,
            created_at=snapshot.created_at,
            file_count=file_count,
        )

    async def get_snapshot(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        snapshot_id: UUID,
    ) -> SnapshotItem:
        """Get summary metadata of a specific snapshot."""
        snapshot = await self.repo.get_snapshot(ctx, project_id, snapshot_id)
        if snapshot is None:
            raise NotFoundError(detail=f"Snapshot '{snapshot_id}' not found")

        file_count = await self.repo.count_snapshot_files(ctx, project_id, snapshot.id)

        return SnapshotItem(
            id=snapshot.id,
            project_id=snapshot.project_id,
            kind=snapshot.kind,
            ref=snapshot.ref,
            label=snapshot.label,
            created_at=snapshot.created_at,
            file_count=file_count,
        )

    async def get_snapshot_detail(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        snapshot_id: UUID,
    ) -> SnapshotDetail:
        """Get complete snapshot metadata and all associated file version mappings."""
        snapshot = await self.repo.get_snapshot(ctx, project_id, snapshot_id)
        if snapshot is None:
            raise NotFoundError(detail=f"Snapshot '{snapshot_id}' not found")

        snapshot_files = await self.repo.get_snapshot_files(ctx, project_id, snapshot_id)

        file_items: list[SnapshotFileItem] = []
        for sf in snapshot_files:
            file_obj = sf.file
            ver_obj = sf.file_version
            file_items.append(
                SnapshotFileItem(
                    file_id=sf.file_id,
                    file_version_id=sf.file_version_id,
                    path=file_obj.path if file_obj else "unknown",
                    language=file_obj.language if file_obj else "unknown",
                    tier=file_obj.tier if file_obj else 1,
                    content_hash=ver_obj.content_hash if ver_obj else "",
                    size_bytes=ver_obj.size_bytes if ver_obj else 0,
                    line_count=ver_obj.line_count if ver_obj else 0,
                )
            )

        summary = SnapshotItem(
            id=snapshot.id,
            project_id=snapshot.project_id,
            kind=snapshot.kind,
            ref=snapshot.ref,
            label=snapshot.label,
            created_at=snapshot.created_at,
            file_count=len(file_items),
        )

        return SnapshotDetail(snapshot=summary, files=file_items)

    async def list_snapshots(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        limit: int = 20,
    ) -> list[SnapshotItem]:
        """List recent project snapshots with file counts."""
        snapshots = await self.repo.list_snapshots(ctx, project_id, limit=limit)
        items: list[SnapshotItem] = []
        for s in snapshots:
            count = await self.repo.count_snapshot_files(ctx, project_id, s.id)
            items.append(
                SnapshotItem(
                    id=s.id,
                    project_id=s.project_id,
                    kind=s.kind,
                    ref=s.ref,
                    label=s.label,
                    created_at=s.created_at,
                    file_count=count,
                )
            )
        return items

    async def compare_snapshots(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        base_snapshot_id: UUID,
        target_snapshot_id: UUID | None = None,
    ) -> SnapshotDiffResponse:
        """Compute file-level diff between two snapshots or against current active state."""
        # 1. Load base snapshot files
        base_snapshot = await self.repo.get_snapshot(ctx, project_id, base_snapshot_id)
        if base_snapshot is None:
            raise NotFoundError(detail=f"Base snapshot '{base_snapshot_id}' not found")

        base_sf_list = await self.repo.get_snapshot_files(ctx, project_id, base_snapshot_id)
        base_map: dict[str, tuple[UUID, str]] = {}
        for sf in base_sf_list:
            if sf.file and sf.file_version:
                base_map[sf.file.path] = (sf.file_version_id, sf.file_version.content_hash)

        # 2. Load target snapshot files (or current active files)
        target_map: dict[str, tuple[UUID, str]] = {}
        if target_snapshot_id is not None:
            target_snapshot = await self.repo.get_snapshot(ctx, project_id, target_snapshot_id)
            if target_snapshot is None:
                raise NotFoundError(detail=f"Target snapshot '{target_snapshot_id}' not found")

            target_sf_list = await self.repo.get_snapshot_files(ctx, project_id, target_snapshot_id)
            for sf in target_sf_list:
                if sf.file and sf.file_version:
                    target_map[sf.file.path] = (sf.file_version_id, sf.file_version.content_hash)
        else:
            active_files = await self.repo.list_active_files(ctx, project_id)
            for f in active_files:
                if f.current_version is not None:
                    target_map[f.path] = (f.current_version.id, f.current_version.content_hash)

        # 3. Categorize differences
        added = 0
        removed = 0
        modified = 0
        unchanged = 0
        differences: list[SnapshotDiffItem] = []

        all_paths = sorted(set(base_map.keys()) | set(target_map.keys()))

        for path in all_paths:
            in_base = path in base_map
            in_target = path in target_map

            if in_base and not in_target:
                removed += 1
                ver_id, chash = base_map[path]
                differences.append(
                    SnapshotDiffItem(
                        path=path,
                        status="removed",
                        base_version_id=ver_id,
                        base_content_hash=chash,
                    )
                )
            elif in_target and not in_base:
                added += 1
                ver_id, chash = target_map[path]
                differences.append(
                    SnapshotDiffItem(
                        path=path,
                        status="added",
                        target_version_id=ver_id,
                        target_content_hash=chash,
                    )
                )
            else:
                base_ver_id, base_hash = base_map[path]
                target_ver_id, target_hash = target_map[path]

                if base_hash == target_hash:
                    unchanged += 1
                    differences.append(
                        SnapshotDiffItem(
                            path=path,
                            status="unchanged",
                            base_version_id=base_ver_id,
                            base_content_hash=base_hash,
                            target_version_id=target_ver_id,
                            target_content_hash=target_hash,
                        )
                    )
                else:
                    modified += 1
                    differences.append(
                        SnapshotDiffItem(
                            path=path,
                            status="modified",
                            base_version_id=base_ver_id,
                            base_content_hash=base_hash,
                            target_version_id=target_ver_id,
                            target_content_hash=target_hash,
                        )
                    )

        return SnapshotDiffResponse(
            base_snapshot_id=base_snapshot_id,
            target_snapshot_id=target_snapshot_id,
            added=added,
            removed=removed,
            modified=modified,
            unchanged=unchanged,
            differences=differences,
        )
