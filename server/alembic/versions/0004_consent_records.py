"""Consent records schema (docs/03 §3.5, docs/07 §7, docs/11 M5-01).

Revision ID: 0004_consent_records
Revises: 0003_project_brain
Create Date: 2026-10-17 14:15:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_consent_records"
down_revision: str | None = "0003_project_brain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "consent_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column(
            "provider_ids",
            postgresql.ARRAY(sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "data_categories",
            postgresql.ARRAY(sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "granted_for",
            sa.String(length=32),
            server_default="project",
            nullable=False,
        ),
        sa.Column(
            "policy_version",
            sa.String(length=64),
            server_default="1.0",
            nullable=False,
        ),
        sa.Column("preview_hash", sa.String(length=128), nullable=True),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_consent_records_workspace_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_consent_records_project_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_consent_records_user_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "scope IN ('snippet_transmission', 'cloud_index', 'llm_processing')",
            name="ck_consent_records_scope",
        ),
        sa.CheckConstraint(
            "granted_for IN ('single_request', 'project')",
            name="ck_consent_records_granted_for",
        ),
    )

    op.create_index(
        "ix_consent_records_project_scope",
        "consent_records",
        ["project_id", "scope"],
    )
    op.create_index(
        "ix_consent_records_workspace_id",
        "consent_records",
        ["workspace_id"],
    )
    op.create_index(
        "ix_consent_records_user_id",
        "consent_records",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_consent_records_user_id", table_name="consent_records")
    op.drop_index("ix_consent_records_workspace_id", table_name="consent_records")
    op.drop_index("ix_consent_records_project_scope", table_name="consent_records")
    op.drop_table("consent_records")
