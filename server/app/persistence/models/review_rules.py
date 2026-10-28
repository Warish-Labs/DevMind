"""Review rule persistence models for ReviewBuddy checklist engine (docs/01 CAP-05, docs/05 §6.4)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
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
    from app.persistence.models.project import Project
    from app.persistence.models.workspace import Workspace


class ReviewRule(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """A project-scoped review rule or built-in checklist rule evaluated on code diffs."""

    __tablename__ = "review_rules"
    __table_args__ = (
        UniqueConstraint("project_id", "rule_id", name="uq_review_rules_project_rule_id"),
        CheckConstraint(
            "category IN ('input_validation', 'error_handling', 'authorization', 'testing', 'documentation', 'quality', 'security', 'other')",
            name="ck_review_rules_category",
        ),
        CheckConstraint(
            "severity IN ('critical', 'high', 'medium', 'low', 'info')",
            name="ck_review_rules_severity",
        ),
        Index("ix_review_rules_workspace_project", "workspace_id", "project_id"),
        Index("ix_review_rules_project_enabled", "project_id", "is_enabled"),
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
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_selector: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default="{}",
        nullable=False,
    )
    check_type: Mapped[str] = mapped_column(String(50), nullable=False)
    check_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default="{}",
        nullable=False,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_fix_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    is_builtin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    workspace: Mapped[Workspace] = relationship("Workspace")
    project: Mapped[Project] = relationship("Project")
