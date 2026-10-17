"""Chunk embeddings schema with pgvector and per-space HNSW vector index (docs/03 §3.2, docs/04 §9, docs/11 M5-07).

Revision ID: 0007_chunk_embeddings
Revises: 0006_embedding_spaces
Create Date: 2026-10-17 17:15:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.persistence.models.vector import PGVector

# revision identifiers, used by Alembic.
revision: str = "0007_chunk_embeddings"
down_revision: str | None = "0006_embedding_spaces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Ensure vector extension is available
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table(
        "chunk_embeddings",
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("space_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding", PGVector(64), nullable=False),
        sa.Column(
            "embedded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("chunk_id", "space_id", name="pk_chunk_embeddings"),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["code_chunks.id"],
            name="fk_chunk_embeddings_chunk_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["space_id"],
            ["embedding_spaces.id"],
            name="fk_chunk_embeddings_space_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_chunk_embeddings_project_id",
            ondelete="CASCADE",
        ),
    )

    op.create_index(
        "ix_chunk_embeddings_project_id",
        "chunk_embeddings",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_chunk_embeddings_space_id",
        "chunk_embeddings",
        ["space_id"],
        unique=False,
    )

    # Per-space HNSW cosine distance index (docs/03 §3.2, docs/04 §9)
    op.execute(
        "CREATE INDEX ix_chunk_embeddings_hnsw ON chunk_embeddings USING hnsw (embedding vector_cosine_ops);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunk_embeddings_hnsw;")
    op.drop_index("ix_chunk_embeddings_space_id", table_name="chunk_embeddings")
    op.drop_index("ix_chunk_embeddings_project_id", table_name="chunk_embeddings")
    op.drop_table("chunk_embeddings")
