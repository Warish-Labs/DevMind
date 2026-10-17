"""Consent records persistence model (docs/03 §3.5, docs/07 §7)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
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


class ConsentRecord(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Source-transmission and indexing consent record (docs/03 §3.5, docs/07 §7)."""

    __tablename__ = "consent_records"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('snippet_transmission', 'cloud_index', 'llm_processing')",
            name="ck_consent_records_scope",
        ),
        CheckConstraint(
            "granted_for IN ('single_request', 'project')",
            name="ck_consent_records_granted_for",
        ),
        Index("ix_consent_records_project_scope", "project_id", "scope"),
        Index("ix_consent_records_workspace_id", "workspace_id"),
        Index("ix_consent_records_user_id", "user_id"),
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
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    scope: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Consent scope: snippet_transmission | cloud_index | llm_processing",
    )
    provider_ids: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
        server_default="{}",
        comment="Allowed AI/embedding provider IDs (e.g. ['anthropic', 'openai'])",
    )
    data_categories: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
        server_default="{}",
        comment="Allowed data categories (e.g. ['code_snippets', 'ast_metadata'])",
    )
    granted_for: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="project",
        server_default="project",
        comment="single_request | project",
    )
    policy_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="1.0",
        server_default="1.0",
        comment="Privacy policy version presented at consent grant",
    )
    preview_hash: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="Cryptographic SHA-256 hash of consent preview content",
    )

    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship("Workspace")
    project: Mapped[Project] = relationship("Project")
    user: Mapped[User] = relationship("User")

    def is_active(self, now: datetime | None = None) -> bool:
        """Determines whether consent is currently valid (not revoked and not expired)."""
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None:
            current = now or datetime.now(UTC)
            return self.expires_at > current
        return True
