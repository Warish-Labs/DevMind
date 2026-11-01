"""Tests for Project Mentor & Health Evaluation benchmark harness and recorded baselines (CAP-08, CAP-09, docs/09 §9, M12-12)."""

from __future__ import annotations

import json
from pathlib import Path

from evals.mentor.harness import (
    DATASET_PATH,
    evaluate_health_case,
    evaluate_recommendation_case,
    run_mentor_benchmark,
    save_benchmark_results,
)
from evals.mentor.metrics import (
    MentorBenchmarkSummary,
    ProjectEvaluationMetrics,
    TaskRecommendationMetrics,
)


def test_mentor_dataset_structure_and_schema() -> None:
    """Verify that dataset.json exists, contains valid schema, and covers recommendation and health cases."""
    assert DATASET_PATH.is_file(), f"Dataset file missing at {DATASET_PATH}"

    with open(DATASET_PATH, encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("benchmark") == "devmind-mentor-eval-v1"
    assert "recommendation_cases" in data
    assert "health_evaluation_cases" in data

    rec_cases = data["recommendation_cases"]
    health_cases = data["health_evaluation_cases"]

    assert len(rec_cases) >= 5, "Must have at least 5 recommendation evaluation cases"
    assert len(health_cases) >= 5, "Must have at least 5 health evaluation cases"

    # Verify recommendation case fields
    for c in rec_cases:
        assert "id" in c
        assert "name" in c
        assert "tasks" in c
        assert "has_cycle" in c
        for t in c["tasks"]:
            assert "id" in t
            assert "title" in t
            assert "priority" in t
            assert "depends_on" in t

    # Verify health evaluation case fields
    for c in health_cases:
        assert "id" in c
        assert "name" in c
        assert "inputs" in c
        assert "expected_verdict" in c
        assert c["expected_verdict"] in {"ready", "ready_with_warnings", "not_ready"}
        assert "expected_blockers_count" in c


def test_evaluate_single_recommendation_case() -> None:
    """Verify evaluation of a single task recommendation benchmark case."""
    with open(DATASET_PATH, encoding="utf-8") as f:
        data = json.load(f)

    first_case = data["recommendation_cases"][0]
    result = evaluate_recommendation_case(first_case)

    assert result["id"] == first_case["id"]
    assert result["cycle_detected"] is False
    assert result["predicted_ranked_ids"][0] == first_case["expected_top_task_id"]
    assert result["predicted_is_ready"] is True
    assert result["predicted_downstream_impact_count"] == 2


def test_evaluate_single_health_case() -> None:
    """Verify evaluation of a single project health audit benchmark case."""
    with open(DATASET_PATH, encoding="utf-8") as f:
        data = json.load(f)

    prod_ready_case = data["health_evaluation_cases"][0]
    result = evaluate_health_case(prod_ready_case)

    assert result["id"] == prod_ready_case["id"]
    assert result["predicted_verdict"] == "ready"
    assert result["predicted_overall_score"] >= 90.0
    assert result["predicted_blockers_count"] == 0
    assert result["predicted_functionality_confidence"] == "high"


def test_run_mentor_benchmark_baseline() -> None:
    """Run full Project Mentor benchmark and verify accuracy and F1 quality thresholds."""
    summary = run_mentor_benchmark(DATASET_PATH)

    assert isinstance(summary, MentorBenchmarkSummary)
    assert isinstance(summary.recommendation_metrics, TaskRecommendationMetrics)
    assert isinstance(summary.evaluation_metrics, ProjectEvaluationMetrics)
    assert summary.status == "passed", f"Benchmark failed: composite={summary.composite_score}"

    # Verify TaskDAG recommendation thresholds (docs/09 §9, CAP-08)
    assert summary.recommendation_metrics.top_1_accuracy >= 0.85
    assert summary.recommendation_metrics.mean_reciprocal_rank >= 0.85
    assert summary.recommendation_metrics.ready_accuracy >= 0.85
    assert summary.recommendation_metrics.cycle_detection_accuracy >= 0.85

    # Verify Health evaluation thresholds (docs/09 §9, CAP-09)
    assert summary.evaluation_metrics.verdict_accuracy >= 0.85
    assert summary.evaluation_metrics.blocker_precision >= 0.85
    assert summary.evaluation_metrics.blocker_recall >= 0.85
    assert summary.evaluation_metrics.blocker_f1_score >= 0.85

    # Composite score quality gate
    assert summary.composite_score >= 0.85


def test_save_and_serialize_mentor_results(tmp_path: Path) -> None:
    """Verify benchmark serialization to dictionary and filesystem persistence."""
    summary = run_mentor_benchmark(DATASET_PATH)
    d = summary.to_dict()

    assert d["benchmark"] == "devmind-mentor-eval-v1"
    assert "recommendation_metrics" in d
    assert "evaluation_metrics" in d
    assert d["status"] == "passed"

    run_file, latest_file = save_benchmark_results(summary)
    assert run_file.exists()
    assert latest_file.exists()
