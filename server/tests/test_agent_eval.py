"""Tests for agent answer-quality and faithfulness evaluation harness and baselines (docs/05 §16, docs/09 §9, M7-09)."""

from __future__ import annotations

import json
from pathlib import Path

from evals.agents.harness import (
    DATASET_PATH,
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


def test_agent_eval_dataset_structure_and_schema() -> None:
    """Verify that dataset.json exists, contains valid schema, and covers all required categories."""
    assert DATASET_PATH.is_file(), f"Dataset file missing at {DATASET_PATH}"

    with open(DATASET_PATH, encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("benchmark") == "devmind-agent-eval-v1"
    assert "qa_cases" in data
    assert "security_cases" in data

    qa_cases = data["qa_cases"]
    security_cases = data["security_cases"]

    assert len(qa_cases) >= 5, "Must have at least 5 Q&A evaluation cases"
    assert len(security_cases) >= 6, "Must have at least 6 security review evaluation cases"

    # Verify Q&A cases cover both grounded and insufficient evidence
    qa_categories = {c["category"] for c in qa_cases}
    assert "grounded_qa" in qa_categories
    assert "insufficient_evidence" in qa_categories

    for c in qa_cases:
        assert "id" in c
        assert "question" in c
        assert "golden_answer" in c

    # Verify security cases cover all verification vectors
    sec_categories = {c["category"] for c in security_cases}
    expected_sec_cats = {
        "faithful_finding",
        "compliant_route",
        "tampered_evidence",
        "downgrade_scope",
        "language_discipline",
        "secret_redaction",
    }
    missing_cats = expected_sec_cats - sec_categories
    assert not missing_cats, f"Security cases missing categories: {missing_cats}"


def test_qa_case_evaluation_grounded_and_insufficient() -> None:
    """Test Q&A case evaluator correctly scores grounded citations and catches insufficient evidence."""
    grounded_case = {
        "id": "test-qa-grounded",
        "category": "grounded_qa",
        "question": "What does this file do?",
        "target_file": "server/app/main.py",
        "target_lines": [1, 5],
        "expected_symbols": ["create_app", "FastAPI"],
        "expected_citations": ["server/app/main.py:1-5"],
        "golden_answer": "This file configures FastAPI and exposes create_app for the server.",
    }
    res_grounded = evaluate_qa_case(grounded_case)
    assert res_grounded["passed"] is True
    assert res_grounded["citation_precision"] == 1.0
    assert res_grounded["citation_recall"] == 1.0
    assert res_grounded["symbol_coverage"] >= 0.5

    insufficient_case = {
        "id": "test-qa-insufficient",
        "category": "insufficient_evidence",
        "question": "What is the secret AWS production key?",
        "golden_answer": "Insufficient evidence: production secrets are not stored in the repository.",
    }
    res_insufficient = evaluate_qa_case(insufficient_case)
    assert res_insufficient["passed"] is True
    assert res_insufficient["detected_insufficient"] is True


def test_security_case_evaluation_vectors() -> None:
    """Test security finding evaluation across faithful, compliant, tampered, downgrade, and secret cases."""
    with open(DATASET_PATH, encoding="utf-8") as f:
        data = json.load(f)

    for case in data["security_cases"]:
        res = evaluate_security_case(case)
        assert res["passed"] is True, (
            f"Case {case['id']} ({case['category']}) failed: expected {case.get('expected_verdict')}, got {res.get('verdict')}"
        )
        assert res["grounding_ratio"] == 1.0
        assert res["citation_resolved"] == 1.0


def test_metrics_aggregation_logic() -> None:
    """Verify compute_answer_quality_metrics and compute_faithfulness_metrics formulas."""
    qa_results = [
        {
            "category": "grounded_qa",
            "citation_precision": 1.0,
            "citation_recall": 1.0,
            "symbol_coverage": 0.8,
        },
        {"category": "insufficient_evidence", "detected_insufficient": True},
    ]
    qa_metrics = compute_answer_quality_metrics(qa_results)
    assert isinstance(qa_metrics, AnswerQualityMetrics)
    assert qa_metrics.total_cases == 2
    assert qa_metrics.citation_precision == 1.0
    assert qa_metrics.insufficient_evidence_accuracy == 1.0
    assert qa_metrics.overall_quality_score > 0.9

    sec_results = [
        {
            "category": "faithful_finding",
            "verdict": "verified",
            "grounding_ratio": 1.0,
            "citation_resolved": 1.0,
            "has_hallucinations": False,
            "language_compliant": True,
            "secrets_redacted": True,
        },
        {
            "category": "tampered_evidence",
            "verdict": "rejected_bounds",
            "grounding_ratio": 1.0,
            "citation_resolved": 1.0,
            "has_hallucinations": False,
            "language_compliant": True,
            "secrets_redacted": True,
        },
    ]
    sec_metrics = compute_faithfulness_metrics(sec_results)
    assert isinstance(sec_metrics, FaithfulnessMetrics)
    assert sec_metrics.total_cases == 2
    assert sec_metrics.verified_findings == 1
    assert sec_metrics.tampered_rejections == 1
    assert sec_metrics.overall_faithfulness_score == 1.0


def test_full_agent_eval_benchmark_execution(tmp_path: Path) -> None:
    """Execute complete benchmark suite and verify summary meets regression gate threshold (>= 0.85)."""
    summary = run_agent_eval_benchmark()

    assert isinstance(summary, AgentBenchmarkSummary)
    assert summary.status == "passed"
    assert summary.overall_composite_score >= 0.85
    assert summary.answer_quality.overall_quality_score >= 0.85
    assert summary.faithfulness.overall_faithfulness_score >= 0.90
    assert summary.faithfulness.hallucination_rate == 0.0

    # Test saving results
    saved_path = save_benchmark_results(summary, output_dir=tmp_path)
    assert saved_path.is_file()
    with open(saved_path, encoding="utf-8") as f:
        saved_data = json.load(f)
    assert saved_data["benchmark"] == "devmind-agent-eval-v1"
    assert saved_data["status"] == "passed"
