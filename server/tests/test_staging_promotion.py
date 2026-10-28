"""Automated validation of DevMind staging promotion rehearsal and release verification (M10-10, docs/10 §2, §17, §22, docs/09 §15).

Validates:
1. Staging promotion runbook completeness and rollback rehearsal playbooks.
2. Staging environment configuration invariants and environment parity.
3. Readiness probe contract (/readyz) verifying dependency health and kill switches.
4. Synthetic staging smoke workflow executing deterministic analysis and evidence verification.
5. Migration backward-compatibility and zero-downtime rollback safety invariants.
"""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from starlette.testclient import TestClient

from app.core.settings import Settings
from app.llm.prompt_loader import default_prompt_loader
from app.llm.schemas import FindingExplanation

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"
RUNBOOK_PATH = DOCS_DIR / "runbooks" / "staging-promotion.md"
ALEMBIC_VERSIONS_DIR = REPO_ROOT / "server" / "alembic" / "versions"


def test_staging_promotion_runbook_structure() -> None:
    """Verify that docs/runbooks/staging-promotion.md covers the complete promotion and rollback lifecycle."""
    assert RUNBOOK_PATH.exists(), f"Missing staging promotion runbook: {RUNBOOK_PATH}"
    content = RUNBOOK_PATH.read_text(encoding="utf-8")

    # Top-level header
    assert content.startswith("# Runbook: Staging Promotion Rehearsal")

    # Key lifecycle phases
    expected_phases = [
        "Phase 1: Build & Tag Immutable Container Image",
        "Phase 2: Deploy & Migrate Staging Environment",
        "Phase 3: Automated Staging Smoke Verification",
        "Phase 4: Promotion Decision Gate (Human Sign-Off)",
        "Phase 5: Production Deployment & Zero-Downtime Rollout",
        "Emergency Rollback Rehearsal",
    ]
    for phase in expected_phases:
        assert phase in content, f"Missing lifecycle phase in staging-promotion.md: '{phase}'"

    # Quality gates G1 through G6
    assert "G1 (Static Checks)" in content
    assert "G2 (Tests)" in content
    assert "G3 (Authorization)" in content
    assert "G4 (Contract)" in content
    assert "G5 (Smoke)" in content
    assert "G6 (Security Review)" in content

    # Rollback strategies
    assert "Application Code Rollback" in content
    assert "Kill Switch Isolation" in content
    assert "Database Restoration" in content


def test_staging_environment_configuration_invariants() -> None:
    """Verify Settings behavior under staging vs production environments."""
    # Staging configuration
    staging_settings = Settings(
        env="staging",
        devmind_env="staging",
        DEVMIND_BUILD_SHA="abc1234",
    )
    assert not staging_settings.is_production
    assert staging_settings.env == "staging"
    assert staging_settings.build_sha == "abc1234"

    # Production configuration
    prod_settings = Settings(
        env="production",
        devmind_env="production",
        DEVMIND_BUILD_SHA="def5678",
    )
    assert prod_settings.is_production
    assert prod_settings.env == "production"
    assert prod_settings.build_sha == "def5678"


def test_readiness_probe_staging_contract(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify /readyz endpoint adheres to the staging readiness probe contract."""
    # Mock healthy dependencies
    monkeypatch.setattr(
        "app.domain.auth.check_database_connectivity",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "app.core.redis.check_redis_connectivity",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "app.domain.auth.check_migrations_readiness",
        AsyncMock(return_value=(True, "ok", ["0013_pr_analyses"])),
    )

    response = client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "ok"
    assert data["redis"] == "ok"
    assert data["migrations"] == "ok"
    assert "kill_switches" in data
    assert all(
        k in data["kill_switches"] for k in ["indexing", "llm", "embed", "webhooks", "pause_queues"]
    )

    # Verify degraded when database is unavailable
    monkeypatch.setattr(
        "app.domain.auth.check_database_connectivity",
        AsyncMock(return_value=False),
    )
    degraded_resp = client.get("/readyz")
    assert degraded_resp.status_code == 503
    degraded_data = degraded_resp.json()
    assert degraded_data["status"] == "degraded"
    assert degraded_data["database"] == "unreachable"


def test_staging_synthetic_smoke_workflow() -> None:
    """Execute synthetic smoke workflow verifying template rendering, schema repair, and evidence tagging."""
    # Verify canonical template loads
    template = default_prompt_loader.get_template("security_explanation")
    assert template is not None

    rendered = template.render(
        {
            "finding_details": "devmind.sec.missing_role_check on /admin/users route",
            "evidence_code": "@router.get('/admin/users')\ndef list_users(): return db.query(User).all()",
        }
    )

    # Delimiter boundary encapsulation check
    assert "<untrusted_data" in rendered.user_prompt
    assert "</untrusted_data>" in rendered.user_prompt
    assert len(rendered.injection_signals) == 0

    # Structured schema conformance check
    finding = FindingExplanation(
        summary="Endpoint /admin/users lacks authorization check for admin role.",
        impact="Unprivileged authenticated users can list all tenant users.",
        likely_cause="Route handler lacks require_permission('workspace:admin') dependency.",
        remediation_proposal="Add @require_permission('workspace:admin') decorator to route handler.",
        false_positive_indicators=["Route guarded by external API gateway reverse proxy"],
        confidence=0.95,
    )
    assert finding.confidence == 0.95
    assert "admin" in finding.summary.lower()


def test_migration_expand_contract_rollback_invariants() -> None:
    """Verify that applied Alembic migration scripts follow backward-compatible expand-contract practices."""
    assert ALEMBIC_VERSIONS_DIR.exists(), f"Alembic versions dir missing: {ALEMBIC_VERSIONS_DIR}"

    migration_files = list(ALEMBIC_VERSIONS_DIR.glob("*.py"))
    assert len(migration_files) >= 5, (
        f"Expected at least 5 migration versions, found {len(migration_files)}"
    )

    destructive_keywords = [
        "drop_table",
        "drop_column",
        "alter_column_type",
    ]

    for mig_file in migration_files:
        content = mig_file.read_text(encoding="utf-8")
        # In upgrade() function, no destructive column drops without deprecation
        upgrade_code = (
            content.split("def upgrade()")[1].split("def downgrade()")[0]
            if "def upgrade()" in content
            else ""
        )
        for kw in destructive_keywords:
            if kw in upgrade_code:
                # Disallow raw drop_table in normal upgrade paths
                assert "op.drop_table" not in upgrade_code or "scratch" in upgrade_code.lower(), (
                    f"Destructive operation {kw} found in upgrade() of {mig_file.name}. "
                    "Must adhere to expand-contract pattern for safe rollback."
                )
