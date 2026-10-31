"""DocsAlive specialist agent, documentation drift detection, and patch proposals (docs/01 CAP-04, docs/05 §6.7).

Per docs/05 §6.7:
1. Compares current routes, exported symbols, and configuration keys with documentation references.
2. Classifies drift (undocumented_route, removed_route, changed_signature, stale_section, missing_symbol).
3. Generates patch proposals with unified diff previews.
4. Applying a patch is strictly gated by human approval (ADR-015, docs/03 §13).
"""

from __future__ import annotations

import difflib
import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.doc_drift_detector import DocDriftDetector, DriftCandidate
from app.analysis.doc_parser import DocParser, ParsedDocument
from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import ConflictError, NotFoundError
from app.llm.models import LLMGenerationRequest
from app.llm.prompt_loader import PromptLoader, default_prompt_loader
from app.llm.repair import extract_json_candidate
from app.llm.router import LLMGatewayRouter
from app.llm.schemas import DocPatchProposal
from app.orchestration.state import (
    DraftFinding,
    NodeError,
    Proposal,
    RunState,
    SpecialistTask,
)
from app.persistence.models.living_documentation import DocDriftItem, DocumentationRecord
from app.persistence.repositories.living_doc_repo import LivingDocRepository
from app.persistence.repositories.project_repo import ProjectRepository

logger = logging.getLogger("devmind.orchestration.docsalive")


def generate_unified_diff(original: str, modified: str, file_path: str) -> str:
    """Generate unified diff between original and modified documentation content."""
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)
    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
    )
    return "".join(diff)


class DocsAliveAgent:
    """Specialist agent coordinating documentation drift detection, patch drafting, and gated approval."""

    def __init__(
        self,
        session: AsyncSession,
        router: LLMGatewayRouter | None = None,
        prompt_loader: PromptLoader | None = None,
    ) -> None:
        self.session = session
        self.repo = LivingDocRepository(session)
        self.project_repo = ProjectRepository(session)
        self.router = router
        self.prompt_loader = prompt_loader or default_prompt_loader

    async def detect_and_propose(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        known_routes: set[str],
        known_symbols: set[str] | None = None,
        known_files: set[str] | None = None,
        known_configs: set[str] | None = None,
    ) -> list[DocDriftItem]:
        """Analyze project documentation, identify drift items, and synthesize patch proposals."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if not project:
            raise NotFoundError(detail=f"Project {project_id} not found")

        # 1. Load tracked documentation records for this project
        doc_records = await self.repo.list_documents_by_project(ctx, project_id)
        if not doc_records:
            logger.info("No documentation records tracked for project %s", project_id)
            return []

        # 2. Parse documents deterministically
        parsed_docs: list[ParsedDocument] = []
        doc_record_map: dict[str, DocumentationRecord] = {}
        for record in doc_records:
            content = record.content_snapshot or ""
            parsed = DocParser.parse(content, record.path)
            parsed_docs.append(parsed)
            doc_record_map[record.path] = record

        # 3. Detect drift deterministically
        candidates: list[DriftCandidate] = DocDriftDetector.detect_drift(
            parsed_docs=parsed_docs,
            known_routes=known_routes,
            known_symbols=known_symbols,
            known_files=known_files,
            known_configs=known_configs,
        )

        persisted_items: list[DocDriftItem] = []
        default_doc = doc_records[0]

        for candidate in candidates:
            doc_record = doc_record_map.get(candidate.doc_path, default_doc)
            doc_content = doc_record.content_snapshot or ""

            # 4. Generate patch proposal (LLM-assisted with deterministic fallback)
            proposal_dict = await self._synthesize_patch_proposal(
                doc_path=doc_record.path,
                candidate=candidate,
                doc_content=doc_content,
            )

            drift_item = await self.repo.record_drift_item(
                ctx=ctx,
                workspace_id=project.workspace_id,
                project_id=project.id,
                documentation_record_id=doc_record.id,
                kind=candidate.kind,
                explanation=candidate.explanation,
                target_symbol_key=candidate.target_symbol_key,
                target_route_path=candidate.target_route_path,
                proposal=proposal_dict,
            )
            persisted_items.append(drift_item)

        return persisted_items

    async def _synthesize_patch_proposal(
        self,
        doc_path: str,
        candidate: DriftCandidate,
        doc_content: str,
    ) -> dict[str, Any]:
        """Draft a patch proposal either via LLM or deterministic diff construction."""
        # Check LLM availability
        if self.router is not None:
            try:
                rendered = self.prompt_loader.render(
                    task="doc_patch_proposal",
                    version=1,
                    variables={
                        "doc_path": doc_path,
                        "drift_kind": candidate.kind,
                        "drift_explanation": candidate.explanation,
                        "code_context": candidate.target_route_path
                        or candidate.target_symbol_key
                        or "",
                        "existing_content": doc_content[:1500],
                    },
                )
                gen_req = LLMGenerationRequest(
                    task="doc_patch_proposal",
                    messages=rendered.messages,
                )
                result = await self.router.generate(gen_req)
                raw_content = result.content or ""
                if not isinstance(raw_content, str):
                    raw_content = json.dumps(raw_content)

                candidate_json = extract_json_candidate(raw_content)
                if candidate_json:
                    parsed_llm = DocPatchProposal.model_validate_json(candidate_json)
                    return {
                        "summary": parsed_llm.summary,
                        "drift_kind": parsed_llm.drift_kind,
                        "target_section": parsed_llm.target_section,
                        "proposed_content": parsed_llm.proposed_content,
                        "diff_content": parsed_llm.diff_content,
                        "gated": True,
                        "confidence": parsed_llm.confidence,
                        "notes": parsed_llm.notes,
                    }
            except Exception as exc:
                logger.warning(
                    "LLM doc patch proposal synthesis failed, falling back to deterministic: %s",
                    exc,
                )

        # Deterministic patch synthesis fallback
        return self._build_deterministic_proposal(doc_path, candidate, doc_content)

    def _build_deterministic_proposal(
        self,
        doc_path: str,
        candidate: DriftCandidate,
        doc_content: str,
    ) -> dict[str, Any]:
        """Construct deterministic unified diff and documentation proposal."""
        lines = doc_content.splitlines()
        updated_lines = list(lines)

        target_section = None
        proposed_addition = ""

        if candidate.kind == "undocumented_route" and candidate.target_route_path:
            target_section = "Endpoints"
            proposed_addition = (
                f"\n### `{candidate.target_route_path}`\n\n"
                f"Active endpoint detected in code. Please document parameters and response schema.\n"
            )
            # Find an existing API/Endpoints section or append
            inserted = False
            for i, line in enumerate(lines):
                if any(k in line.lower() for k in ("endpoints", "routes", "api")):
                    if line.startswith("#"):
                        updated_lines.insert(i + 1, proposed_addition)
                        inserted = True
                        break
            if not inserted:
                updated_lines.append(f"\n## API Endpoints\n{proposed_addition}")

        elif candidate.kind == "removed_route" and candidate.target_route_path:
            target_section = "Deprecated Routes"
            for i, line in enumerate(lines):
                if candidate.target_route_path in line:
                    updated_lines[i] = f"<!-- REMOVED: {line} -->"

        elif candidate.kind == "missing_symbol" and candidate.target_symbol_key:
            target_section = "Symbols"
            for i, line in enumerate(lines):
                if candidate.target_symbol_key in line:
                    updated_lines[i] = f"<!-- DEPRECATED_SYMBOL: {line} -->"

        else:
            updated_lines.append(f"\n<!-- Drift remediation note: {candidate.explanation} -->\n")

        new_content = "\n".join(updated_lines) + ("\n" if doc_content.endswith("\n") else "")
        diff_text = generate_unified_diff(doc_content, new_content, doc_path)

        return {
            "summary": f"Propose reconciliation for {candidate.kind}: {candidate.explanation}",
            "drift_kind": candidate.kind,
            "target_section": target_section,
            "proposed_content": proposed_addition.strip(),
            "diff_content": diff_text,
            "gated": True,
            "confidence": 0.85,
            "notes": [
                "Generated deterministically from codebase ground truth.",
                "Review diff carefully before approving and applying patch.",
            ],
        }

    async def approve_drift(
        self,
        ctx: AuthContext | SystemContext,
        drift_id: UUID,
        decided_by: str | None = None,
    ) -> DocDriftItem:
        """Maintainer approves a proposed documentation patch (docs/03 §13)."""
        drift = await self.repo.get_drift_item_by_id(ctx, drift_id)
        if not drift:
            raise NotFoundError(detail=f"Drift item {drift_id} not found")

        proposal = dict(drift.proposal or {})
        proposal["decided_by"] = decided_by or (
            ctx.actor_id if isinstance(ctx, AuthContext) else "system"
        )
        proposal["decided_at"] = datetime.now(UTC).isoformat()

        updated = await self.repo.update_drift_status(
            ctx=ctx,
            drift_id=drift_id,
            status="approved",
            proposal=proposal,
        )
        if updated is None:
            raise NotFoundError(detail=f"Drift item {drift_id} not found")
        return updated

    async def reject_drift(
        self,
        ctx: AuthContext | SystemContext,
        drift_id: UUID,
        reason: str | None = None,
    ) -> DocDriftItem:
        """Maintainer rejects a proposed documentation patch."""
        drift = await self.repo.get_drift_item_by_id(ctx, drift_id)
        if not drift:
            raise NotFoundError(detail=f"Drift item {drift_id} not found")

        proposal = dict(drift.proposal or {})
        proposal["rejection_reason"] = reason or "Rejected by maintainer"
        proposal["decided_by"] = ctx.actor_id if isinstance(ctx, AuthContext) else "system"
        proposal["decided_at"] = datetime.now(UTC).isoformat()

        updated = await self.repo.update_drift_status(
            ctx=ctx,
            drift_id=drift_id,
            status="rejected",
            proposal=proposal,
        )
        if updated is None:
            raise NotFoundError(detail=f"Drift item {drift_id} not found")
        return updated

    async def apply_patch(
        self,
        ctx: AuthContext | SystemContext,
        drift_id: UUID,
    ) -> tuple[DocDriftItem, DocumentationRecord]:
        """Apply an approved patch to the documentation record (gated by maintainer approval)."""
        drift = await self.repo.get_drift_item_by_id(ctx, drift_id)
        if not drift:
            raise NotFoundError(detail=f"Drift item {drift_id} not found")

        # Human Approval Gate: status MUST be 'approved'
        if drift.status != "approved":
            raise ConflictError(
                detail=f"Drift patch cannot be applied; current status is '{drift.status}' (must be 'approved')",
                code="doc_drift.not_approved",
            )

        doc = await self.repo.get_document_by_id(ctx, drift.documentation_record_id)
        if not doc:
            raise NotFoundError(
                detail=f"Documentation record {drift.documentation_record_id} not found"
            )

        # Apply the proposed diff or content addition
        proposal = drift.proposal or {}
        proposed_content = proposal.get("proposed_content", "")
        current_content = doc.content_snapshot or ""

        if proposed_content and proposed_content not in current_content:
            updated_content = f"{current_content}\n\n{proposed_content}\n"
        else:
            updated_content = current_content

        new_hash = hashlib.sha256(updated_content.encode("utf-8")).hexdigest()
        doc.content_snapshot = updated_content
        doc.current_version_hash = new_hash
        doc.last_parsed_at = datetime.now(UTC)

        proposal["applied_at"] = datetime.now(UTC).isoformat()
        updated_drift = await self.repo.update_drift_status(
            ctx=ctx,
            drift_id=drift_id,
            status="applied",
            proposal=proposal,
        )

        await self.session.flush()
        return updated_drift or drift, doc


async def run_docsalive_specialist(
    state: RunState,
    task: SpecialistTask,
    router: LLMGatewayRouter | None = None,
    prompt_loader: PromptLoader | None = None,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Execute DocsAlive specialist task within Agent Manager workflow graph (docs/05 §4.1, §6.7)."""
    if session is None:
        return {
            "node_errors": [
                NodeError(
                    node="docsalive",
                    error_code="session_missing",
                    message="DocsAlive specialist requires active database session",
                )
            ]
        }

    agent = DocsAliveAgent(session=session, router=router, prompt_loader=prompt_loader)
    project_id_raw = state.get("project_id")
    if not project_id_raw:
        return {
            "node_errors": [
                NodeError(
                    node="docsalive",
                    error_code="project_id_missing",
                    message="RunState missing project_id",
                )
            ]
        }

    project_id = UUID(project_id_raw) if isinstance(project_id_raw, str) else project_id_raw
    ctx = SystemContext(reason="DocsAlive specialist drift analysis")

    params = task.params or {}
    known_routes = set(params.get("known_routes", []))
    known_symbols = set(params.get("known_symbols", [])) if "known_symbols" in params else None
    known_files = set(params.get("known_files", [])) if "known_files" in params else None
    known_configs = set(params.get("known_configs", [])) if "known_configs" in params else None

    drift_items = await agent.detect_and_propose(
        ctx=ctx,
        project_id=project_id,
        known_routes=known_routes,
        known_symbols=known_symbols,
        known_files=known_files,
        known_configs=known_configs,
    )

    draft_findings: list[DraftFinding] = []
    proposals: list[Proposal] = []

    for item in drift_items:
        draft_findings.append(
            DraftFinding(
                draft_id=str(item.id),
                finding_type="documentation_drift",
                title=f"Doc Drift: {item.kind}",
                file_path=item.documentation_record.path if item.documentation_record else "docs",
                line_range=(1, 50),
                rule_id=f"devmind.docs.{item.kind}",
                severity="medium" if item.kind == "undocumented_route" else "low",
                explanation=item.explanation,
            )
        )
        if item.proposal:
            proposals.append(
                Proposal(
                    proposal_type="diff_patch",
                    title=f"Doc Patch Proposal ({item.kind})",
                    description=item.explanation,
                    diff_content=item.proposal.get("diff_content"),
                    gated=True,
                )
            )

    task.status = "completed"
    response_msg = (
        f"DocsAlive identified {len(drift_items)} drift item(s) across project documentation."
        if drift_items
        else "DocsAlive verified documentation is in sync with project code."
    )

    return {
        "plan": [task],
        "draft_findings": draft_findings,
        "proposals": proposals,
        "final_response": response_msg,
    }
