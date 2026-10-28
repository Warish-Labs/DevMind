"""PR analyses table for PRAgent change impact and PR intelligence (docs/01 CAP-06, docs/03 §3.5, docs/05 §6.5).

Revision ID: 0013_pr_analyses
Revises: 0012_review_rules
Create Date: 2026-10-28 17:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013_pr_analyses"
down_revision: str | None = "0012_review_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pr_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pull_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("head_sha", sa.String(64), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "risk_level",
            sa.String(20),
            server_default="low",
            nullable=False,
        ),
        sa.Column(
            "summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "impact",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pull_request_id"],
            ["pull_requests.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["analysis_jobs.id"],
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')",
            name="ck_pr_analyses_risk_level",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "pull_request_id",
            "head_sha",
            "job_id",
            name="uq_pr_analyses_pr_head_job",
        ),
    )

    op.create_index(
        "ix_pr_analyses_workspace_project",
        "pr_analyses",
        ["workspace_id", "project_id"],
    )
    op.create_index(
        "ix_pr_analyses_pull_request_id",
        "pr_analyses",
        ["pull_request_id"],
    )
    op.create_index(
        "ix_pr_analyses_head_sha",
        "pr_analyses",
        ["head_sha"],
    )


def downgrade() -> None:
    op.drop_index("ix_pr_analyses_head_sha", table_name="pr_analyses")
    op.drop_index("ix_pr_analyses_pull_request_id", table_name="pr_analyses")
    op.drop_index("ix_pr_analyses_workspace_project", table_name="pr_analyses")
    op.drop_table("pr_analyses")
