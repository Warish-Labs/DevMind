"""Benchmark harness and evaluation runner for Project Mentor & Health Evaluation (docs/01 CAP-08/09, docs/09 §9, M12-12)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SERVER_DIR = ROOT_DIR / "server"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from app.analysis.eval_scoring import (  # noqa: E402
    BugRecordInput,
    DocDriftInput,
    EvaluationInputs,
    FeatureChecklistInput,
    FindingInput,
    ProjectEvaluationScorer,
    TaskSummaryInput,
    TestSignalInput,
)
from app.analysis.task_dag import CyclicDependencyError, TaskDAG, TaskNode  # noqa: E402
from evals.mentor.metrics import (  # noqa: E402
    MentorBenchmarkSummary,
    ProjectEvaluationMetrics,
    TaskRecommendationMetrics,
    compute_project_evaluation_metrics,
    compute_task_recommendation_metrics,
)

DATASET_PATH = Path(__file__).resolve().parent / "dataset.json"
RESULTS_DIR = ROOT_DIR / "evals" / "results" / "mentor"


def get_git_commit_hash() -> str:
    """Resolve current short git commit hash for benchmark tracking."""
    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT_DIR),
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return output.strip()
    except Exception:
        return "unknown"


def evaluate_recommendation_case(case: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a single TaskDAG recommendation benchmark case."""
    dag = TaskDAG()
    cycle_detected = False

    # 1. Register task nodes
    for raw_task in case.get("tasks", []):
        node = TaskNode(
            id=UUID(raw_task["id"]),
            title=raw_task.get("title", ""),
            status=raw_task.get("status", "open"),
            priority=raw_task.get("priority", "medium"),
            finding_severity=raw_task.get("finding_severity"),
        )
        dag.add_node(node)

    # 2. Add edges and detect cycles
    for raw_task in case.get("tasks", []):
        task_id = UUID(raw_task["id"])
        for dep_str in raw_task.get("depends_on", []):
            dep_id = UUID(dep_str)
            try:
                dag.add_edge(task_id, dep_id)
            except CyclicDependencyError:
                cycle_detected = True

    if not cycle_detected and dag.detect_cycle() is not None:
        cycle_detected = True

    # 3. Perform ranking if acyclic
    ranked_ids: list[str] = []
    top_ready: bool | None = None
    top_downstream: int = 0

    if not cycle_detected:
        ranked = dag.rank_tasks()
        ranked_ids = [str(r.task.id) for r in ranked]
        if ranked:
            top_ready = ranked[0].is_ready
            top_downstream = ranked[0].downstream_impact_count

    return {
        "id": case["id"],
        "name": case.get("name", ""),
        "has_cycle": case.get("has_cycle", False),
        "cycle_detected": cycle_detected,
        "expected_top_task_id": case.get("expected_top_task_id"),
        "predicted_ranked_ids": ranked_ids,
        "expected_is_ready": case.get("expected_is_ready"),
        "predicted_is_ready": top_ready,
        "expected_downstream_impact_count": case.get("expected_downstream_impact_count", 0),
        "predicted_downstream_impact_count": top_downstream,
    }


def evaluate_health_case(case: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a single project health audit benchmark case."""
    raw_inputs = case.get("inputs", {})

    findings = [
        FindingInput(
            id=f.get("id", ""),
            title=f.get("title", ""),
            severity=f.get("severity", "MEDIUM"),
            status=f.get("status", "open"),
            category=f.get("category", "security"),
        )
        for f in raw_inputs.get("findings", [])
    ]

    bugs = [
        BugRecordInput(
            id=b.get("id", ""),
            title=b.get("title", ""),
            occurrence_count=b.get("occurrence_count", 1),
            has_resolution=b.get("has_resolution", False),
        )
        for b in raw_inputs.get("bugs", [])
    ]

    drift_items = [
        DocDriftInput(
            id=d.get("id", ""),
            kind=d.get("kind", "stale_section"),
            status=d.get("status", "detected"),
            explanation=d.get("explanation", ""),
        )
        for d in raw_inputs.get("drift_items", [])
    ]

    raw_tests = raw_inputs.get("test_signals", {})
    test_signals = TestSignalInput(
        total_tests=raw_tests.get("total_tests", 0),
        passed_tests=raw_tests.get("passed_tests", 0),
        failed_tests=raw_tests.get("failed_tests", 0),
        skipped_tests=raw_tests.get("skipped_tests", 0),
        has_ci_run=raw_tests.get("has_ci_run", True),
    )

    checklist = [
        FeatureChecklistInput(
            name=c.get("name", ""),
            completed=c.get("completed", False),
            is_critical=c.get("is_critical", False),
        )
        for c in raw_inputs.get("feature_checklist", [])
    ]

    raw_tasks = raw_inputs.get("task_summary", {})
    task_summary = TaskSummaryInput(
        total_tasks=raw_tasks.get("total_tasks", 0),
        completed_tasks=raw_tasks.get("completed_tasks", 0),
        blocked_tasks=raw_tasks.get("blocked_tasks", 0),
        has_cyclic_dependency=raw_tasks.get("has_cyclic_dependency", False),
    )

    inputs = EvaluationInputs(
        findings=findings,
        bugs=bugs,
        drift_items=drift_items,
        test_signals=test_signals,
        feature_checklist=checklist,
        task_summary=task_summary,
        has_tracked_docs=raw_inputs.get("has_tracked_docs", True),
    )

    result = ProjectEvaluationScorer.evaluate(inputs)

    return {
        "id": case["id"],
        "name": case.get("name", ""),
        "expected_verdict": case.get("expected_verdict"),
        "predicted_verdict": result.verdict,
        "predicted_overall_score": result.overall_score,
        "expected_min_score": case.get("expected_min_score"),
        "expected_max_score": case.get("expected_max_score"),
        "expected_blockers_count": case.get("expected_blockers_count", 0),
        "predicted_blockers_count": len(result.blockers),
        "expected_warnings_count": case.get("expected_warnings_count"),
        "predicted_warnings_count": len(result.warnings),
        "expected_functionality_confidence": case.get("expected_functionality_confidence", "high"),
        "predicted_functionality_confidence": result.functionality_confidence,
    }


def run_mentor_benchmark(dataset_path: Path = DATASET_PATH) -> MentorBenchmarkSummary:
    """Run full Project Mentor and Health Evaluation benchmark suite."""
    if not dataset_path.is_file():
        raise FileNotFoundError(f"Evaluation dataset not found at {dataset_path}")

    with open(dataset_path, encoding="utf-8") as f:
        data = json.load(f)

    rec_cases = data.get("recommendation_cases", [])
    health_cases = data.get("health_evaluation_cases", [])

    rec_eval_results = [evaluate_recommendation_case(c) for c in rec_cases]
    health_eval_results = [evaluate_health_case(c) for c in health_cases]

    rec_metrics: TaskRecommendationMetrics = compute_task_recommendation_metrics(rec_eval_results)
    health_metrics: ProjectEvaluationMetrics = compute_project_evaluation_metrics(health_eval_results)

    # Composite score: mean of rec top-1 accuracy, MRR, health verdict accuracy, and blocker F1
    composite = round(
        (
            rec_metrics.top_1_accuracy
            + rec_metrics.mean_reciprocal_rank
            + health_metrics.verdict_accuracy
            + health_metrics.blocker_f1_score
        )
        / 4.0,
        4,
    )

    passed = (
        composite >= 0.85
        and rec_metrics.top_1_accuracy >= 0.85
        and rec_metrics.mean_reciprocal_rank >= 0.85
        and health_metrics.verdict_accuracy >= 0.85
        and health_metrics.blocker_f1_score >= 0.85
    )

    status = "passed" if passed else "failed"
    git_commit = get_git_commit_hash()
    timestamp = datetime.now(UTC).isoformat()

    return MentorBenchmarkSummary(
        benchmark=data.get("benchmark", "devmind-mentor-eval-v1"),
        git_commit=git_commit,
        timestamp=timestamp,
        recommendation_metrics=rec_metrics,
        evaluation_metrics=health_metrics,
        composite_score=composite,
        status=status,
    )


def save_benchmark_results(summary: MentorBenchmarkSummary) -> tuple[Path, Path]:
    """Persist benchmark run results to evals/results/mentor/."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts_slug = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    run_file = RESULTS_DIR / f"{ts_slug}_{summary.git_commit}.json"
    latest_file = RESULTS_DIR / "latest.json"

    data = summary.to_dict()
    payload = json.dumps(data, indent=2) + "\n"

    with open(run_file, "w", encoding="utf-8") as f:
        f.write(payload)

    with open(latest_file, "w", encoding="utf-8") as f:
        f.write(payload)

    return run_file, latest_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Project Mentor & Health Evaluation Benchmark Runner")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DATASET_PATH,
        help="Path to dataset.json",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        default=True,
        help="Persist benchmark results",
    )
    args = parser.parse_args()

    summary = run_mentor_benchmark(dataset_path=args.dataset)
    print(
        f"Project Mentor Benchmark: {summary.status.upper()} (Composite Score: {summary.composite_score:.2%})"
    )
    print(
        f"  Recommendation: Top-1 Acc={summary.recommendation_metrics.top_1_accuracy:.2%}, "
        f"MRR={summary.recommendation_metrics.mean_reciprocal_rank:.4f}, "
        f"Ready Acc={summary.recommendation_metrics.ready_accuracy:.2%}"
    )
    print(
        f"  Health Audit:   Verdict Acc={summary.evaluation_metrics.verdict_accuracy:.2%}, "
        f"Blocker F1={summary.evaluation_metrics.blocker_f1_score:.2%}, "
        f"Score MAE={summary.evaluation_metrics.score_mae:.2f}"
    )

    if args.save:
        _, latest = save_benchmark_results(summary)
        print(f"  Persisted results to {latest}")

    if summary.status != "passed":
        sys.exit(1)


if __name__ == "__main__":
    main()
