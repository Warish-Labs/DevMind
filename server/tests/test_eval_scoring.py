"""Unit tests for Deterministic Evaluation & Release-Readiness Scoring Engine (CAP-09, docs/01 §8, docs/03 §3.7, OQ-18, M12-09)."""

from __future__ import annotations

from app.analysis.eval_scoring import (
    BugRecordInput,
    DocDriftInput,
    EvaluationInputs,
    FeatureChecklistInput,
    FindingInput,
    ProjectEvaluationScorer,
    TaskSummaryInput,
    TestSignalInput,
)


def test_eval_scoring_perfect_project_verdict_ready() -> None:
    """Verify clean project with 0 findings, 100% tests, and synced docs yields 'ready' verdict."""
    inputs = EvaluationInputs(
        findings=[],
        bugs=[],
        drift_items=[],
        test_signals=TestSignalInput(
            total_tests=50,
            passed_tests=50,
            failed_tests=0,
            has_ci_run=True,
        ),
        feature_checklist=[
            FeatureChecklistInput(name="Auth Flow", completed=True, is_critical=True),
            FeatureChecklistInput(name="API Gateway", completed=True, is_critical=True),
        ],
        task_summary=TaskSummaryInput(
            total_tasks=10,
            completed_tasks=10,
            blocked_tasks=0,
            has_cyclic_dependency=False,
        ),
        has_tracked_docs=True,
    )

    result = ProjectEvaluationScorer.evaluate(inputs)

    assert result.verdict == "ready"
    assert result.overall_score >= 95.0
    assert len(result.blockers) == 0
    assert len(result.warnings) == 0
    assert result.functionality_confidence == "high"
    assert any("Zero open security findings" in pos for pos in result.positive_indicators)
    assert any("100% test pass rate" in pos for pos in result.positive_indicators)


def test_eval_scoring_critical_security_vulnerability_blocks_release() -> None:
    """Verify an open critical security finding drops security score and forces 'not_ready'."""
    inputs = EvaluationInputs(
        findings=[
            FindingInput(
                id="finding_sec_1",
                title="SQL Injection in /api/v1/search",
                severity="CRITICAL",
                status="open",
                category="security",
            ),
        ],
        test_signals=TestSignalInput(total_tests=10, passed_tests=10),
    )

    result = ProjectEvaluationScorer.evaluate(inputs)

    assert result.verdict == "not_ready"
    assert result.dimension_scores["security"] == 65.0  # 100 - 35
    assert len(result.blockers) == 1
    assert result.blockers[0]["dimension"] == "security"
    assert result.blockers[0]["severity"] == "CRITICAL"


def test_eval_scoring_dismissed_and_fixed_findings_do_not_penalize() -> None:
    """Verify dismissed false positives and fixed findings do not degrade scores."""
    inputs = EvaluationInputs(
        findings=[
            FindingInput(
                id="finding_sec_dismissed",
                title="Potential SSRF in internal fetch",
                severity="CRITICAL",
                status="dismissed",
                category="security",
            ),
            FindingInput(
                id="finding_sec_fixed",
                title="Missing CSRF on form",
                severity="HIGH",
                status="fixed",
                category="security",
            ),
        ],
        test_signals=TestSignalInput(total_tests=10, passed_tests=10),
    )

    result = ProjectEvaluationScorer.evaluate(inputs)

    assert result.dimension_scores["security"] == 100.0
    assert len(result.blockers) == 0


def test_eval_scoring_severe_recurring_bug_penalizes_code_quality() -> None:
    """Verify unresolved bug with >= 10 occurrences penalizes code quality and blocks release."""
    inputs = EvaluationInputs(
        bugs=[
            BugRecordInput(
                id="bug_1",
                title="Unhandled NullPointerException in Billing",
                occurrence_count=12,
                has_resolution=False,
            )
        ],
        test_signals=TestSignalInput(total_tests=10, passed_tests=10),
    )

    result = ProjectEvaluationScorer.evaluate(inputs)

    assert result.verdict == "not_ready"
    assert result.dimension_scores["code_quality"] == 85.0
    assert any(b["dimension"] == "code_quality" for b in result.blockers)


def test_eval_scoring_failing_tests_trigger_blocker() -> None:
    """Verify failing tests degrade test score and create a critical release blocker."""
    inputs = EvaluationInputs(
        test_signals=TestSignalInput(
            total_tests=20,
            passed_tests=18,
            failed_tests=2,
            has_ci_run=True,
        )
    )

    result = ProjectEvaluationScorer.evaluate(inputs)

    assert result.verdict == "not_ready"
    assert result.dimension_scores["testing"] == 50.0  # 100 - (2 * 25)
    assert any(b["id"] == "failed_tests" for b in result.blockers)


def test_eval_scoring_documentation_drift_creates_warnings() -> None:
    """Verify active undocumented routes reduce doc score and produce 'ready_with_warnings'."""
    inputs = EvaluationInputs(
        drift_items=[
            DocDriftInput(
                id="drift_1",
                kind="undocumented_route",
                status="detected",
                explanation="POST /api/v1/refunds is undocumented",
            ),
            DocDriftInput(
                id="drift_2",
                kind="removed_route",
                status="detected",
                explanation="GET /api/v1/legacy is removed from code",
            ),
        ],
        test_signals=TestSignalInput(total_tests=10, passed_tests=10),
        has_tracked_docs=True,
    )

    result = ProjectEvaluationScorer.evaluate(inputs)

    assert result.verdict == "ready_with_warnings"
    assert result.dimension_scores["documentation"] == 80.0  # 100 - 12 - 8
    assert len(result.blockers) == 0
    assert len(result.warnings) == 2


def test_eval_scoring_oq18_functionality_confidence() -> None:
    """Verify OQ-18 rule: feature checklist gives high confidence, missing checklist gives low confidence."""
    # Case A: No checklist supplied
    inputs_no_checklist = EvaluationInputs(
        feature_checklist=[],
        task_summary=TaskSummaryInput(total_tasks=8, completed_tasks=6),
        test_signals=TestSignalInput(total_tests=10, passed_tests=10),
    )
    res_a = ProjectEvaluationScorer.evaluate(inputs_no_checklist)
    assert res_a.functionality_confidence == "low"
    assert res_a.dimension_scores["functionality"] == 75.0  # (6 / 8) * 100

    # Case B: Checklist supplied with incomplete critical feature
    inputs_with_checklist = EvaluationInputs(
        feature_checklist=[
            FeatureChecklistInput(name="Core Auth", completed=True, is_critical=True),
            FeatureChecklistInput(name="Payment Integration", completed=False, is_critical=True),
        ],
        test_signals=TestSignalInput(total_tests=10, passed_tests=10),
    )
    res_b = ProjectEvaluationScorer.evaluate(inputs_with_checklist)
    assert res_b.functionality_confidence == "high"
    assert res_b.verdict == "not_ready"
    assert any(b["id"] == "feat_Payment Integration" for b in res_b.blockers)


def test_eval_scoring_cyclic_task_dependency_blocks_architecture() -> None:
    """Verify cyclic dependency in task DAG creates an architectural blocker."""
    inputs = EvaluationInputs(
        task_summary=TaskSummaryInput(
            total_tasks=5,
            completed_tasks=2,
            has_cyclic_dependency=True,
        ),
        test_signals=TestSignalInput(total_tests=10, passed_tests=10),
    )

    result = ProjectEvaluationScorer.evaluate(inputs)

    assert result.verdict == "not_ready"
    assert result.dimension_scores["architecture"] == 65.0  # 100 - 35
    assert any(b["id"] == "cyclic_dependency" for b in result.blockers)


def test_eval_scoring_composite_weighted_score_calculation() -> None:
    """Verify composite overall score equals exact weighted sum of dimensions."""
    inputs = EvaluationInputs(
        test_signals=TestSignalInput(total_tests=10, passed_tests=10),
        has_tracked_docs=True,
    )
    result = ProjectEvaluationScorer.evaluate(inputs)

    expected = (
        result.dimension_scores["security"] * 0.25
        + result.dimension_scores["code_quality"] * 0.20
        + result.dimension_scores["testing"] * 0.20
        + result.dimension_scores["documentation"] * 0.15
        + result.dimension_scores["functionality"] * 0.10
        + result.dimension_scores["architecture"] * 0.10
    )
    assert abs(result.overall_score - round(expected, 1)) < 0.05
