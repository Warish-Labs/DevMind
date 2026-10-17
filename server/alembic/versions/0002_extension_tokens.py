"""Extension registrations and extension tokens schema (ADR-012, docs/03 §3.1).

Revision ID: 0002_extension_tokens
Revises: 0001_initial_tenancy
Create Date: 2026-10-17 11:45:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_extension_tokens"
down_revision: str | None = "0001_initial_tenancy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. extension_registrations (docs/03 §3.1)
    op.create_table(
        "extension_registrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("platform", sa.String(length=64), nullable=False),
        sa.Column("extension_version", sa.String(length=64), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_extension_registrations_user_id", ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_extension_registrations_user_id", "extension_registrations", ["user_id"], unique=False
    )

    # 2. extension_tokens (docs/03 §3.1, ADR-012)
    op.create_table(
        "extension_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("registration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.String(length=255), nullable=False, server_default="project:sync"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_from", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["registration_id"],
            ["extension_registrations.id"],
            name="fk_extension_tokens_registration_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["rotated_from"],
            ["extension_tokens.id"],
            name="fk_extension_tokens_rotated_from",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("token_hash", name="uq_extension_tokens_token_hash"),
    )
    op.create_index(
        "ix_extension_tokens_registration_id",
        "extension_tokens",
        ["registration_id"],
        unique=False,
    )
    op.create_index(
        "ix_extension_tokens_token_hash", "extension_tokens", ["token_hash"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_extension_tokens_token_hash", table_name="extension_tokens")
    op.drop_index("ix_extension_tokens_registration_id", table_name="extension_tokens")
    op.drop_table("extension_tokens")

    op.drop_index("ix_extension_registrations_user_id", table_name="extension_registrations")
    op.drop_table("extension_registrations")
