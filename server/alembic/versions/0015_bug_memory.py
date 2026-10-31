"""Bug Memory schema for error signatures, recurring bug tracking, and resolutions (docs/01 CAP-03, docs/03 §3.4, docs/05 §6.6).

Revision ID: 0015_bug_memory
Revises: 0014_workspace_invitations
Create Date: 2026-10-31 06:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015_bug_memory"
down_revision: str | None = "0014_workspace_invitations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. bug_records table
    op.create_table(
        "bug_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("error_signature", sa.Text(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("module_hint", sa.String(255), nullable=True),
        sa.Column("raw_error", sa.Text(), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
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
            name="fk_bug_records_workspace_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_bug_records_project_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bug_records"),
        sa.UniqueConstraint("project_id", "fingerprint", name="uq_bug_records_project_fingerprint"),
    )
    op.create_index(
        "ix_bug_records_workspace_project",
        "bug_records",
        ["workspace_id", "project_id"],
        unique=False,
    )
    op.create_index(
        "ix_bug_records_project_fingerprint",
        "bug_records",
        ["project_id", "fingerprint"],
        unique=False,
    )
    op.create_index(
        "ix_bug_records_project_module_hint",
        "bug_records",
        ["project_id", "module_hint"],
        unique=False,
    )

    # 2. bug_resolutions table
    op.create_table(
        "bug_resolutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bug_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cause", sa.Text(), nullable=False),
        sa.Column("fix_summary", sa.Text(), nullable=False),
        sa.Column(
            "files",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
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
            ["bug_record_id"],
            ["bug_records.id"],
            name="fk_bug_resolutions_bug_record_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["findings.id"],
            name="fk_bug_resolutions_finding_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"],
            ["users.id"],
            name="fk_bug_resolutions_resolved_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bug_resolutions"),
    )
    op.create_index(
        "ix_bug_resolutions_bug_record_id",
        "bug_resolutions",
        ["bug_record_id"],
        unique=False,
    )
    op.create_index(
        "ix_bug_resolutions_finding_id",
        "bug_resolutions",
        ["finding_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_bug_resolutions_finding_id", table_name="bug_resolutions")
    op.drop_index("ix_bug_resolutions_bug_record_id", table_name="bug_resolutions")
    op.drop_table("bug_resolutions")

    op.drop_index("ix_bug_records_project_module_hint", table_name="bug_records")
    op.drop_index("ix_bug_records_project_fingerprint", table_name="bug_records")
    op.drop_index("ix_bug_records_workspace_project", table_name="bug_records")
    op.drop_table("bug_records")
