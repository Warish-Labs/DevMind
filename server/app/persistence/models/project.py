"""Project and ProjectMembership models (docs/03 §3.1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.models.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    UUID7PrimaryKeyMixin,
)

if TYPE_CHECKING:
    from app.persistence.models.usage import UsageRecord
    from app.persistence.models.user import User
    from app.persistence.models.workspace import Workspace


class Project(Base, UUID7PrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """A codebase or repository boundary within a workspace."""

    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_projects_workspace_slug"),
        CheckConstraint("visibility IN ('workspace', 'private')", name="ck_projects_visibility"),
        CheckConstraint("sync_mode IN ('metadata_only', 'indexed')", name="ck_projects_sync_mode"),
        CheckConstraint("source_kind IN ('local', 'github')", name="ck_projects_source_kind"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="workspace")
    sync_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="metadata_only")
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="local")
    primary_language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    default_branch: Mapped[str] = mapped_column(String(128), nullable=False, default="main")
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="projects")
    memberships: Mapped[list[ProjectMembership]] = relationship(
        "ProjectMembership",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    usage_records: Mapped[list[UsageRecord]] = relationship(
        "UsageRecord",
        back_populates="project",
    )


class ProjectMembership(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Explicit per-project membership override (docs/03 §4.1)."""

    __tablename__ = "project_memberships"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_memberships_project_user"),
        CheckConstraint(
            "role IN ('maintainer', 'contributor', 'viewer')",
            name="ck_project_memberships_role",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="contributor")

    # Relationships
    project: Mapped[Project] = relationship("Project", back_populates="memberships")
    user: Mapped[User] = relationship("User", back_populates="project_memberships")
