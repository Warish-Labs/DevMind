"""GitHub connections table for direct OAuth and App integration (docs/03 §3.1, docs/11 M11).

Revision ID: 0008_github_connections
Revises: 0007_chunk_embeddings
Create Date: 2026-10-17 18:20:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_github_connections"
down_revision: str | None = "0007_chunk_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "github_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("external_account", sa.String(255), nullable=False),
        sa.Column(
            "scopes",
            postgresql.ARRAY(sa.String(100)).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("encrypted_credential", sa.Text(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_github_connections"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_github_connections_workspace_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_github_connections_user_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "user_id",
            "kind",
            name="uq_github_connections_workspace_user_kind",
        ),
        sa.CheckConstraint(
            "kind IN ('oauth', 'app_installation')",
            name="ck_github_connections_kind",
        ),
    )

    op.create_index(
        "ix_github_connections_workspace_id",
        "github_connections",
        ["workspace_id"],
    )
    op.create_index(
        "ix_github_connections_user_id",
        "github_connections",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_github_connections_user_id", table_name="github_connections")
    op.drop_index("ix_github_connections_workspace_id", table_name="github_connections")
    op.drop_table("github_connections")
