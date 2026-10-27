"""GitHub connection and repository persistence models (docs/03 §3.5)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID
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


class GitHubRepositoryBinding(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Linked GitHub repository record bound to a DevMind project (docs/03 §3.5)."""

    __tablename__ = "github_repositories"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_github_repositories_project_id"),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("github_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    default_branch: Mapped[str] = mapped_column(String(100), nullable=False, default="main")
    external_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    connection: Mapped[GitHubConnection] = relationship("GitHubConnection")
    project: Mapped[Project] = relationship("Project")
    pull_requests: Mapped[list[PullRequest]] = relationship(
        "PullRequest",
        back_populates="repository",
        cascade="all, delete-orphan",
    )


class PullRequest(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Mirrored GitHub Pull Request for change-impact analysis and reviews (docs/03 §3.5)."""

    __tablename__ = "pull_requests"
    __table_args__ = (
        UniqueConstraint("repository_id", "number", name="uq_pull_requests_repository_number"),
        Index("ix_pull_requests_repo_state", "repository_id", "state"),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("github_repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author_login: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    head_sha: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    base_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    head_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    base_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    diff_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    repository: Mapped[GitHubRepositoryBinding] = relationship(
        "GitHubRepositoryBinding",
        back_populates="pull_requests",
    )
