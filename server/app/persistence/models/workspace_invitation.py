"""Workspace invitation persistence model (docs/01 FR-PLT-05, docs/03 §3.1, ADR-014)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.models.base import (
    Base,
    TimestampMixin,
    UUID7PrimaryKeyMixin,
)

if TYPE_CHECKING:
    from app.persistence.models.user import User
    from app.persistence.models.workspace import Workspace


class WorkspaceInvitation(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Pending or accepted invitation for team membership in a workspace."""

    __tablename__ = "workspace_invitations"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'member', 'viewer')",
            name="ck_workspace_invitations_role",
        ),
        UniqueConstraint("token_hash", name="uq_workspace_invitations_token_hash"),
        Index("ix_workspace_invitations_workspace_email", "workspace_id", "email"),
        Index("ix_workspace_invitations_expires_at", "expires_at"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship("Workspace", back_populates="invitations")
    inviter: Mapped[User | None] = relationship("User", foreign_keys=[invited_by])
