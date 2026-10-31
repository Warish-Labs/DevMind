"""Tests for Bug Memory and Living Docs evaluation benchmark harness and baselines (CAP-03, CAP-04, docs/09 §9, M12-06)."""

from __future__ import annotations

import json
from pathlib import Path

from evals.bug_docs.harness import (
    DATASET_PATH,
    evaluate_bug_case,
    evaluate_drift_case,
    run_bug_docs_benchmark,
    save_benchmark_results,
)
from evals.bug_docs.metrics import (
    BugDocsBenchmarkSummary,
    BugMemoryMetrics,
    LivingDocsMetrics,
)


def test_bug_docs_dataset_structure_and_schema() -> None:
    """Verify that dataset.json exists, has valid structure, and includes bug and drift test cases."""
    assert DATASET_PATH.is_file(), f"Dataset file missing at {DATASET_PATH}"

    with open(DATASET_PATH, encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("benchmark") == "devmind-bug-docs-v1"
    assert "bug_cases" in data
    assert "drift_cases" in data

    bug_cases = data["bug_cases"]
    drift_cases = data["drift_cases"]

    assert len(bug_cases) >= 5, "Must have at least 5 bug evaluation cases"
    assert len(drift_cases) >= 5, "Must have at least 5 drift evaluation cases"

    # Verify bug case structure
    for c in bug_cases:
        assert "id" in c
        assert "name" in c
        assert "raw_error" in c
        assert "candidate_bugs" in c
        assert "expected_exception_type" in c

    # Verify drift case structure
    for c in drift_cases:
        assert "id" in c
        assert "name" in c
        assert "markdown_doc" in c
        assert "expected_drift_kinds" in c
        assert "expected_drift_count" in c


def test_evaluate_single_bug_case() -> None:
    """Verify evaluation of a single bug memory case."""
    with open(DATASET_PATH, encoding="utf-8") as f:
        data = json.load(f)

    case = data["bug_cases"][0]
    result = evaluate_bug_case(case)

    assert result["id"] == case["id"]
    assert result["fingerprint_correct"] is True
    assert result["predicted_candidate_id"] == case["expected_top_candidate_id"]
    assert result["max_score"] >= case["expected_min_score"]


def test_evaluate_single_drift_case() -> None:
    """Verify evaluation of a single documentation drift case."""
    with open(DATASET_PATH, encoding="utf-8") as f:
        data = json.load(f)

    case = data["drift_cases"][0]
    result = evaluate_drift_case(case)

    assert result["id"] == case["id"]
    assert set(result["predicted_drift_kinds"]) == set(case["expected_drift_kinds"])
    assert result["diff_valid"] is True


def test_compute_metrics_and_summary_thresholds() -> None:
    """Verify benchmark metrics calculation and pass/fail gate criteria."""
    summary = run_bug_docs_benchmark(DATASET_PATH)

    assert isinstance(summary, BugDocsBenchmarkSummary)
    assert isinstance(summary.bug_memory_metrics, BugMemoryMetrics)
    assert isinstance(summary.living_docs_metrics, LivingDocsMetrics)

    assert summary.bug_memory_metrics.total_cases >= 5
    assert summary.bug_memory_metrics.top_1_accuracy >= 0.80
    assert summary.bug_memory_metrics.mean_reciprocal_rank >= 0.80

    assert summary.living_docs_metrics.total_cases >= 5
    assert summary.living_docs_metrics.drift_f1_score >= 0.80
    assert summary.living_docs_metrics.patch_diff_validity >= 0.80

    assert summary.composite_score >= 0.85
    assert summary.status == "passed"


def test_save_and_serialize_results(tmp_path: Path) -> None:
    """Verify serialization to dictionary and persistence."""
    summary = run_bug_docs_benchmark(DATASET_PATH)
    d = summary.to_dict()

    assert d["benchmark"] == "devmind-bug-docs-v1"
    assert "bug_memory_metrics" in d
    assert "living_docs_metrics" in d
    assert d["status"] in ("passed", "failed")

    run_file, latest_file = save_benchmark_results(summary)
    assert run_file.exists()
    assert latest_file.exists()
