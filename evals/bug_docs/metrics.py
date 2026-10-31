"""Evaluation metrics and benchmark data classes for Bug Memory and Living Docs (docs/01 CAP-03/04, docs/09 §9, M12-06)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class BugMemoryMetrics:
    """Quantitative evaluation metrics for error signature normalization and similarity search."""

    total_cases: int
    fingerprint_accuracy: float
    top_1_accuracy: float
    recall_at_3: float
    mean_reciprocal_rank: float
    negative_rejection_rate: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LivingDocsMetrics:
    """Quantitative evaluation metrics for documentation drift detection and patch generation."""

    total_cases: int
    drift_precision: float
    drift_recall: float
    drift_f1_score: float
    patch_diff_validity: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BugDocsBenchmarkSummary:
    """Composite benchmark summary for Bug Memory and Living Documentation (CAP-03 & CAP-04)."""

    benchmark: str
    git_commit: str
    timestamp: str
    bug_memory_metrics: BugMemoryMetrics
    living_docs_metrics: LivingDocsMetrics
    composite_score: float
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark": self.benchmark,
            "git_commit": self.git_commit,
            "timestamp": self.timestamp,
            "bug_memory_metrics": self.bug_memory_metrics.to_dict(),
            "living_docs_metrics": self.living_docs_metrics.to_dict(),
            "composite_score": self.composite_score,
            "status": self.status,
        }


def compute_bug_memory_metrics(results: list[dict[str, Any]]) -> BugMemoryMetrics:
    """Compute aggregate retrieval & normalization metrics across evaluated bug cases."""
    if not results:
        return BugMemoryMetrics(
            total_cases=0,
            fingerprint_accuracy=0.0,
            top_1_accuracy=0.0,
            recall_at_3=0.0,
            mean_reciprocal_rank=0.0,
            negative_rejection_rate=0.0,
        )

    correct_fingerprints = 0
    top_1_correct = 0
    recall_at_3_count = 0
    reciprocal_ranks: list[float] = []

    negative_cases = 0
    negative_rejected = 0

    for res in results:
        is_neg = not res.get("is_duplicate", True)
        if is_neg:
            negative_cases += 1
            if res.get("predicted_candidate_id") is None or res.get("max_score", 0.0) < 0.5:
                negative_rejected += 1
            continue

        if res.get("fingerprint_correct", False):
            correct_fingerprints += 1

        top_cand = res.get("predicted_candidate_id")
        expected_top = res.get("expected_top_candidate_id")

        if top_cand == expected_top:
            top_1_correct += 1

        ranked_cands = res.get("ranked_candidate_ids", [])
        if expected_top in ranked_cands[:3]:
            recall_at_3_count += 1

        if expected_top in ranked_cands:
            rank = ranked_cands.index(expected_top) + 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)

    pos_cases = len(results) - negative_cases
    fp_acc = (correct_fingerprints / pos_cases) if pos_cases > 0 else 1.0
    top1_acc = (top_1_correct / pos_cases) if pos_cases > 0 else 1.0
    rec3 = (recall_at_3_count / pos_cases) if pos_cases > 0 else 1.0
    mrr = (sum(reciprocal_ranks) / pos_cases) if pos_cases > 0 else 1.0
    neg_rej = (negative_rejected / negative_cases) if negative_cases > 0 else 1.0

    return BugMemoryMetrics(
        total_cases=len(results),
        fingerprint_accuracy=round(fp_acc, 4),
        top_1_accuracy=round(top1_acc, 4),
        recall_at_3=round(rec3, 4),
        mean_reciprocal_rank=round(mrr, 4),
        negative_rejection_rate=round(neg_rej, 4),
    )


def compute_living_docs_metrics(results: list[dict[str, Any]]) -> LivingDocsMetrics:
    """Compute aggregate drift detection precision, recall, F1, and diff validity."""
    if not results:
        return LivingDocsMetrics(
            total_cases=0,
            drift_precision=0.0,
            drift_recall=0.0,
            drift_f1_score=0.0,
            patch_diff_validity=0.0,
        )

    total_tp = 0
    total_fp = 0
    total_fn = 0
    valid_diffs = 0
    evaluated_diffs = 0

    for res in results:
        expected_identifiers = set(res.get("expected_affected_identifiers", []))
        predicted_identifiers = set(res.get("predicted_affected_identifiers", []))

        tp = len(expected_identifiers & predicted_identifiers)
        fp = len(predicted_identifiers - expected_identifiers)
        fn = len(expected_identifiers - predicted_identifiers)

        total_tp += tp
        total_fp += fp
        total_fn += fn

        diff_valid = res.get("diff_valid")
        if diff_valid is not None:
            evaluated_diffs += 1
            if diff_valid:
                valid_diffs += 1

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 1.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 1.0
    diff_val = (valid_diffs / evaluated_diffs) if evaluated_diffs > 0 else 1.0

    return LivingDocsMetrics(
        total_cases=len(results),
        drift_precision=round(precision, 4),
        drift_recall=round(recall, 4),
        drift_f1_score=round(f1, 4),
        patch_diff_validity=round(diff_val, 4),
    )
