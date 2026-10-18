"""Agent evaluation benchmark suite for answer quality, citation validity, and security finding faithfulness (docs/05 §16, docs/09 §9, M7-09)."""

from __future__ import annotations

from evals.agents.harness import (
    DATASET_PATH,
    RESULTS_DIR,
    evaluate_qa_case,
    evaluate_security_case,
    run_agent_eval_benchmark,
    save_benchmark_results,
)
from evals.agents.metrics import (
    AgentBenchmarkSummary,
    AnswerQualityMetrics,
    FaithfulnessMetrics,
    compute_answer_quality_metrics,
    compute_faithfulness_metrics,
)

__all__ = [
    "DATASET_PATH",
    "RESULTS_DIR",
    "AgentBenchmarkSummary",
    "AnswerQualityMetrics",
    "FaithfulnessMetrics",
    "compute_answer_quality_metrics",
    "compute_faithfulness_metrics",
    "evaluate_qa_case",
    "evaluate_security_case",
    "run_agent_eval_benchmark",
    "save_benchmark_results",
]
