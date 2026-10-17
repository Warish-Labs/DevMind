"""Project Brain schema: files, versions, snapshots, symbols, relationships, jobs, findings (docs/03 §3.2-3.4, docs/11 M4-01).

Revision ID: 0003_project_brain
Revises: 0002_extension_tokens
Create Date: 2026-10-17 12:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_project_brain"
down_revision: str | None = "0002_extension_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. scan_runs (docs/03 §3.3)
    op.create_table(
        "scan_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("origin", sa.String(length=32), nullable=False, server_default="extension"),
        sa.Column("registration_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rules_version", sa.String(length=64), nullable=True),
        sa.Column(
            "stats",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_scan_runs_project_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["registration_id"],
            ["extension_registrations.id"],
            name="fk_scan_runs_registration_id",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "origin IN ('extension', 'cloud_fetch', 'github_pr')",
            name="ck_scan_runs_origin",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'cancelled')",
            name="ck_scan_runs_status",
        ),
        sa.UniqueConstraint(
            "project_id", "idempotency_key", name="uq_scan_runs_project_idempotency_key"
        ),
    )
    op.create_index("ix_scan_runs_project_id", "scan_runs", ["project_id"], unique=False)

    # 2. local_workspace_registrations (docs/03 §3.1)
    op.create_table(
        "local_workspace_registrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("registration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_label", sa.String(length=255), nullable=False),
        sa.Column("root_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("last_scan_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_local_workspace_registrations_project_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["registration_id"],
            ["extension_registrations.id"],
            name="fk_local_workspace_registrations_registration_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["last_scan_run_id"],
            ["scan_runs.id"],
            name="fk_local_workspace_registrations_last_scan_run_id",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "project_id",
            "registration_id",
            "root_fingerprint",
            name="uq_local_workspace_reg_triple",
        ),
    )
    op.create_index(
        "ix_local_workspace_registrations_project_id",
        "local_workspace_registrations",
        ["project_id"],
        unique=False,
    )

    # 3. files (docs/03 §3.2)
    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("language", sa.String(length=64), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_files_project_id", ondelete="CASCADE"
        ),
        sa.CheckConstraint("tier IN (1, 2, 3)", name="ck_files_tier"),
        sa.UniqueConstraint("project_id", "path", name="uq_files_project_path"),
    )
    op.create_index("ix_files_project_id", "files", ["project_id"], unique=False)
    op.create_index("ix_files_path", "files", ["path"], unique=False)

    # 4. file_versions (docs/03 §3.2)
    op.create_table(
        "file_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("line_count", sa.Integer(), nullable=False),
        sa.Column("scan_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("origin", sa.String(length=32), nullable=False, server_default="extension"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["file_id"], ["files.id"], name="fk_file_versions_file_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_file_versions_project_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["scan_run_id"],
            ["scan_runs.id"],
            name="fk_file_versions_scan_run_id",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint("origin IN ('extension', 'github')", name="ck_file_versions_origin"),
        sa.UniqueConstraint("file_id", "content_hash", name="uq_file_versions_file_content_hash"),
    )
    op.create_index(
        "ix_file_versions_project_content_hash",
        "file_versions",
        ["project_id", "content_hash"],
        unique=False,
    )

    # Add deferred FK from files.current_version_id to file_versions.id
    op.create_foreign_key(
        "fk_files_current_version_id",
        "files",
        "file_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 5. project_snapshots (docs/03 §3.2)
    op.create_table(
        "project_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="scan"),
        sa.Column("ref", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_snapshots_project_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "kind IN ('scan', 'commit', 'manual')", name="ck_project_snapshots_kind"
        ),
    )
    op.create_index(
        "ix_project_snapshots_project_created",
        "project_snapshots",
        ["project_id", "created_at"],
        unique=False,
    )

    # 6. snapshot_files (docs/03 §3.2)
    op.create_table(
        "snapshot_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["project_snapshots.id"],
            name="fk_snapshot_files_snapshot_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"], ["files.id"], name="fk_snapshot_files_file_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["file_version_id"],
            ["file_versions.id"],
            name="fk_snapshot_files_file_version_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("snapshot_id", "file_id", name="uq_snapshot_files_snapshot_file"),
    )
    op.create_index(
        "ix_snapshot_files_snapshot_id", "snapshot_files", ["snapshot_id"], unique=False
    )
    op.create_index(
        "ix_snapshot_files_file_version_id", "snapshot_files", ["file_version_id"], unique=False
    )

    # 7. code_symbols (docs/03 §3.2)
    op.create_table(
        "code_symbols",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol_key", sa.String(length=512), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("qualified_name", sa.String(length=512), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column(
            "framework_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("is_current", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_code_symbols_project_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["file_version_id"],
            ["file_versions.id"],
            name="fk_code_symbols_file_version_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "kind IN ('function', 'method', 'class', 'route_handler', 'server_action', 'model', 'constant', 'module')",
            name="ck_code_symbols_kind",
        ),
    )
    op.create_index(
        "ix_code_symbols_project_symbol_key",
        "code_symbols",
        ["project_id", "symbol_key"],
        unique=False,
    )
    op.create_index(
        "ix_code_symbols_project_name", "code_symbols", ["project_id", "name"], unique=False
    )
    op.create_index(
        "ix_code_symbols_project_current",
        "code_symbols",
        ["project_id", "is_current"],
        unique=False,
    )

    # 8. code_relationships (docs/03 §3.2)
    op.create_table(
        "code_relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_symbol_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("to_symbol_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("to_external", sa.String(length=512), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("resolution", sa.String(length=32), nullable=False, server_default="resolved"),
        sa.Column("file_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_code_relationships_project_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["from_symbol_id"],
            ["code_symbols.id"],
            name="fk_code_relationships_from_symbol_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["to_symbol_id"],
            ["code_symbols.id"],
            name="fk_code_relationships_to_symbol_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["file_version_id"],
            ["file_versions.id"],
            name="fk_code_relationships_file_version_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "kind IN ('imports', 'calls', 'defines_route', 'guarded_by', 'reads_model', 'writes_model', 'tests', 'documents')",
            name="ck_code_relationships_kind",
        ),
        sa.CheckConstraint(
            "resolution IN ('resolved', 'inferred', 'unresolved')",
            name="ck_code_relationships_resolution",
        ),
    )
    op.create_index(
        "ix_code_relationships_from_kind",
        "code_relationships",
        ["project_id", "from_symbol_id", "kind"],
        unique=False,
    )
    op.create_index(
        "ix_code_relationships_to_kind",
        "code_relationships",
        ["project_id", "to_symbol_id", "kind"],
        unique=False,
    )

    # 9. analysis_jobs (docs/03 §3.3)
    op.create_table(
        "analysis_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("queue", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_ref", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("consent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("budget", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_analysis_jobs_project_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name="fk_analysis_jobs_requested_by",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'awaiting_approval', 'succeeded', 'partially_succeeded', 'failed', 'cancel_requested', 'cancelled', 'timed_out')",
            name="ck_analysis_jobs_status",
        ),
        sa.UniqueConstraint(
            "project_id", "idempotency_key", name="uq_analysis_jobs_project_idempotency_key"
        ),
    )
    op.create_index(
        "ix_analysis_jobs_status_heartbeat",
        "analysis_jobs",
        ["status", "heartbeat_at"],
        unique=False,
    )
    op.create_index("ix_analysis_jobs_project_id", "analysis_jobs", ["project_id"], unique=False)

    # 10. job_events (docs/03 §3.3)
    op.create_table(
        "job_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("message", sa.String(length=1024), nullable=False),
        sa.Column(
            "data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["analysis_jobs.id"], name="fk_job_events_job_id", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("job_id", "seq", name="uq_job_events_job_seq"),
    )
    op.create_index("ix_job_events_job_id", "job_events", ["job_id"], unique=False)

    # 11. findings (docs/03 §3.4)
    op.create_table(
        "findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("rule_id", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="scanner"),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False, server_default="medium"),
        sa.Column("evidence_level", sa.String(length=8), nullable=False, server_default="E1"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("first_seen_scan_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_seen_scan_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("primary_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("primary_start_line", sa.Integer(), nullable=True),
        sa.Column("primary_end_line", sa.Integer(), nullable=True),
        sa.Column("suggested_fix", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status_reason", sa.String(length=64), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_findings_project_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["first_seen_scan_run_id"],
            ["scan_runs.id"],
            name="fk_findings_first_seen_scan_run_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["last_seen_scan_run_id"],
            ["scan_runs.id"],
            name="fk_findings_last_seen_scan_run_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["primary_file_id"],
            ["files.id"],
            name="fk_findings_primary_file_id",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "source IN ('scanner', 'devmind_rule', 'llm_verified')",
            name="ck_findings_source",
        ),
        sa.CheckConstraint(
            "category IN ('authentication', 'authorization', 'secret_exposure', 'input_validation', 'error_handling', 'testing', 'documentation', 'configuration', 'dependency', 'quality', 'other')",
            name="ck_findings_category",
        ),
        sa.CheckConstraint(
            "severity IN ('critical', 'high', 'medium', 'low', 'info')",
            name="ck_findings_severity",
        ),
        sa.CheckConstraint(
            "confidence IN ('low', 'medium', 'high')",
            name="ck_findings_confidence",
        ),
        sa.CheckConstraint(
            "evidence_level IN ('E0', 'E1', 'E2', 'E3')",
            name="ck_findings_evidence_level",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'acknowledged', 'in_progress', 'dismissed', 'accepted_risk', 'fix_proposed', 'stale', 'resolved', 'reopened')",
            name="ck_findings_status",
        ),
        sa.UniqueConstraint("project_id", "fingerprint", name="uq_findings_project_fingerprint"),
    )
    op.create_index(
        "ix_findings_project_status_severity",
        "findings",
        ["project_id", "status", "severity"],
        unique=False,
    )

    # 12. finding_evidence (docs/03 §3.4)
    op.create_table(
        "finding_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("snippet_hash", sa.String(length=64), nullable=False),
        sa.Column("snippet_text", sa.Text(), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="primary"),
        sa.Column(
            "detail",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("is_current", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["findings.id"],
            name="fk_finding_evidence_finding_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_finding_evidence_project_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_version_id"],
            ["file_versions.id"],
            name="fk_finding_evidence_file_version_id",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "role IN ('primary', 'supporting', 'missing_check')",
            name="ck_finding_evidence_role",
        ),
    )
    op.create_index(
        "ix_finding_evidence_finding_id", "finding_evidence", ["finding_id"], unique=False
    )
    op.create_index(
        "ix_finding_evidence_project_path",
        "finding_evidence",
        ["project_id", "path"],
        unique=False,
    )

    # 13. finding_status_history (docs/03 §3.4)
    op.create_table(
        "finding_status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=False),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("actor_kind", sa.String(length=32), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["findings.id"],
            name="fk_finding_status_history_finding_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "actor_kind IN ('user', 'system')",
            name="ck_finding_status_history_actor_kind",
        ),
    )
    op.create_index(
        "ix_finding_status_history_finding_id",
        "finding_status_history",
        ["finding_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("finding_status_history")
    op.drop_table("finding_evidence")
    op.drop_table("findings")
    op.drop_table("job_events")
    op.drop_table("analysis_jobs")
    op.drop_table("code_relationships")
    op.drop_table("code_symbols")
    op.drop_table("snapshot_files")
    op.drop_table("project_snapshots")
    op.drop_constraint("fk_files_current_version_id", "files", type_="foreignkey")
    op.drop_table("file_versions")
    op.drop_table("files")
    op.drop_table("local_workspace_registrations")
    op.drop_table("scan_runs")
