"""Automated validation of DevMind threat model and residual risk ledger (M10-09, docs/07 §18, §20).

Validates:
1. Threat model completeness: all 24 cataloged threats (T-01 to T-24) exist with full columns.
2. Verification evidence integrity: all test files referenced in the threat matrix exist.
3. Residual risk ledger completeness: all 6 residual risk items (RR-01 to RR-06) exist with full metadata.
4. Operational playbook links: all referenced runbook playbooks exist.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"
SECURITY_DOC = DOCS_DIR / "07-security-privacy-and-threat-model.md"


def test_threat_model_catalog_completeness() -> None:
    """Verify that all 24 threats (T-01 to T-24) exist in docs/07 §18 with complete columns."""
    assert SECURITY_DOC.exists(), f"Missing security doc: {SECURITY_DOC}"
    content = SECURITY_DOC.read_text(encoding="utf-8")

    # Verify all 24 Threat IDs exist
    expected_threat_ids = [f"T-{i:02d}" for i in range(1, 25)]
    for tid in expected_threat_ids:
        assert f"| {tid} |" in content, f"Missing threat {tid} in threat model table"

    # Extract all rows in §18 table
    table_pattern = re.compile(r"\|\s*(T-\d{2})\s*\|([^|\n]+\|){7}")
    matches = table_pattern.findall(content)
    found_threat_ids = [m[0] for m in matches]
    assert set(found_threat_ids) == set(expected_threat_ids), (
        f"Mismatch in threat IDs found in table: {set(expected_threat_ids) - set(found_threat_ids)}"
    )


def test_threat_model_verification_evidence_files_exist() -> None:
    """Verify that every test file referenced in the threat matrix's Verification Evidence exists."""
    content = SECURITY_DOC.read_text(encoding="utf-8")

    # Match test file references in markdown links: [link text](../server/tests/test_foo.py) or `evals/...`
    test_file_pattern = re.compile(
        r"(?:server/tests/test_[a-zA-Z0-9_]+\.py|evals/[a-zA-Z0-9_/]+\.py|docs/runbooks/[a-zA-Z0-9_-]+\.md)"
    )
    referenced_files = set(test_file_pattern.findall(content))
    assert len(referenced_files) >= 15, f"Expected at least 15 verified file references, found {len(referenced_files)}"

    for rel_path in referenced_files:
        full_path = REPO_ROOT / rel_path
        assert full_path.exists(), f"Referenced verification file does not exist: {rel_path}"


def test_residual_risk_ledger_completeness() -> None:
    """Verify that residual risk ledger in docs/07 §20 catalogs RR-01 to RR-06 with complete metadata."""
    content = SECURITY_DOC.read_text(encoding="utf-8")

    expected_risk_ids = [f"RR-{i:02d}" for i in range(1, 7)]
    for rid in expected_risk_ids:
        assert f"**{rid}**" in content, f"Missing residual risk {rid} in residual risk ledger"

    # Verify key threat mappings in residual risk ledger
    expected_mappings = {
        "RR-01": "T-19",  # AI Provider Data Handling & Terms
        "RR-02": "T-04",  # Novel or Unrecognized Secret Formats
        "RR-03": "T-03",  # Prompt-Induced Misleading Explanations
        "RR-04": "T-11",  # GitHub OAuth Scope Breadth for Private Repos
        "RR-05": "T-01",  # Cross-Tenant Authorization Drift on New Endpoints
        "RR-06": "T-18",  # Provider Backup Retention Window Persistence
    }

    for rid, tid in expected_mappings.items():
        pattern = re.compile(rf"\*\*{rid}\*\*\s*\|\s*{tid}\b")
        assert pattern.search(content), f"Residual risk {rid} must reference threat {tid}"


def test_playbook_references_resolve() -> None:
    """Verify that all runbooks referenced in §17 incident response playbooks exist."""
    content = SECURITY_DOC.read_text(encoding="utf-8")

    playbook_pattern = re.compile(r"docs/runbooks/([a-zA-Z0-9_-]+\.md)")
    playbook_files = set(playbook_pattern.findall(content))
    assert len(playbook_files) >= 5, f"Expected at least 5 playbook runbook references, found {len(playbook_files)}"

    runbooks_dir = DOCS_DIR / "runbooks"
    for filename in playbook_files:
        assert (runbooks_dir / filename).exists(), f"Referenced playbook runbook missing: {filename}"
