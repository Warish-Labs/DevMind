"""Evaluation metrics for LLM prompt rendering, injection defense, and structured outputs (docs/05 §16, docs/09 §12)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InjectionEvaluationMetrics:
    """Metrics assessing prompt injection resistance and heuristic detection accuracy."""

    total_cases: int = 0
    injection_cases: int = 0
    benign_cases: int = 0
    escaped_cases: int = 0
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0

    @property
    def delimiter_integrity_rate(self) -> float:
        """Proportion of test cases where untrusted blocks preserved delimiter integrity."""
        if self.total_cases == 0:
            return 1.0
        return round(self.escaped_cases / self.total_cases, 4)

    @property
    def detection_precision(self) -> float:
        """Precision of the heuristic prompt injection signal detector."""
        denom = self.true_positives + self.false_positives
        if denom == 0:
            return 1.0
        return round(self.true_positives / denom, 4)

    @property
    def detection_recall(self) -> float:
        """Recall of the heuristic prompt injection signal detector."""
        denom = self.true_positives + self.false_negatives
        if denom == 0:
            return 1.0
        return round(self.true_positives / denom, 4)

    @property
    def detection_f1(self) -> float:
        """F1 score of the heuristic prompt injection signal detector."""
        p = self.detection_precision
        r = self.detection_recall
        if p + r == 0:
            return 0.0
        return round(2 * (p * r) / (p + r), 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_cases": self.total_cases,
            "injection_cases": self.injection_cases,
            "benign_cases": self.benign_cases,
            "escaped_cases": self.escaped_cases,
            "delimiter_integrity_rate": self.delimiter_integrity_rate,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "true_negatives": self.true_negatives,
            "false_negatives": self.false_negatives,
            "precision": self.detection_precision,
            "recall": self.detection_recall,
            "f1_score": self.detection_f1,
        }


@dataclass
class SchemaEvaluationMetrics:
    """Metrics assessing structured output conformance and repair efficacy."""

    total_outputs: int = 0
    valid_outputs: int = 0
    repaired_outputs: int = 0
    unrepairable_outputs: int = 0

    @property
    def schema_validity_rate(self) -> float:
        """Proportion of outputs conforming to target Pydantic schema (including repairs)."""
        if self.total_outputs == 0:
            return 1.0
        return round((self.valid_outputs + self.repaired_outputs) / self.total_outputs, 4)

    @property
    def one_shot_repair_rate(self) -> float:
        """Proportion of invalid candidates recovered by the one-shot repair step."""
        invalid_count = self.repaired_outputs + self.unrepairable_outputs
        if invalid_count == 0:
            return 1.0
        return round(self.repaired_outputs / invalid_count, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_outputs": self.total_outputs,
            "valid_outputs": self.valid_outputs,
            "repaired_outputs": self.repaired_outputs,
            "unrepairable_outputs": self.unrepairable_outputs,
            "schema_validity_rate": self.schema_validity_rate,
            "one_shot_repair_rate": self.one_shot_repair_rate,
        }


@dataclass
class LLMBenchmarkSummary:
    """Comprehensive benchmark summary for an evaluation run."""

    benchmark_id: str
    timestamp: str
    commit: str
    injection_metrics: InjectionEvaluationMetrics = field(default_factory=InjectionEvaluationMetrics)
    schema_metrics: SchemaEvaluationMetrics = field(default_factory=SchemaEvaluationMetrics)
    task_scores: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark": self.benchmark_id,
            "timestamp": self.timestamp,
            "commit": self.commit,
            "injection_defense": self.injection_metrics.to_dict(),
            "structured_outputs": self.schema_metrics.to_dict(),
            "task_scores": self.task_scores,
        }
