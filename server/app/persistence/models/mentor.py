"""Project Mentor and Evaluation persistence models (docs/01 CAP-08, CAP-09, docs/03 §3.6, §3.7)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.models.base import (
    Base,
    TimestampMixin,
    UUID7PrimaryKeyMixin,
)

if TYPE_CHECKING:
    from app.persistence.models.brain import Finding, ProjectSnapshot
    from app.persistence.models.project import Project
    from app.persistence.models.user import User
    from app.persistence.models.workspace import Workspace


class TaskDependency(Base):
    """Explicit DAG dependency relationship between project tasks."""

    __tablename__ = "task_dependencies"
    __table_args__ = (Index("ix_task_dependencies_depends_on", "depends_on_task_id"),)

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ProjectTask(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """A developer or agent work item with dependency tracking and priority ranking."""

    __tablename__ = "project_tasks"
    __table_args__ = (
        Index("ix_project_tasks_workspace_project", "workspace_id", "project_id"),
        Index("ix_project_tasks_status", "project_id", "status"),
        Index("ix_project_tasks_priority", "project_id", "priority"),
        Index("ix_project_tasks_finding_id", "finding_id"),
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
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="open",
        server_default="open",
        nullable=False,
        comment="open, in_progress, blocked, completed, cancelled",
    )
    priority: Mapped[str] = mapped_column(
        String(32),
        default="medium",
        server_default="medium",
        nullable=False,
        comment="critical, high, medium, low",
    )
    source: Mapped[str] = mapped_column(
        String(32),
        default="user",
        server_default="user",
        nullable=False,
        comment="user, agent, finding",
    )
    finding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        server_default="{}",
        nullable=False,
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship(lazy="selectin")
    project: Mapped[Project] = relationship(lazy="selectin")
    finding: Mapped[Finding | None] = relationship(lazy="selectin")

    dependencies: Mapped[list[ProjectTask]] = relationship(
        "ProjectTask",
        secondary="task_dependencies",
        primaryjoin="ProjectTask.id == TaskDependency.task_id",
        secondaryjoin="ProjectTask.id == TaskDependency.depends_on_task_id",
        back_populates="dependents",
        lazy="selectin",
    )
    dependents: Mapped[list[ProjectTask]] = relationship(
        "ProjectTask",
        secondary="task_dependencies",
        primaryjoin="ProjectTask.id == TaskDependency.depends_on_task_id",
        secondaryjoin="ProjectTask.id == TaskDependency.task_id",
        back_populates="dependencies",
        lazy="selectin",
    )


class ProjectEvaluation(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Rubric-based multidimensional health evaluation and release-readiness verdict."""

    __tablename__ = "project_evaluations"
    __table_args__ = (
        Index("ix_project_evaluations_project", "project_id", "created_at"),
        Index("ix_project_evaluations_workspace", "workspace_id"),
        Index("ix_project_evaluations_snapshot_id", "snapshot_id"),
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
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    overall_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Normalized composite score 0.0 to 100.0",
    )
    dimension_scores: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default="{}",
        nullable=False,
        comment="Normalized scores per dimension (quality, security, architecture, velocity, documentation)",
    )
    verdict: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="ready, ready_with_warnings, not_ready",
    )
    blockers: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        server_default="[]",
        nullable=False,
        comment="Blocking issues preventing deployment/release",
    )
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        server_default="[]",
        nullable=False,
        comment="Non-blocking recommendations and cautions",
    )
    positive_indicators: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        server_default="[]",
        nullable=False,
        comment="Positive architecture and health signals observed",
    )
    rubric_version: Mapped[str] = mapped_column(
        String(32),
        default="1.0",
        server_default="1.0",
        nullable=False,
    )
    evaluated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship(lazy="selectin")
    project: Mapped[Project] = relationship(lazy="selectin")
    snapshot: Mapped[ProjectSnapshot | None] = relationship(lazy="selectin")
    evaluator: Mapped[User | None] = relationship(lazy="selectin")
