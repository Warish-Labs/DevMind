"""Brain repository managing files, versions, snapshots, symbols, relationships, jobs, and findings (docs/03 §3.2-§3.4, docs/03 §4)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth_context import AuthContext, SystemContext
from app.core.ids import generate_uuid7
from app.persistence.models.brain import (
    AgentRun,
    AnalysisJob,
    ChunkEmbedding,
    CodeChunk,
    CodeRelationship,
    CodeSymbol,
    EmbeddingSpace,
    File,
    FileVersion,
    Finding,
    FindingEvidence,
    FindingStatusHistory,
    JobEvent,
    LocalWorkspaceRegistration,
    ProjectFile,
    ProjectSnapshot,
    ScanRun,
    SnapshotFile,
)
from app.persistence.models.project import Project
from app.persistence.repositories.base import BaseRepository


class BrainRepository(BaseRepository):
    """Repository managing Project Brain metadata, symbols, snapshots, jobs and findings.

    Enforces workspace-level and project-level isolation via AuthContext on every operation.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def _verify_project_access(
        self, ctx: AuthContext | SystemContext, project_id: UUID
    ) -> Project:
        """Verify that the caller has access to the target project.

        Raises:
            PermissionError: If caller's workspace does not own the project.
            ValueError: If project does not exist.
        """
        self._validate_context(ctx)
        stmt = select(Project).where(Project.id == project_id)
        if isinstance(ctx, AuthContext):
            if ctx.workspace_id is None:
                raise PermissionError("Access denied: missing workspace context")
            stmt = stmt.where(Project.workspace_id == ctx.workspace_id)

        result = await self.session.execute(stmt)
        project = result.scalars().first()
        if not project:
            if isinstance(ctx, AuthContext):
                raise PermissionError(
                    f"Access denied: project {project_id} not found in workspace {ctx.workspace_id}"
                )
            raise ValueError(f"Project {project_id} not found")
        return project

    # --- Local Workspace Registrations ---

    async def upsert_local_workspace_registration(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        registration_id: UUID,
        workspace_label: str,
        root_fingerprint: str,
    ) -> LocalWorkspaceRegistration:
        """Register or update a local workspace folder linked to a project."""
        await self._verify_project_access(ctx, project_id)

        stmt = select(LocalWorkspaceRegistration).where(
            LocalWorkspaceRegistration.project_id == project_id,
            LocalWorkspaceRegistration.registration_id == registration_id,
            LocalWorkspaceRegistration.root_fingerprint == root_fingerprint,
        )
        result = await self.session.execute(stmt)
        reg = result.scalars().first()

        now = datetime.now(UTC)
        if reg:
            reg.workspace_label = workspace_label
            reg.last_sync_at = now
            await self.session.flush()
            return reg

        new_reg = LocalWorkspaceRegistration(
            project_id=project_id,
            registration_id=registration_id,
            workspace_label=workspace_label,
            root_fingerprint=root_fingerprint,
            last_sync_at=now,
        )
        self.session.add(new_reg)
        await self.session.flush()
        return new_reg

    async def get_local_workspace_registration(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        registration_id: UUID,
        root_fingerprint: str,
    ) -> LocalWorkspaceRegistration | None:
        """Retrieve local workspace registration by triple key."""
        await self._verify_project_access(ctx, project_id)
        stmt = select(LocalWorkspaceRegistration).where(
            LocalWorkspaceRegistration.project_id == project_id,
            LocalWorkspaceRegistration.registration_id == registration_id,
            LocalWorkspaceRegistration.root_fingerprint == root_fingerprint,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    # --- Scan Runs ---

    async def create_scan_run(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        origin: str = "extension",
        registration_id: UUID | None = None,
        rules_version: str | None = None,
        idempotency_key: str | None = None,
        stats: dict[str, Any] | None = None,
    ) -> ScanRun:
        """Record the start of a scan run."""
        await self._verify_project_access(ctx, project_id)

        if idempotency_key:
            stmt = select(ScanRun).where(
                ScanRun.project_id == project_id,
                ScanRun.idempotency_key == idempotency_key,
            )
            result = await self.session.execute(stmt)
            existing = result.scalars().first()
            if existing:
                return existing

        now = datetime.now(UTC)
        scan = ScanRun(
            project_id=project_id,
            origin=origin,
            registration_id=registration_id,
            status="running",
            started_at=now,
            rules_version=rules_version,
            stats=stats or {},
            idempotency_key=idempotency_key,
        )
        self.session.add(scan)
        await self.session.flush()
        return scan

    async def get_scan_run(
        self, ctx: AuthContext | SystemContext, project_id: UUID, scan_run_id: UUID
    ) -> ScanRun | None:
        """Get scan run by ID."""
        await self._verify_project_access(ctx, project_id)
        stmt = select(ScanRun).where(
            ScanRun.id == scan_run_id,
            ScanRun.project_id == project_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update_scan_run_status(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        scan_run_id: UUID,
        status: str,
        stats: dict[str, Any] | None = None,
        finished_at: datetime | None = None,
    ) -> ScanRun | None:
        """Update status and stats of a scan run."""
        scan = await self.get_scan_run(ctx, project_id, scan_run_id)
        if not scan:
            return None

        scan.status = status
        if stats is not None:
            scan.stats = stats
        if finished_at is not None:
            scan.finished_at = finished_at
        elif status in ("completed", "failed", "cancelled") and scan.finished_at is None:
            scan.finished_at = datetime.now(UTC)

        await self.session.flush()
        return scan

    async def list_scan_runs(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ScanRun]:
        """List scan runs for a project ordered by creation time descending."""
        await self._verify_project_access(ctx, project_id)
        stmt = (
            select(ScanRun)
            .where(ScanRun.project_id == project_id)
            .order_by(ScanRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status:
            stmt = stmt.where(ScanRun.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_scan_run(
        self, ctx: AuthContext | SystemContext, project_id: UUID
    ) -> ScanRun | None:
        """Get the most recent scan run for a project."""
        await self._verify_project_access(ctx, project_id)
        stmt = (
            select(ScanRun)
            .where(ScanRun.project_id == project_id)
            .order_by(ScanRun.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    # --- Files and Versions ---

    async def upsert_file(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        path: str,
        language: str,
        tier: int = 1,
    ) -> ProjectFile:
        """Upsert file entry for a repo-relative path."""
        await self._verify_project_access(ctx, project_id)

        stmt = select(ProjectFile).where(
            ProjectFile.project_id == project_id,
            ProjectFile.path == path,
        )
        result = await self.session.execute(stmt)
        file = result.scalars().first()

        if file:
            file.language = language
            file.tier = tier
            file.removed_at = None
            await self.session.flush()
            return file

        new_file = ProjectFile(
            project_id=project_id,
            path=path,
            language=language,
            tier=tier,
        )
        self.session.add(new_file)
        await self.session.flush()
        return new_file

    async def get_file_by_path(
        self, ctx: AuthContext | SystemContext, project_id: UUID, path: str
    ) -> ProjectFile | None:
        """Find file by path within a project."""
        await self._verify_project_access(ctx, project_id)
        stmt = select(ProjectFile).where(
            ProjectFile.project_id == project_id,
            ProjectFile.path == path,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_active_files(
        self, ctx: AuthContext | SystemContext, project_id: UUID
    ) -> list[ProjectFile]:
        """List all non-removed files for a project with current_version eagerly loaded."""
        await self._verify_project_access(ctx, project_id)
        stmt = (
            select(ProjectFile)
            .options(selectinload(ProjectFile.current_version))
            .where(
                ProjectFile.project_id == project_id,
                ProjectFile.removed_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_file_by_id(
        self, ctx: AuthContext | SystemContext, project_id: UUID, file_id: UUID
    ) -> ProjectFile | None:
        """Retrieve a project file by its primary key with current version and historical versions."""
        await self._verify_project_access(ctx, project_id)
        stmt = (
            select(ProjectFile)
            .options(
                selectinload(ProjectFile.current_version),
                selectinload(ProjectFile.versions),
            )
            .where(
                ProjectFile.id == file_id,
                ProjectFile.project_id == project_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def mark_files_removed(
        self, ctx: AuthContext | SystemContext, project_id: UUID, paths: list[str]
    ) -> int:
        """Mark missing files as removed."""
        if not paths:
            return 0
        await self._verify_project_access(ctx, project_id)
        now = datetime.now(UTC)
        stmt = (
            update(ProjectFile)
            .where(
                ProjectFile.project_id == project_id,
                ProjectFile.path.in_(paths),
                ProjectFile.removed_at.is_(None),
            )
            .values(removed_at=now)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def create_file_version(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        file_id: UUID,
        content_hash: str,
        size_bytes: int,
        line_count: int,
        scan_run_id: UUID | None = None,
        origin: str = "extension",
    ) -> FileVersion:
        """Create or reuse immutable content version for a file."""
        await self._verify_project_access(ctx, project_id)

        stmt = select(FileVersion).where(
            FileVersion.file_id == file_id,
            FileVersion.content_hash == content_hash,
        )
        result = await self.session.execute(stmt)
        existing = result.scalars().first()
        if existing:
            # Update current_version_id if needed
            file_stmt = select(ProjectFile).where(ProjectFile.id == file_id)
            file_res = await self.session.execute(file_stmt)
            file_obj = file_res.scalars().first()
            if file_obj and file_obj.current_version_id != existing.id:
                file_obj.current_version_id = existing.id
                await self.session.flush()
            return existing

        version = FileVersion(
            file_id=file_id,
            project_id=project_id,
            content_hash=content_hash,
            size_bytes=size_bytes,
            line_count=line_count,
            scan_run_id=scan_run_id,
            origin=origin,
        )
        self.session.add(version)
        await self.session.flush()

        # Update file's current_version_id
        file_stmt = select(ProjectFile).where(ProjectFile.id == file_id)
        file_res = await self.session.execute(file_stmt)
        file_obj = file_res.scalars().first()
        if file_obj:
            file_obj.current_version_id = version.id
            await self.session.flush()

        return version

    # --- Project Snapshots ---

    async def create_snapshot(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        kind: str = "scan",
        ref: str = "",
        label: str | None = None,
        file_mappings: list[tuple[UUID, UUID]] | None = None,
    ) -> ProjectSnapshot:
        """Create an immutable snapshot of project state."""
        await self._verify_project_access(ctx, project_id)

        snapshot = ProjectSnapshot(
            project_id=project_id,
            kind=kind,
            ref=ref,
            label=label,
        )
        self.session.add(snapshot)
        await self.session.flush()

        if file_mappings:
            for file_id, file_version_id in file_mappings:
                sf = SnapshotFile(
                    snapshot_id=snapshot.id,
                    file_id=file_id,
                    file_version_id=file_version_id,
                )
                self.session.add(sf)
            await self.session.flush()

        return snapshot

    async def get_snapshot(
        self, ctx: AuthContext | SystemContext, project_id: UUID, snapshot_id: UUID
    ) -> ProjectSnapshot | None:
        """Get snapshot by ID."""
        await self._verify_project_access(ctx, project_id)
        stmt = select(ProjectSnapshot).where(
            ProjectSnapshot.id == snapshot_id,
            ProjectSnapshot.project_id == project_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_snapshots(
        self, ctx: AuthContext | SystemContext, project_id: UUID, limit: int = 20
    ) -> list[ProjectSnapshot]:
        """List recent project snapshots."""
        await self._verify_project_access(ctx, project_id)
        stmt = (
            select(ProjectSnapshot)
            .where(ProjectSnapshot.project_id == project_id)
            .order_by(ProjectSnapshot.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_snapshot(
        self, ctx: AuthContext | SystemContext, project_id: UUID
    ) -> ProjectSnapshot | None:
        """Get the latest snapshot for a project."""
        await self._verify_project_access(ctx, project_id)
        stmt = (
            select(ProjectSnapshot)
            .where(ProjectSnapshot.project_id == project_id)
            .order_by(ProjectSnapshot.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_snapshot_from_active_files(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        kind: str = "scan",
        ref: str = "",
        label: str | None = None,
    ) -> ProjectSnapshot:
        """Create a point-in-time snapshot capturing all currently active files and their versions."""
        await self._verify_project_access(ctx, project_id)
        active_files = await self.list_active_files(ctx, project_id)
        file_mappings = [
            (f.id, f.current_version_id) for f in active_files if f.current_version_id is not None
        ]
        return await self.create_snapshot(
            ctx,
            project_id=project_id,
            kind=kind,
            ref=ref,
            label=label,
            file_mappings=file_mappings,
        )

    async def get_snapshot_files(
        self, ctx: AuthContext | SystemContext, project_id: UUID, snapshot_id: UUID
    ) -> list[SnapshotFile]:
        """List all file mappings for a given snapshot with eagerly loaded file and file_version."""
        await self._verify_project_access(ctx, project_id)
        stmt = (
            select(SnapshotFile)
            .join(ProjectSnapshot, SnapshotFile.snapshot_id == ProjectSnapshot.id)
            .options(
                selectinload(SnapshotFile.file),
                selectinload(SnapshotFile.file_version),
            )
            .where(
                SnapshotFile.snapshot_id == snapshot_id,
                ProjectSnapshot.project_id == project_id,
            )
            .order_by(SnapshotFile.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_snapshot_files(
        self, ctx: AuthContext | SystemContext, project_id: UUID, snapshot_id: UUID
    ) -> int:
        """Count total files captured in a snapshot."""
        await self._verify_project_access(ctx, project_id)
        stmt = (
            select(func.count(SnapshotFile.id))
            .join(ProjectSnapshot, SnapshotFile.snapshot_id == ProjectSnapshot.id)
            .where(
                SnapshotFile.snapshot_id == snapshot_id,
                ProjectSnapshot.project_id == project_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    # --- Code Symbols and Relationships ---

    async def batch_upsert_symbols(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        symbols_data: list[dict[str, Any]],
    ) -> list[CodeSymbol]:
        """Batch insert code symbols."""
        if not symbols_data:
            return []
        await self._verify_project_access(ctx, project_id)

        created: list[CodeSymbol] = []
        for data in symbols_data:
            symbol = CodeSymbol(
                project_id=project_id,
                file_version_id=data["file_version_id"],
                symbol_key=data["symbol_key"],
                name=data["name"],
                qualified_name=data["qualified_name"],
                kind=data["kind"],
                signature=data.get("signature"),
                start_line=data["start_line"],
                end_line=data["end_line"],
                framework_tags=data.get("framework_tags", []),
                is_current=data.get("is_current", True),
                metadata_json=data.get("metadata", {}),
            )
            self.session.add(symbol)
            created.append(symbol)

        await self.session.flush()
        return created

    async def batch_upsert_relationships(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        rels_data: list[dict[str, Any]],
    ) -> list[CodeRelationship]:
        """Batch insert code relationships."""
        if not rels_data:
            return []
        await self._verify_project_access(ctx, project_id)

        created: list[CodeRelationship] = []
        for data in rels_data:
            rel = CodeRelationship(
                project_id=project_id,
                from_symbol_id=data["from_symbol_id"],
                to_symbol_id=data.get("to_symbol_id"),
                to_external=data.get("to_external"),
                kind=data["kind"],
                resolution=data.get("resolution", "resolved"),
                file_version_id=data["file_version_id"],
                is_current=data.get("is_current", True),
            )
            self.session.add(rel)
            created.append(rel)

        await self.session.flush()
        return created

    async def mark_symbols_non_current_for_versions(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        file_version_ids: list[UUID],
    ) -> int:
        """Mark symbols and relationships for superseded versions as is_current=False."""
        if not file_version_ids:
            return 0
        await self._verify_project_access(ctx, project_id)

        stmt_sym = (
            update(CodeSymbol)
            .where(
                CodeSymbol.project_id == project_id,
                CodeSymbol.file_version_id.in_(file_version_ids),
                CodeSymbol.is_current.is_(True),
            )
            .values(is_current=False)
        )
        res_sym = await self.session.execute(stmt_sym)

        stmt_rel = (
            update(CodeRelationship)
            .where(
                CodeRelationship.project_id == project_id,
                CodeRelationship.file_version_id.in_(file_version_ids),
                CodeRelationship.is_current.is_(True),
            )
            .values(is_current=False)
        )
        await self.session.execute(stmt_rel)

        stmt_chunk = (
            update(CodeChunk)
            .where(
                CodeChunk.project_id == project_id,
                CodeChunk.file_version_id.in_(file_version_ids),
                CodeChunk.is_current.is_(True),
            )
            .values(is_current=False)
        )
        await self.session.execute(stmt_chunk)

        await self.session.flush()
        return res_sym.rowcount

    async def list_current_symbols(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        kind: str | None = None,
        limit: int = 100,
    ) -> list[CodeSymbol]:
        """List current active code symbols in a project."""
        await self._verify_project_access(ctx, project_id)
        stmt = (
            select(CodeSymbol)
            .where(
                CodeSymbol.project_id == project_id,
                CodeSymbol.is_current.is_(True),
            )
            .order_by(CodeSymbol.name.asc())
            .limit(limit)
        )
        if kind:
            stmt = stmt.where(CodeSymbol.kind == kind)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search_symbols(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        query: str,
        limit: int = 20,
    ) -> list[CodeSymbol]:
        """Search active code symbols by name or symbol_key (exact, prefix, and substring)."""
        await self._verify_project_access(ctx, project_id)
        if not query or not query.strip():
            return []
        clean = query.strip()
        stmt = (
            select(CodeSymbol)
            .options(selectinload(CodeSymbol.file_version).selectinload(FileVersion.file))
            .where(
                CodeSymbol.project_id == project_id,
                CodeSymbol.is_current.is_(True),
                (CodeSymbol.name.ilike(f"%{clean}%") | CodeSymbol.symbol_key.ilike(f"%{clean}%")),
            )
            .order_by(
                (CodeSymbol.name == clean).desc(),
                CodeSymbol.name.startswith(clean).desc(),
                CodeSymbol.name.asc(),
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_symbol_by_id(
        self, ctx: AuthContext | SystemContext, project_id: UUID, symbol_id: UUID
    ) -> CodeSymbol | None:
        """Find symbol by ID within a project."""
        await self._verify_project_access(ctx, project_id)
        stmt = select(CodeSymbol).where(
            CodeSymbol.id == symbol_id,
            CodeSymbol.project_id == project_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_symbols_by_keys(
        self, ctx: AuthContext | SystemContext, project_id: UUID, symbol_keys: list[str]
    ) -> list[CodeSymbol]:
        """Find symbols by their unique keys within a project."""
        if not symbol_keys:
            return []
        await self._verify_project_access(ctx, project_id)
        stmt = select(CodeSymbol).where(
            CodeSymbol.project_id == project_id,
            CodeSymbol.symbol_key.in_(symbol_keys),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_relationships(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        is_current: bool = True,
        limit: int = 200,
    ) -> list[CodeRelationship]:
        """List code relationships within a project."""
        await self._verify_project_access(ctx, project_id)
        stmt = (
            select(CodeRelationship)
            .where(
                CodeRelationship.project_id == project_id,
                CodeRelationship.is_current == is_current,
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_relationships_for_symbols(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        symbol_ids: list[UUID],
        limit: int = 50,
    ) -> list[CodeRelationship]:
        """Retrieve active relationships where from_symbol_id or to_symbol_id is in symbol_ids."""
        if not symbol_ids:
            return []
        await self._verify_project_access(ctx, project_id)
        stmt = (
            select(CodeRelationship)
            .where(
                CodeRelationship.project_id == project_id,
                CodeRelationship.is_current.is_(True),
                (
                    CodeRelationship.from_symbol_id.in_(symbol_ids)
                    | CodeRelationship.to_symbol_id.in_(symbol_ids)
                ),
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_chunks(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        chunks_data: list[dict[str, Any]],
    ) -> list[CodeChunk]:
        """Persist a batch of code chunks (docs/03 §3.2, docs/04 §4).

        Each chunk must be consented and redacted before insertion.
        """
        if not chunks_data:
            return []
        project = await self._verify_project_access(ctx, project_id)

        created: list[CodeChunk] = []
        for data in chunks_data:
            chunk = CodeChunk(
                workspace_id=project.workspace_id,
                project_id=project_id,
                file_version_id=data["file_version_id"],
                symbol_id=data.get("symbol_id"),
                kind=data["kind"],
                start_line=data["start_line"],
                end_line=data["end_line"],
                content=data["content"],
                content_hash=data["content_hash"],
                search_text=data["search_text"],
                token_estimate=data["token_estimate"],
                redaction_count=data.get("redaction_count", 0),
                is_current=data.get("is_current", True),
            )
            self.session.add(chunk)
            created.append(chunk)

        await self.session.flush()
        return created

    async def list_chunks(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        file_version_id: UUID | None = None,
        is_current: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CodeChunk]:
        """List code chunks within a project."""
        await self._verify_project_access(ctx, project_id)
        stmt = select(CodeChunk).where(
            CodeChunk.project_id == project_id,
            CodeChunk.is_current == is_current,
        )
        if file_version_id is not None:
            stmt = stmt.where(CodeChunk.file_version_id == file_version_id)

        stmt = stmt.order_by(CodeChunk.file_version_id.asc(), CodeChunk.start_line.asc())
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search_chunks_text(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        query: str,
        limit: int = 20,
    ) -> list[CodeChunk]:
        """Search code chunks within a project matching query text in search_text."""
        await self._verify_project_access(ctx, project_id)
        if not query or not query.strip():
            return []
        clean_query = query.strip()
        stmt = (
            select(CodeChunk)
            .options(selectinload(CodeChunk.file_version).selectinload(FileVersion.file))
            .where(
                CodeChunk.project_id == project_id,
                CodeChunk.is_current.is_(True),
                CodeChunk.search_text.ilike(f"%{clean_query}%"),
            )
            .order_by(CodeChunk.start_line.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def purge_project_chunks(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
    ) -> dict[str, int]:
        """Purge all stored code chunks and associated embeddings for a project (ADR-022 sync mode transition).

        Returns dict with 'code_chunks' and 'embeddings' deleted counts.
        """
        await self._verify_project_access(ctx, project_id)

        # Count embeddings to be deleted
        emb_count_stmt = select(func.count(ChunkEmbedding.chunk_id)).where(
            ChunkEmbedding.project_id == project_id
        )
        emb_count = (await self.session.execute(emb_count_stmt)).scalar() or 0

        # Count chunks to be deleted
        chunk_count_stmt = select(func.count(CodeChunk.id)).where(
            CodeChunk.project_id == project_id
        )
        chunk_count = (await self.session.execute(chunk_count_stmt)).scalar() or 0

        # Delete embeddings directly first
        if emb_count > 0:
            del_emb_stmt = delete(ChunkEmbedding).where(ChunkEmbedding.project_id == project_id)
            await self.session.execute(del_emb_stmt)

        # Delete chunks
        if chunk_count > 0:
            del_chunk_stmt = delete(CodeChunk).where(CodeChunk.project_id == project_id)
            await self.session.execute(del_chunk_stmt)

        await self.session.flush()
        return {"code_chunks": chunk_count, "embeddings": emb_count}

    async def purge_project_data(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        scope: str = "all",
    ) -> dict[str, Any]:
        """Purge data for a project across PostgreSQL, Redis, and LangGraph checkpoints (M9-03, docs/11).

        Returns per-store deletion counts.
        """
        await self._verify_project_access(ctx, project_id)

        # 1. PostgreSQL Purges
        # Code chunks & vector embeddings
        emb_count_stmt = select(func.count(ChunkEmbedding.chunk_id)).where(
            ChunkEmbedding.project_id == project_id
        )
        emb_count = (await self.session.execute(emb_count_stmt)).scalar() or 0
        if emb_count > 0:
            await self.session.execute(
                delete(ChunkEmbedding).where(ChunkEmbedding.project_id == project_id)
            )

        chunk_count_stmt = select(func.count(CodeChunk.id)).where(
            CodeChunk.project_id == project_id
        )
        chunk_count = (await self.session.execute(chunk_count_stmt)).scalar() or 0
        if chunk_count > 0:
            await self.session.execute(delete(CodeChunk).where(CodeChunk.project_id == project_id))

        # Clear consented snippet texts from finding_evidence if full purge
        snippet_count = 0
        if scope == "all":
            finding_ids_stmt = select(Finding.id).where(Finding.project_id == project_id)
            evidence_count_stmt = select(func.count(FindingEvidence.id)).where(
                FindingEvidence.finding_id.in_(finding_ids_stmt),
                FindingEvidence.snippet_text.is_not(None),
            )
            snippet_count = (await self.session.execute(evidence_count_stmt)).scalar() or 0
            if snippet_count > 0:
                await self.session.execute(
                    update(FindingEvidence)
                    .where(
                        FindingEvidence.finding_id.in_(finding_ids_stmt),
                        FindingEvidence.snippet_text.is_not(None),
                    )
                    .values(snippet_text=None)
                )

        # Job events
        job_ids_stmt = select(AnalysisJob.id).where(AnalysisJob.project_id == project_id)
        events_count_stmt = select(func.count(JobEvent.id)).where(JobEvent.job_id.in_(job_ids_stmt))
        events_count = (await self.session.execute(events_count_stmt)).scalar() or 0
        if events_count > 0 and scope == "all":
            await self.session.execute(delete(JobEvent).where(JobEvent.job_id.in_(job_ids_stmt)))

        # 2. Checkpoints (LangGraph thread writes and checkpoints)
        thread_prefix = f"devmind:{project_id}:%"
        threads_count = 0
        try:
            agent_runs_count_stmt = select(func.count(AgentRun.id)).where(
                AgentRun.thread_id.like(thread_prefix)
            )
            threads_count = (await self.session.execute(agent_runs_count_stmt)).scalar() or 0
            if scope == "all":
                await self.session.execute(
                    text("DELETE FROM langgraph.checkpoint_writes WHERE thread_id LIKE :prefix"),
                    {"prefix": thread_prefix},
                )
                await self.session.execute(
                    text("DELETE FROM langgraph.checkpoints WHERE thread_id LIKE :prefix"),
                    {"prefix": thread_prefix},
                )
        except Exception:
            pass

        # 3. Redis Purge
        redis_keys_purged = 0
        try:
            from app.core.redis import get_async_redis_client

            redis_client = get_async_redis_client()
            pattern = f"*{project_id}*"
            keys = []
            async for key in redis_client.scan_iter(match=pattern, count=100):
                keys.append(key)
            if keys:
                redis_keys_purged = await redis_client.delete(*keys)
        except Exception:
            pass

        await self.session.flush()

        return {
            "postgres": {
                "code_chunks": chunk_count,
                "chunk_embeddings": emb_count,
                "evidence_snippets": snippet_count,
                "job_events": events_count if scope == "all" else 0,
            },
            "redis": {
                "cache_keys_purged": redis_keys_purged,
            },
            "checkpoints": {
                "threads_purged": threads_count,
            },
        }

    async def sweep_project_retention(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        cutoffs: dict[str, datetime],
    ) -> dict[str, int]:
        """Sweep expired records for a project based on cutoff timestamps per kind (docs/03 §3.1, docs/07 §9).

        Idempotent and safe to run multiple times. Returns count of purged records per kind.
        """
        await self._verify_project_access(ctx, project_id)
        results: dict[str, int] = {
            "job_events": 0,
            "evidence_snippets": 0,
            "snapshots": 0,
            "checkpoints": 0,
            "agent_runs": 0,
        }

        # 1. Sweep expired JobEvents
        if "job_events" in cutoffs:
            cutoff = cutoffs["job_events"]
            job_ids_stmt = select(AnalysisJob.id).where(AnalysisJob.project_id == project_id)
            del_events_stmt = delete(JobEvent).where(
                JobEvent.job_id.in_(job_ids_stmt),
                JobEvent.created_at < cutoff,
            )
            res = await self.session.execute(del_events_stmt)
            results["job_events"] = res.rowcount or 0

        # 2. Sweep expired evidence snippet text
        if "ephemeral_snippets" in cutoffs or "evidence_snippets" in cutoffs:
            cutoff = cutoffs.get("ephemeral_snippets") or cutoffs.get("evidence_snippets")
            if cutoff:
                finding_ids_stmt = select(Finding.id).where(Finding.project_id == project_id)
                upd_snippets_stmt = (
                    update(FindingEvidence)
                    .where(
                        FindingEvidence.finding_id.in_(finding_ids_stmt),
                        FindingEvidence.snippet_text.is_not(None),
                        FindingEvidence.created_at < cutoff,
                    )
                    .values(snippet_text=None)
                )
                res = await self.session.execute(upd_snippets_stmt)
                results["evidence_snippets"] = res.rowcount or 0

        # 3. Sweep expired snapshot versions (non-current FileVersion older than cutoff)
        if "snapshots" in cutoffs:
            cutoff = cutoffs["snapshots"]
            active_file_version_ids_stmt = select(File.current_version_id).where(
                File.project_id == project_id, File.current_version_id.is_not(None)
            )
            stale_versions_stmt = select(FileVersion.id).where(
                FileVersion.file_id.in_(select(File.id).where(File.project_id == project_id)),
                FileVersion.created_at < cutoff,
                FileVersion.id.not_in(active_file_version_ids_stmt),
            )
            stale_version_ids = (await self.session.execute(stale_versions_stmt)).scalars().all()
            if stale_version_ids:
                stale_chunks_stmt = select(CodeChunk.id).where(
                    CodeChunk.file_version_id.in_(stale_version_ids)
                )
                await self.session.execute(
                    delete(ChunkEmbedding).where(ChunkEmbedding.chunk_id.in_(stale_chunks_stmt))
                )
                del_chunks_res = await self.session.execute(
                    delete(CodeChunk).where(CodeChunk.file_version_id.in_(stale_version_ids))
                )
                del_vers_res = await self.session.execute(
                    delete(FileVersion).where(FileVersion.id.in_(stale_version_ids))
                )
                results["snapshots"] = (del_vers_res.rowcount or 0) + (del_chunks_res.rowcount or 0)

        # 4. Sweep expired agent runs & LangGraph checkpoints
        if "checkpoints" in cutoffs:
            cutoff = cutoffs["checkpoints"]
            del_runs_stmt = delete(AgentRun).where(
                AgentRun.project_id == project_id,
                AgentRun.created_at < cutoff,
            )
            res = await self.session.execute(del_runs_stmt)
            results["agent_runs"] = res.rowcount or 0
            results["checkpoints"] = results["agent_runs"]

        await self.session.flush()
        return results

    async def get_active_embedding_space(
        self,
        ctx: AuthContext | SystemContext,
    ) -> EmbeddingSpace | None:
        """Retrieve the currently active embedding space (docs/04 §10)."""
        self._validate_context(ctx)
        stmt = (
            select(EmbeddingSpace)
            .where(EmbeddingSpace.status == "active")
            .order_by(EmbeddingSpace.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_embedding_space(
        self,
        ctx: AuthContext | SystemContext,
        provider_id: str,
        model_id: str,
        dimension: int,
        status: str = "building",
        config_hash: str = "",
    ) -> EmbeddingSpace:
        """Create a new embedding space record."""
        self._validate_context(ctx)
        space = EmbeddingSpace(
            provider_id=provider_id,
            model_id=model_id,
            dimension=dimension,
            status=status,
            config_hash=config_hash,
        )
        self.session.add(space)
        await self.session.flush()
        return space

    async def set_active_embedding_space(
        self,
        ctx: AuthContext | SystemContext,
        space_id: UUID,
    ) -> EmbeddingSpace:
        """Activate the specified embedding space, deprecating previously active spaces."""
        self._validate_context(ctx)
        stmt_dep = (
            update(EmbeddingSpace)
            .where(EmbeddingSpace.status == "active")
            .values(status="deprecated")
        )
        await self.session.execute(stmt_dep)

        stmt_act = (
            update(EmbeddingSpace).where(EmbeddingSpace.id == space_id).values(status="active")
        )
        await self.session.execute(stmt_act)
        await self.session.flush()

        stmt_get = select(EmbeddingSpace).where(EmbeddingSpace.id == space_id)
        space = (await self.session.execute(stmt_get)).scalars().first()
        if not space:
            raise ValueError(f"Embedding space {space_id} not found")
        return space

    async def get_unembedded_chunks(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        space_id: UUID,
        limit: int = 100,
    ) -> list[CodeChunk]:
        """Retrieve current chunks that need embedding vectors in the target space."""
        await self._verify_project_access(ctx, project_id)
        stmt = (
            select(CodeChunk)
            .outerjoin(
                ChunkEmbedding,
                (ChunkEmbedding.chunk_id == CodeChunk.id) & (ChunkEmbedding.space_id == space_id),
            )
            .where(
                CodeChunk.project_id == project_id,
                CodeChunk.is_current.is_(True),
                ChunkEmbedding.chunk_id.is_(None),
            )
            .order_by(CodeChunk.file_version_id.asc(), CodeChunk.start_line.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def save_chunk_embeddings(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        space_id: UUID,
        embeddings_data: list[tuple[UUID, list[float]]],
    ) -> int:
        """Persist chunk embedding vectors for a project in a specific space."""
        if not embeddings_data:
            return 0
        await self._verify_project_access(ctx, project_id)

        count = 0
        for chunk_id, vector in embeddings_data:
            emb = ChunkEmbedding(
                chunk_id=chunk_id,
                space_id=space_id,
                project_id=project_id,
                embedding=vector,
            )
            self.session.add(emb)
            count += 1

        await self.session.flush()
        return count

    async def search_chunks_vector(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        space_id: UUID,
        query_vector: list[float],
        limit: int = 20,
        is_current: bool = True,
    ) -> list[tuple[CodeChunk, float]]:
        """Perform similarity search on chunk embeddings using cosine distance (<=>).

        Returns list of (CodeChunk, cosine_similarity) tuples ordered by similarity descending.
        """
        await self._verify_project_access(ctx, project_id)
        if not query_vector:
            return []

        dist_expr = ChunkEmbedding.embedding.cosine_distance(query_vector).label("distance")
        stmt = (
            select(CodeChunk, dist_expr)
            .options(selectinload(CodeChunk.file_version).selectinload(FileVersion.file))
            .join(ChunkEmbedding, ChunkEmbedding.chunk_id == CodeChunk.id)
            .where(
                ChunkEmbedding.project_id == project_id,
                ChunkEmbedding.space_id == space_id,
                CodeChunk.is_current == is_current,
            )
            .order_by(dist_expr.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        # Convert cosine distance to similarity: similarity = 1.0 - distance
        return [(row[0], round(1.0 - float(row[1]), 4)) for row in rows]

    async def resolve_relationships(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
    ) -> int:
        """Attempt to resolve unresolved relationships where to_external matches an active symbol."""
        await self._verify_project_access(ctx, project_id)

        stmt = select(CodeRelationship).where(
            CodeRelationship.project_id == project_id,
            CodeRelationship.to_symbol_id.is_(None),
            CodeRelationship.to_external.isnot(None),
            CodeRelationship.is_current.is_(True),
        )
        rels = list((await self.session.execute(stmt)).scalars().all())
        if not rels:
            return 0

        target_names = [r.to_external for r in rels if r.to_external]
        if not target_names:
            return 0

        sym_stmt = select(CodeSymbol).where(
            CodeSymbol.project_id == project_id,
            CodeSymbol.is_current.is_(True),
            (
                CodeSymbol.symbol_key.in_(target_names)
                | CodeSymbol.qualified_name.in_(target_names)
                | CodeSymbol.name.in_(target_names)
            ),
        )
        target_symbols = list((await self.session.execute(sym_stmt)).scalars().all())

        sym_by_key = {s.symbol_key: s for s in target_symbols}
        sym_by_qname = {s.qualified_name: s for s in target_symbols}
        sym_by_name = {s.name: s for s in target_symbols}

        resolved_count = 0
        for rel in rels:
            matched = (
                sym_by_key.get(rel.to_external)
                or sym_by_qname.get(rel.to_external)
                or sym_by_name.get(rel.to_external)
            )
            if matched:
                rel.to_symbol_id = matched.id
                rel.resolution = "resolved"
                resolved_count += 1

        if resolved_count > 0:
            await self.session.flush()

        return resolved_count

    async def get_graph_data(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        root_symbol_key: str | None = None,
        depth: int = 2,
        limit: int = 200,
    ) -> tuple[list[CodeSymbol], list[CodeRelationship]]:
        """Retrieve architectural graph nodes and edges for visualization and derivation."""
        await self._verify_project_access(ctx, project_id)

        if root_symbol_key is None:
            symbols = await self.list_current_symbols(ctx, project_id, limit=limit)
            symbol_ids = {s.id for s in symbols}
            if not symbol_ids:
                return [], []

            stmt_edges = select(CodeRelationship).where(
                CodeRelationship.project_id == project_id,
                CodeRelationship.is_current.is_(True),
                CodeRelationship.from_symbol_id.in_(symbol_ids),
            )
            edges = list((await self.session.execute(stmt_edges)).scalars().all())
            return symbols, edges

        stmt_root = select(CodeSymbol).where(
            CodeSymbol.project_id == project_id,
            CodeSymbol.symbol_key == root_symbol_key,
            CodeSymbol.is_current.is_(True),
        )
        root = (await self.session.execute(stmt_root)).scalars().first()
        if not root:
            return [], []

        visited_symbol_ids: set[UUID] = {root.id}
        collected_symbols: dict[UUID, CodeSymbol] = {root.id: root}
        collected_edges: list[CodeRelationship] = []
        current_layer_ids: set[UUID] = {root.id}

        for _ in range(depth):
            if not current_layer_ids:
                break

            stmt_rels = select(CodeRelationship).where(
                CodeRelationship.project_id == project_id,
                CodeRelationship.is_current.is_(True),
                (
                    CodeRelationship.from_symbol_id.in_(current_layer_ids)
                    | CodeRelationship.to_symbol_id.in_(current_layer_ids)
                ),
            )
            layer_rels = list((await self.session.execute(stmt_rels)).scalars().all())

            next_layer_ids: set[UUID] = set()
            for r in layer_rels:
                collected_edges.append(r)
                if r.from_symbol_id not in visited_symbol_ids:
                    next_layer_ids.add(r.from_symbol_id)
                if r.to_symbol_id and r.to_symbol_id not in visited_symbol_ids:
                    next_layer_ids.add(r.to_symbol_id)

            if next_layer_ids:
                syms_stmt = select(CodeSymbol).where(
                    CodeSymbol.id.in_(next_layer_ids),
                    CodeSymbol.project_id == project_id,
                )
                found_syms = list((await self.session.execute(syms_stmt)).scalars().all())
                for s in found_syms:
                    collected_symbols[s.id] = s
                    visited_symbol_ids.add(s.id)

            current_layer_ids = next_layer_ids

        unique_edges = {e.id: e for e in collected_edges}
        return list(collected_symbols.values()), list(unique_edges.values())

    # --- Analysis Jobs and Job Events ---

    async def create_job(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        job_type: str,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        requested_by: UUID | None = None,
        queue: str = "default",
    ) -> AnalysisJob:
        """Create or return an idempotent background analysis job."""
        await self._verify_project_access(ctx, project_id)

        if idempotency_key:
            stmt = select(AnalysisJob).where(
                AnalysisJob.project_id == project_id,
                AnalysisJob.idempotency_key == idempotency_key,
            )
            result = await self.session.execute(stmt)
            existing = result.scalars().first()
            if existing:
                return existing

        job = AnalysisJob(
            project_id=project_id,
            type=job_type,
            status="queued",
            requested_by=requested_by,
            params=params or {},
            idempotency_key=idempotency_key,
            queue=queue,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_job(
        self, ctx: AuthContext | SystemContext, project_id: UUID, job_id: UUID
    ) -> AnalysisJob | None:
        """Get an analysis job by ID."""
        await self._verify_project_access(ctx, project_id)
        stmt = select(AnalysisJob).where(
            AnalysisJob.id == job_id,
            AnalysisJob.project_id == project_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_job_by_id(
        self, ctx: AuthContext | SystemContext, job_id: UUID
    ) -> AnalysisJob | None:
        """Get an analysis job by ID, verifying access to its parent project."""
        self._validate_context(ctx)
        stmt = select(AnalysisJob).where(AnalysisJob.id == job_id)
        result = await self.session.execute(stmt)
        job = result.scalars().first()
        if not job:
            return None
        await self._verify_project_access(ctx, job.project_id)
        return job

    async def list_jobs(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AnalysisJob]:
        """List background jobs for a project."""
        await self._verify_project_access(ctx, project_id)
        stmt = select(AnalysisJob).where(AnalysisJob.project_id == project_id)
        if status:
            stmt = stmt.where(AnalysisJob.status == status)
        stmt = stmt.order_by(AnalysisJob.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_job_events(
        self,
        ctx: AuthContext | SystemContext,
        job_id: UUID,
        since_seq: int = 0,
    ) -> list[JobEvent]:
        """Get milestone events for an analysis job since sequence number."""
        job = await self.get_job_by_id(ctx, job_id)
        if not job:
            return []
        stmt = (
            select(JobEvent)
            .where(
                JobEvent.job_id == job_id,
                JobEvent.seq > since_seq,
            )
            .order_by(JobEvent.seq.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def record_job_event(
        self,
        ctx: AuthContext | SystemContext,
        job_id: UUID,
        kind: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> JobEvent:
        """Append milestone event to job log."""
        self._validate_context(ctx)

        # Get next seq
        stmt = select(func.coalesce(func.max(JobEvent.seq), 0)).where(JobEvent.job_id == job_id)
        res = await self.session.execute(stmt)
        current_max = res.scalar_one()

        event = JobEvent(
            job_id=job_id,
            seq=current_max + 1,
            kind=kind,
            message=message,
            data=data or {},
        )
        self.session.add(event)
        await self.session.flush()
        return event

    # --- Findings and Lifecycle ---

    async def batch_upsert_findings(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        findings_data: list[dict[str, Any]],
    ) -> list[Finding]:
        """Upsert findings with fingerprint deduplication (docs/03 §3.4, §5.1)."""
        if not findings_data:
            return []
        await self._verify_project_access(ctx, project_id)

        persisted: list[Finding] = []
        for data in findings_data:
            fingerprint = data["fingerprint"]
            stmt = select(Finding).where(
                Finding.project_id == project_id,
                Finding.fingerprint == fingerprint,
            )
            res = await self.session.execute(stmt)
            existing = res.scalars().first()

            if existing:
                # Update last seen scan run and primary location if provided
                if "last_seen_scan_run_id" in data:
                    existing.last_seen_scan_run_id = data["last_seen_scan_run_id"]
                if "title" in data:
                    existing.title = data["title"]
                if "summary" in data:
                    existing.summary = data["summary"]
                if "explanation" in data:
                    existing.explanation = data["explanation"]
                if existing.status == "stale":
                    # Finding re-verified
                    existing.status = "open"
                persisted.append(existing)
            else:
                new_finding = Finding(
                    project_id=project_id,
                    fingerprint=fingerprint,
                    rule_id=data["rule_id"],
                    source=data.get("source", "scanner"),
                    category=data["category"],
                    title=data["title"],
                    summary=data["summary"],
                    explanation=data.get("explanation"),
                    severity=data["severity"],
                    confidence=data.get("confidence", "medium"),
                    evidence_level=data.get("evidence_level", "E1"),
                    status=data.get("status", "open"),
                    first_seen_scan_run_id=data.get("first_seen_scan_run_id"),
                    last_seen_scan_run_id=data.get("last_seen_scan_run_id"),
                    primary_file_id=data.get("primary_file_id"),
                    primary_start_line=data.get("primary_start_line"),
                    primary_end_line=data.get("primary_end_line"),
                    suggested_fix=data.get("suggested_fix"),
                )
                self.session.add(new_finding)
                persisted.append(new_finding)

        await self.session.flush()
        return persisted

    async def get_finding(
        self, ctx: AuthContext | SystemContext, project_id: UUID, finding_id: UUID
    ) -> Finding | None:
        """Get finding by ID."""
        await self._verify_project_access(ctx, project_id)
        stmt = select(Finding).where(
            Finding.id == finding_id,
            Finding.project_id == project_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_findings(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> list[Finding]:
        """List findings for a project filtered by status and severity."""
        await self._verify_project_access(ctx, project_id)
        stmt = (
            select(Finding)
            .where(Finding.project_id == project_id)
            .order_by(Finding.created_at.desc())
            .limit(limit)
        )
        if status:
            stmt = stmt.where(Finding.status == status)
        if severity:
            stmt = stmt.where(Finding.severity == severity)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_finding_status(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        finding_id: UUID,
        to_status: str,
        actor_kind: str = "system",
        actor_id: UUID | None = None,
        reason: str | None = None,
    ) -> Finding | None:
        """Transition finding status and record immutable history (docs/03 §5.1)."""
        finding = await self.get_finding(ctx, project_id, finding_id)
        if not finding:
            return None

        from_status = finding.status
        finding.status = to_status
        if to_status == "resolved":
            finding.resolved_at = datetime.now(UTC)
        if reason:
            finding.status_reason = reason

        history = FindingStatusHistory(
            finding_id=finding.id,
            from_status=from_status,
            to_status=to_status,
            actor_kind=actor_kind,
            actor_id=actor_id,
            reason=reason,
        )
        self.session.add(history)
        await self.session.flush()
        return finding

    async def record_finding_evidence(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        finding_id: UUID,
        path: str,
        start_line: int,
        end_line: int,
        snippet_hash: str,
        file_version_id: UUID | None = None,
        snippet_text: str | None = None,
        role: str = "primary",
        detail: dict[str, Any] | None = None,
    ) -> FindingEvidence:
        """Record machine-checkable evidence item for a finding (docs/03 §3.4)."""
        await self._verify_project_access(ctx, project_id)

        evidence = FindingEvidence(
            finding_id=finding_id,
            project_id=project_id,
            file_version_id=file_version_id,
            path=path,
            start_line=start_line,
            end_line=end_line,
            snippet_hash=snippet_hash,
            snippet_text=snippet_text,
            role=role,
            detail=detail or {},
        )
        self.session.add(evidence)
        await self.session.flush()
        return evidence

    async def mark_findings_stale_for_files(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        paths: list[str],
    ) -> int:
        """Mark active findings stale when their primary file or evidence files are changed or removed (docs/03 §5.1 rule 3)."""
        if not paths:
            return 0
        await self._verify_project_access(ctx, project_id)

        # 1. Look up file_ids for the specified paths
        file_stmt = select(ProjectFile.id).where(
            ProjectFile.project_id == project_id,
            ProjectFile.path.in_(paths),
        )
        file_ids = list((await self.session.execute(file_stmt)).scalars().all())

        # 2. Find active findings where primary_file_id is in file_ids OR evidence path is in paths
        ev_subquery = select(FindingEvidence.finding_id).where(
            FindingEvidence.project_id == project_id,
            FindingEvidence.path.in_(paths),
        )

        active_statuses = ["open", "acknowledged", "in_progress", "fix_proposed"]
        clauses = []
        if file_ids:
            clauses.append(Finding.primary_file_id.in_(file_ids))
        clauses.append(Finding.id.in_(ev_subquery))

        from sqlalchemy import or_

        finding_stmt = select(Finding).where(
            Finding.project_id == project_id,
            Finding.status.in_(active_statuses),
            or_(*clauses),
        )
        findings_to_stale = list((await self.session.execute(finding_stmt)).scalars().all())

        # Mark matching evidence records as non-current
        ev_update_stmt = (
            update(FindingEvidence)
            .where(
                FindingEvidence.project_id == project_id,
                FindingEvidence.path.in_(paths),
                FindingEvidence.is_current.is_(True),
            )
            .values(is_current=False)
        )
        await self.session.execute(ev_update_stmt)

        if not findings_to_stale:
            await self.session.flush()
            return 0

        for f in findings_to_stale:
            prev_status = f.status
            f.status = "stale"
            history = FindingStatusHistory(
                id=generate_uuid7(),
                finding_id=f.id,
                from_status=prev_status,
                to_status="stale",
                actor_kind="system",
                reason="evidence file modified or removed",
            )
            self.session.add(history)

        await self.session.flush()
        return len(findings_to_stale)

    async def resolve_stale_findings_for_files(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        scanned_paths: list[str],
        detected_fingerprints: set[str],
        scan_run_id: UUID | None = None,
    ) -> int:
        """Resolve stale findings on scanned files when re-verification confirms the issue is gone (docs/03 §5.1 rule 1)."""
        if not scanned_paths:
            return 0
        await self._verify_project_access(ctx, project_id)

        file_stmt = select(ProjectFile.id).where(
            ProjectFile.project_id == project_id,
            ProjectFile.path.in_(scanned_paths),
        )
        file_ids = list((await self.session.execute(file_stmt)).scalars().all())

        ev_subquery = select(FindingEvidence.finding_id).where(
            FindingEvidence.project_id == project_id,
            FindingEvidence.path.in_(scanned_paths),
        )

        clauses = []
        if file_ids:
            clauses.append(Finding.primary_file_id.in_(file_ids))
        clauses.append(Finding.id.in_(ev_subquery))

        from sqlalchemy import or_

        stmt = select(Finding).where(
            Finding.project_id == project_id,
            Finding.status == "stale",
            or_(*clauses),
        )
        if detected_fingerprints:
            stmt = stmt.where(Finding.fingerprint.notin_(list(detected_fingerprints)))

        stale_findings = list((await self.session.execute(stmt)).scalars().all())
        now = datetime.now(UTC)
        for f in stale_findings:
            f.status = "resolved"
            f.resolved_at = now
            if scan_run_id:
                f.last_seen_scan_run_id = scan_run_id
            f.status_reason = "re-verification: no longer detected in scan"
            history = FindingStatusHistory(
                id=generate_uuid7(),
                finding_id=f.id,
                from_status="stale",
                to_status="resolved",
                actor_kind="system",
                reason="re-verification: no longer detected in scan",
            )
            self.session.add(history)

        if stale_findings:
            await self.session.flush()

        return len(stale_findings)

    async def get_brain_summary_stats(
        self, ctx: AuthContext | SystemContext, project_id: UUID
    ) -> dict[str, Any]:
        """Aggregate summary counts and metrics for the project brain."""
        await self._verify_project_access(ctx, project_id)

        # 1. Active files count and language distribution
        files_stmt = (
            select(ProjectFile.language, func.count(ProjectFile.id))
            .where(
                ProjectFile.project_id == project_id,
                ProjectFile.removed_at.is_(None),
            )
            .group_by(ProjectFile.language)
        )
        lang_rows = (await self.session.execute(files_stmt)).all()
        languages: dict[str, int] = {str(row[0]): int(row[1]) for row in lang_rows}
        total_files = sum(languages.values())

        # 2. File versions count
        ver_stmt = (
            select(func.count(FileVersion.id))
            .join(ProjectFile, FileVersion.file_id == ProjectFile.id)
            .where(ProjectFile.project_id == project_id)
        )
        total_versions = int((await self.session.execute(ver_stmt)).scalar() or 0)

        # 3. Snapshots count
        snap_stmt = select(func.count(ProjectSnapshot.id)).where(
            ProjectSnapshot.project_id == project_id
        )
        total_snapshots = int((await self.session.execute(snap_stmt)).scalar() or 0)

        # 4. Current Symbols count
        sym_stmt = select(func.count(CodeSymbol.id)).where(
            CodeSymbol.project_id == project_id,
            CodeSymbol.is_current.is_(True),
        )
        total_symbols = int((await self.session.execute(sym_stmt)).scalar() or 0)

        # 5. Current Relationships count
        rel_stmt = select(func.count(CodeRelationship.id)).where(
            CodeRelationship.project_id == project_id,
            CodeRelationship.is_current.is_(True),
        )
        total_relationships = int((await self.session.execute(rel_stmt)).scalar() or 0)

        # 6. Current Chunks count
        chunk_stmt = select(func.count(CodeChunk.id)).where(
            CodeChunk.project_id == project_id,
            CodeChunk.is_current.is_(True),
        )
        total_chunks = int((await self.session.execute(chunk_stmt)).scalar() or 0)

        # 7. Findings summary by status
        find_stmt = (
            select(Finding.status, func.count(Finding.id))
            .where(Finding.project_id == project_id)
            .group_by(Finding.status)
        )
        find_rows = (await self.session.execute(find_stmt)).all()
        findings_summary: dict[str, int] = {str(row[0]): int(row[1]) for row in find_rows}

        # 8. Latest snapshot and latest scan run
        latest_snapshot = await self.get_latest_snapshot(ctx, project_id)
        latest_scan = await self.get_latest_scan_run(ctx, project_id)

        return {
            "project_id": project_id,
            "total_files": total_files,
            "languages": languages,
            "total_versions": total_versions,
            "total_snapshots": total_snapshots,
            "total_symbols": total_symbols,
            "total_relationships": total_relationships,
            "total_chunks": total_chunks,
            "findings_summary": findings_summary,
            "latest_snapshot": latest_snapshot,
            "latest_scan": latest_scan,
        }
