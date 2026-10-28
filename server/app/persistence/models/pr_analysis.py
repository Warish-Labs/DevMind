"""PR analysis persistence model for PRAgent change impact and PR intelligence (docs/01 CAP-06, docs/03 §3.5, docs/05 §6.5)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.models.base import (
    Base,
    TimestampMixin,
    UUID7PrimaryKeyMixin,
)

if TYPE_CHECKING:
    from app.persistence.models.brain import AnalysisJob
    from app.persistence.models.github import PullRequest
    from app.persistence.models.project import Project
    from app.persistence.models.workspace import Workspace


class PRAnalysis(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Stores PRAgent analysis results, impact subgraph, and synthesized PR summary."""

    __tablename__ = "pr_analyses"
    __table_args__ = (
        UniqueConstraint(
            "pull_request_id",
            "head_sha",
            "job_id",
            name="uq_pr_analyses_pr_head_job",
        ),
        CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')",
            name="ck_pr_analyses_risk_level",
        ),
        Index("ix_pr_analyses_workspace_project", "workspace_id", "project_id"),
        Index("ix_pr_analyses_pull_request_id", "pull_request_id"),
        Index("ix_pr_analyses_head_sha", "head_sha"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    pull_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pull_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    head_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )

    risk_level: Mapped[str] = mapped_column(
        String(20),
        default="low",
        server_default="low",
        nullable=False,
    )

    # Structured summary: purpose, files_changed, affected_areas, risks,
    # security_summary, testing_concerns, documentation_impact
    summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default="{}",
        nullable=False,
    )

    # Change-impact subgraph: changed_files, direct_symbols, affected_modules,
    # affected_routes, affected_tests, dependency_graph_nodes, risk_level
    impact: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default="{}",
        nullable=False,
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship("Workspace", lazy="selectin")
    project: Mapped[Project] = relationship("Project", lazy="selectin")
    pull_request: Mapped[PullRequest] = relationship("PullRequest", lazy="selectin")
    job: Mapped[AnalysisJob | None] = relationship("AnalysisJob", lazy="selectin")
