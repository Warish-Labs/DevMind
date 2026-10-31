"""Bug Memory persistence models for recurring bug tracking and resolution memory (docs/01 CAP-03, docs/03 §3.4)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
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
    from app.persistence.models.brain import Finding
    from app.persistence.models.project import Project
    from app.persistence.models.user import User
    from app.persistence.models.workspace import Workspace


class BugRecord(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """An identified, normalized bug or recurring error trace within a project."""

    __tablename__ = "bug_records"
    __table_args__ = (
        UniqueConstraint("project_id", "fingerprint", name="uq_bug_records_project_fingerprint"),
        Index("ix_bug_records_workspace_project", "workspace_id", "project_id"),
        Index("ix_bug_records_project_fingerprint", "project_id", "fingerprint"),
        Index("ix_bug_records_project_module_hint", "project_id", "module_hint"),
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
        comment="Deterministic SHA-256 hash of normalized error signature",
    )
    error_signature: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Normalized error type and canonical stack frames",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    module_hint: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Primary application module extracted from stack trace",
    )
    raw_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Sanitized original error text / stack snippet",
    )
    occurrence_count: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
        nullable=False,
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship(lazy="selectin")
    project: Mapped[Project] = relationship(lazy="selectin")
    resolutions: Mapped[list[BugResolution]] = relationship(
        back_populates="bug_record",
        cascade="all, delete-orphan",
        order_by="desc(BugResolution.created_at)",
        lazy="selectin",
    )


class BugResolution(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Documented root cause, fix summary, and affected files for a resolved BugRecord."""

    __tablename__ = "bug_resolutions"
    __table_args__ = (
        Index("ix_bug_resolutions_bug_record_id", "bug_record_id"),
        Index("ix_bug_resolutions_finding_id", "finding_id"),
    )

    bug_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bug_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    cause: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Root cause analysis of the bug",
    )
    fix_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Summary of the code modification or architectural fix applied",
    )
    files: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        server_default="[]",
        nullable=False,
        comment="List of changed file paths and symbol context",
    )
    finding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="SET NULL"),
        nullable=True,
        comment="Optional linked finding if resolved via finding remediation",
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    bug_record: Mapped[BugRecord] = relationship(back_populates="resolutions")
    finding: Mapped[Finding | None] = relationship(lazy="selectin")
    resolver: Mapped[User | None] = relationship(lazy="selectin")
