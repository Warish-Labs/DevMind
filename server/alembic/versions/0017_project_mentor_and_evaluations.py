"""Project Mentor and Evaluation schema for tasks, dependencies, and health evaluations (docs/01 CAP-08, CAP-09, docs/03 §3.6, §3.7).

Revision ID: 0017_project_mentor_and_evaluations
Revises: 0016_living_documentation
Create Date: 2026-10-31 15:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017_project_mentor_and_evaluations"
down_revision: str | None = "0016_living_documentation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. project_tasks table
    op.create_table(
        "project_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), server_default="open", nullable=False),
        sa.Column("priority", sa.String(32), server_default="medium", nullable=False),
        sa.Column("source", sa.String(32), server_default="user", nullable=False),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_project_tasks_workspace_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_tasks_project_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["findings.id"],
            name="fk_project_tasks_finding_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_tasks"),
    )
    op.create_index(
        "ix_project_tasks_workspace_project",
        "project_tasks",
        ["workspace_id", "project_id"],
    )
    op.create_index(
        "ix_project_tasks_status",
        "project_tasks",
        ["project_id", "status"],
    )
    op.create_index(
        "ix_project_tasks_priority",
        "project_tasks",
        ["project_id", "priority"],
    )
    op.create_index(
        "ix_project_tasks_finding_id",
        "project_tasks",
        ["finding_id"],
    )

    # 2. task_dependencies table
    op.create_table(
        "task_dependencies",
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("depends_on_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["project_tasks.id"],
            name="fk_task_dependencies_task_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["depends_on_task_id"],
            ["project_tasks.id"],
            name="fk_task_dependencies_depends_on_task_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("task_id", "depends_on_task_id", name="pk_task_dependencies"),
    )
    op.create_index(
        "ix_task_dependencies_depends_on",
        "task_dependencies",
        ["depends_on_task_id"],
    )

    # 3. project_evaluations table
    op.create_table(
        "project_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column(
            "dimension_scores",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("verdict", sa.String(32), nullable=False),
        sa.Column(
            "blockers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "warnings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "positive_indicators",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("rubric_version", sa.String(32), server_default="1.0", nullable=False),
        sa.Column("evaluated_by", postgresql.UUID(as_uuid=True), nullable=True),
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
            name="fk_project_evaluations_workspace_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_evaluations_project_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["project_snapshots.id"],
            name="fk_project_evaluations_snapshot_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["evaluated_by"],
            ["users.id"],
            name="fk_project_evaluations_evaluated_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_evaluations"),
    )
    op.create_index(
        "ix_project_evaluations_project",
        "project_evaluations",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_project_evaluations_workspace",
        "project_evaluations",
        ["workspace_id"],
    )
    op.create_index(
        "ix_project_evaluations_snapshot_id",
        "project_evaluations",
        ["snapshot_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_evaluations_snapshot_id", table_name="project_evaluations")
    op.drop_index("ix_project_evaluations_workspace", table_name="project_evaluations")
    op.drop_index("ix_project_evaluations_project", table_name="project_evaluations")
    op.drop_table("project_evaluations")

    op.drop_index("ix_task_dependencies_depends_on", table_name="task_dependencies")
    op.drop_table("task_dependencies")

    op.drop_index("ix_project_tasks_finding_id", table_name="project_tasks")
    op.drop_index("ix_project_tasks_priority", table_name="project_tasks")
    op.drop_index("ix_project_tasks_status", table_name="project_tasks")
    op.drop_index("ix_project_tasks_workspace_project", table_name="project_tasks")
    op.drop_table("project_tasks")
