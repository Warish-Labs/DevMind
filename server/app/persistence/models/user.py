"""User model mapping Clerk identity to DevMind entities (docs/03 §3.1)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.models.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    UUID7PrimaryKeyMixin,
)

if TYPE_CHECKING:
    from app.persistence.models.project import ProjectMembership
    from app.persistence.models.workspace import WorkspaceMembership


class User(Base, UUID7PrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """User account mapped to an external Clerk identity."""

    __tablename__ = "users"

    clerk_user_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    display_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    workspace_memberships: Mapped[list[WorkspaceMembership]] = relationship(
        "WorkspaceMembership",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    project_memberships: Mapped[list[ProjectMembership]] = relationship(
        "ProjectMembership",
        back_populates="user",
        cascade="all, delete-orphan",
    )
