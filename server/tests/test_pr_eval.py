"""Tests for PR Intelligence and ReviewBuddy evaluation harness and baselines (docs/01 CAP-05/06, docs/09 §9, M11-08)."""

from __future__ import annotations

import json
from pathlib import Path

from evals.pr_intelligence.harness import (
    DATASET_PATH,
    evaluate_impact_case,
    evaluate_review_case,
    run_pr_intelligence_benchmark,
    save_benchmark_results,
)
from evals.pr_intelligence.metrics import (
    ChangeImpactMetrics,
    PRIntelligenceBenchmarkSummary,
    ReviewChecklistMetrics,
)


def test_pr_intelligence_dataset_structure_and_schema() -> None:
    """Verify that dataset.json exists, contains valid schema, and covers impact and review cases."""
    assert DATASET_PATH.is_file(), f"Dataset file missing at {DATASET_PATH}"

    with open(DATASET_PATH, encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("benchmark") == "devmind-pr-intelligence-v1"
    assert "impact_cases" in data
    assert "review_cases" in data

    impact_cases = data["impact_cases"]
    review_cases = data["review_cases"]

    assert len(impact_cases) >= 5, "Must have at least 5 change-impact evaluation cases"
    assert len(review_cases) >= 5, "Must have at least 5 review checklist evaluation cases"

    # Verify impact case fields
    for c in impact_cases:
        assert "id" in c
        assert "name" in c
        assert "changed_files" in c
        assert "expected_risk" in c
        assert c["expected_risk"] in {"critical", "high", "medium", "low"}
        assert "expected_impacted" in c

    # Verify review case fields
    for c in review_cases:
        assert "id" in c
        assert "name" in c
        assert "diff" in c
        assert "expected_rules" in c


def test_evaluate_single_impact_case() -> None:
    """Verify evaluation of a single change-impact benchmark case."""
    with open(DATASET_PATH, encoding="utf-8") as f:
        data = json.load(f)

    first_case = data["impact_cases"][0]
    result = evaluate_impact_case(first_case)

    assert result["id"] == first_case["id"]
    assert result["predicted_risk"] == first_case["expected_risk"]
    assert "revoke_auth_session" in result["predicted_direct_symbols"]


def test_evaluate_single_review_case() -> None:
    """Verify evaluation of a single ReviewBuddy checklist benchmark case."""
    with open(DATASET_PATH, encoding="utf-8") as f:
        data = json.load(f)

    compliant_case = [c for c in data["review_cases"] if c["id"] == "review-case-05-compliant-change"][0]
    result = evaluate_review_case(compliant_case)

    assert result["id"] == compliant_case["id"]
    assert len(result["predicted_rules"]) == 0, "Compliant case must have 0 false alarm findings"


def test_run_pr_intelligence_benchmark_baseline() -> None:
    """Run full PR intelligence benchmark and verify precision/recall meet quality thresholds."""
    summary = run_pr_intelligence_benchmark(DATASET_PATH)

    assert isinstance(summary, PRIntelligenceBenchmarkSummary)
    assert summary.status == "passed", f"Benchmark failed: composite={summary.composite_score}"

    # Verify change-impact thresholds (docs/09 §9)
    assert summary.impact_metrics.precision >= 0.85
    assert summary.impact_metrics.recall >= 0.85
    assert summary.impact_metrics.risk_accuracy >= 0.80

    # Verify ReviewBuddy thresholds
    assert summary.review_metrics.precision >= 0.85
    assert summary.review_metrics.recall >= 0.85
    assert summary.review_metrics.false_positive_rate <= 0.15

    # Verify composite score
    assert summary.composite_score >= 0.85


def test_save_pr_intelligence_benchmark_results(tmp_path: Path, monkeypatch) -> None:
    """Verify persisting benchmark results to JSON."""
    monkeypatch.setattr("evals.pr_intelligence.harness.RESULTS_DIR", tmp_path)

    summary = PRIntelligenceBenchmarkSummary(
        benchmark="devmind-pr-intelligence-test",
        git_commit="test_sha",
        timestamp="2026-10-31T00:00:00Z",
        impact_metrics=ChangeImpactMetrics(
            total_cases=5, precision=1.0, recall=1.0, f1_score=1.0, risk_accuracy=1.0
        ),
        review_metrics=ReviewChecklistMetrics(
            total_cases=5,
            precision=1.0,
            recall=1.0,
            f1_score=1.0,
            false_positive_rate=0.0,
            category_accuracy=1.0,
        ),
        composite_score=1.0,
        status="passed",
    )

    run_file, latest_file = save_benchmark_results(summary)
    assert run_file.is_file()
    assert latest_file.is_file()

    with open(latest_file, encoding="utf-8") as f:
        data = json.load(f)
    assert data["benchmark"] == "devmind-pr-intelligence-test"
    assert data["status"] == "passed"
    assert data["composite_score"] == 1.0
