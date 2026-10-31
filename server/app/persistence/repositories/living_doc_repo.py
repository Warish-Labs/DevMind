"""Repository for Living Documentation records and doc drift persistence (docs/01 CAP-04, docs/03 §3.4)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth_context import AuthContext, SystemContext
from app.core.ids import generate_uuid7
from app.persistence.models.living_documentation import DocDriftItem, DocumentationRecord
from app.persistence.repositories.base import BaseRepository


class LivingDocRepository(BaseRepository):
    """Repository managing DocumentationRecord and DocDriftItem persistence with tenant boundaries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def upsert_document_record(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        project_id: UUID,
        path: str,
        title: str,
        kind: str = "other",
        current_version_hash: str,
        content_snapshot: str | None = None,
        extracted_symbols: list[dict[str, Any]] | None = None,
        file_id: UUID | None = None,
    ) -> tuple[DocumentationRecord, bool]:
        """Insert or update a tracked documentation record for a project file.

        Returns:
            Tuple of (DocumentationRecord, is_new).
        """
        self._validate_context(ctx)
        self._scope_workspace_query(
            select(DocumentationRecord),
            DocumentationRecord.workspace_id,
            ctx,
            target_workspace_id=workspace_id,
        )

        stmt = (
            select(DocumentationRecord)
            .where(
                DocumentationRecord.workspace_id == workspace_id,
                DocumentationRecord.project_id == project_id,
                DocumentationRecord.path == path,
            )
            .options(selectinload(DocumentationRecord.drift_items))
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()

        now = datetime.now(UTC)
        if existing is not None:
            existing.title = title
            existing.kind = kind
            existing.current_version_hash = current_version_hash
            existing.content_snapshot = content_snapshot
            existing.extracted_symbols = extracted_symbols or []
            existing.last_parsed_at = now
            if file_id:
                existing.file_id = file_id
            await self.session.flush()
            return existing, False

        new_record = DocumentationRecord(
            id=generate_uuid7(),
            workspace_id=workspace_id,
            project_id=project_id,
            file_id=file_id,
            path=path,
            title=title,
            kind=kind,
            current_version_hash=current_version_hash,
            content_snapshot=content_snapshot,
            extracted_symbols=extracted_symbols or [],
            last_parsed_at=now,
            created_at=now,
            updated_at=now,
        )
        self.session.add(new_record)
        await self.session.flush()
        return new_record, True

    async def get_document_by_id(
        self,
        ctx: AuthContext | SystemContext,
        doc_id: UUID,
    ) -> DocumentationRecord | None:
        """Find a documentation record by ID scoped to caller workspace."""
        self._validate_context(ctx)
        stmt = select(DocumentationRecord).where(DocumentationRecord.id == doc_id)
        stmt = self._scope_workspace_query(stmt, DocumentationRecord.workspace_id, ctx)
        stmt = stmt.options(selectinload(DocumentationRecord.drift_items))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_document_by_path(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        path: str,
    ) -> DocumentationRecord | None:
        """Find a documentation record by relative file path within authorized project."""
        self._validate_context(ctx)
        stmt = select(DocumentationRecord).where(
            DocumentationRecord.project_id == project_id,
            DocumentationRecord.path == path,
        )
        stmt = self._scope_workspace_query(stmt, DocumentationRecord.workspace_id, ctx)
        stmt = stmt.options(selectinload(DocumentationRecord.drift_items))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_documents_by_project(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        *,
        kind: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DocumentationRecord]:
        """List documentation records tracked in a project."""
        self._validate_context(ctx)
        stmt = select(DocumentationRecord).where(DocumentationRecord.project_id == project_id)
        stmt = self._scope_workspace_query(stmt, DocumentationRecord.workspace_id, ctx)

        if kind:
            stmt = stmt.where(DocumentationRecord.kind == kind)

        stmt = (
            stmt.order_by(DocumentationRecord.path.asc())
            .limit(limit)
            .offset(offset)
            .options(selectinload(DocumentationRecord.drift_items))
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def record_drift_item(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        project_id: UUID,
        documentation_record_id: UUID,
        kind: str,
        explanation: str,
        target_symbol_key: str | None = None,
        target_route_path: str | None = None,
        proposal: dict[str, Any] | None = None,
    ) -> DocDriftItem:
        """Create a new drift item associated with a documentation record."""
        self._validate_context(ctx)
        doc = await self.get_document_by_id(ctx, documentation_record_id)
        if doc is None:
            raise ValueError(
                f"DocumentationRecord {documentation_record_id} not found or inaccessible"
            )

        now = datetime.now(UTC)
        drift = DocDriftItem(
            id=generate_uuid7(),
            workspace_id=workspace_id,
            project_id=project_id,
            documentation_record_id=documentation_record_id,
            kind=kind,
            target_symbol_key=target_symbol_key,
            target_route_path=target_route_path,
            explanation=explanation.strip(),
            status="detected",
            proposal=proposal,
            created_at=now,
            updated_at=now,
        )
        self.session.add(drift)
        await self.session.flush()
        return drift

    async def list_drift_items_by_project(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        *,
        status: str | None = None,
        kind: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DocDriftItem]:
        """List drift items for a project filtered by status or kind."""
        self._validate_context(ctx)
        stmt = select(DocDriftItem).where(DocDriftItem.project_id == project_id)
        stmt = self._scope_workspace_query(stmt, DocDriftItem.workspace_id, ctx)

        if status:
            stmt = stmt.where(DocDriftItem.status == status)
        if kind:
            stmt = stmt.where(DocDriftItem.kind == kind)

        stmt = stmt.order_by(DocDriftItem.created_at.desc()).limit(limit).offset(offset)
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_drift_item_by_id(
        self,
        ctx: AuthContext | SystemContext,
        drift_id: UUID,
    ) -> DocDriftItem | None:
        """Find a drift item by ID scoped to caller workspace."""
        self._validate_context(ctx)
        stmt = select(DocDriftItem).where(DocDriftItem.id == drift_id)
        stmt = self._scope_workspace_query(stmt, DocDriftItem.workspace_id, ctx)
        stmt = stmt.options(selectinload(DocDriftItem.documentation_record))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def update_drift_status(
        self,
        ctx: AuthContext | SystemContext,
        *,
        drift_id: UUID,
        status: str,
        proposal: dict[str, Any] | None = None,
    ) -> DocDriftItem | None:
        """Update drift status (detected, patch_proposed, resolved, dismissed)."""
        self._validate_context(ctx)
        drift = await self.get_drift_item_by_id(ctx, drift_id)
        if drift is None:
            return None

        drift.status = status
        if proposal is not None:
            drift.proposal = proposal
        drift.updated_at = datetime.now(UTC)
        await self.session.flush()
        return drift

    async def delete_document_record(
        self,
        ctx: AuthContext | SystemContext,
        doc_id: UUID,
    ) -> bool:
        """Delete a documentation record and its cascading drift items."""
        self._validate_context(ctx)
        doc = await self.get_document_by_id(ctx, doc_id)
        if doc is None:
            return False

        await self.session.delete(doc)
        await self.session.flush()
        return True
