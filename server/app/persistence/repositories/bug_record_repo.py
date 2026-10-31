"""Bug Record and Resolution repository for Bug Memory (docs/01 CAP-03, docs/03 §3.4)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.analysis.error_normalizer import ErrorNormalizer, NormalizedError
from app.core.auth_context import AuthContext, SystemContext
from app.persistence.models.bug_memory import BugRecord, BugResolution
from app.persistence.repositories.base import BaseRepository


class BugRecordRepository(BaseRepository):
    """Repository managing BugRecord and BugResolution persistence with tenant scoping."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def record_bug(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        project_id: UUID,
        raw_error: str,
        title: str | None = None,
        summary: str | None = None,
        module_hint: str | None = None,
    ) -> tuple[BugRecord, bool]:
        """Normalize an error trace and upsert a BugRecord.

        Returns:
            Tuple of (BugRecord, is_new).
        """
        self._validate_context(ctx)
        self._scope_workspace_query(
            select(BugRecord),
            BugRecord.workspace_id,
            ctx,
            target_workspace_id=workspace_id,
        )

        norm: NormalizedError = ErrorNormalizer.normalize(raw_error)
        chosen_module = module_hint or norm.module_hint
        chosen_title = title or f"{norm.exception_type}: {norm.clean_message[:60]}"

        # Look up existing record by (project_id, fingerprint)
        stmt = (
            select(BugRecord)
            .where(
                BugRecord.workspace_id == workspace_id,
                BugRecord.project_id == project_id,
                BugRecord.fingerprint == norm.fingerprint,
            )
            .options(selectinload(BugRecord.resolutions))
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()

        now = datetime.now(UTC)
        if existing is not None:
            existing.occurrence_count += 1
            existing.last_seen_at = now
            if not existing.raw_error and norm.raw_preview:
                existing.raw_error = norm.raw_preview
            if summary and not existing.summary:
                existing.summary = summary
            if chosen_module and not existing.module_hint:
                existing.module_hint = chosen_module
            await self.session.flush()
            return existing, False

        new_record = BugRecord(
            workspace_id=workspace_id,
            project_id=project_id,
            fingerprint=norm.fingerprint,
            error_signature=norm.normalized_signature,
            title=chosen_title[:255],
            summary=summary,
            module_hint=chosen_module[:255] if chosen_module else None,
            raw_error=norm.raw_preview,
            occurrence_count=1,
            first_seen_at=now,
            last_seen_at=now,
        )
        self.session.add(new_record)
        await self.session.flush()
        return new_record, True

    async def get_by_id(
        self,
        ctx: AuthContext | SystemContext,
        bug_record_id: UUID,
    ) -> BugRecord | None:
        """Retrieve a bug record by ID within authorized workspace."""
        self._validate_context(ctx)
        stmt = select(BugRecord).where(BugRecord.id == bug_record_id)
        stmt = self._scope_workspace_query(stmt, BugRecord.workspace_id, ctx)
        stmt = stmt.options(selectinload(BugRecord.resolutions))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_fingerprint(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        fingerprint: str,
    ) -> BugRecord | None:
        """Find a bug record by fingerprint within authorized workspace/project."""
        self._validate_context(ctx)
        stmt = select(BugRecord).where(
            BugRecord.project_id == project_id,
            BugRecord.fingerprint == fingerprint,
        )
        stmt = self._scope_workspace_query(stmt, BugRecord.workspace_id, ctx)
        stmt = stmt.options(selectinload(BugRecord.resolutions))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_by_project(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        *,
        module_hint: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BugRecord]:
        """List bug records for a project ordered by most recent occurrence."""
        self._validate_context(ctx)
        stmt = select(BugRecord).where(BugRecord.project_id == project_id)
        stmt = self._scope_workspace_query(stmt, BugRecord.workspace_id, ctx)

        if module_hint:
            stmt = stmt.where(BugRecord.module_hint == module_hint)

        stmt = (
            stmt.order_by(BugRecord.last_seen_at.desc())
            .limit(limit)
            .offset(offset)
            .options(selectinload(BugRecord.resolutions))
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def add_resolution(
        self,
        ctx: AuthContext | SystemContext,
        *,
        bug_record_id: UUID,
        cause: str,
        fix_summary: str,
        files: list[dict[str, Any]] | None = None,
        finding_id: UUID | None = None,
        resolved_by: UUID | None = None,
    ) -> BugResolution:
        """Attach a resolution record to an existing BugRecord."""
        self._validate_context(ctx)
        # Ensure the bug record exists and is accessible
        record = await self.get_by_id(ctx, bug_record_id)
        if record is None:
            raise ValueError(f"BugRecord {bug_record_id} not found or inaccessible")

        resolution = BugResolution(
            bug_record_id=bug_record_id,
            cause=cause.strip(),
            fix_summary=fix_summary.strip(),
            files=files or [],
            finding_id=finding_id,
            resolved_by=resolved_by,
        )
        self.session.add(resolution)
        await self.session.flush()
        return resolution

    async def list_resolutions_by_bug(
        self,
        ctx: AuthContext | SystemContext,
        bug_record_id: UUID,
    ) -> list[BugResolution]:
        """List all documented resolutions for a bug record."""
        self._validate_context(ctx)
        record = await self.get_by_id(ctx, bug_record_id)
        if record is None:
            return []

        stmt = (
            select(BugResolution)
            .where(BugResolution.bug_record_id == bug_record_id)
            .order_by(BugResolution.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def delete_bug_record(
        self,
        ctx: AuthContext | SystemContext,
        bug_record_id: UUID,
    ) -> bool:
        """Delete a bug record and its resolutions."""
        self._validate_context(ctx)
        record = await self.get_by_id(ctx, bug_record_id)
        if record is None:
            return False

        await self.session.delete(record)
        await self.session.flush()
        return True
