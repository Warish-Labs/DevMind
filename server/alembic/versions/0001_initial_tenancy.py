"""Initial tenancy, user identity, audit, and usage schema.

Revision ID: 0001_initial_tenancy
Revises:
Create Date: 2026-10-16 19:30:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_tenancy"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("clerk_user_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("clerk_user_id", name="uq_users_clerk_user_id"),
    )
    op.create_index("ix_users_clerk_user_id", "users", ["clerk_user_id"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=False)

    # 2. workspaces
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="personal"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_workspaces_created_by", ondelete="SET NULL"
        ),
        sa.UniqueConstraint("slug", name="uq_workspaces_slug"),
        sa.CheckConstraint("kind IN ('personal', 'team')", name="ck_workspaces_kind"),
    )
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"], unique=True)

    # 3. workspace_memberships
    op.create_table(
        "workspace_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="member"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_workspace_memberships_workspace_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_workspace_memberships_user_id", ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "workspace_id", "user_id", name="uq_workspace_memberships_workspace_user"
        ),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'member', 'viewer')", name="ck_workspace_memberships_role"
        ),
    )
    op.create_index(
        "ix_workspace_memberships_workspace_id", "workspace_memberships", ["workspace_id"]
    )
    op.create_index("ix_workspace_memberships_user_id", "workspace_memberships", ["user_id"])

    # 4. projects
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("visibility", sa.String(length=32), nullable=False, server_default="workspace"),
        sa.Column(
            "sync_mode", sa.String(length=32), nullable=False, server_default="metadata_only"
        ),
        sa.Column("source_kind", sa.String(length=32), nullable=False, server_default="local"),
        sa.Column("primary_language", sa.String(length=64), nullable=True),
        sa.Column("default_branch", sa.String(length=128), nullable=False, server_default="main"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name="fk_projects_workspace_id", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_projects_workspace_slug"),
        sa.CheckConstraint("visibility IN ('workspace', 'private')", name="ck_projects_visibility"),
        sa.CheckConstraint(
            "sync_mode IN ('metadata_only', 'indexed')", name="ck_projects_sync_mode"
        ),
        sa.CheckConstraint("source_kind IN ('local', 'github')", name="ck_projects_source_kind"),
    )
    op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"])

    # 5. project_memberships
    op.create_table(
        "project_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="contributor"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_memberships_project_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_project_memberships_user_id", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_memberships_project_user"),
        sa.CheckConstraint(
            "role IN ('maintainer', 'contributor', 'viewer')", name="ck_project_memberships_role"
        ),
    )
    op.create_index("ix_project_memberships_project_id", "project_memberships", ["project_id"])
    op.create_index("ix_project_memberships_user_id", "project_memberships", ["user_id"])

    # 6. audit_events
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_kind", sa.String(length=32), nullable=False, server_default="user"),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_kind", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_audit_events_workspace_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "actor_kind IN ('user', 'system', 'extension', 'agent')",
            name="ck_audit_events_actor_kind",
        ),
    )
    op.create_index("ix_audit_events_workspace_id", "audit_events", ["workspace_id"])
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])
    op.create_index(
        "ix_audit_events_workspace_created", "audit_events", ["workspace_id", "created_at"]
    )

    # 7. usage_records
    op.create_table(
        "usage_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("llm_task", sa.String(length=64), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cost_units", sa.Integer(), server_default="0", nullable=False),
        sa.Column("latency_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False, server_default="success"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_usage_records_workspace_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_usage_records_project_id", ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "outcome IN ('success', 'failure', 'cached', 'timeout')",
            name="ck_usage_records_outcome",
        ),
    )
    op.create_index("ix_usage_records_workspace_id", "usage_records", ["workspace_id"])
    op.create_index("ix_usage_records_project_id", "usage_records", ["project_id"])
    op.create_index("ix_usage_records_job_id", "usage_records", ["job_id"])
    op.create_index(
        "ix_usage_records_workspace_created", "usage_records", ["workspace_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("usage_records")
    op.drop_table("audit_events")
    op.drop_table("project_memberships")
    op.drop_table("projects")
    op.drop_table("workspace_memberships")
    op.drop_table("workspaces")
    op.drop_table("users")
