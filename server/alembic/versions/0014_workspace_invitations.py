"""Workspace invitations table for team membership onboarding via Resend (docs/01 FR-PLT-05, docs/03 §3.1, ADR-014).

Revision ID: 0014_workspace_invitations
Revises: 0013_pr_analyses
Create Date: 2026-10-30 23:45:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014_workspace_invitations"
down_revision: str | None = "0013_pr_analyses"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), server_default="member", nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
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
            name="fk_workspace_invitations_workspace_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by"],
            ["users.id"],
            name="fk_workspace_invitations_invited_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workspace_invitations"),
        sa.CheckConstraint(
            "role IN ('admin', 'member', 'viewer')",
            name="ck_workspace_invitations_role",
        ),
        sa.UniqueConstraint("token_hash", name="uq_workspace_invitations_token_hash"),
    )
    op.create_index(
        "ix_workspace_invitations_workspace_id",
        "workspace_invitations",
        ["workspace_id"],
        unique=False,
    )
    op.create_index(
        "ix_workspace_invitations_workspace_email",
        "workspace_invitations",
        ["workspace_id", "email"],
        unique=False,
    )
    op.create_index(
        "ix_workspace_invitations_expires_at",
        "workspace_invitations",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_workspace_invitations_expires_at", table_name="workspace_invitations")
    op.drop_index("ix_workspace_invitations_workspace_email", table_name="workspace_invitations")
    op.drop_index("ix_workspace_invitations_workspace_id", table_name="workspace_invitations")
    op.drop_table("workspace_invitations")
