"""Embedding spaces schema for vector dimension and model lifecycle (docs/03 §3.2, docs/04 §10, docs/11 M5-06).

Revision ID: 0006_embedding_spaces
Revises: 0005_code_chunks
Create Date: 2026-10-17 17:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_embedding_spaces"
down_revision: str | None = "0005_code_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "embedding_spaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="building", nullable=False),
        sa.Column("config_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "provider_id",
            "model_id",
            "dimension",
            name="uq_embedding_spaces_provider_model_dim",
        ),
        sa.CheckConstraint(
            "status IN ('building', 'active', 'deprecated')",
            name="ck_embedding_spaces_status",
        ),
        sa.CheckConstraint("dimension > 0", name="ck_embedding_spaces_dimension"),
    )

    op.create_index("ix_embedding_spaces_status", "embedding_spaces", ["status"], unique=False)
    op.create_index(
        "ix_embedding_spaces_provider_model",
        "embedding_spaces",
        ["provider_id", "model_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_embedding_spaces_provider_model", table_name="embedding_spaces")
    op.drop_index("ix_embedding_spaces_status", table_name="embedding_spaces")
    op.drop_table("embedding_spaces")
