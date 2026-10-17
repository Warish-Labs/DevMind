"""Code chunks schema with tsvector and trigram indices (docs/03 §3.2, docs/04 §4, docs/11 M5-05).

Revision ID: 0005_code_chunks
Revises: 0004_consent_records
Create Date: 2026-10-17 16:30:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_code_chunks"
down_revision: str | None = "0004_consent_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Ensure pg_trgm extension is available for trigram similarity index
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    op.create_table(
        "code_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False),
        sa.Column("redaction_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_code_chunks_workspace_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_code_chunks_project_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_version_id"],
            ["file_versions.id"],
            name="fk_code_chunks_file_version_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["symbol_id"],
            ["code_symbols.id"],
            name="fk_code_chunks_symbol_id",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "file_version_id",
            "start_line",
            "end_line",
            "content_hash",
            name="uq_code_chunks_version_lines_hash",
        ),
        sa.CheckConstraint(
            "start_line >= 1 AND end_line >= start_line",
            name="ck_code_chunks_lines",
        ),
        sa.CheckConstraint(
            "kind IN ('module_prelude', 'function', 'class', 'statement', 'heading', 'window')",
            name="ck_code_chunks_kind",
        ),
    )

    op.create_index("ix_code_chunks_workspace_id", "code_chunks", ["workspace_id"], unique=False)
    op.create_index("ix_code_chunks_project_id", "code_chunks", ["project_id"], unique=False)
    op.create_index(
        "ix_code_chunks_file_version_id", "code_chunks", ["file_version_id"], unique=False
    )
    op.create_index("ix_code_chunks_symbol_id", "code_chunks", ["symbol_id"], unique=False)
    op.create_index(
        "ix_code_chunks_project_current",
        "code_chunks",
        ["project_id", "is_current"],
        unique=False,
    )

    # Full-text tsvector index (GIN)
    op.execute(
        "CREATE INDEX ix_code_chunks_search_tsvector ON code_chunks USING gin (to_tsvector('english', search_text));"
    )

    # Trigram similarity index (GIN)
    op.execute(
        "CREATE INDEX ix_code_chunks_search_trgm ON code_chunks USING gin (search_text gin_trgm_ops);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_code_chunks_search_trgm;")
    op.execute("DROP INDEX IF EXISTS ix_code_chunks_search_tsvector;")
    op.drop_index("ix_code_chunks_project_current", table_name="code_chunks")
    op.drop_index("ix_code_chunks_symbol_id", table_name="code_chunks")
    op.drop_index("ix_code_chunks_file_version_id", table_name="code_chunks")
    op.drop_index("ix_code_chunks_project_id", table_name="code_chunks")
    op.drop_index("ix_code_chunks_workspace_id", table_name="code_chunks")
    op.drop_table("code_chunks")
