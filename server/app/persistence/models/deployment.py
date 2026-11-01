"""Deployment Incident persistence models for Deployment Diagnosis (docs/01 CAP-07, docs/03 §3.4)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
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
    from app.persistence.models.project import Project
    from app.persistence.models.user import User
    from app.persistence.models.workspace import Workspace


class DeploymentIncident(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """A past or active deployment failure, root cause diagnosis, and resolution playbook."""

    __tablename__ = "deployment_incidents"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "fingerprint",
            name="uq_deployment_incidents_project_fingerprint",
        ),
        Index(
            "ix_deployment_incidents_workspace_project",
            "workspace_id",
            "project_id",
        ),
        Index(
            "ix_deployment_incidents_project_fingerprint",
            "project_id",
            "fingerprint",
        ),
        Index(
            "ix_deployment_incidents_project_env",
            "project_id",
            "environment",
        ),
        Index(
            "ix_deployment_incidents_project_category",
            "project_id",
            "failure_category",
        ),
        Index(
            "ix_deployment_incidents_project_last_seen",
            "project_id",
            "last_seen_at",
        ),
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
    fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Deterministic SHA-256 hash of normalized deployment failure signature",
    )
    summary: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Concise summary of the deployment failure",
    )
    probable_cause: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Synthesized or deduced probable root cause of the incident",
    )
    resolution: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Documented remediation, resolution steps, or playbook",
    )
    error_signature: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Normalized stack trace, build error, or failure log frame",
    )
    environment: Mapped[str] = mapped_column(
        String(32),
        server_default="production",
        nullable=False,
        comment="Target deployment environment (production, staging, preview, etc.)",
    )
    service_name: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Affected service name if multi-service (e.g. web, worker, client)",
    )
    failure_category: Mapped[str] = mapped_column(
        String(64),
        server_default="unhandled_exception",
        nullable=False,
        comment="Classification (missing_env_var, database_migration_failed, etc.)",
    )
    log_snippet: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Redacted log excerpt containing the crucial failure frames (never secrets)",
    )
    report_object_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Optional S3/R2 object storage key for larger diagnostic payloads",
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="UTC timestamp when the incident was marked resolved",
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User UUID who verified or documented the resolution",
    )
    occurrence_count: Mapped[int] = mapped_column(
        Integer,
        server_default="1",
        nullable=False,
        comment="Number of times this deployment failure has recurred",
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="UTC timestamp when this failure fingerprint was most recently observed",
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        server_default="{}",
        nullable=False,
        comment="Schemaless details: referenced env vars, code paths, log line numbers, tags",
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship("Workspace", lazy="raise")
    project: Mapped[Project] = relationship("Project", lazy="raise")
    resolver: Mapped[User | None] = relationship("User", lazy="raise")
