"""GitHub connection persistence model for OAuth and App credentials (docs/03 §3.1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects import postgresql
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


class GitHubConnection(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """External GitHub credential grant associated with a workspace and user."""

    __tablename__ = "github_connections"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "user_id",
            "kind",
            name="uq_github_connections_workspace_user_kind",
        ),
        CheckConstraint(
            "kind IN ('oauth', 'app_installation')",
            name="ck_github_connections_kind",
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
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="oauth")
    external_account: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(
        postgresql.ARRAY(String(100)).with_variant(JSON, "sqlite"),
        nullable=False,
        default=list,
    )
    encrypted_credential: Mapped[str] = mapped_column(Text, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship("Workspace")
    user: Mapped[User] = relationship("User")
