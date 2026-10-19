"""Retention policies table for configurable data expiration (docs/03 §3.1, docs/07 §9).

Revision ID: 0010_retention_policies
Revises: 0009_agent_runs
Create Date: 2026-10-19 05:15:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_retention_policies"
down_revision: str | None = "0009_agent_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "retention_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("days >= 1", name="ck_retention_policies_days_positive"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "project_id",
            "kind",
            name="uq_retention_policies_target_kind",
        ),
    )
    op.create_index("ix_retention_policies_workspace_id", "retention_policies", ["workspace_id"], unique=False)
    op.create_index("ix_retention_policies_project_id", "retention_policies", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_retention_policies_project_id", table_name="retention_policies")
    op.drop_index("ix_retention_policies_workspace_id", table_name="retention_policies")
    op.drop_table("retention_policies")
