"""Workspace and WorkspaceMembership models for multi-tenant isolation (docs/03 §3.1)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.models.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    UUID7PrimaryKeyMixin,
)

if TYPE_CHECKING:
    from app.persistence.models.audit import AuditEvent
    from app.persistence.models.project import Project
    from app.persistence.models.usage import UsageRecord
    from app.persistence.models.user import User
    from app.persistence.models.workspace_invitation import WorkspaceInvitation


class Workspace(Base, UUID7PrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Tenant container representing an organization or personal boundary."""

    __tablename__ = "workspaces"
    __table_args__ = (CheckConstraint("kind IN ('personal', 'team')", name="ck_workspaces_kind"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="personal")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    memberships: Mapped[list[WorkspaceMembership]] = relationship(
        "WorkspaceMembership",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    projects: Mapped[list[Project]] = relationship(
        "Project",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(
        "AuditEvent",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    invitations: Mapped[list[WorkspaceInvitation]] = relationship(
        "WorkspaceInvitation",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    usage_records: Mapped[list[UsageRecord]] = relationship(
        "UsageRecord",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )


class WorkspaceMembership(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Associates a user with a workspace and an RBAC role."""

    __tablename__ = "workspace_memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_memberships_workspace_user"),
        CheckConstraint(
            "role IN ('owner', 'admin', 'member', 'viewer')",
            name="ck_workspace_memberships_role",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")

    # Relationships
    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="memberships")
    user: Mapped[User] = relationship("User", back_populates="workspace_memberships")
