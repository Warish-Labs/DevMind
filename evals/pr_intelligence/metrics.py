"""Evaluation metrics and benchmark data classes for PR Intelligence & ReviewBuddy (docs/01 CAP-05/06, docs/09 §9, M11-08)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ChangeImpactMetrics:
    """Quantitative evaluation metrics for change-impact graph traversal and blast radius."""

    total_cases: int
    precision: float
    recall: float
    f1_score: float
    risk_accuracy: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewChecklistMetrics:
    """Quantitative evaluation metrics for ReviewBuddy rule checklist detection and false alarms."""

    total_cases: int
    precision: float
    recall: float
    f1_score: float
    false_positive_rate: float
    category_accuracy: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PRIntelligenceBenchmarkSummary:
    """Composite benchmark summary for PR Intelligence (CAP-05 & CAP-06)."""

    benchmark: str
    git_commit: str
    timestamp: str
    impact_metrics: ChangeImpactMetrics
    review_metrics: ReviewChecklistMetrics
    composite_score: float
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark": self.benchmark,
            "git_commit": self.git_commit,
            "timestamp": self.timestamp,
            "impact_metrics": self.impact_metrics.to_dict(),
            "review_metrics": self.review_metrics.to_dict(),
            "composite_score": self.composite_score,
            "status": self.status,
        }


def compute_change_impact_metrics(eval_results: list[dict[str, Any]]) -> ChangeImpactMetrics:
    """Compute precision, recall, F1, and risk level accuracy across change-impact benchmark cases."""
    if not eval_results:
        return ChangeImpactMetrics(
            total_cases=0,
            precision=0.0,
            recall=0.0,
            f1_score=0.0,
            risk_accuracy=0.0,
        )

    precisions: list[float] = []
    recalls: list[float] = []
    risk_matches = 0

    for res in eval_results:
        expected_impacted = set(res.get("expected_impacted", []))
        predicted_impacted = set(res.get("predicted_impacted", []))

        if not expected_impacted and not predicted_impacted:
            precisions.append(1.0)
            recalls.append(1.0)
        elif not predicted_impacted:
            precisions.append(1.0)
            recalls.append(0.0)
        elif not expected_impacted:
            precisions.append(0.0)
            recalls.append(1.0)
        else:
            intersection = expected_impacted & predicted_impacted
            p = len(intersection) / len(predicted_impacted)
            r = len(intersection) / len(expected_impacted)
            precisions.append(p)
            recalls.append(r)

        if res.get("expected_risk") == res.get("predicted_risk"):
            risk_matches += 1

    avg_precision = sum(precisions) / len(precisions) if precisions else 0.0
    avg_recall = sum(recalls) / len(recalls) if recalls else 0.0
    f1 = (
        2 * (avg_precision * avg_recall) / (avg_precision + avg_recall)
        if (avg_precision + avg_recall) > 0
        else 0.0
    )
    risk_acc = risk_matches / len(eval_results) if eval_results else 0.0

    return ChangeImpactMetrics(
        total_cases=len(eval_results),
        precision=round(avg_precision, 4),
        recall=round(avg_recall, 4),
        f1_score=round(f1, 4),
        risk_accuracy=round(risk_acc, 4),
    )


def compute_review_checklist_metrics(eval_results: list[dict[str, Any]]) -> ReviewChecklistMetrics:
    """Compute precision, recall, false positive rate, and category accuracy for ReviewBuddy."""
    if not eval_results:
        return ReviewChecklistMetrics(
            total_cases=0,
            precision=0.0,
            recall=0.0,
            f1_score=0.0,
            false_positive_rate=0.0,
            category_accuracy=0.0,
        )

    total_expected_findings = 0
    total_predicted_findings = 0
    true_positives = 0
    false_positives = 0
    category_matches = 0

    for res in eval_results:
        expected_rules = res.get("expected_rules", [])
        predicted_rules = res.get("predicted_rules", [])

        total_expected_findings += len(expected_rules)
        total_predicted_findings += len(predicted_rules)

        # Expected rule set matches
        exp_rule_ids = {r["rule_id"] for r in expected_rules}
        pred_rule_ids = {r["rule_id"] for r in predicted_rules}

        tp = len(exp_rule_ids & pred_rule_ids)
        fp = len(pred_rule_ids - exp_rule_ids)

        true_positives += tp
        false_positives += fp

        # Category match
        exp_cats = {r.get("category") for r in expected_rules if "category" in r}
        pred_cats = {r.get("category") for r in predicted_rules if "category" in r}
        if exp_cats and pred_cats:
            if exp_cats.issubset(pred_cats):
                category_matches += 1
        elif not exp_cats and not pred_cats:
            category_matches += 1

    precision = (
        true_positives / total_predicted_findings
        if total_predicted_findings > 0
        else (1.0 if total_expected_findings == 0 else 0.0)
    )
    recall = (
        true_positives / total_expected_findings
        if total_expected_findings > 0
        else (1.0 if total_predicted_findings == 0 else 0.0)
    )
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    fpr = (
        false_positives / total_predicted_findings
        if total_predicted_findings > 0
        else 0.0
    )
    category_acc = category_matches / len(eval_results) if eval_results else 0.0

    return ReviewChecklistMetrics(
        total_cases=len(eval_results),
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1_score=round(f1, 4),
        false_positive_rate=round(fpr, 4),
        category_accuracy=round(category_acc, 4),
    )
