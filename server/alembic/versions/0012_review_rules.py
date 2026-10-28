"""Review rules table for ReviewBuddy checklist engine (docs/01 CAP-05, docs/05 §6.4, docs/11 M11).

Revision ID: 0012_review_rules
Revises: 0011_github_repositories_and_prs
Create Date: 2026-10-28 12:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012_review_rules"
down_revision: str | None = "0011_github_repositories_and_prs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column(
            "scope_selector",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("check_type", sa.String(50), nullable=False),
        sa.Column(
            "check_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("suggested_fix_template", sa.Text(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_builtin", sa.Boolean(), server_default=sa.text("false"), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_review_rules"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_review_rules_workspace_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_review_rules_project_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("project_id", "rule_id", name="uq_review_rules_project_rule_id"),
        sa.CheckConstraint(
            "category IN ('input_validation', 'error_handling', 'authorization', 'testing', 'documentation', 'quality', 'security', 'other')",
            name="ck_review_rules_category",
        ),
        sa.CheckConstraint(
            "severity IN ('critical', 'high', 'medium', 'low', 'info')",
            name="ck_review_rules_severity",
        ),
    )

    op.create_index(
        "ix_review_rules_workspace_project",
        "review_rules",
        ["workspace_id", "project_id"],
    )
    op.create_index(
        "ix_review_rules_project_enabled",
        "review_rules",
        ["project_id", "is_enabled"],
    )


def downgrade() -> None:
    op.drop_index("ix_review_rules_project_enabled", table_name="review_rules")
    op.drop_index("ix_review_rules_workspace_project", table_name="review_rules")
    op.drop_table("review_rules")
