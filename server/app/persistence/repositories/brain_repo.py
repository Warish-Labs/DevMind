"""Brain repository managing files, versions, snapshots, symbols, relationships, jobs, and findings (docs/03 §3.2-§3.4, docs/03 §4)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth_context import AuthContext, SystemContext
from app.persistence.models.brain import (
    AnalysisJob,
    CodeRelationship,
    CodeSymbol,
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
