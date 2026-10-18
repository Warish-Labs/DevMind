"""Evaluation metrics and data classes for agent answer-quality and security finding faithfulness (docs/05 §16, docs/09 §9, M7-09)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AnswerQualityMetrics:
    """Quantitative quality metrics for code Q&A responses (CodeMate)."""

    total_cases: int
    grounded_cases: int
    insufficient_evidence_cases: int
    citation_precision: float
    citation_recall: float
    symbol_coverage: float
    insufficient_evidence_accuracy: float
    overall_quality_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FaithfulnessMetrics:
    """Quantitative grounding and evidence integrity metrics for security reviews (AuthCheck)."""

    total_cases: int
    verified_findings: int
    compliant_rejections: int
    tampered_rejections: int
    scope_downgrades: int
    grounding_ratio: float
    citation_resolution_rate: float
    hallucination_rate: float
    language_discipline_rate: float
    secret_redaction_rate: float
    overall_faithfulness_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentBenchmarkSummary:
    """Composite benchmark result combining answer-quality and faithfulness baselines."""

    benchmark: str
    version: str
    timestamp: str
    commit: str
    answer_quality: AnswerQualityMetrics
    faithfulness: FaithfulnessMetrics
    overall_composite_score: float
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark": self.benchmark,
            "version": self.version,
            "timestamp": self.timestamp,
            "commit": self.commit,
            "answer_quality": self.answer_quality.to_dict(),
            "faithfulness": self.faithfulness.to_dict(),
            "overall_composite_score": self.overall_composite_score,
            "status": self.status,
        }


def compute_answer_quality_metrics(results: list[dict[str, Any]]) -> AnswerQualityMetrics:
    """Aggregate per-case Q&A evaluation results into AnswerQualityMetrics."""
    if not results:
        return AnswerQualityMetrics(0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0)

    total = len(results)
    grounded = [r for r in results if r.get("category") == "grounded_qa"]
    insufficient = [r for r in results if r.get("category") == "insufficient_evidence"]

    # Citation precision & recall
    precisions = [r["citation_precision"] for r in grounded if "citation_precision" in r]
    recalls = [r["citation_recall"] for r in grounded if "citation_recall" in r]
    avg_precision = sum(precisions) / len(precisions) if precisions else 1.0
    avg_recall = sum(recalls) / len(recalls) if recalls else 1.0

    # Symbol coverage
    coverages = [r["symbol_coverage"] for r in grounded if "symbol_coverage" in r]
    avg_coverage = sum(coverages) / len(coverages) if coverages else 1.0

    # Insufficient evidence detection accuracy
    insufficient_correct = sum(1 for r in insufficient if r.get("detected_insufficient", False))
    insufficient_acc = insufficient_correct / len(insufficient) if insufficient else 1.0

    # Composite score: 35% precision, 35% recall, 15% coverage, 15% insufficient accuracy
    overall = round(
        0.35 * avg_precision + 0.35 * avg_recall + 0.15 * avg_coverage + 0.15 * insufficient_acc,
        4,
    )

    return AnswerQualityMetrics(
        total_cases=total,
        grounded_cases=len(grounded),
        insufficient_evidence_cases=len(insufficient),
        citation_precision=round(avg_precision, 4),
        citation_recall=round(avg_recall, 4),
        symbol_coverage=round(avg_coverage, 4),
        insufficient_evidence_accuracy=round(insufficient_acc, 4),
        overall_quality_score=overall,
    )


def compute_faithfulness_metrics(results: list[dict[str, Any]]) -> FaithfulnessMetrics:
    """Aggregate per-case security review evaluation results into FaithfulnessMetrics."""
    if not results:
        return FaithfulnessMetrics(0, 0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    total = len(results)
    verified_count = sum(1 for r in results if r.get("verdict") == "verified")
    compliant_count = sum(1 for r in results if r.get("verdict") == "rejected_as_compliant")
    tampered_count = sum(
        1
        for r in results
        if "rejected" in r.get("verdict", "") and r.get("verdict") != "rejected_as_compliant"
    )
    downgrade_count = sum(1 for r in results if r.get("verdict") == "downgraded_to_e1")

    # Metric rates
    grounding_ratios = [r.get("grounding_ratio", 1.0) for r in results if "grounding_ratio" in r]
    avg_grounding = sum(grounding_ratios) / len(grounding_ratios) if grounding_ratios else 1.0

    resolution_rates = [
        r.get("citation_resolved", 1.0) for r in results if "citation_resolved" in r
    ]
    avg_resolution = sum(resolution_rates) / len(resolution_rates) if resolution_rates else 1.0

    hallucination_counts = [1.0 if r.get("has_hallucinations", False) else 0.0 for r in results]
    avg_hallucination = (
        sum(hallucination_counts) / len(hallucination_counts) if hallucination_counts else 0.0
    )

    discipline_rates = [1.0 if r.get("language_compliant", True) else 0.0 for r in results]
    avg_discipline = sum(discipline_rates) / len(discipline_rates) if discipline_rates else 1.0

    redaction_rates = [1.0 if r.get("secrets_redacted", True) else 0.0 for r in results]
    avg_redaction = sum(redaction_rates) / len(redaction_rates) if redaction_rates else 1.0

    # Composite score: 30% grounding, 25% resolution, 20% (1 - hallucination), 15% discipline, 10% redaction
    overall = round(
        0.30 * avg_grounding
        + 0.25 * avg_resolution
        + 0.20 * (1.0 - avg_hallucination)
        + 0.15 * avg_discipline
        + 0.10 * avg_redaction,
        4,
    )

    return FaithfulnessMetrics(
        total_cases=total,
        verified_findings=verified_count,
        compliant_rejections=compliant_count,
        tampered_rejections=tampered_count,
        scope_downgrades=downgrade_count,
        grounding_ratio=round(avg_grounding, 4),
        citation_resolution_rate=round(avg_resolution, 4),
        hallucination_rate=round(avg_hallucination, 4),
        language_discipline_rate=round(avg_discipline, 4),
        secret_redaction_rate=round(avg_redaction, 4),
        overall_faithfulness_score=overall,
    )
