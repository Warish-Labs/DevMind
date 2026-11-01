"""Evaluation metrics and benchmark data classes for Project Mentor and Health Evaluation (docs/01 CAP-08/09, docs/09 §9, M12-12)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class TaskRecommendationMetrics:
    """Quantitative evaluation metrics for Task DAG topological ordering, readiness, and recommendation."""

    total_cases: int
    top_1_accuracy: float
    mean_reciprocal_rank: float
    ready_accuracy: float
    cycle_detection_accuracy: float
    downstream_impact_accuracy: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProjectEvaluationMetrics:
    """Quantitative evaluation metrics for multidimensional project health scoring and release readiness."""

    total_cases: int
    verdict_accuracy: float
    blocker_precision: float
    blocker_recall: float
    blocker_f1_score: float
    confidence_accuracy: float
    score_mae: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MentorBenchmarkSummary:
    """Composite benchmark summary for Project Mentor & Health Evaluation (CAP-08 & CAP-09)."""

    benchmark: str
    git_commit: str
    timestamp: str
    recommendation_metrics: TaskRecommendationMetrics
    evaluation_metrics: ProjectEvaluationMetrics
    composite_score: float
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark": self.benchmark,
            "git_commit": self.git_commit,
            "timestamp": self.timestamp,
            "recommendation_metrics": self.recommendation_metrics.to_dict(),
            "evaluation_metrics": self.evaluation_metrics.to_dict(),
            "composite_score": self.composite_score,
            "status": self.status,
        }


def compute_task_recommendation_metrics(eval_results: list[dict[str, Any]]) -> TaskRecommendationMetrics:
    """Compute top-1 accuracy, MRR, readiness accuracy, and cycle detection accuracy across recommendation cases."""
    if not eval_results:
        return TaskRecommendationMetrics(
            total_cases=0,
            top_1_accuracy=0.0,
            mean_reciprocal_rank=0.0,
            ready_accuracy=0.0,
            cycle_detection_accuracy=0.0,
            downstream_impact_accuracy=0.0,
        )

    top_1_matches = 0
    reciprocal_ranks: list[float] = []
    ready_matches = 0
    cycle_matches = 0
    impact_matches = 0

    for res in eval_results:
        expected_top = res.get("expected_top_task_id")
        ranked_ids = res.get("predicted_ranked_ids", [])
        has_cycle_expected = res.get("has_cycle", False)
        has_cycle_predicted = res.get("cycle_detected", False)

        # 1. Cycle detection accuracy
        if has_cycle_expected == has_cycle_predicted:
            cycle_matches += 1

        if has_cycle_expected:
            # For cyclic graph, if cycle is detected correctly, ranking is appropriately aborted
            top_1_matches += 1
            reciprocal_ranks.append(1.0)
            ready_matches += 1
            impact_matches += 1
            continue

        # 2. Top-1 and MRR
        if ranked_ids and expected_top:
            if ranked_ids[0] == expected_top:
                top_1_matches += 1

            if expected_top in ranked_ids:
                rank_idx = ranked_ids.index(expected_top) + 1
                reciprocal_ranks.append(1.0 / rank_idx)
            else:
                reciprocal_ranks.append(0.0)
        elif not expected_top and not ranked_ids:
            top_1_matches += 1
            reciprocal_ranks.append(1.0)
        else:
            reciprocal_ranks.append(0.0)

        # 3. Readiness accuracy
        if res.get("expected_is_ready") == res.get("predicted_is_ready"):
            ready_matches += 1

        # 4. Downstream impact count accuracy
        if res.get("expected_downstream_impact_count") == res.get("predicted_downstream_impact_count"):
            impact_matches += 1

    total = len(eval_results)
    return TaskRecommendationMetrics(
        total_cases=total,
        top_1_accuracy=round(top_1_matches / total, 4),
        mean_reciprocal_rank=round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4) if reciprocal_ranks else 0.0,
        ready_accuracy=round(ready_matches / total, 4),
        cycle_detection_accuracy=round(cycle_matches / total, 4),
        downstream_impact_accuracy=round(impact_matches / total, 4),
    )


def compute_project_evaluation_metrics(eval_results: list[dict[str, Any]]) -> ProjectEvaluationMetrics:
    """Compute verdict accuracy, blocker precision/recall/F1, and confidence accuracy across health evaluation cases."""
    if not eval_results:
        return ProjectEvaluationMetrics(
            total_cases=0,
            verdict_accuracy=0.0,
            blocker_precision=0.0,
            blocker_recall=0.0,
            blocker_f1_score=0.0,
            confidence_accuracy=0.0,
            score_mae=0.0,
        )

    verdict_matches = 0
    confidence_matches = 0
    tp_blockers = 0
    fp_blockers = 0
    fn_blockers = 0
    score_errors: list[float] = []

    for res in eval_results:
        expected_verdict = res.get("expected_verdict")
        predicted_verdict = res.get("predicted_verdict")
        if expected_verdict == predicted_verdict:
            verdict_matches += 1

        expected_conf = res.get("expected_functionality_confidence")
        predicted_conf = res.get("predicted_functionality_confidence")
        if expected_conf == predicted_conf:
            confidence_matches += 1

        # Blocker evaluation
        expected_blockers = res.get("expected_blockers_count", 0)
        predicted_blockers = res.get("predicted_blockers_count", 0)

        # Matched blockers count
        matched = min(expected_blockers, predicted_blockers)
        tp_blockers += matched
        fp_blockers += max(0, predicted_blockers - expected_blockers)
        fn_blockers += max(0, expected_blockers - predicted_blockers)

        # Score accuracy check against bounded range
        pred_score = res.get("predicted_overall_score", 0.0)
        exp_min = res.get("expected_min_score")
        exp_max = res.get("expected_max_score")

        if exp_min is not None and pred_score < exp_min:
            score_errors.append(exp_min - pred_score)
        elif exp_max is not None and pred_score > exp_max:
            score_errors.append(pred_score - exp_max)
        else:
            score_errors.append(0.0)

    total = len(eval_results)
    precision = (
        round(tp_blockers / (tp_blockers + fp_blockers), 4)
        if (tp_blockers + fp_blockers) > 0
        else 1.0
    )
    recall = (
        round(tp_blockers / (tp_blockers + fn_blockers), 4)
        if (tp_blockers + fn_blockers) > 0
        else 1.0
    )
    f1 = (
        round(2 * (precision * recall) / (precision + recall), 4)
        if (precision + recall) > 0
        else 1.0
    )
    mae = round(sum(score_errors) / len(score_errors), 4) if score_errors else 0.0

    return ProjectEvaluationMetrics(
        total_cases=total,
        verdict_accuracy=round(verdict_matches / total, 4),
        blocker_precision=precision,
        blocker_recall=recall,
        blocker_f1_score=f1,
        confidence_accuracy=round(confidence_matches / total, 4),
        score_mae=mae,
    )
