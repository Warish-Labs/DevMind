"""Living Documentation schema for documentation records and doc drift detection (docs/01 CAP-04, docs/03 §3.4, docs/05 §6.7).

Revision ID: 0016_living_documentation
Revises: 0015_bug_memory
Create Date: 2026-10-31 07:30:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016_living_documentation"
down_revision: str | None = "0015_bug_memory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. documentation_records table
    op.create_table(
        "documentation_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("path", sa.String(512), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(32), server_default="other", nullable=False),
        sa.Column("current_version_hash", sa.String(64), nullable=False),
        sa.Column("content_snapshot", sa.Text(), nullable=True),
        sa.Column(
            "extracted_symbols",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "last_parsed_at",
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
            name="fk_doc_records_workspace_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_doc_records_project_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["files.id"],
            name="fk_doc_records_file_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_documentation_records"),
        sa.UniqueConstraint("project_id", "path", name="uq_doc_records_project_path"),
    )
    op.create_index(
        "ix_documentation_records_workspace_project",
        "documentation_records",
        ["workspace_id", "project_id"],
        unique=False,
    )
    op.create_index(
        "ix_documentation_records_project_kind",
        "documentation_records",
        ["project_id", "kind"],
        unique=False,
    )

    # 2. doc_drift_items table
    op.create_table(
        "doc_drift_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("documentation_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("target_symbol_key", sa.String(255), nullable=True),
        sa.Column("target_route_path", sa.String(255), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), server_default="detected", nullable=False),
        sa.Column(
            "proposal",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
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
            name="fk_doc_drift_workspace_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_doc_drift_project_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["documentation_record_id"],
            ["documentation_records.id"],
            name="fk_doc_drift_doc_record_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_doc_drift_items"),
    )
    op.create_index(
        "ix_doc_drift_items_workspace_project",
        "doc_drift_items",
        ["workspace_id", "project_id"],
        unique=False,
    )
    op.create_index(
        "ix_doc_drift_items_record_status",
        "doc_drift_items",
        ["documentation_record_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_doc_drift_items_record_status", table_name="doc_drift_items")
    op.drop_index("ix_doc_drift_items_workspace_project", table_name="doc_drift_items")
    op.drop_table("doc_drift_items")

    op.drop_index(
        "ix_documentation_records_project_kind",
        table_name="documentation_records",
    )
    op.drop_index(
        "ix_documentation_records_workspace_project",
        table_name="documentation_records",
    )
    op.drop_table("documentation_records")
