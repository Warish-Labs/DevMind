"""Tests verifying Alembic migration configuration and revision consistency (docs/03 §9)."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.persistence.models import Base


def test_alembic_config_and_revisions() -> None:
    """Verify that alembic.ini points to a valid script directory and has exactly 1 head."""
    ini_path = Path(__file__).parent.parent / "alembic.ini"
    assert ini_path.exists(), "alembic.ini must exist in server root"

    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(ini_path.parent / "alembic"))
    script_dir = ScriptDirectory.from_config(cfg)

    heads = script_dir.get_heads()
    assert len(heads) == 1, f"Expected exactly 1 migration head, got: {heads}"
    assert heads[0] == "0018_deployment_incidents"


def test_migration_models_match_metadata() -> None:
    """Verify that Base.metadata contains the tables declared in migrations."""
    expected_tables = {
        "users",
        "workspaces",
        "workspace_memberships",
        "workspace_invitations",
        "projects",
        "project_memberships",
        "audit_events",
        "usage_records",
        "extension_registrations",
        "extension_tokens",
        "scan_runs",
        "local_workspace_registrations",
        "files",
        "file_versions",
        "project_snapshots",
        "snapshot_files",
        "code_symbols",
        "code_relationships",
        "code_chunks",
        "embedding_spaces",
        "chunk_embeddings",
        "github_connections",
        "github_repositories",
        "pull_requests",
        "pr_analyses",
        "review_rules",
        "agent_runs",
        "analysis_jobs",
        "job_events",
        "findings",
        "finding_evidence",
        "finding_status_history",
        "consent_records",
        "retention_policies",
        "bug_records",
        "bug_resolutions",
        "documentation_records",
        "doc_drift_items",
        "project_tasks",
        "task_dependencies",
        "project_evaluations",
        "deployment_incidents",
    }
    assert expected_tables.issubset(Base.metadata.tables.keys())
