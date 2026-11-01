"""Evaluation metrics and benchmark data classes for Deployment Diagnosis (docs/01 CAP-07, docs/09 §9, M12-17)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class LogSanitizationMetrics:
    """Quantitative evaluation metrics for deterministic secret redaction and ANSI stripping."""

    total_cases: int
    secret_redaction_rate: float
    ansi_strip_rate: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DiagnosisClassificationMetrics:
    """Quantitative evaluation metrics for failure classification and primary log line citation."""

    total_cases: int
    category_accuracy: float
    primary_line_accuracy: float
    insufficient_log_accuracy: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EnvVarAnalysisMetrics:
    """Quantitative evaluation metrics for environment variable mismatch and typo candidate matching."""

    total_cases: int
    missing_precision: float
    missing_recall: float
    missing_f1_score: float
    typo_match_accuracy: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IncidentRetrievalMetrics:
    """Quantitative evaluation metrics for past incident similarity retrieval and tenant isolation."""

    total_cases: int
    top_1_accuracy: float
    mean_reciprocal_rank: float
    tenant_isolation_rate: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DeploymentBenchmarkSummary:
    """Composite benchmark summary for Deployment Diagnosis (CAP-07)."""

    benchmark: str
    git_commit: str
    timestamp: str
    sanitization_metrics: LogSanitizationMetrics
    classification_metrics: DiagnosisClassificationMetrics
    env_var_metrics: EnvVarAnalysisMetrics
    retrieval_metrics: IncidentRetrievalMetrics
    composite_score: float
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark": self.benchmark,
            "git_commit": self.git_commit,
            "timestamp": self.timestamp,
            "sanitization_metrics": self.sanitization_metrics.to_dict(),
            "classification_metrics": self.classification_metrics.to_dict(),
            "env_var_metrics": self.env_var_metrics.to_dict(),
            "retrieval_metrics": self.retrieval_metrics.to_dict(),
            "composite_score": self.composite_score,
            "status": self.status,
        }


def compute_sanitization_metrics(results: list[dict[str, Any]]) -> LogSanitizationMetrics:
    """Compute secret redaction and ANSI stripping metrics across benchmark cases."""
    if not results:
        return LogSanitizationMetrics(
            total_cases=0, secret_redaction_rate=0.0, ansi_strip_rate=0.0
        )

    redaction_hits = sum(1 for r in results if r.get("secrets_leaked", 0) == 0)
    ansi_hits = sum(1 for r in results if not r.get("has_ansi", False))

    total = len(results)
    return LogSanitizationMetrics(
        total_cases=total,
        secret_redaction_rate=redaction_hits / total if total > 0 else 0.0,
        ansi_strip_rate=ansi_hits / total if total > 0 else 0.0,
    )


def compute_classification_metrics(results: list[dict[str, Any]]) -> DiagnosisClassificationMetrics:
    """Compute category classification, primary line attribution, and insufficient log detection."""
    if not results:
        return DiagnosisClassificationMetrics(
            total_cases=0,
            category_accuracy=0.0,
            primary_line_accuracy=0.0,
            insufficient_log_accuracy=0.0,
        )

    cat_hits = sum(1 for r in results if r.get("category_match", False))
    line_hits = sum(1 for r in results if r.get("primary_line_match", False))
    insuff_hits = sum(1 for r in results if r.get("insufficient_log_match", False))

    total = len(results)
    return DiagnosisClassificationMetrics(
        total_cases=total,
        category_accuracy=cat_hits / total if total > 0 else 0.0,
        primary_line_accuracy=line_hits / total if total > 0 else 0.0,
        insufficient_log_accuracy=insuff_hits / total if total > 0 else 0.0,
    )


def compute_env_var_metrics(results: list[dict[str, Any]]) -> EnvVarAnalysisMetrics:
    """Compute precision, recall, and F1 for missing environment variables and typo matching."""
    if not results:
        return EnvVarAnalysisMetrics(
            total_cases=0,
            missing_precision=0.0,
            missing_recall=0.0,
            missing_f1_score=0.0,
            typo_match_accuracy=0.0,
        )

    total_tp = sum(r.get("missing_tp", 0) for r in results)
    total_fp = sum(r.get("missing_fp", 0) for r in results)
    total_fn = sum(r.get("missing_fn", 0) for r in results)

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 1.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 1.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    typo_cases = [r for r in results if "typo_match" in r]
    typo_hits = sum(1 for r in typo_cases if r.get("typo_match", False))
    typo_acc = typo_hits / len(typo_cases) if typo_cases else 1.0

    return EnvVarAnalysisMetrics(
        total_cases=len(results),
        missing_precision=precision,
        missing_recall=recall,
        missing_f1_score=f1,
        typo_match_accuracy=typo_acc,
    )


def compute_retrieval_metrics(results: list[dict[str, Any]]) -> IncidentRetrievalMetrics:
    """Compute Top-1 accuracy, MRR, and cross-tenant leakage defense rate."""
    if not results:
        return IncidentRetrievalMetrics(
            total_cases=0,
            top_1_accuracy=0.0,
            mean_reciprocal_rank=0.0,
            tenant_isolation_rate=0.0,
        )

    top_1_hits = sum(1 for r in results if r.get("top_1_match", False))
    mrr_sum = sum(r.get("reciprocal_rank", 0.0) for r in results)
    isolation_hits = sum(1 for r in results if r.get("tenant_isolated", True))

    total = len(results)
    return IncidentRetrievalMetrics(
        total_cases=total,
        top_1_accuracy=top_1_hits / total if total > 0 else 0.0,
        mean_reciprocal_rank=mrr_sum / total if total > 0 else 0.0,
        tenant_isolation_rate=isolation_hits / total if total > 0 else 1.0,
    )
