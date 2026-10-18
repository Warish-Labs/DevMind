"""Prompt injection evaluation dataset, test vectors, and harness (docs/07 §8, docs/09 §12)."""

from pathlib import Path

from evals.injection.harness import (
    GraphInjectionHarness,
    run_injection_eval,
)
from evals.injection.metrics import (
    GraphInjectionBenchmarkSummary,
    GraphInjectionCaseResult,
    compute_injection_summary,
)

INJECTION_CORPUS_PATH = Path(__file__).resolve().parent / "corpus.json"

__all__ = [
    "INJECTION_CORPUS_PATH",
    "GraphInjectionBenchmarkSummary",
    "GraphInjectionCaseResult",
    "GraphInjectionHarness",
    "compute_injection_summary",
    "run_injection_eval",
]
