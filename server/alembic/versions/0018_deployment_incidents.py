"""Deployment Incident schema for Deployment Diagnosis (docs/01 CAP-07, docs/03 §3.4).

Revision ID: 0018_deployment_incidents
Revises: 0017_project_mentor_and_evaluations
Create Date: 2026-11-01 12:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018_deployment_incidents"
down_revision: str | None = "0017_project_mentor_and_evaluations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "deployment_incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("summary", sa.String(255), nullable=False),
        sa.Column("probable_cause", sa.Text(), nullable=False),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("error_signature", sa.Text(), nullable=False),
        sa.Column("environment", sa.String(32), server_default="production", nullable=False),
        sa.Column("service_name", sa.String(64), nullable=True),
        sa.Column(
            "failure_category",
            sa.String(64),
            server_default="unhandled_exception",
            nullable=False,
        ),
        sa.Column("log_snippet", sa.Text(), nullable=True),
        sa.Column("report_object_key", sa.String(255), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
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
        sa.PrimaryKeyConstraint("id", name="pk_deployment_incidents"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_deployment_incidents_workspace_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_deployment_incidents_project_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"],
            ["users.id"],
            name="fk_deployment_incidents_resolved_by",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "project_id",
            "fingerprint",
            name="uq_deployment_incidents_project_fingerprint",
        ),
    )

    op.create_index(
        "ix_deployment_incidents_workspace_project",
        "deployment_incidents",
        ["workspace_id", "project_id"],
        unique=False,
    )
    op.create_index(
        "ix_deployment_incidents_project_fingerprint",
        "deployment_incidents",
        ["project_id", "fingerprint"],
        unique=False,
    )
    op.create_index(
        "ix_deployment_incidents_project_env",
        "deployment_incidents",
        ["project_id", "environment"],
        unique=False,
    )
    op.create_index(
        "ix_deployment_incidents_project_category",
        "deployment_incidents",
        ["project_id", "failure_category"],
        unique=False,
    )
    op.create_index(
        "ix_deployment_incidents_project_last_seen",
        "deployment_incidents",
        ["project_id", "last_seen_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_deployment_incidents_project_last_seen",
        table_name="deployment_incidents",
    )
    op.drop_index(
        "ix_deployment_incidents_project_category",
        table_name="deployment_incidents",
    )
    op.drop_index(
        "ix_deployment_incidents_project_env",
        table_name="deployment_incidents",
    )
    op.drop_index(
        "ix_deployment_incidents_project_fingerprint",
        table_name="deployment_incidents",
    )
    op.drop_index(
        "ix_deployment_incidents_workspace_project",
        table_name="deployment_incidents",
    )
    op.drop_table("deployment_incidents")
