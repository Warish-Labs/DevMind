"""GitHub repositories and pull requests mirror tables (docs/03 §3.5, docs/11 M11).

Revision ID: 0011_github_repositories_and_prs
Revises: 0010_retention_policies
Create Date: 2026-10-27 18:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_github_repositories_and_prs"
down_revision: str | None = "0010_retention_policies"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. github_repositories table
    op.create_table(
        "github_repositories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("default_branch", sa.String(100), server_default="main", nullable=False),
        sa.Column("external_id", sa.String(64), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_github_repositories"),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["github_connections.id"],
            name="fk_github_repositories_connection_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_github_repositories_project_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("project_id", name="uq_github_repositories_project_id"),
    )

    op.create_index(
        "ix_github_repositories_connection_id",
        "github_repositories",
        ["connection_id"],
    )
    op.create_index(
        "ix_github_repositories_full_name",
        "github_repositories",
        ["full_name"],
    )

    # 2. pull_requests table
    op.create_table(
        "pull_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("author_login", sa.String(255), nullable=False),
        sa.Column("state", sa.String(32), server_default="open", nullable=False),
        sa.Column("head_sha", sa.String(64), nullable=False),
        sa.Column("base_sha", sa.String(64), nullable=False),
        sa.Column("head_ref", sa.String(255), nullable=True),
        sa.Column("base_ref", sa.String(255), nullable=True),
        sa.Column("diff_url", sa.String(500), nullable=True),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pull_requests"),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["github_repositories.id"],
            name="fk_pull_requests_repository_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "repository_id",
            "number",
            name="uq_pull_requests_repository_number",
        ),
    )

    op.create_index(
        "ix_pull_requests_repository_id",
        "pull_requests",
        ["repository_id"],
    )
    op.create_index(
        "ix_pull_requests_head_sha",
        "pull_requests",
        ["head_sha"],
    )
    op.create_index(
        "ix_pull_requests_repo_state",
        "pull_requests",
        ["repository_id", "state"],
    )


def downgrade() -> None:
    op.drop_index("ix_pull_requests_repo_state", table_name="pull_requests")
    op.drop_index("ix_pull_requests_head_sha", table_name="pull_requests")
    op.drop_index("ix_pull_requests_repository_id", table_name="pull_requests")
    op.drop_table("pull_requests")

    op.drop_index("ix_github_repositories_full_name", table_name="github_repositories")
    op.drop_index("ix_github_repositories_connection_id", table_name="github_repositories")
    op.drop_table("github_repositories")
