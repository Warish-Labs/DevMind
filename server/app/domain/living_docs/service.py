"""Domain service coordinating Living Documentation tracking, DocsAlive drift detection, and gated patch approval (docs/01 CAP-04, docs/03 §3.4)."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.doc_parser import DocParser
from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import NotFoundError
from app.domain.living_docs.schemas import (
    DocDriftDetectRequest,
    DocDriftDetectResponse,
    DocDriftItemResponse,
    DocRecordCreate,
    DocRecordDetailResponse,
    DocRecordResponse,
    DriftActionResponse,
    DriftApprovalRequest,
    PatchProposalResponse,
)
from app.llm.router import LLMGatewayRouter
from app.orchestration.docsalive import DocsAliveAgent
from app.persistence.models.living_documentation import DocDriftItem, DocumentationRecord
from app.persistence.repositories.living_doc_repo import LivingDocRepository
from app.persistence.repositories.project_repo import ProjectRepository

logger = logging.getLogger(__name__)


def _to_doc_record_response(record: DocumentationRecord) -> DocRecordResponse:
    now = datetime.now(UTC)
    return DocRecordResponse(
        id=record.id,
        workspace_id=record.workspace_id,
        project_id=record.project_id,
        file_id=record.file_id,
        path=record.path,
        title=record.title,
        kind=record.kind,
        current_version_hash=record.current_version_hash,
        last_parsed_at=record.last_parsed_at or now,
        created_at=record.created_at or now,
        updated_at=record.updated_at or now,
    )


def _to_doc_record_detail(record: DocumentationRecord) -> DocRecordDetailResponse:
    now = datetime.now(UTC)
    return DocRecordDetailResponse(
        id=record.id,
        workspace_id=record.workspace_id,
        project_id=record.project_id,
        file_id=record.file_id,
        path=record.path,
        title=record.title,
        kind=record.kind,
        current_version_hash=record.current_version_hash,
        content_snapshot=record.content_snapshot,
        extracted_symbols=record.extracted_symbols or [],
        drift_item_count=len(record.drift_items) if record.drift_items is not None else 0,
        last_parsed_at=record.last_parsed_at or now,
        created_at=record.created_at or now,
        updated_at=record.updated_at or now,
    )


def _to_drift_item_response(item: DocDriftItem) -> DocDriftItemResponse:
    proposal_resp = None
    if item.proposal:
        proposal_resp = PatchProposalResponse(
            summary=item.proposal.get("summary", ""),
            drift_kind=item.proposal.get("drift_kind", item.kind),
            target_section=item.proposal.get("target_section"),
            proposed_content=item.proposal.get("proposed_content", ""),
            diff_content=item.proposal.get("diff_content"),
            gated=item.proposal.get("gated", True),
            confidence=item.proposal.get("confidence", 0.85),
            notes=item.proposal.get("notes", []),
            decided_by=item.proposal.get("decided_by"),
            decided_at=item.proposal.get("decided_at"),
            rejection_reason=item.proposal.get("rejection_reason"),
            applied_at=item.proposal.get("applied_at"),
        )

    return DocDriftItemResponse(
        id=item.id,
        workspace_id=item.workspace_id,
        project_id=item.project_id,
        documentation_record_id=item.documentation_record_id,
        kind=item.kind,
        target_symbol_key=item.target_symbol_key,
        target_route_path=item.target_route_path,
        explanation=item.explanation,
        status=item.status,
        proposal=proposal_resp,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


class LivingDocService:
    """Coordinates documentation tracking, drift detection, and human-in-the-loop patch management."""

    def __init__(
        self,
        session: AsyncSession,
        router: LLMGatewayRouter | None = None,
    ) -> None:
        self.session = session
        self.repo = LivingDocRepository(session)
        self.project_repo = ProjectRepository(session)
        self.agent = DocsAliveAgent(session=session, router=router)

    async def list_documents(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        kind: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DocRecordResponse]:
        """List tracked documentation records for a project."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if not project:
            raise NotFoundError(detail=f"Project {project_id} not found")

        records = await self.repo.list_documents_by_project(
            ctx=ctx,
            project_id=project_id,
            kind=kind,
            limit=limit,
            offset=offset,
        )
        return [_to_doc_record_response(r) for r in records]

    async def get_document(
        self,
        ctx: AuthContext | SystemContext,
        doc_id: UUID,
    ) -> DocRecordDetailResponse:
        """Get detail of a documentation record including cached content and symbol mentions."""
        record = await self.repo.get_document_by_id(ctx, doc_id)
        if not record:
            raise NotFoundError(detail=f"Documentation record {doc_id} not found")
        return _to_doc_record_detail(record)

    async def register_document(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        data: DocRecordCreate,
    ) -> DocRecordDetailResponse:
        """Register or update a documentation record and extract symbols deterministically."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if not project:
            raise NotFoundError(detail=f"Project {project_id} not found")

        # 1. Deterministic parsing
        parsed = DocParser.parse(data.content, data.path)
        extracted_symbols = parsed.to_extracted_symbols_json()

        # 2. Content hashing
        content_hash = hashlib.sha256(data.content.encode("utf-8")).hexdigest()

        # 3. Persistence
        record, _ = await self.repo.upsert_document_record(
            ctx=ctx,
            workspace_id=project.workspace_id,
            project_id=project.id,
            path=data.path,
            title=data.title,
            kind=data.kind,
            current_version_hash=content_hash,
            content_snapshot=data.content,
            extracted_symbols=extracted_symbols,
            file_id=data.file_id,
        )
        return _to_doc_record_detail(record)

    async def detect_drift(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        req: DocDriftDetectRequest,
    ) -> DocDriftDetectResponse:
        """Run DocsAlive agent to identify discrepancies and propose patches."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if not project:
            raise NotFoundError(detail=f"Project {project_id} not found")

        drift_items = await self.agent.detect_and_propose(
            ctx=ctx,
            project_id=project_id,
            known_routes=set(req.known_routes),
            known_symbols=set(req.known_symbols) if req.known_symbols else None,
            known_files=set(req.known_files) if req.known_files else None,
            known_configs=set(req.known_configs) if req.known_configs else None,
        )

        doc_records = await self.repo.list_documents_by_project(ctx, project_id)
        summary = (
            f"Detected {len(drift_items)} drift item(s) across {len(doc_records)} documentation file(s)."
            if drift_items
            else f"All {len(doc_records)} documentation file(s) are in sync with active code."
        )

        return DocDriftDetectResponse(
            project_id=project_id,
            total_docs_analyzed=len(doc_records),
            drift_count=len(drift_items),
            drift_items=[_to_drift_item_response(item) for item in drift_items],
            summary=summary,
        )

    async def list_drift_items(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        status: str | None = None,
        kind: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DocDriftItemResponse]:
        """List tracked drift items for a project with optional status filter."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if not project:
            raise NotFoundError(detail=f"Project {project_id} not found")

        items = await self.repo.list_drift_items_by_project(
            ctx=ctx,
            project_id=project_id,
            status=status,
            kind=kind,
            limit=limit,
            offset=offset,
        )
        return [_to_drift_item_response(i) for i in items]

    async def get_drift_item(
        self,
        ctx: AuthContext | SystemContext,
        drift_id: UUID,
    ) -> DocDriftItemResponse:
        """Get detail of a drift item including proposal diff."""
        item = await self.repo.get_drift_item_by_id(ctx, drift_id)
        if not item:
            raise NotFoundError(detail=f"Drift item {drift_id} not found")
        return _to_drift_item_response(item)

    async def approve_drift_item(
        self,
        ctx: AuthContext | SystemContext,
        drift_id: UUID,
        req: DriftApprovalRequest,
    ) -> DriftActionResponse:
        """Approve a proposed patch (human maintainer gate)."""
        drift = await self.agent.approve_drift(
            ctx=ctx,
            drift_id=drift_id,
            decided_by=req.reason,
        )
        return DriftActionResponse(
            drift_id=drift.id,
            status=drift.status,
            message="Drift patch proposal approved by maintainer.",
            applied_patch_preview=drift.proposal.get("diff_content") if drift.proposal else None,
        )

    async def reject_drift_item(
        self,
        ctx: AuthContext | SystemContext,
        drift_id: UUID,
        req: DriftApprovalRequest,
    ) -> DriftActionResponse:
        """Reject a proposed patch (human maintainer gate)."""
        drift = await self.agent.reject_drift(
            ctx=ctx,
            drift_id=drift_id,
            reason=req.reason,
        )
        return DriftActionResponse(
            drift_id=drift.id,
            status=drift.status,
            message="Drift patch proposal rejected.",
        )

    async def apply_drift_patch(
        self,
        ctx: AuthContext | SystemContext,
        drift_id: UUID,
    ) -> DriftActionResponse:
        """Apply an approved documentation patch."""
        drift, doc = await self.agent.apply_patch(ctx=ctx, drift_id=drift_id)
        return DriftActionResponse(
            drift_id=drift.id,
            status=drift.status,
            message=f"Patch successfully applied to {doc.path}.",
            applied_patch_preview=drift.proposal.get("diff_content") if drift.proposal else None,
        )
