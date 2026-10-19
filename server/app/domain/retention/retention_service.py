"""Domain service for managing retention policies, effective expiration windows, and cleanup sweeps (docs/03 §3.1, docs/07 §9)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import NotFoundError, ValidationError
from app.persistence.database import session_scope
from app.persistence.models.project import Project
from app.persistence.models.retention import RetentionPolicy
from app.persistence.repositories.audit_repo import AuditEventRepository
from app.persistence.repositories.brain_repo import BrainRepository
from app.persistence.repositories.project_repo import ProjectRepository
from app.persistence.repositories.retention_repo import RetentionRepository

# ADR-026 Interim Retention Defaults (days)
DEFAULT_RETENTION_DAYS: dict[str, int] = {
    "job_events": 30,
    "snapshots": 90,
    "ephemeral_snippets": 7,
    "checkpoints": 30,
    "idempotency_keys": 1,
    "audit_events": 365,
}

RETENTION_KIND_DESCRIPTIONS: dict[str, str] = {
    "job_events": "Transient job execution events and live SSE logs.",
    "snapshots": "Historical AST syntax trees and non-current chunk/embedding versions.",
    "ephemeral_snippets": "Single-request source code excerpts attached to completed jobs.",
    "checkpoints": "LangGraph multi-step reasoning thread checkpoints and execution state.",
    "idempotency_keys": "Request replay deduplication tokens and cache.",
    "audit_events": "Immutable tenant activity and sensitive action audit trail.",
}


class RetentionPolicyItem(BaseModel):
    """Retention policy item returned by API."""

    id: str
    workspace_id: str
    project_id: str | None
    kind: str
    days: int
    is_override: bool
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, model: RetentionPolicy) -> RetentionPolicyItem:
        return cls(
            id=str(model.id),
            workspace_id=str(model.workspace_id),
            project_id=str(model.project_id) if model.project_id else None,
            kind=model.kind,
            days=model.days,
            is_override=model.project_id is not None,
            created_at=model.created_at.isoformat(),
            updated_at=model.updated_at.isoformat(),
        )


class EffectiveRetentionKind(BaseModel):
    """Effective retention window for a specific category."""

    kind: str
    days: int
    default_days: int
    description: str
    is_custom: bool
    source: str  # "project_override", "workspace_policy", or "default"


class EffectiveRetentionSummary(BaseModel):
    """Complete effective retention settings for a workspace or project."""

    workspace_id: str
    project_id: str | None = None
    backup_retention_notice: str = Field(
        default="Provider automated backups retain deleted data until backup expiration per ADR-026 and docs/03 §8."
    )
    categories: list[EffectiveRetentionKind]


class RetentionSweepReport(BaseModel):
    """Result of an executed retention cleanup sweep."""

    project_id: str
    swept_at: str
    purged_counts: dict[str, int]
    effective_windows: dict[str, int]


class RetentionService:
    """Domain service managing retention policies and scheduled cleanup sweeps."""

    async def get_workspace_retention(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
    ) -> EffectiveRetentionSummary:
        """Get effective retention settings for a workspace."""
        async with session_scope() as session:
            repo = RetentionRepository(session)
            policies = await repo.list_workspace_policies(ctx, workspace_id)
            policy_map = {p.kind: p for p in policies}

            categories: list[EffectiveRetentionKind] = []
            for kind, default_days in DEFAULT_RETENTION_DAYS.items():
                policy = policy_map.get(kind)
                if policy:
                    categories.append(
                        EffectiveRetentionKind(
                            kind=kind,
                            days=policy.days,
                            default_days=default_days,
                            description=RETENTION_KIND_DESCRIPTIONS.get(kind, ""),
                            is_custom=True,
                            source="workspace_policy",
                        )
                    )
                else:
                    categories.append(
                        EffectiveRetentionKind(
                            kind=kind,
                            days=default_days,
                            default_days=default_days,
                            description=RETENTION_KIND_DESCRIPTIONS.get(kind, ""),
                            is_custom=False,
                            source="default",
                        )
                    )

            return EffectiveRetentionSummary(
                workspace_id=str(workspace_id),
                categories=categories,
            )

    async def update_workspace_retention(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        kind: str,
        days: int,
    ) -> RetentionPolicyItem:
        """Set a workspace-level retention policy."""
        if kind not in DEFAULT_RETENTION_DAYS:
            raise ValidationError(f"Unknown retention category: '{kind}'. Allowed: {list(DEFAULT_RETENTION_DAYS.keys())}")
        if days < 1:
            raise ValidationError("Retention period must be at least 1 day")

        async with session_scope() as session:
            repo = RetentionRepository(session)
            policy = await repo.upsert_policy(ctx, workspace_id, kind, days)

            # Record audit event
            audit_repo = AuditEventRepository(session)
            actor_id = getattr(ctx, "user_id", None) or getattr(ctx, "client_id", None)
            await audit_repo.record(
                workspace_id=workspace_id,
                action="retention.workspace_updated",
                target_kind="retention_policy",
                target_id=policy.id,
                actor_id=actor_id,
                actor_kind="user" if isinstance(ctx, AuthContext) else "system",
                metadata={"kind": kind, "days": days},
            )

            return RetentionPolicyItem.from_model(policy)

    async def get_project_retention(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
    ) -> EffectiveRetentionSummary:
        """Get effective retention settings for a project including overrides."""
        async with session_scope() as session:
            p_repo = ProjectRepository(session)
            project = await p_repo.get_by_id(ctx, project_id)
            if not project:
                raise NotFoundError(f"Project '{project_id}' not found")

            repo = RetentionRepository(session)
            ws_policies = await repo.list_workspace_policies(ctx, project.workspace_id)
            p_policies = await repo.list_project_policies(ctx, project.workspace_id, project_id)

            ws_map = {p.kind: p for p in ws_policies}
            p_map = {p.kind: p for p in p_policies}

            categories: list[EffectiveRetentionKind] = []
            for kind, default_days in DEFAULT_RETENTION_DAYS.items():
                p_policy = p_map.get(kind)
                ws_policy = ws_map.get(kind)

                if p_policy:
                    categories.append(
                        EffectiveRetentionKind(
                            kind=kind,
                            days=p_policy.days,
                            default_days=default_days,
                            description=RETENTION_KIND_DESCRIPTIONS.get(kind, ""),
                            is_custom=True,
                            source="project_override",
                        )
                    )
                elif ws_policy:
                    categories.append(
                        EffectiveRetentionKind(
                            kind=kind,
                            days=ws_policy.days,
                            default_days=default_days,
                            description=RETENTION_KIND_DESCRIPTIONS.get(kind, ""),
                            is_custom=True,
                            source="workspace_policy",
                        )
                    )
                else:
                    categories.append(
                        EffectiveRetentionKind(
                            kind=kind,
                            days=default_days,
                            default_days=default_days,
                            description=RETENTION_KIND_DESCRIPTIONS.get(kind, ""),
                            is_custom=False,
                            source="default",
                        )
                    )

            return EffectiveRetentionSummary(
                workspace_id=str(project.workspace_id),
                project_id=str(project_id),
                categories=categories,
            )

    async def update_project_retention(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        kind: str,
        days: int,
    ) -> RetentionPolicyItem:
        """Set a project-level retention override."""
        if kind not in DEFAULT_RETENTION_DAYS:
            raise ValidationError(f"Unknown retention category: '{kind}'. Allowed: {list(DEFAULT_RETENTION_DAYS.keys())}")
        if days < 1:
            raise ValidationError("Retention period must be at least 1 day")

        async with session_scope() as session:
            p_repo = ProjectRepository(session)
            project = await p_repo.get_by_id(ctx, project_id)
            if not project:
                raise NotFoundError(f"Project '{project_id}' not found")

            repo = RetentionRepository(session)
            policy = await repo.upsert_policy(ctx, project.workspace_id, kind, days, project_id)

            # Record audit event
            audit_repo = AuditEventRepository(session)
            actor_id = getattr(ctx, "user_id", None) or getattr(ctx, "client_id", None)
            await audit_repo.record(
                workspace_id=project.workspace_id,
                action="retention.project_updated",
                target_kind="retention_policy",
                target_id=policy.id,
                actor_id=actor_id,
                actor_kind="user" if isinstance(ctx, AuthContext) else "system",
                metadata={"project_id": str(project_id), "kind": kind, "days": days},
            )

            return RetentionPolicyItem.from_model(policy)

    async def reset_project_retention(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        kind: str,
    ) -> bool:
        """Reset a project-level retention override to inherit from workspace."""
        async with session_scope() as session:
            p_repo = ProjectRepository(session)
            project = await p_repo.get_by_id(ctx, project_id)
            if not project:
                raise NotFoundError(f"Project '{project_id}' not found")

            repo = RetentionRepository(session)
            deleted = await repo.delete_policy(ctx, project.workspace_id, kind, project_id)

            if deleted:
                audit_repo = AuditEventRepository(session)
                actor_id = getattr(ctx, "user_id", None) or getattr(ctx, "client_id", None)
                await audit_repo.record(
                    workspace_id=project.workspace_id,
                    action="retention.project_reset",
                    target_kind="project",
                    target_id=project_id,
                    actor_id=actor_id,
                    actor_kind="user" if isinstance(ctx, AuthContext) else "system",
                    metadata={"project_id": str(project_id), "kind": kind},
                )

            return deleted

    async def execute_retention_sweep(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID | None = None,
        workspace_id: UUID | None = None,
    ) -> list[RetentionSweepReport]:
        """Execute scheduled or on-demand retention sweep across target projects.

        Safe to run twice (idempotent per docs/10 §9).
        """
        reports: list[RetentionSweepReport] = []
        now = datetime.now(UTC)

        async with session_scope() as session:
            p_repo = ProjectRepository(session)
            brain_repo = BrainRepository(session)
            audit_repo = AuditEventRepository(session)

            # Determine target projects
            if project_id is not None:
                p = await p_repo.get_by_id(ctx, project_id)
                target_projects: list[Project] = [p] if p else []
            elif workspace_id is not None:
                target_projects = await p_repo.list_by_workspace(ctx, workspace_id)
            else:
                # System sweep: all non-deleted projects
                from sqlalchemy import select
                stmt = select(Project).where(Project.deleted_at.is_(None))
                res = await session.execute(stmt)
                target_projects = list(res.scalars().all())

            for target in target_projects:
                summary = await self.get_project_retention(ctx, target.id)
                effective_windows: dict[str, int] = {c.kind: c.days for c in summary.categories}

                cutoffs: dict[str, datetime] = {
                    kind: now - timedelta(days=days)
                    for kind, days in effective_windows.items()
                }

                purged_counts = await brain_repo.sweep_project_retention(ctx, target.id, cutoffs)

                report = RetentionSweepReport(
                    project_id=str(target.id),
                    swept_at=now.isoformat(),
                    purged_counts=purged_counts,
                    effective_windows=effective_windows,
                )
                reports.append(report)

                # Record audit event if any records were purged
                total_purged = sum(purged_counts.values())
                if total_purged > 0 or project_id is not None:
                    actor_id = getattr(ctx, "user_id", None) or getattr(ctx, "client_id", None)
                    await audit_repo.record(
                        workspace_id=target.workspace_id,
                        action="retention.sweep_completed",
                        target_kind="project",
                        target_id=target.id,
                        actor_id=actor_id,
                        actor_kind="user" if isinstance(ctx, AuthContext) else "system",
                        metadata={
                            "project_id": str(target.id),
                            "purged_counts": purged_counts,
                            "effective_windows": effective_windows,
                        },
                    )

        return reports
