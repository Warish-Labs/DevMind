"""Retention policy models for workspace and project data expiration (docs/03 §3.1, docs/07 §9)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.models.base import (
    Base,
    TimestampMixin,
    UUID7PrimaryKeyMixin,
)

if TYPE_CHECKING:
    from app.persistence.models.project import Project
    from app.persistence.models.workspace import Workspace


class RetentionPolicy(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Configurable retention window per data category for a workspace or specific project override."""

    __tablename__ = "retention_policies"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "project_id",
            "kind",
            name="uq_retention_policies_target_kind",
        ),
        CheckConstraint("days >= 1", name="ck_retention_policies_days_positive"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    workspace: Mapped[Workspace] = relationship("Workspace")
    project: Mapped[Project | None] = relationship("Project")
