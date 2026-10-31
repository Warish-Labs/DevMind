"""Automated validation of DevMind operational runbooks and disaster recovery procedures (M10-08, docs/10 §16, §18, §21, §22).

Validates:
1. Operational runbooks inventory and markdown structure.
2. Incident diagnosis playbooks covering all 5 core failure modes from docs/10 §18.
3. Subsystem kill switch consistency across code, settings, and runbook definitions.
4. Business continuity and disaster recovery scenario coverage (docs/10 §16).
5. Free-tier operational quotas alignment with server/configs/quotas.free.yaml (ADR-046).
"""

from pathlib import Path

import yaml

from app.core.kill_switches import VALID_KILL_SWITCHES, get_active_kill_switches
from app.core.settings import get_settings

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"
RUNBOOKS_DIR = DOCS_DIR / "runbooks"


def test_operational_runbooks_inventory() -> None:
    """Verify that all required operational and disaster recovery runbooks exist and are non-empty."""
    required_runbooks = [
        "incident-response.md",
        "disaster-recovery.md",
        "free-tier-operations.md",
        "database-restore.md",
        "secrets-rotation.md",
        "deploy-render-vercel.md",
        "github-integration-and-pr-intelligence.md",
    ]

    for filename in required_runbooks:
        runbook_path = RUNBOOKS_DIR / filename
        assert runbook_path.exists(), f"Required runbook missing: docs/runbooks/{filename}"
        content = runbook_path.read_text(encoding="utf-8")
        assert len(content) > 1000, f"Runbook docs/runbooks/{filename} is too short or empty"
        assert content.startswith("# "), (
            f"Runbook docs/runbooks/{filename} must start with top-level markdown header '# '"
        )


def test_incident_response_playbooks_coverage() -> None:
    """Verify incident-response.md covers all five core failure modes from docs/10 §18."""
    incident_file = RUNBOOKS_DIR / "incident-response.md"
    content = incident_file.read_text(encoding="utf-8")

    # Core failure mode playbooks
    playbook_markers = [
        "Playbook 1: Worker Stall, Backpressure & Stranded Tasks",
        "Playbook 2: Retrieval Degradation & Embedding Provider Outage",
        "Playbook 3: Real-Time SSE Disconnects & Proxy Timeouts",
        "Playbook 4: Cross-Tenant Isolation Suspicion or Security Incident",
        "Playbook 5: Duplicate Task Execution & Stale Idempotency Locks",
    ]

    for marker in playbook_markers:
        assert marker in content, f"Missing required playbook in incident-response.md: '{marker}'"

    # Severity tiers
    assert "SEV-1" in content
    assert "SEV-2" in content
    assert "SEV-3" in content
    assert "SEV-4" in content

    # Privacy constraint reminder per ADR-047
    assert "Never request, export, or log user source code" in content


def test_subsystem_kill_switches_code_consistency() -> None:
    """Verify that all kill switches in incident-response.md match Settings and VALID_KILL_SWITCHES."""
    incident_file = RUNBOOKS_DIR / "incident-response.md"
    content = incident_file.read_text(encoding="utf-8")

    # The 5 operational kill switches
    expected_env_switches = {
        "DEVMIND_KILL_INDEXING": "indexing",
        "DEVMIND_KILL_LLM": "llm",
        "DEVMIND_KILL_EMBED": "embed",
        "DEVMIND_KILL_WEBHOOKS": "webhooks",
        "DEVMIND_PAUSE_QUEUES": "pause_queues",
    }

    # Verify each switch is documented in incident-response.md
    for env_var in expected_env_switches:
        assert env_var in content, (
            f"Kill switch {env_var} must be documented in incident-response.md"
        )

    # Verify each switch maps to VALID_KILL_SWITCHES in core/kill_switches.py
    normalized_names = set(expected_env_switches.values())
    assert normalized_names == VALID_KILL_SWITCHES, (
        f"Mismatch between expected kill switches and code: {normalized_names} != {VALID_KILL_SWITCHES}"
    )

    # Verify each switch exists as a field on Settings
    settings = get_settings()
    settings_fields = type(settings).model_fields
    assert "kill_indexing" in settings_fields
    assert "kill_llm" in settings_fields
    assert "kill_embed" in settings_fields
    assert "kill_webhooks" in settings_fields
    assert "pause_queues" in settings_fields

    # Verify get_active_kill_switches returns all 5
    active = get_active_kill_switches(settings)
    assert set(active.keys()) == normalized_names


def test_disaster_recovery_scenarios_coverage() -> None:
    """Verify disaster-recovery.md covers the four catastrophic disaster scenarios from docs/10 §16."""
    dr_file = RUNBOOKS_DIR / "disaster-recovery.md"
    content = dr_file.read_text(encoding="utf-8")

    expected_scenarios = [
        "Scenario 1: Regional / Infrastructure Outage",
        "Scenario 2: Corrupted or Incompatible Embedding Space",
        "Scenario 3: Accidental Destructive Migration or Database Loss",
        "Scenario 4: Critical Secret & Credential Disclosure",
    ]

    for scenario in expected_scenarios:
        assert scenario in content, (
            f"Missing disaster scenario in disaster-recovery.md: '{scenario}'"
        )

    # Cross-references to detailed specialized runbooks
    assert "database-restore.md" in content
    assert "secrets-rotation.md" in content


def test_free_tier_operations_quotas_alignment() -> None:
    """Verify free-tier-operations.md matches server/configs/quotas.free.yaml and ADR-046."""
    free_ops_file = RUNBOOKS_DIR / "free-tier-operations.md"
    content = free_ops_file.read_text(encoding="utf-8")

    quotas_file = REPO_ROOT / "server" / "configs" / "quotas.free.yaml"
    with quotas_file.open("r", encoding="utf-8") as f:
        quotas = yaml.safe_load(f)

    # Database cap: 512 MB Neon Free
    assert "512 MB" in content
    assert quotas["storage"]["database_storage_cap_bytes"] == 512 * 1024 * 1024

    # Container RAM cap: 512 MB Render Free
    assert quotas["memory"]["container_ram_cap_bytes"] == 512 * 1024 * 1024
    assert quotas["memory"]["worker_concurrency"] == 1

    # Upstash Redis: 10,000 commands/day cap
    assert "10,000 commands/day" in content or "10,000 Redis commands" in content

    # Render spin-down (15 minutes) and Neon auto-suspend (5 minutes)
    assert "15 minutes" in content
    assert "5 minutes" in content


def test_github_integration_and_pr_intelligence_runbook_coverage() -> None:
    """Verify github-integration-and-pr-intelligence.md covers core M11 operations per ADR-014, ADR-015, and docs/10 §18."""
    runbook_file = RUNBOOKS_DIR / "github-integration-and-pr-intelligence.md"
    assert runbook_file.exists()
    content = runbook_file.read_text(encoding="utf-8")

    # Critical M11 operational procedures
    required_sections = [
        "3.1 GitHub Webhook secret rotation",
        "3.2 GitHub OAuth credentials rotation",
        "3.3 Webhook delivery failure triage & manual replay",
        "3.4 GitHub rate limiting mitigation",
        "3.5 Emergency kill switch activation",
        "4. Resend email and workspace invitations",
        "5. Audit and compliance verification",
    ]
    for section in required_sections:
        assert section in content, (
            f"Missing section '{section}' in github-integration-and-pr-intelligence.md"
        )

    # Crucial security invariants
    assert "DEVMIND_GITHUB_WEBHOOK_SECRET" in content
    assert "DEVMIND_ENCRYPTION_KEYS" in content
    assert "DEVMIND_KILL_WEBHOOKS" in content
    assert "DEVMIND_RESEND_API_KEY" in content
    assert "Never log user source code or decrypted access tokens" in content
