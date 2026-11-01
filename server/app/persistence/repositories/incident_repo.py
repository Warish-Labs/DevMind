"""Deployment Incident repository for Deployment Diagnosis (docs/01 CAP-07, docs/03 §3.4)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.log_parser import LogParser, ParsedDeploymentLog
from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import ForbiddenError
from app.core.ids import generate_uuid7
from app.persistence.models.deployment import DeploymentIncident
from app.persistence.repositories.base import BaseRepository


class DeploymentIncidentRepository(BaseRepository):
    """Repository managing DeploymentIncident persistence with strict tenant scoping."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    def _check_tenant_access(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        project_id: UUID | None = None,
    ) -> None:
        """Enforce strict workspace and project isolation."""
        self._validate_context(ctx)
        if isinstance(ctx, AuthContext):
            if ctx.workspace_id and ctx.workspace_id != workspace_id:
                raise ForbiddenError(detail="Cross-workspace incident access is forbidden")
            if project_id and ctx.project_id and ctx.project_id != project_id:
                raise ForbiddenError(detail="Cross-project incident access is forbidden")

    async def record_incident(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        project_id: UUID,
        raw_log: str,
        environment: str = "production",
        service_name: str | None = None,
        summary: str | None = None,
        probable_cause: str | None = None,
        resolution: str | None = None,
    ) -> tuple[DeploymentIncident, bool, ParsedDeploymentLog]:
        """Normalize, redact, and upsert a deployment failure incident.

        Guarantees that credentials in logs are redacted prior to persistence.
        If an incident with the same fingerprint already exists for this project,
        increments occurrence_count and updates last_seen_at.

        Returns:
            Tuple of (DeploymentIncident, is_new, ParsedDeploymentLog).
        """
        self._check_tenant_access(ctx, workspace_id, project_id)

        parsed: ParsedDeploymentLog = LogParser.redact_and_parse(
            raw_log,
            environment=environment,
            service_name=service_name,
        )

        chosen_summary = summary or parsed.summary
        chosen_cause = probable_cause or parsed.probable_cause

        # Look up existing record by (project_id, fingerprint)
        stmt = select(DeploymentIncident).where(
            DeploymentIncident.workspace_id == workspace_id,
            DeploymentIncident.project_id == project_id,
            DeploymentIncident.fingerprint == parsed.fingerprint,
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()

        now = datetime.now(UTC)
        if existing is not None:
            existing.occurrence_count += 1
            existing.last_seen_at = now
            existing.log_snippet = parsed.redacted_text[:4000]
            if resolution and not existing.resolution:
                existing.resolution = resolution
                existing.resolved_at = now
            if service_name:
                existing.service_name = service_name
            await self.session.flush()
            return existing, False, parsed

        # Construct new deployment incident
        metadata: dict[str, Any] = {
            "referenced_env_vars": parsed.referenced_env_vars,
            "referenced_files": parsed.referenced_files,
            "primary_log_line": parsed.primary_log_line,
            "confidence": parsed.confidence,
            "recommended_action": parsed.recommended_action,
            "redaction_count": parsed.redaction_count,
            "counts_by_type": parsed.counts_by_type,
        }

        incident = DeploymentIncident(
            id=generate_uuid7(),
            workspace_id=workspace_id,
            project_id=project_id,
            fingerprint=parsed.fingerprint,
            summary=chosen_summary,
            probable_cause=chosen_cause,
            resolution=resolution,
            error_signature=parsed.error_signature,
            environment=environment,
            service_name=service_name,
            failure_category=parsed.failure_category,
            log_snippet=parsed.redacted_text[:4000],
            occurrence_count=1,
            last_seen_at=now,
            created_at=now,
            updated_at=now,
            metadata_=metadata,
        )

        self.session.add(incident)
        await self.session.flush()
        return incident, True, parsed

    async def get_incident(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        project_id: UUID,
        incident_id: UUID,
    ) -> DeploymentIncident | None:
        """Fetch a deployment incident by ID with tenant scoping."""
        self._check_tenant_access(ctx, workspace_id, project_id)
        stmt = select(DeploymentIncident).where(
            DeploymentIncident.id == incident_id,
            DeploymentIncident.workspace_id == workspace_id,
            DeploymentIncident.project_id == project_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_fingerprint(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        project_id: UUID,
        fingerprint: str,
    ) -> DeploymentIncident | None:
        """Fetch a deployment incident by fingerprint with tenant scoping."""
        self._check_tenant_access(ctx, workspace_id, project_id)
        stmt = select(DeploymentIncident).where(
            DeploymentIncident.workspace_id == workspace_id,
            DeploymentIncident.project_id == project_id,
            DeploymentIncident.fingerprint == fingerprint,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_incidents(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        project_id: UUID,
        environment: str | None = None,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[DeploymentIncident], int]:
        """List deployment incidents with optional environment/category filters."""
        self._check_tenant_access(ctx, workspace_id, project_id)

        base_filter = [
            DeploymentIncident.workspace_id == workspace_id,
            DeploymentIncident.project_id == project_id,
        ]
        if environment:
            base_filter.append(DeploymentIncident.environment == environment)
        if category:
            base_filter.append(DeploymentIncident.failure_category == category)

        count_stmt = select(func.count(DeploymentIncident.id)).where(*base_filter)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = (
            select(DeploymentIncident)
            .where(*base_filter)
            .order_by(DeploymentIncident.last_seen_at.desc())
            .offset(offset)
            .limit(limit)
        )
        incidents = list((await self.session.execute(stmt)).scalars().all())
        return incidents, total

    async def search_similar_incidents(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        project_id: UUID,
        fingerprint: str | None = None,
        failure_category: str | None = None,
        error_signature: str | None = None,
        referenced_env_vars: list[str] | None = None,
        limit: int = 5,
    ) -> list[tuple[DeploymentIncident, float, str]]:
        """Search historical deployment incidents for matches and resolutions (docs/01 CAP-07, docs/05 §6.10).

        Returns:
            List of (incident, similarity_score, match_type) tuples ordered by highest score.
        """
        import re

        self._check_tenant_access(ctx, workspace_id, project_id)

        # Retrieve recent incidents for the project
        stmt = (
            select(DeploymentIncident)
            .where(
                DeploymentIncident.workspace_id == workspace_id,
                DeploymentIncident.project_id == project_id,
            )
            .order_by(DeploymentIncident.last_seen_at.desc())
            .limit(50)
        )
        candidates = list((await self.session.execute(stmt)).scalars().all())

        scored_results: list[tuple[DeploymentIncident, float, str]] = []
        ref_vars_set = set(referenced_env_vars or [])

        for inc in candidates:
            # 1. Exact fingerprint match
            if fingerprint and inc.fingerprint == fingerprint:
                scored_results.append((inc, 1.0, "exact_fingerprint"))
                continue

            score = 0.0
            match_types: list[str] = []

            # 2. Failure category match
            if failure_category and inc.failure_category == failure_category:
                score += 0.5
                match_types.append("category_match")

            # 3. Referenced environment variables overlap
            inc_meta = inc.metadata_ or {}
            inc_vars = set(inc_meta.get("referenced_env_vars", []))
            if ref_vars_set and inc_vars:
                common_vars = ref_vars_set.intersection(inc_vars)
                if common_vars:
                    score += 0.3
                    match_types.append(f"env_overlap({','.join(sorted(common_vars))})")

            # 4. Error signature token overlap
            if error_signature and inc.error_signature:
                sig1_tokens = set(re.findall(r"\w+", error_signature.lower()))
                sig2_tokens = set(re.findall(r"\w+", inc.error_signature.lower()))
                if sig1_tokens and sig2_tokens:
                    token_overlap = len(sig1_tokens.intersection(sig2_tokens)) / max(
                        len(sig1_tokens.union(sig2_tokens)), 1
                    )
                    if token_overlap > 0.4:
                        score += 0.2
                        match_types.append("signature_similarity")

            if score >= 0.5:
                final_score = min(score, 0.99)
                scored_results.append((inc, final_score, " + ".join(match_types)))

        # Sort by similarity score descending, then last_seen_at descending
        scored_results.sort(key=lambda x: (x[1], x[0].last_seen_at), reverse=True)
        return scored_results[:limit]

    async def update_resolution(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        project_id: UUID,
        incident_id: UUID,
        resolution: str,
        resolved_by: UUID | None = None,
    ) -> DeploymentIncident | None:
        """Update or document resolution details for an incident."""
        self._check_tenant_access(ctx, workspace_id, project_id)
        incident = await self.get_incident(
            ctx,
            workspace_id=workspace_id,
            project_id=project_id,
            incident_id=incident_id,
        )
        if incident is None:
            return None

        incident.resolution = resolution
        incident.resolved_at = datetime.now(UTC)
        incident.resolved_by = resolved_by
        await self.session.flush()
        return incident

    async def delete_incident(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        project_id: UUID,
        incident_id: UUID,
    ) -> bool:
        """Delete an incident record."""
        self._check_tenant_access(ctx, workspace_id, project_id)
        incident = await self.get_incident(
            ctx,
            workspace_id=workspace_id,
            project_id=project_id,
            incident_id=incident_id,
        )
        if incident is None:
            return False

        await self.session.delete(incident)
        await self.session.flush()
        return True
