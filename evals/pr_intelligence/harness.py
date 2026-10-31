"""Benchmark harness and evaluation runner for PR Intelligence and ReviewBuddy (docs/01 CAP-05/06, docs/09 §9, M11-08)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SERVER_DIR = ROOT_DIR / "server"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from app.analysis.change_impact import ChangeImpactAnalyzer  # noqa: E402
from app.analysis.review_buddy import ReviewBuddyAnalyzer  # noqa: E402
from app.persistence.repositories.review_rule_repo import DEFAULT_CHECKLIST_RULES  # noqa: E402
from evals.pr_intelligence.metrics import (  # noqa: E402
    ChangeImpactMetrics,
    PRIntelligenceBenchmarkSummary,
    ReviewChecklistMetrics,
    compute_change_impact_metrics,
    compute_review_checklist_metrics,
)

DATASET_PATH = Path(__file__).resolve().parent / "dataset.json"
RESULTS_DIR = ROOT_DIR / "evals" / "results" / "pr_intelligence"


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


def evaluate_impact_case(case: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a single change-impact benchmark case."""
    symbols = case.get("symbols", [])
    relationships = case.get("relationships", [])
    changed_files = case.get("changed_files", [])
    diff_text = case.get("diff", "")

    analyzer = ChangeImpactAnalyzer(symbols=symbols, relationships=relationships)
    report = analyzer.analyze(changed_files=changed_files, diff_text=diff_text)

    predicted_impacted = report.affected_modules
    predicted_risk = report.risk_level
    predicted_symbols = [s.name for s in report.direct_symbols]

    return {
        "id": case["id"],
        "name": case.get("name", ""),
        "expected_risk": case.get("expected_risk", "low"),
        "predicted_risk": predicted_risk,
        "expected_direct_symbols": case.get("expected_direct_symbols", []),
        "predicted_direct_symbols": predicted_symbols,
        "expected_impacted": case.get("expected_impacted", []),
        "predicted_impacted": predicted_impacted,
    }


def evaluate_review_case(case: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a single ReviewBuddy checklist benchmark case."""
    diff_text = case.get("diff", "")
    custom_rules = case.get("custom_rules")
    rules_to_use = custom_rules if custom_rules is not None else DEFAULT_CHECKLIST_RULES
    known_tests = set(case.get("known_test_files", []))

    analyzer = ReviewBuddyAnalyzer(rules=rules_to_use)
    findings = analyzer.evaluate_diff(diff_text=diff_text, known_test_files=known_tests)

    predicted_rules = [
        {
            "rule_id": f.rule_id,
            "category": f.category,
            "severity": f.severity,
            "file_path": f.file_path,
            "start_line": f.start_line,
        }
        for f in findings
    ]

    return {
        "id": case["id"],
        "name": case.get("name", ""),
        "expected_rules": case.get("expected_rules", []),
        "predicted_rules": predicted_rules,
    }


def run_pr_intelligence_benchmark(dataset_path: Path = DATASET_PATH) -> PRIntelligenceBenchmarkSummary:
    """Run full PR intelligence and ReviewBuddy benchmark evaluation."""
    if not dataset_path.is_file():
        raise FileNotFoundError(f"Evaluation dataset not found at {dataset_path}")

    with open(dataset_path, encoding="utf-8") as f:
        data = json.load(f)

    impact_cases = data.get("impact_cases", [])
    review_cases = data.get("review_cases", [])

    impact_eval_results = [evaluate_impact_case(c) for c in impact_cases]
    review_eval_results = [evaluate_review_case(c) for c in review_cases]

    impact_metrics: ChangeImpactMetrics = compute_change_impact_metrics(impact_eval_results)
    review_metrics: ReviewChecklistMetrics = compute_review_checklist_metrics(review_eval_results)

    # Composite score: mean of impact F1, impact risk accuracy, review precision, review recall
    composite = round(
        (
            impact_metrics.f1_score
            + impact_metrics.risk_accuracy
            + review_metrics.precision
            + review_metrics.recall
        )
        / 4.0,
        4,
    )

    passed = (
        composite >= 0.85
        and impact_metrics.risk_accuracy >= 0.80
        and review_metrics.precision >= 0.80
        and review_metrics.recall >= 0.80
    )

    status = "passed" if passed else "failed"
    git_commit = get_git_commit_hash()
    timestamp = datetime.now(UTC).isoformat()

    return PRIntelligenceBenchmarkSummary(
        benchmark=data.get("benchmark", "devmind-pr-intelligence-v1"),
        git_commit=git_commit,
        timestamp=timestamp,
        impact_metrics=impact_metrics,
        review_metrics=review_metrics,
        composite_score=composite,
        status=status,
    )


def save_benchmark_results(summary: PRIntelligenceBenchmarkSummary) -> tuple[Path, Path]:
    """Persist benchmark run results to evals/results/pr_intelligence/."""
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
    parser = argparse.ArgumentParser(description="PR Intelligence & ReviewBuddy Benchmark Runner")
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

    summary = run_pr_intelligence_benchmark(dataset_path=args.dataset)
    print(
        f"PR Intelligence Benchmark: {summary.status.upper()} (Composite Score: {summary.composite_score:.2%})"
    )
    print(
        f"  Change-Impact: P={summary.impact_metrics.precision:.2%}, R={summary.impact_metrics.recall:.2%}, "
        f"Risk-Acc={summary.impact_metrics.risk_accuracy:.2%}"
    )
    print(
        f"  ReviewBuddy:   P={summary.review_metrics.precision:.2%}, R={summary.review_metrics.recall:.2%}, "
        f"FP-Rate={summary.review_metrics.false_positive_rate:.2%}"
    )

    if args.save:
        _, latest = save_benchmark_results(summary)
        print(f"  Persisted results to {latest}")

    if summary.status != "passed":
        sys.exit(1)


if __name__ == "__main__":
    main()
