"""LLM evaluation benchmark harness, metrics, and dataset loaders (docs/05 §16, docs/09 §12)."""

from evals.llm.harness import (
    evaluate_injection_defense,
    evaluate_structured_outputs,
    load_injection_corpus,
    run_llm_benchmark,
)
from evals.llm.metrics import (
    InjectionEvaluationMetrics,
    LLMBenchmarkSummary,
    SchemaEvaluationMetrics,
)

__all__ = [
    "InjectionEvaluationMetrics",
    "LLMBenchmarkSummary",
    "SchemaEvaluationMetrics",
    "evaluate_injection_defense",
    "evaluate_structured_outputs",
    "load_injection_corpus",
    "run_llm_benchmark",
]
