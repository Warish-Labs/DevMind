"""Unit tests for deterministic EvidenceVerifier and CitationVerifier (docs/05 §7, M7-07)."""

import pytest

from app.analysis.evidence_verifier import (
    CitationVerifier,
    EvidenceVerifier,
    compute_snippet_hash,
    is_known_rule,
    redact_evidence_secrets,
    register_known_rule,
    verify_citations,
    verify_evidence,
)
from app.analysis.guard_resolution import (
    GuardResolutionChain,
    GuardType,
    ProjectSecurityConfig,
    ResolvedGuard,
    RouteDefinition,
    RouteFramework,
    RouteGuardAnalyzer,
)


@pytest.fixture
def sample_snapshot() -> dict[str, str]:
    """Sample repository file snapshot with realistic source files."""
    return {
        "server/app/api/users.py": (
            "from fastapi import APIRouter, Depends\n"
            "router = APIRouter()\n"
            "\n"
            "@router.get('/users')\n"
            "def list_users():\n"
            "    return [{'id': 1, 'name': 'Alice'}]\n"
            "\n"
            "@router.delete('/users/{user_id}')\n"
            "def delete_user(user_id: int):\n"
            "    return {'deleted': user_id}\n"
        ),
        "server/app/api/admin.py": (
            "from fastapi import APIRouter\n"
            "router = APIRouter()\n"
            "\n"
            "@router.post('/admin/reset')\n"
            "def reset_database():\n"
            "    return {'status': 'reset'}\n"
        ),
        "server/app/core/auth.py": (
            "def require_auth():\n    pass\n\ndef require_admin():\n    pass\n"
        ),
    }


# ---------------------------------------------------------------------------
# 1. Rule ID Registry Tests (Check 4)
# ---------------------------------------------------------------------------


def test_known_rules_and_prefixes() -> None:
    """Verify built-in DevMind rules and standard scanner prefixes."""
    assert is_known_rule("devmind.authn.unprotected_route")
    assert is_known_rule("devmind.authz.missing_role_check")
    assert is_known_rule("devmind.secret.detected_credential")
    assert is_known_rule("devmind.injection.sql")

    # Scanner prefixes
    assert is_known_rule("bandit.B101")
    assert is_known_rule("semgrep.python.security.injection")
    assert is_known_rule("trivy.CVE-2024-9999")
    assert is_known_rule("gitleaks.generic-api-key")
    assert is_known_rule("eslint.security/detect-eval-with-expression")
    assert is_known_rule("ruff.S101")

    # Unknown rule
    assert not is_known_rule("malicious.unregistered.rule")
    assert not is_known_rule("")


def test_dynamic_rule_registration() -> None:
    """Verify custom rule IDs can be dynamically registered."""
    custom_rule = "custom.internal.security_check"
    assert not is_known_rule(custom_rule)
    register_known_rule(custom_rule, "Custom internal rule")
    assert is_known_rule(custom_rule)


# ---------------------------------------------------------------------------
# 2. File Snapshot and Version Checks (Check 1)
# ---------------------------------------------------------------------------


def test_file_and_version_verification(sample_snapshot: dict[str, str]) -> None:
    """File presence and snapshot version match verification."""
    file_versions = {
        "server/app/api/users.py": "v1_hash_abc",
        "server/app/api/admin.py": "v1_hash_def",
    }
    verifier = EvidenceVerifier(file_snapshot=sample_snapshot, file_versions=file_versions)

    # 1. Valid file and matching version
    valid_draft = {
        "draft_id": "draft_01",
        "rule_id": "devmind.authn.unprotected_route",
        "file_path": "server/app/api/users.py",
        "line_range": (4, 6),
        "file_version_id": "v1_hash_abc",
        "evidence_level": "E2",
    }
    res = verifier.verify_draft_finding(valid_draft)
    assert res.is_verified is True
    assert res.status == "verified"
    assert len(res.rejection_reasons) == 0

    # 2. Non-existent file
    missing_file_draft = {
        "draft_id": "draft_02",
        "rule_id": "devmind.authn.unprotected_route",
        "file_path": "server/app/api/nonexistent.py",
        "line_range": (1, 5),
        "evidence_level": "E2",
    }
    res_missing = verifier.verify_draft_finding(missing_file_draft)
    assert res_missing.is_verified is False
    assert res_missing.status == "rejected"
    assert any("not present in the repository snapshot" in r for r in res_missing.rejection_reasons)

    # 3. Mismatched file version
    version_mismatch_draft = {
        "draft_id": "draft_03",
        "rule_id": "devmind.authn.unprotected_route",
        "file_path": "server/app/api/users.py",
        "line_range": (4, 6),
        "file_version_id": "outdated_v0_hash",
        "evidence_level": "E2",
    }
    res_ver = verifier.verify_draft_finding(version_mismatch_draft)
    assert res_ver.is_verified is False
    assert res_ver.status == "rejected"
    assert any("does not match snapshot version" in r for r in res_ver.rejection_reasons)


# ---------------------------------------------------------------------------
# 3. Line Range Bounds Checks (Check 2)
# ---------------------------------------------------------------------------


def test_line_range_bounds_validation(sample_snapshot: dict[str, str]) -> None:
    """Line range boundaries: positive start, end >= start, inside file length."""
    verifier = EvidenceVerifier(file_snapshot=sample_snapshot)

    # Negative / 0 start
    res_zero = verifier.verify_draft_finding(
        {
            "draft_id": "d1",
            "rule_id": "devmind.authn.unprotected_route",
            "file_path": "server/app/api/users.py",
            "line_range": (0, 5),
        }
    )
    assert res_zero.is_verified is False
    assert any("start must be >= 1" in r for r in res_zero.rejection_reasons)

    # Inverted range
    res_inv = verifier.verify_draft_finding(
        {
            "draft_id": "d2",
            "rule_id": "devmind.authn.unprotected_route",
            "file_path": "server/app/api/users.py",
            "line_range": (8, 3),
        }
    )
    assert res_inv.is_verified is False
    assert any("cannot be less than start" in r for r in res_inv.rejection_reasons)

    # Exceeding file bounds (users.py has 10 lines)
    res_overflow = verifier.verify_draft_finding(
        {
            "draft_id": "d3",
            "rule_id": "devmind.authn.unprotected_route",
            "file_path": "server/app/api/users.py",
            "line_range": (5, 50),
        }
    )
    assert res_overflow.is_verified is False
    assert any("outside file bounds" in r for r in res_overflow.rejection_reasons)


# ---------------------------------------------------------------------------
# 4. Snippet Hash Confirmation (Check 3)
# ---------------------------------------------------------------------------


def test_snippet_hash_verification(sample_snapshot: dict[str, str]) -> None:
    """Snippet hash must match computed hash of cited line slice."""
    verifier = EvidenceVerifier(file_snapshot=sample_snapshot)

    # Lines 4-6 of users.py:
    # "@router.get('/users')\n"
    # "def list_users():\n"
    # "    return [{'id': 1, 'name': 'Alice'}]"
    lines = sample_snapshot["server/app/api/users.py"].splitlines()[3:6]
    expected_snippet = "\n".join(lines)
    expected_hash = compute_snippet_hash(expected_snippet)

    # Valid hash
    res_ok = verifier.verify_draft_finding(
        {
            "draft_id": "d_hash_ok",
            "rule_id": "devmind.authn.unprotected_route",
            "file_path": "server/app/api/users.py",
            "line_range": (4, 6),
            "evidence_details": {"snippet_hash": expected_hash},
            "evidence_level": "E2",
        }
    )
    assert res_ok.is_verified is True
    assert res_ok.status == "verified"
    assert res_ok.sanitized_evidence[0].snippet_hash == expected_hash

    # Tampered / mismatched hash
    res_tampered = verifier.verify_draft_finding(
        {
            "draft_id": "d_tampered",
            "rule_id": "devmind.authn.unprotected_route",
            "file_path": "server/app/api/users.py",
            "line_range": (4, 6),
            "evidence_details": {"snippet_hash": "deadbeef" * 8},
            "evidence_level": "E2",
        }
    )
    assert res_tampered.is_verified is False
    assert res_tampered.status == "rejected"
    assert any("Snippet hash mismatch" in r for r in res_tampered.rejection_reasons)


# ---------------------------------------------------------------------------
# 5. Structural Claim Verification (Check 5)
# ---------------------------------------------------------------------------


def test_structural_claim_with_route_analyzer(sample_snapshot: dict[str, str]) -> None:
    """Structural claim: false claim on a protected route is rejected."""
    # Build RouteGuardAnalyzer with known endpoints
    from uuid import uuid4

    routes = [
        RouteDefinition(
            symbol_id=uuid4(),
            symbol_key="sym_list_users",
            name="list_users",
            framework=RouteFramework.FASTAPI,
            http_method="GET",
            http_route="/users",
            file_path="server/app/api/users.py",
            start_line=4,
            end_line=6,
        ),
        RouteDefinition(
            symbol_id=uuid4(),
            symbol_key="sym_reset_db",
            name="reset_database",
            framework=RouteFramework.FASTAPI,
            http_method="POST",
            http_route="/admin/reset",
            file_path="server/app/api/admin.py",
            start_line=4,
            end_line=6,
        ),
    ]

    # /users has no guards; /admin/reset has an admin guard
    guards_by_route = {
        "sym_list_users": GuardResolutionChain(
            route_symbol_key="sym_list_users",
            guards=[],
            callees_examined=["db.query"],
            is_fully_resolved=True,
        ),
        "sym_reset_db": GuardResolutionChain(
            route_symbol_key="sym_reset_db",
            guards=[
                ResolvedGuard(
                    name="require_admin",
                    guard_type=GuardType.DEPENDENCY,
                    file_path="server/app/core/auth.py",
                    line_number=4,
                    is_authentication=True,
                    is_authorization=True,
                    is_admin_check=True,
                )
            ],
            callees_examined=["require_admin"],
            is_fully_resolved=True,
        ),
    }

    analyzer = RouteGuardAnalyzer(config=ProjectSecurityConfig())
    eval_users = analyzer.evaluate_route_security(routes[0], guards_by_route["sym_list_users"])
    eval_admin = analyzer.evaluate_route_security(routes[1], guards_by_route["sym_reset_db"])

    verifier = EvidenceVerifier(
        file_snapshot=sample_snapshot,
        route_evaluations=[eval_users, eval_admin],
    )

    # 1. Legitimate finding on /users (unprotected)
    res_legit = verifier.verify_draft_finding(
        {
            "draft_id": "d_users",
            "rule_id": "devmind.authn.unprotected_route",
            "file_path": "server/app/api/users.py",
            "line_range": (4, 6),
            "evidence_details": {
                "route_symbol_key": "sym_list_users",
                "analysis_scope": "handler and 1 resolved callee; 0 unresolved dependencies",
                "is_fully_resolved": True,
            },
            "evidence_level": "E2",
        }
    )
    assert res_legit.is_verified is True
    assert res_legit.verified_level == "E2"

    # 2. False claim on /admin/reset (which is actually protected!)
    res_false = verifier.verify_draft_finding(
        {
            "draft_id": "d_false_claim",
            "rule_id": "devmind.authn.unprotected_route",
            "file_path": "server/app/api/admin.py",
            "line_range": (4, 6),
            "evidence_details": {
                "route_symbol_key": "sym_reset_db",
                "analysis_scope": "handler and 1 resolved callee; 0 unresolved dependencies",
                "is_fully_resolved": True,
            },
            "evidence_level": "E2",
        }
    )
    assert res_false.is_verified is False
    assert res_false.status == "rejected"
    assert any(
        "Structural claim failed: route is actually protected" in r
        for r in res_false.rejection_reasons
    )


# ---------------------------------------------------------------------------
# 6. Evidence Level Downgrade & Language Sanitization (Check 6)
# ---------------------------------------------------------------------------


def test_e2_downgrade_on_unresolved_dependencies(sample_snapshot: dict[str, str]) -> None:
    """Claims E2 but analysis_scope shows unresolved nodes -> downgraded to E1."""
    verifier = EvidenceVerifier(file_snapshot=sample_snapshot)

    # Finding claiming E2 with dynamic unresolved dependency in scope
    res_downgrade = verifier.verify_draft_finding(
        {
            "draft_id": "d_unresolved",
            "rule_id": "devmind.authz.missing_role_check",
            "file_path": "server/app/api/users.py",
            "line_range": (7, 9),
            "evidence_details": {
                "analysis_scope": "handler and 2 resolved callees; unresolved: 1 dynamic dependency (dispatch_hook)",
                "is_fully_resolved": False,
                "unresolved_dependencies": ["dispatch_hook"],
            },
            "evidence_level": "E2",
        }
    )

    assert res_downgrade.is_verified is True
    assert res_downgrade.status == "downgraded"
    assert res_downgrade.verified_level == "E1"
    assert res_downgrade.evidence_score == 0.8
    assert any("downgraded to E1" in d for d in res_downgrade.downgrade_reasons)


def test_e3_exploitability_downgrade_in_v1(sample_snapshot: dict[str, str]) -> None:
    """E3 exploitability is disabled in v1 (ADR-041) -> downgraded to E2."""
    verifier = EvidenceVerifier(file_snapshot=sample_snapshot)

    res_e3 = verifier.verify_draft_finding(
        {
            "draft_id": "d_e3",
            "rule_id": "devmind.authn.unprotected_route",
            "file_path": "server/app/api/users.py",
            "line_range": (4, 6),
            "evidence_details": {
                "analysis_scope": "handler and 0 resolved callees; 0 unresolved dependencies",
                "is_fully_resolved": True,
            },
            "evidence_level": "E3",
        }
    )

    assert res_e3.is_verified is True
    assert res_e3.status == "downgraded"
    assert res_e3.verified_level == "E2"
    assert any(
        "E3 exploitability findings are disabled in v1" in d for d in res_e3.downgrade_reasons
    )


def test_exploitability_language_sanitization(sample_snapshot: dict[str, str]) -> None:
    """E0/E1 language sanitization replaces 'vulnerable'/'exploitable' (AGENTS.md §5.7)."""
    verifier = EvidenceVerifier(file_snapshot=sample_snapshot)

    draft = {
        "draft_id": "d_lang",
        "rule_id": "devmind.authn.unprotected_route",
        "title": "Critical vulnerable endpoint detected",
        "summary": "This route is highly exploitable by attackers.",
        "explanation": "Severe vulnerability in user controller.",
        "file_path": "server/app/api/users.py",
        "line_range": (4, 6),
        "evidence_details": {
            "analysis_scope": "handler and 1 resolved callee; unresolved: 1 dynamic dependency",
            "is_fully_resolved": False,
        },
        "evidence_level": "E1",
    }

    res = verifier.verify_draft_finding(draft)
    assert res.is_verified is True
    assert res.verified_level == "E1"
    # Ensure "vulnerable" and "exploitable" were sanitized
    assert "vulnerable" not in res.title.lower()
    assert "potentially unprotected" in res.title.lower()
    assert "exploitable" not in res.summary.lower()
    assert "vulnerability" not in res.explanation.lower()


# ---------------------------------------------------------------------------
# 7. Secret Redaction in Evidence Snippets (Check 7)
# ---------------------------------------------------------------------------


def test_secret_redaction_in_evidence_snippet() -> None:
    """Snippet containing API keys or private keys is redacted."""
    raw_snippet = (
        'OPENAI_API_KEY = "sk-12345678901234567890123456789012"\n'
        'ANTHROPIC_KEY = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz123456"\n'
        'GITHUB_TOKEN = "ghp_123456789012345678901234567890123456"\n'
    )
    redacted, count = redact_evidence_secrets(raw_snippet)
    assert count == 3
    assert "sk-12345678901234567890123456789012" not in redacted
    assert "[REDACTED:openai_key:" in redacted
    assert "[REDACTED:anthropic_key:" in redacted
    assert "[REDACTED:github_token:" in redacted


def test_secret_in_file_snapshot_is_redacted_in_evidence() -> None:
    """File snapshot containing secret produces sanitized EvidenceItem."""
    secret_snapshot = {
        "config.py": ("SECRET_TOKEN = 'sk_live_123456789012345678901234'\nDEBUG = True\n")
    }
    verifier = EvidenceVerifier(file_snapshot=secret_snapshot)

    draft = {
        "draft_id": "d_secret",
        "rule_id": "devmind.secret.detected_credential",
        "file_path": "config.py",
        "line_range": (1, 2),
        "evidence_level": "E2",
    }

    res = verifier.verify_draft_finding(draft)
    assert res.is_verified is True
    evidence = res.sanitized_evidence[0]
    assert "sk_live_" not in evidence.snippet_text
    assert "[REDACTED:stripe_live:" in evidence.snippet_text
    assert any("Redacted 1 sensitive credential" in d for d in res.downgrade_reasons)


# ---------------------------------------------------------------------------
# 8. Citation Verification Tests
# ---------------------------------------------------------------------------


def test_citation_verifier_single(sample_snapshot: dict[str, str]) -> None:
    """Verify single citations against files, symbols, and chunks."""
    verifier = CitationVerifier(
        available_files=set(sample_snapshot.keys()),
        file_line_counts={"server/app/api/users.py": 10},
        available_symbols={"list_users", "delete_user", "require_auth"},
        available_chunks={"chunk_abc123"},
    )

    # 1. Valid file with line range
    c1 = verifier.verify_single("server/app/api/users.py:4-6")
    assert c1.resolved is True
    assert c1.path == "server/app/api/users.py"
    assert c1.start_line == 4
    assert c1.end_line == 6

    # 2. Valid symbol
    c2 = verifier.verify_single("[list_users]")
    assert c2.resolved is True
    assert c2.symbol_key == "list_users"

    # 3. Valid chunk doc_id
    c3 = verifier.verify_single("[chunk_abc123]")
    assert c3.resolved is True
    assert c3.doc_id == "chunk_abc123"

    # 4. Unknown path
    c4 = verifier.verify_single("server/app/nonexistent.py:1-10")
    assert c4.resolved is False
    assert "not found in snapshot" in c4.error_reason

    # 5. Out of bounds line range
    c5 = verifier.verify_single("server/app/api/users.py:1-50")
    assert c5.resolved is False
    assert "exceeds file length" in c5.error_reason


def test_citation_batch_verification(sample_snapshot: dict[str, str]) -> None:
    """Verify markdown text with inline citations and compute grounding ratio."""
    markdown_text = (
        "The endpoints are defined in [source: server/app/api/users.py:4-6]. "
        "Also see [server/app/core/auth.py] and unknown helper [unknown_service.py:1-5]."
    )

    result = verify_citations(
        citations=[],
        available_files=set(sample_snapshot.keys()),
        file_line_counts={"server/app/api/users.py": 10, "server/app/core/auth.py": 6},
        text_content=markdown_text,
    )

    assert result.total_citations == 3
    assert len(result.resolved_citations) == 2
    assert len(result.unresolved_citations) == 1
    assert result.is_fully_grounded is False
    assert round(result.grounding_ratio, 2) == 0.67
    assert "Unresolved citations detected" in result.feedback_message


# ---------------------------------------------------------------------------
# 9. Batch Finding Verification
# ---------------------------------------------------------------------------


def test_verify_evidence_batch(sample_snapshot: dict[str, str]) -> None:
    """Batch verification separates accepted findings from rejected ones."""
    drafts = [
        # Valid draft
        {
            "draft_id": "valid_01",
            "rule_id": "devmind.authn.unprotected_route",
            "file_path": "server/app/api/users.py",
            "line_range": (4, 6),
            "evidence_level": "E2",
        },
        # Invalid draft: unknown rule
        {
            "draft_id": "invalid_rule",
            "rule_id": "unknown_suspicious_rule",
            "file_path": "server/app/api/users.py",
            "line_range": (4, 6),
            "evidence_level": "E2",
        },
        # Invalid draft: out of bounds lines
        {
            "draft_id": "invalid_bounds",
            "rule_id": "devmind.authn.unprotected_route",
            "file_path": "server/app/api/users.py",
            "line_range": (20, 30),
            "evidence_level": "E2",
        },
    ]

    accepted, rejected = verify_evidence(drafts, file_snapshot=sample_snapshot)
    assert len(accepted) == 1
    assert accepted[0].draft_id == "valid_01"
    assert accepted[0].is_verified is True

    assert len(rejected) == 2
    rejected_ids = [r.draft_id for r in rejected]
    assert "invalid_rule" in rejected_ids
    assert "invalid_bounds" in rejected_ids
