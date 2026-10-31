"""Benchmark harness and evaluation runner for Bug Memory & Living Docs (docs/01 CAP-03/04, docs/09 §9, M12-06)."""

from __future__ import annotations

import argparse
import json
import re
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

from app.analysis.doc_drift_detector import DocDriftDetector  # noqa: E402
from app.analysis.doc_parser import DocParser  # noqa: E402
from app.analysis.error_normalizer import ErrorNormalizer  # noqa: E402
from app.orchestration.docsalive import DocsAliveAgent  # noqa: E402
from evals.bug_docs.metrics import (  # noqa: E402
    BugDocsBenchmarkSummary,
    BugMemoryMetrics,
    LivingDocsMetrics,
    compute_bug_memory_metrics,
    compute_living_docs_metrics,
)

DATASET_PATH = Path(__file__).resolve().parent / "dataset.json"
RESULTS_DIR = ROOT_DIR / "evals" / "results" / "bug_docs"


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


def evaluate_bug_case(case: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a single error trace against Bug Memory normalizer and similarity matching."""
    raw_error = case.get("raw_error", "")
    norm = ErrorNormalizer.normalize(raw_error)

    expected_exception = case.get("expected_exception_type")
    exception_correct = norm.exception_type.lower() == expected_exception.lower() if expected_exception else True

    candidate_bugs = case.get("candidate_bugs", [])
    query_tokens = set(re.findall(r"[a-zA-Z0-9_]{3,}", norm.normalized_signature.lower()))

    scored_cands: list[tuple[str, float]] = []
    for cand in candidate_bugs:
        cand_id = cand["id"]
        cand_fp = cand.get("fingerprint") or ""
        # If candidate has empty fingerprint, check exact match with norm
        if cand_fp == norm.fingerprint:
            scored_cands.append((cand_id, 1.0))
            continue

        cand_text = f"{cand.get('signature', '')} {cand.get('title', '')} {cand.get('summary', '')}"
        cand_tokens = set(re.findall(r"[a-zA-Z0-9_]{3,}", cand_text.lower()))

        token_sim = 0.0
        if query_tokens and cand_tokens:
            intersection = query_tokens & cand_tokens
            union = query_tokens | cand_tokens
            token_sim = len(intersection) / len(union) if union else 0.0

        module_boost = 0.0
        cand_mod = cand.get("module_hint", "")
        if norm.module_hint and cand_mod and (norm.module_hint.lower() in cand_mod.lower() or cand_mod.lower() in norm.module_hint.lower()):
            module_boost = 0.25

        score = round(min(0.95, (token_sim * 0.7) + module_boost), 3)
        if score >= 0.15:
            scored_cands.append((cand_id, score))

    scored_cands.sort(key=lambda x: x[1], reverse=True)

    predicted_id = scored_cands[0][0] if scored_cands else None
    max_score = scored_cands[0][1] if scored_cands else 0.0

    return {
        "id": case.get("id"),
        "fingerprint": norm.fingerprint,
        "exception_type": norm.exception_type,
        "fingerprint_correct": exception_correct and bool(norm.fingerprint),
        "predicted_candidate_id": predicted_id,
        "expected_top_candidate_id": case.get("expected_top_candidate_id"),
        "ranked_candidate_ids": [c[0] for c in scored_cands],
        "max_score": max_score,
        "is_duplicate": case.get("is_duplicate", True),
    }


def evaluate_drift_case(case: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a single living documentation case against doc parser and drift detector."""
    markdown_doc = case.get("markdown_doc", "")
    doc_path = case.get("doc_path", "README.md")
    known_symbols = set(case.get("known_symbols", []))
    known_routes = set(case.get("known_routes", []))
    known_files = set(case.get("known_files", []))

    parsed = DocParser.parse(content=markdown_doc, path=doc_path)
    drift_items = DocDriftDetector.detect_drift(
        parsed_docs=[parsed],
        known_routes=known_routes,
        known_symbols=known_symbols,
        known_files=known_files,
    )

    predicted_identifiers: list[str] = [
        item.target_symbol_key or item.target_route_path or ""
        for item in drift_items
        if (item.target_symbol_key or item.target_route_path)
    ]
    predicted_drift_kinds: list[str] = [item.kind for item in drift_items]

    # Test patch proposal generation and diff validity
    diff_valid = True
    if drift_items:
        try:
            from unittest.mock import AsyncMock

            agent = DocsAliveAgent(session=AsyncMock())
            for item in drift_items:
                proposal = agent._build_deterministic_proposal(
                    doc_path=doc_path,
                    candidate=item,
                    doc_content=markdown_doc,
                )
                if not proposal.get("diff_content"):
                    diff_valid = False
                    break
        except Exception:
            diff_valid = False

    return {
        "id": case.get("id"),
        "predicted_affected_identifiers": predicted_identifiers,
        "expected_affected_identifiers": case.get("expected_affected_identifiers", []),
        "predicted_drift_kinds": predicted_drift_kinds,
        "expected_drift_kinds": case.get("expected_drift_kinds", []),
        "diff_valid": diff_valid,
    }


def run_bug_docs_benchmark(dataset_path: Path = DATASET_PATH) -> BugDocsBenchmarkSummary:
    """Execute full evaluation benchmark on Bug Memory and Living Docs cases."""
    with open(dataset_path, encoding="utf-8") as f:
        data = json.load(f)

    bug_cases = data.get("bug_cases", [])
    drift_cases = data.get("drift_cases", [])

    bug_results = [evaluate_bug_case(c) for c in bug_cases]
    drift_results = [evaluate_drift_case(c) for c in drift_cases]

    bug_metrics = compute_bug_memory_metrics(bug_results)
    drift_metrics = compute_living_docs_metrics(drift_results)

    # Composite score: mean of Bug Memory MRR and Living Docs F1 + Diff Validity
    composite = round(
        (
            bug_metrics.mean_reciprocal_rank
            + bug_metrics.top_1_accuracy
            + drift_metrics.drift_f1_score
            + drift_metrics.patch_diff_validity
        )
        / 4.0,
        4,
    )

    passed = (
        composite >= 0.85
        and bug_metrics.top_1_accuracy >= 0.80
        and drift_metrics.drift_f1_score >= 0.80
        and drift_metrics.patch_diff_validity >= 0.80
    )

    status = "passed" if passed else "failed"
    git_commit = get_git_commit_hash()
    timestamp = datetime.now(UTC).isoformat()

    return BugDocsBenchmarkSummary(
        benchmark=data.get("benchmark", "devmind-bug-docs-v1"),
        git_commit=git_commit,
        timestamp=timestamp,
        bug_memory_metrics=bug_metrics,
        living_docs_metrics=drift_metrics,
        composite_score=composite,
        status=status,
    )


def save_benchmark_results(summary: BugDocsBenchmarkSummary) -> tuple[Path, Path]:
    """Persist benchmark run results to evals/results/bug_docs/."""
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
    parser = argparse.ArgumentParser(description="Bug Memory & Living Docs Benchmark Runner")
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
        help="Save results to evals/results/bug_docs/",
    )
    args = parser.parse_args()

    print(f"Running Bug Memory & Living Docs Benchmark on {args.dataset}...")
    summary = run_bug_docs_benchmark(args.dataset)

    print("\n========================================================")
    print(f"Benchmark: {summary.benchmark} (Commit: {summary.git_commit})")
    print(f"Status: {summary.status.upper()} (Composite: {summary.composite_score})")
    print("--------------------------------------------------------")
    print(f"Bug Memory Cases: {summary.bug_memory_metrics.total_cases}")
    print(f"  - Top-1 Accuracy:            {summary.bug_memory_metrics.top_1_accuracy:.2%}")
    print(f"  - Recall@3:                  {summary.bug_memory_metrics.recall_at_3:.2%}")
    print(f"  - MRR:                       {summary.bug_memory_metrics.mean_reciprocal_rank:.4f}")
    print(f"  - Fingerprint Accuracy:      {summary.bug_memory_metrics.fingerprint_accuracy:.2%}")
    print(f"  - Negative Rejection Rate:   {summary.bug_memory_metrics.negative_rejection_rate:.2%}")
    print("--------------------------------------------------------")
    print(f"Living Docs Cases: {summary.living_docs_metrics.total_cases}")
    print(f"  - Drift Precision:           {summary.living_docs_metrics.drift_precision:.2%}")
    print(f"  - Drift Recall:              {summary.living_docs_metrics.drift_recall:.2%}")
    print(f"  - Drift F1 Score:            {summary.living_docs_metrics.drift_f1_score:.4f}")
    print(f"  - Patch Diff Validity:       {summary.living_docs_metrics.patch_diff_validity:.2%}")
    print("========================================================\n")

    if args.save:
        run_file, latest_file = save_benchmark_results(summary)
        print(f"Saved run result: {run_file}")
        print(f"Updated latest:   {latest_file}")

    if summary.status != "passed":
        sys.exit(1)


if __name__ == "__main__":
    main()
