"""Living Documentation persistence models for doc drift detection and update proposals (docs/01 CAP-04, docs/03 §3.4)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
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
    from app.persistence.models.brain import ProjectFile
    from app.persistence.models.project import Project
    from app.persistence.models.workspace import Workspace


class DocumentationRecord(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """A tracked project documentation file (e.g. README.md, API specs, architecture guides)."""

    __tablename__ = "documentation_records"
    __table_args__ = (
        UniqueConstraint("project_id", "path", name="uq_doc_records_project_path"),
        Index("ix_documentation_records_workspace_project", "workspace_id", "project_id"),
        Index("ix_documentation_records_project_kind", "project_id", "kind"),
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
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="SET NULL"),
        nullable=True,
    )
    path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="Relative path in repo e.g. README.md or docs/api.md",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(
        String(32),
        default="other",
        server_default="other",
        nullable=False,
        comment="Classification: readme, api, architecture, tutorial, changelog, other",
    )
    current_version_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash of documentation content when last analyzed",
    )
    content_snapshot: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Cached content or parsed section excerpt",
    )
    extracted_symbols: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        server_default="[]",
        nullable=False,
        comment="Extracted route patterns, symbol keys, and config mentions",
    )
    last_parsed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship(lazy="selectin")
    project: Mapped[Project] = relationship(lazy="selectin")
    file: Mapped[ProjectFile | None] = relationship(lazy="selectin")
    drift_items: Mapped[list[DocDriftItem]] = relationship(
        back_populates="documentation_record",
        cascade="all, delete-orphan",
        order_by="desc(DocDriftItem.created_at)",
        lazy="selectin",
    )


class DocDriftItem(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """An identified discrepancy between project code and a documentation record."""

    __tablename__ = "doc_drift_items"
    __table_args__ = (
        Index("ix_doc_drift_items_workspace_project", "workspace_id", "project_id"),
        Index("ix_doc_drift_items_record_status", "documentation_record_id", "status"),
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
    documentation_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documentation_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Drift type: undocumented_route, removed_route, changed_signature, stale_section, missing_symbol",
    )
    target_symbol_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Key of code symbol associated with drift",
    )
    target_route_path: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="HTTP route path e.g. /api/v1/projects/{pid}/bugs",
    )
    explanation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed description of what code element is missing, renamed, or stale in docs",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="detected",
        server_default="detected",
        nullable=False,
        comment="Lifecycle status: detected, patch_proposed, resolved, dismissed",
    )
    proposal: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Proposed documentation patch or Markdown addition (gated for approval)",
    )

    # Relationships
    documentation_record: Mapped[DocumentationRecord] = relationship(back_populates="drift_items")
    workspace: Mapped[Workspace] = relationship(lazy="selectin")
    project: Mapped[Project] = relationship(lazy="selectin")
