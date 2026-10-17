"""Findings domain service: batch ingestion, fingerprinting, and lifecycle state machine (docs/03 §3.4, §5.1, §12.5).

Enforces:
- Deterministic 64-character SHA-256 fingerprinting stabilized against line number shifts.
- Extension-local evidence ceiling capped at E1 (ADR-047, docs/03 §12.5).
- Invariant lifecycle state machine transitions (docs/03 §5.1).
- Append-only audit history for all status changes.
- Tenant isolation and zero unconsented source persistence at rest.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.ids import generate_uuid7
from app.domain.brain.context import resolve_project_context
from app.persistence.models.brain import (
    Finding,
    FindingEvidence,
    FindingStatusHistory,
    ProjectFile,
)
from app.persistence.repositories.brain_repo import BrainRepository

VALID_CATEGORIES = frozenset(
    {
        "authentication",
        "authorization",
        "secret_exposure",
        "input_validation",
        "error_handling",
        "testing",
        "documentation",
        "configuration",
        "dependency",
        "quality",
        "other",
    }
)

VALID_SEVERITIES = frozenset({"critical", "high", "medium", "low", "info"})
VALID_CONFIDENCES = frozenset({"low", "medium", "high"})
VALID_EVIDENCE_LEVELS = frozenset({"E0", "E1", "E2", "E3"})
VALID_STATUSES = frozenset(
    {
        "open",
        "acknowledged",
        "in_progress",
        "dismissed",
        "accepted_risk",
        "fix_proposed",
        "stale",
        "resolved",
        "reopened",
    }
)

# Lifecycle transition matrix (docs/03 §5.1)
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "open": frozenset(
        {"acknowledged", "in_progress", "dismissed", "accepted_risk", "fix_proposed", "stale"}
    ),
    "acknowledged": frozenset({"in_progress", "dismissed", "accepted_risk", "open"}),
    "in_progress": frozenset({"fix_proposed", "resolved", "dismissed", "accepted_risk", "open"}),
    "fix_proposed": frozenset({"resolved", "in_progress", "dismissed", "accepted_risk", "open"}),
    "stale": frozenset({"open", "resolved"}),
    "resolved": frozenset({"reopened"}),
    "dismissed": frozenset({"reopened"}),
    "accepted_risk": frozenset({"reopened"}),
    "reopened": frozenset({"acknowledged", "in_progress", "dismissed", "accepted_risk", "open"}),
}


def compute_finding_fingerprint(
    rule_id: str,
    path: str,
    canonical_identifier: str | None = None,
    location_fallback: str | None = None,
) -> str:
    """Compute stable 64-character SHA-256 fingerprint for a finding.

    Stabilized against line number shifts by prioritizing rule_id + normalized_path + canonical_identifier
    (e.g., HTTP route signature, symbol qualified name, or token type).
    """
    clean_path = path.strip().replace("\\", "/").lstrip("/")
    identifier = (canonical_identifier or location_fallback or "").strip()
    raw = f"{rule_id}:{clean_path}:{identifier}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# --- Pydantic Schemas ---


class SuggestedFixPayload(BaseModel):
    kind: str = "proposal"
    description: str
    diff: str | None = None


class FindingLocationPayload(BaseModel):
    path: str
    start_line: int | None = None
    end_line: int | None = None


class FindingEvidencePayload(BaseModel):
    path: str
    start_line: int
    end_line: int
    snippet_hash: str
    role: str = "primary"
    file_version_id: UUID | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class FindingPayload(BaseModel):
    rule_id: str
    category: str
    title: str
    summary: str
    explanation: str | None = None
    severity: str
    confidence: str = "medium"
    evidence_level: str = "E1"
    status: str = "open"
    location: FindingLocationPayload | None = None
    canonical_identifier: str | None = None
    fingerprint: str | None = None
    evidence: list[FindingEvidencePayload] = Field(default_factory=list)
    suggested_fix: SuggestedFixPayload | None = None


class BatchFindingsRequest(BaseModel):
    scan_run_id: UUID | None = None
    findings: list[FindingPayload]


class FindingEvidenceItem(BaseModel):
    id: UUID
    finding_id: UUID
    path: str
    start_line: int
    end_line: int
    snippet_hash: str
    role: str
    detail: dict[str, Any]
    is_current: bool
    created_at: datetime


class FindingStatusHistoryItem(BaseModel):
    id: UUID
    finding_id: UUID
    from_status: str
    to_status: str
    actor_kind: str
    actor_id: UUID | None = None
    reason: str | None = None
    created_at: datetime


class FindingItem(BaseModel):
    id: UUID
    project_id: UUID
    fingerprint: str
    rule_id: str
    source: str
    category: str
    title: str
    summary: str
    explanation: str | None = None
    severity: str
    confidence: str
    evidence_level: str
    status: str
    first_seen_scan_run_id: UUID | None = None
    last_seen_scan_run_id: UUID | None = None
    primary_file_id: UUID | None = None
    primary_path: str | None = None
    primary_start_line: int | None = None
    primary_end_line: int | None = None
    suggested_fix: dict[str, Any] | None = None
    status_reason: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class FindingDetailItem(FindingItem):
    evidence: list[FindingEvidenceItem] = Field(default_factory=list)
    history: list[FindingStatusHistoryItem] = Field(default_factory=list)


class BatchFindingsResponse(BaseModel):
    ingested: int
    created: int
    updated: int
    reopened: int
    findings: list[FindingItem]


class FindingStatusTransitionRequest(BaseModel):
    to_status: str
    reason: str | None = None


# --- Domain Service ---


class FindingsService:
    """Manages finding ingestion, fingerprint calculation, and lifecycle state transitions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = BrainRepository(session)

    async def resolve_project_context(
        self, ctx: AuthContext | SystemContext, project_id: UUID
    ) -> AuthContext | SystemContext:
        """Resolve and verify tenant authorization context for project."""
        return await resolve_project_context(self.session, ctx, project_id)

    async def batch_ingest_findings(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        payload: BatchFindingsRequest,
        source: str = "scanner",
    ) -> BatchFindingsResponse:
        """Batch ingest findings from extension scanner or automated rule analysis.

        Enforces:
        - Extension evidence capped at E1.
        - Fingerprint deduplication and recurrence reopening.
        - Historical state transition logging.
        """
        await self.repo._verify_project_access(ctx, project_id)

        created_count = 0
        updated_count = 0
        reopened_count = 0
        persisted_findings: list[Finding] = []

        # Pre-fetch existing files for primary_file_id resolution
        file_paths: set[str] = set()
        for f in payload.findings:
            if f.location and f.location.path:
                file_paths.add(f.location.path)
            for ev in f.evidence:
                file_paths.add(ev.path)

        files_map: dict[str, ProjectFile] = {}
        if file_paths:
            stmt = select(ProjectFile).where(
                ProjectFile.project_id == project_id,
                ProjectFile.path.in_(list(file_paths)),
                ProjectFile.removed_at.is_(None),
            )
            files_result = await self.session.execute(stmt)
            for file_row in files_result.scalars().all():
                files_map[file_row.path] = file_row

        for finding_in in payload.findings:
            # 1. Validation
            category = finding_in.category.lower()
            if category not in VALID_CATEGORIES:
                raise ValidationError(
                    code="finding.invalid_category",
                    detail=f"Category '{category}' is invalid. Allowed: {sorted(VALID_CATEGORIES)}",
                )

            severity = finding_in.severity.lower()
            if severity not in VALID_SEVERITIES:
                raise ValidationError(
                    code="finding.invalid_severity",
                    detail=f"Severity '{severity}' is invalid. Allowed: {sorted(VALID_SEVERITIES)}",
                )

            confidence = finding_in.confidence.lower()
            if confidence not in VALID_CONFIDENCES:
                raise ValidationError(
                    code="finding.invalid_confidence",
                    detail=f"Confidence '{confidence}' is invalid. Allowed: {sorted(VALID_CONFIDENCES)}",
                )

            # Cap evidence level at E1 for extension-local/scanner findings (Rule 5 & docs/03 §12.5)
            evidence_level = finding_in.evidence_level.upper()
            if evidence_level not in VALID_EVIDENCE_LEVELS:
                evidence_level = "E1"
            if source == "scanner" and evidence_level in ("E2", "E3"):
                evidence_level = "E1"

            # 2. Primary location resolution
            primary_path: str = ""
            primary_start_line: int | None = None
            primary_end_line: int | None = None
            if finding_in.location:
                primary_path = finding_in.location.path
                primary_start_line = finding_in.location.start_line
                primary_end_line = finding_in.location.end_line
            elif finding_in.evidence:
                primary_ev = finding_in.evidence[0]
                primary_path = primary_ev.path
                primary_start_line = primary_ev.start_line
                primary_end_line = primary_ev.end_line

            primary_file = files_map.get(primary_path)
            primary_file_id = primary_file.id if primary_file else None

            # 3. Fingerprint calculation
            location_fb = (
                f"{primary_start_line}:{primary_end_line}"
                if primary_start_line is not None
                else None
            )
            if finding_in.fingerprint and len(finding_in.fingerprint) == 64:
                fingerprint = finding_in.fingerprint
            else:
                fingerprint = compute_finding_fingerprint(
                    rule_id=finding_in.rule_id,
                    path=primary_path,
                    canonical_identifier=finding_in.canonical_identifier,
                    location_fallback=location_fb,
                )

            # 4. Check for existing finding
            stmt_find = (
                select(Finding)
                .options(selectinload(Finding.evidence_items))
                .where(
                    Finding.project_id == project_id,
                    Finding.fingerprint == fingerprint,
                )
            )
            existing = (await self.session.execute(stmt_find)).scalars().first()

            suggested_fix_dict = (
                finding_in.suggested_fix.model_dump() if finding_in.suggested_fix else None
            )

            if existing:
                # Update existing finding
                if payload.scan_run_id:
                    existing.last_seen_scan_run_id = payload.scan_run_id
                existing.title = finding_in.title
                existing.summary = finding_in.summary
                if finding_in.explanation:
                    existing.explanation = finding_in.explanation
                existing.severity = severity
                existing.confidence = confidence
                existing.evidence_level = evidence_level
                if primary_file_id:
                    existing.primary_file_id = primary_file_id
                existing.primary_start_line = primary_start_line
                existing.primary_end_line = primary_end_line
                if suggested_fix_dict:
                    existing.suggested_fix = suggested_fix_dict

                # State machine transition on re-detection (docs/03 §5.1)
                if existing.status == "stale":
                    from_st = existing.status
                    existing.status = "open"
                    history_entry = FindingStatusHistory(
                        id=generate_uuid7(),
                        finding_id=existing.id,
                        from_status=from_st,
                        to_status="open",
                        actor_kind="system",
                        reason="re-verified in scan",
                    )
                    self.session.add(history_entry)
                    updated_count += 1
                elif existing.status == "resolved":
                    # Recurrence of resolved issue reopens it
                    from_st = existing.status
                    existing.status = "reopened"
                    existing.resolved_at = None
                    history_entry = FindingStatusHistory(
                        id=generate_uuid7(),
                        finding_id=existing.id,
                        from_status=from_st,
                        to_status="reopened",
                        actor_kind="system",
                        reason="recurrence detected in scan",
                    )
                    self.session.add(history_entry)
                    reopened_count += 1
                else:
                    updated_count += 1

                # Ingest new evidence items if not already present
                existing_hashes = {ev.snippet_hash for ev in existing.evidence_items}
                for ev_payload in finding_in.evidence:
                    if ev_payload.snippet_hash not in existing_hashes:
                        ev_file = files_map.get(ev_payload.path)
                        evidence = FindingEvidence(
                            id=generate_uuid7(),
                            finding_id=existing.id,
                            project_id=project_id,
                            file_version_id=ev_payload.file_version_id
                            or (ev_file.current_version_id if ev_file else None),
                            path=ev_payload.path,
                            start_line=ev_payload.start_line,
                            end_line=ev_payload.end_line,
                            snippet_hash=ev_payload.snippet_hash,
                            snippet_text=None,  # Zero unconsented source at rest (ADR-047)
                            role=ev_payload.role,
                            detail=ev_payload.detail,
                            is_current=True,
                        )
                        self.session.add(evidence)

                persisted_findings.append(existing)

            else:
                # Create brand new finding
                new_finding = Finding(
                    id=generate_uuid7(),
                    project_id=project_id,
                    fingerprint=fingerprint,
                    rule_id=finding_in.rule_id,
                    source=source,
                    category=category,
                    title=finding_in.title,
                    summary=finding_in.summary,
                    explanation=finding_in.explanation,
                    severity=severity,
                    confidence=confidence,
                    evidence_level=evidence_level,
                    status="open",
                    first_seen_scan_run_id=payload.scan_run_id,
                    last_seen_scan_run_id=payload.scan_run_id,
                    primary_file_id=primary_file_id,
                    primary_start_line=primary_start_line,
                    primary_end_line=primary_end_line,
                    suggested_fix=suggested_fix_dict,
                )
                self.session.add(new_finding)
                await self.session.flush()

                # Record initial creation status history
                history_entry = FindingStatusHistory(
                    id=generate_uuid7(),
                    finding_id=new_finding.id,
                    from_status="none",
                    to_status="open",
                    actor_kind="system",
                    reason="initial scan discovery",
                )
                self.session.add(history_entry)

                # Add evidence items
                for ev_payload in finding_in.evidence:
                    ev_file = files_map.get(ev_payload.path)
                    evidence = FindingEvidence(
                        id=generate_uuid7(),
                        finding_id=new_finding.id,
                        project_id=project_id,
                        file_version_id=ev_payload.file_version_id
                        or (ev_file.current_version_id if ev_file else None),
                        path=ev_payload.path,
                        start_line=ev_payload.start_line,
                        end_line=ev_payload.end_line,
                        snippet_hash=ev_payload.snippet_hash,
                        snippet_text=None,
                        role=ev_payload.role,
                        detail=ev_payload.detail,
                        is_current=True,
                    )
                    self.session.add(evidence)

                created_count += 1
                persisted_findings.append(new_finding)

        await self.session.flush()

        # Build serialized response items
        items: list[FindingItem] = []
        for pf in persisted_findings:
            p_file = (
                files_map.get(pf.primary_file.path)
                if pf.primary_file
                else (
                    next((f for f in files_map.values() if f.id == pf.primary_file_id), None)
                    if pf.primary_file_id
                    else None
                )
            )
            items.append(
                FindingItem(
                    id=pf.id,
                    project_id=pf.project_id,
                    fingerprint=pf.fingerprint,
                    rule_id=pf.rule_id,
                    source=pf.source,
                    category=pf.category,
                    title=pf.title,
                    summary=pf.summary,
                    explanation=pf.explanation,
                    severity=pf.severity,
                    confidence=pf.confidence,
                    evidence_level=pf.evidence_level,
                    status=pf.status,
                    first_seen_scan_run_id=pf.first_seen_scan_run_id,
                    last_seen_scan_run_id=pf.last_seen_scan_run_id,
                    primary_file_id=pf.primary_file_id,
                    primary_path=p_file.path if p_file else None,
                    primary_start_line=pf.primary_start_line,
                    primary_end_line=pf.primary_end_line,
                    suggested_fix=pf.suggested_fix,
                    status_reason=pf.status_reason,
                    resolved_at=pf.resolved_at,
                    created_at=pf.created_at or datetime.now(UTC),
                    updated_at=pf.updated_at or datetime.now(UTC),
                )
            )

        return BatchFindingsResponse(
            ingested=len(payload.findings),
            created=created_count,
            updated=updated_count,
            reopened=reopened_count,
            findings=items,
        )

    async def list_findings(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        status_filter: str | None = None,
        severity_filter: str | None = None,
        category_filter: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[FindingItem]:
        """List project findings with optional status, severity, and category filters."""
        await self.repo._verify_project_access(ctx, project_id)

        stmt = (
            select(Finding)
            .options(selectinload(Finding.primary_file))
            .where(Finding.project_id == project_id)
            .order_by(Finding.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if status_filter:
            stmt = stmt.where(Finding.status == status_filter)
        if severity_filter:
            stmt = stmt.where(Finding.severity == severity_filter)
        if category_filter:
            stmt = stmt.where(Finding.category == category_filter)

        result = await self.session.execute(stmt)
        findings = list(result.scalars().all())

        return [
            FindingItem(
                id=f.id,
                project_id=f.project_id,
                fingerprint=f.fingerprint,
                rule_id=f.rule_id,
                source=f.source,
                category=f.category,
                title=f.title,
                summary=f.summary,
                explanation=f.explanation,
                severity=f.severity,
                confidence=f.confidence,
                evidence_level=f.evidence_level,
                status=f.status,
                first_seen_scan_run_id=f.first_seen_scan_run_id,
                last_seen_scan_run_id=f.last_seen_scan_run_id,
                primary_file_id=f.primary_file_id,
                primary_path=f.primary_file.path if f.primary_file else None,
                primary_start_line=f.primary_start_line,
                primary_end_line=f.primary_end_line,
                suggested_fix=f.suggested_fix,
                status_reason=f.status_reason,
                resolved_at=f.resolved_at,
                created_at=f.created_at or datetime.now(UTC),
                updated_at=f.updated_at or datetime.now(UTC),
            )
            for f in findings
        ]

    async def get_finding_detail(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        finding_id: UUID,
    ) -> FindingDetailItem:
        """Get complete finding details including machine-checkable evidence and status history."""
        await self.repo._verify_project_access(ctx, project_id)

        stmt = (
            select(Finding)
            .options(
                selectinload(Finding.evidence_items),
                selectinload(Finding.status_history),
                selectinload(Finding.primary_file),
            )
            .where(
                Finding.id == finding_id,
                Finding.project_id == project_id,
            )
        )
        finding = (await self.session.execute(stmt)).scalars().first()
        if not finding:
            raise NotFoundError(
                code="finding.not_found",
                detail=f"Finding with ID '{finding_id}' not found in project.",
            )

        evidence_items = [
            FindingEvidenceItem(
                id=ev.id,
                finding_id=ev.finding_id,
                path=ev.path,
                start_line=ev.start_line,
                end_line=ev.end_line,
                snippet_hash=ev.snippet_hash,
                role=ev.role,
                detail=ev.detail,
                is_current=ev.is_current,
                created_at=ev.created_at or datetime.now(UTC),
            )
            for ev in finding.evidence_items
        ]

        history_items = [
            FindingStatusHistoryItem(
                id=h.id,
                finding_id=h.finding_id,
                from_status=h.from_status,
                to_status=h.to_status,
                actor_kind=h.actor_kind,
                actor_id=h.actor_id,
                reason=h.reason,
                created_at=h.created_at or datetime.now(UTC),
            )
            for h in sorted(finding.status_history, key=lambda x: x.created_at or datetime.now(UTC))
        ]

        return FindingDetailItem(
            id=finding.id,
            project_id=finding.project_id,
            fingerprint=finding.fingerprint,
            rule_id=finding.rule_id,
            source=finding.source,
            category=finding.category,
            title=finding.title,
            summary=finding.summary,
            explanation=finding.explanation,
            severity=finding.severity,
            confidence=finding.confidence,
            evidence_level=finding.evidence_level,
            status=finding.status,
            first_seen_scan_run_id=finding.first_seen_scan_run_id,
            last_seen_scan_run_id=finding.last_seen_scan_run_id,
            primary_file_id=finding.primary_file_id,
            primary_path=finding.primary_file.path if finding.primary_file else None,
            primary_start_line=finding.primary_start_line,
            primary_end_line=finding.primary_end_line,
            suggested_fix=finding.suggested_fix,
            status_reason=finding.status_reason,
            resolved_at=finding.resolved_at,
            created_at=finding.created_at or datetime.now(UTC),
            updated_at=finding.updated_at or datetime.now(UTC),
            evidence=evidence_items,
            history=history_items,
        )

    async def transition_status(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        finding_id: UUID,
        request: FindingStatusTransitionRequest,
    ) -> FindingDetailItem:
        """Execute a state machine transition on a finding (docs/03 §5.1).

        Enforces:
        - Valid state transition per ALLOWED_TRANSITIONS graph.
        - Mandatory reason for dismissal ('false_positive', 'not_applicable', 'duplicate', 'other').
        - Timestamps on resolution and clearing on reopening.
        - Append-only audit history log entry.
        """
        await self.repo._verify_project_access(ctx, project_id)

        target_status = request.to_status.lower()
        if target_status not in VALID_STATUSES:
            raise ValidationError(
                code="finding.invalid_status",
                detail=f"Target status '{target_status}' is invalid. Allowed: {sorted(VALID_STATUSES)}",
            )

        stmt = select(Finding).where(
            Finding.id == finding_id,
            Finding.project_id == project_id,
        )
        finding = (await self.session.execute(stmt)).scalars().first()
        if not finding:
            raise NotFoundError(
                code="finding.not_found",
                detail=f"Finding with ID '{finding_id}' not found in project.",
            )

        current_status = finding.status
        if target_status == current_status:
            return await self.get_finding_detail(ctx, project_id, finding_id)

        allowed = ALLOWED_TRANSITIONS.get(current_status, frozenset())
        if target_status not in allowed:
            raise ConflictError(
                code="finding.invalid_transition",
                detail=f"Cannot transition finding from '{current_status}' to '{target_status}'. Allowed transitions: {sorted(allowed)}",
            )

        if target_status == "dismissed" and not request.reason:
            raise ValidationError(
                code="finding.reason_required",
                detail="A reason code is required when dismissing a finding (false_positive, not_applicable, duplicate, other).",
            )

        # Update finding status
        finding.status = target_status
        if target_status == "resolved":
            finding.resolved_at = datetime.now(UTC)
        elif target_status in ("open", "reopened"):
            finding.resolved_at = None

        if request.reason:
            finding.status_reason = request.reason

        actor_kind = "user" if isinstance(ctx, AuthContext) and ctx.user_id else "system"
        actor_id = ctx.user_id if isinstance(ctx, AuthContext) else None

        # Append audit history
        history = FindingStatusHistory(
            id=generate_uuid7(),
            finding_id=finding.id,
            from_status=current_status,
            to_status=target_status,
            actor_kind=actor_kind,
            actor_id=actor_id,
            reason=request.reason,
        )
        self.session.add(history)
        await self.session.flush()

        return await self.get_finding_detail(ctx, project_id, finding_id)
