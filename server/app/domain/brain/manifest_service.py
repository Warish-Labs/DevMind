"""Manifest synchronization and diff domain service (docs/03 §11.2, §12.3, docs/04 §11)."""

from __future__ import annotations

import dataclasses
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import ForbiddenError, NotFoundError, StaleBaseError
from app.persistence.models.project import Project, ProjectMembership
from app.persistence.models.workspace import WorkspaceMembership
from app.persistence.repositories.brain_repo import BrainRepository


class FileManifestEntry(BaseModel):
    """File metadata entry within an extension scan manifest."""

    path: str = Field(min_length=1, max_length=1024, description="Repository-relative file path")
    content_hash: str = Field(
        min_length=64, max_length=64, description="SHA-256 hash of file content"
    )
    size_bytes: int = Field(ge=0, description="File size in bytes")
    line_count: int = Field(ge=0, description="Total line count")
    language: str = Field(
        min_length=1, max_length=64, description="Detected language (e.g. typescript, python)"
    )
    tier: int = Field(
        default=1, ge=1, le=3, description="Parser tier: 1=semantic, 2=text, 3=unsupported"
    )


class MissingFileEntry(BaseModel):
    """File item requiring full metadata/symbol extraction upload."""

    path: str
    content_hash: str


class ManifestDiffRequest(BaseModel):
    """Payload for computing cloud-to-local manifest diff."""

    scan_run_id: UUID | None = None
    base_snapshot_id: UUID | None = None
    files: list[FileManifestEntry] = Field(default_factory=list)


class ManifestDiffResponse(BaseModel):
    """Cloud manifest diff results identifying missing or changed files."""

    unchanged: int
    new: int
    changed: int
    removed: list[str] = Field(default_factory=list)
    stale_base: bool = False
    missing_files: list[MissingFileEntry] = Field(default_factory=list)
    sync_base_token: str | None = None


class PutManifestRequest(BaseModel):
    """Payload for registering synced files and versions in Project Brain."""

    scan_run_id: UUID | None = None
    base_snapshot_id: UUID | None = None
    files: list[FileManifestEntry] = Field(default_factory=list)
    removed_paths: list[str] = Field(default_factory=list)


class PutManifestResponse(BaseModel):
    """Result receipt for manifest metadata sync."""

    status: str = "synced"
    project_id: UUID
    scan_run_id: UUID | None = None
    files_count: int
    versions_created: int
    removed_count: int


class ManifestService:
    """Domain service computing cloud-to-local manifest diffs and upserting synced file metadata."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = BrainRepository(session)

    async def resolve_project_context(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
    ) -> AuthContext | SystemContext:
        """Resolve and verify tenant workspace context for caller on target project."""
        if isinstance(ctx, SystemContext):
            return ctx

        stmt = select(Project).where(
            Project.id == project_id,
            Project.deleted_at.is_(None),
        )
        res = await self.session.execute(stmt)
        project = res.scalars().first()
        if project is None:
            raise NotFoundError(detail=f"Project '{project_id}' not found")

        if ctx.workspace_id == project.workspace_id:
            return ctx

        # Check workspace membership
        ws_stmt = select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == project.workspace_id,
            WorkspaceMembership.user_id == ctx.user_id,
        )
        ws_mem = (await self.session.execute(ws_stmt)).scalars().first()

        if ws_mem is None:
            # Check project membership
            pm_stmt = select(ProjectMembership).where(
                ProjectMembership.project_id == project.id,
                ProjectMembership.user_id == ctx.user_id,
            )
            pm = (await self.session.execute(pm_stmt)).scalars().first()
            if pm is None:
                raise ForbiddenError(
                    detail=f"Forbidden: caller lacks membership in project '{project_id}'"
                )

        return dataclasses.replace(
            ctx,
            workspace_id=project.workspace_id,
            project_id=project.id,
            workspace_role=ws_mem.role if ws_mem else None,
        )

    async def compute_diff(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        payload: ManifestDiffRequest,
    ) -> ManifestDiffResponse:
        """Compute manifest diff between incoming local scan files and current cloud Brain state.

        Detects:
        - `unchanged`: paths matching active file with identical content hash.
        - `new`: paths not previously recorded in this project.
        - `changed`: known paths whose content hash differs from the current version.
        - `removed`: active cloud paths absent from the incoming manifest.
        - `sync.stale_base`: 409 conflict when base_snapshot_id does not match project's latest snapshot.
        """
        # 1. Base snapshot staleness check (docs/03 §10.1, docs/04 §11)
        if payload.base_snapshot_id is not None:
            latest = await self.repo.get_latest_snapshot(ctx, project_id)
            if latest is not None and latest.id != payload.base_snapshot_id:
                raise StaleBaseError(
                    detail=f"Client base snapshot {payload.base_snapshot_id} is stale; current latest is {latest.id}"
                )

        # 2. Retrieve active files with current version loaded
        active_files = await self.repo.list_active_files(ctx, project_id)
        active_by_path = {f.path: f for f in active_files}

        # 3. Categorize incoming files
        unchanged = 0
        new = 0
        changed = 0
        missing_files: list[MissingFileEntry] = []
        incoming_paths: set[str] = set()

        for f in payload.files:
            incoming_paths.add(f.path)
            existing = active_by_path.get(f.path)

            if existing is None:
                new += 1
                missing_files.append(MissingFileEntry(path=f.path, content_hash=f.content_hash))
            else:
                curr_version = existing.current_version
                if curr_version is not None and curr_version.content_hash == f.content_hash:
                    unchanged += 1
                else:
                    changed += 1
                    missing_files.append(MissingFileEntry(path=f.path, content_hash=f.content_hash))

        # 4. Identify removed files
        removed_paths = [p for p in active_by_path if p not in incoming_paths]

        token_ref = str(payload.base_snapshot_id or "base")

        return ManifestDiffResponse(
            unchanged=unchanged,
            new=new,
            changed=changed,
            removed=removed_paths,
            stale_base=False,
            missing_files=missing_files,
            sync_base_token=token_ref,
        )

    async def put_manifest(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        payload: PutManifestRequest,
    ) -> PutManifestResponse:
        """Register or update file metadata and versions from an extension scan."""
        # 1. Base snapshot staleness check
        if payload.base_snapshot_id is not None:
            latest = await self.repo.get_latest_snapshot(ctx, project_id)
            if latest is not None and latest.id != payload.base_snapshot_id:
                raise StaleBaseError(
                    detail=f"Client base snapshot {payload.base_snapshot_id} is stale; current latest is {latest.id}"
                )

        # 2. Upsert each file and create immutable content version
        versions_created = 0
        for f in payload.files:
            file_rec = await self.repo.upsert_file(
                ctx,
                project_id=project_id,
                path=f.path,
                language=f.language,
                tier=f.tier,
            )
            await self.repo.create_file_version(
                ctx,
                project_id=project_id,
                file_id=file_rec.id,
                content_hash=f.content_hash,
                size_bytes=f.size_bytes,
                line_count=f.line_count,
                scan_run_id=payload.scan_run_id,
                origin="extension",
            )
            versions_created += 1

        # 3. Mark removed files if any specified
        removed_count = 0
        if payload.removed_paths:
            removed_count = await self.repo.mark_files_removed(
                ctx, project_id, payload.removed_paths
            )

        return PutManifestResponse(
            status="synced",
            project_id=project_id,
            scan_run_id=payload.scan_run_id,
            files_count=len(payload.files),
            versions_created=versions_created,
            removed_count=removed_count,
        )
