import json
from pathlib import Path

import pytest
from evals.retrieval.harness import (
    DEFAULT_DATASET_PATH,
    InMemoryFixtureRetriever,
    run_benchmark,
)
from evals.retrieval.metrics import (
    aggregate_query_metrics,
    calculate_mrr,
    calculate_ndcg_at_k,
    calculate_no_answer_accuracy,
    calculate_recall_at_k,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_metrics_recall_calculation() -> None:
    """Verify Recall@k computation under various hit distributions."""
    relevant = {"docA", "docB", "docC"}

    # Perfect recall at k=3
    assert calculate_recall_at_k(["docA", "docB", "docC"], relevant, k=3) == 1.0

    # Partial recall at k=2
    assert calculate_recall_at_k(["docA", "docX", "docB"], relevant, k=2) == pytest.approx(1 / 3)

    # Partial recall at k=3
    assert calculate_recall_at_k(["docA", "docX", "docB"], relevant, k=3) == pytest.approx(2 / 3)

    # Zero recall
    assert calculate_recall_at_k(["docX", "docY"], relevant, k=5) == 0.0

    # No-answer query (empty relevant set)
    assert calculate_recall_at_k([], set(), k=5) == 1.0
    assert calculate_recall_at_k(["docA"], set(), k=5) == 0.0


def test_metrics_mrr_calculation() -> None:
    """Verify Mean Reciprocal Rank (MRR) handles 1-based ranks and missing items."""
    relevant = {"target"}

    assert calculate_mrr(["target", "other"], relevant, k=5) == 1.0
    assert calculate_mrr(["other", "target"], relevant, k=5) == 0.5
    assert calculate_mrr(["o1", "o2", "target"], relevant, k=5) == pytest.approx(1 / 3)
    assert calculate_mrr(["o1", "o2", "o3"], relevant, k=2) == 0.0

    # No-answer query
    assert calculate_mrr([], set(), k=5) == 1.0


def test_metrics_ndcg_calculation() -> None:
    """Verify nDCG@k properly discounts ranks and rewards graded relevance."""
    relevance_map = {"docA": 2, "docB": 1, "docC": 0}

    # Ideal order: docA (rel=2) at rank 1, docB (rel=1) at rank 2
    perfect_ndcg = calculate_ndcg_at_k(["docA", "docB"], relevance_map, k=5)
    assert perfect_ndcg == pytest.approx(1.0)

    # Suboptimal order: docB at rank 1, docA at rank 2
    suboptimal_ndcg = calculate_ndcg_at_k(["docB", "docA"], relevance_map, k=5)
    assert 0.0 < suboptimal_ndcg < 1.0

    # Irrelevant first
    bad_ndcg = calculate_ndcg_at_k(["docC", "docB"], relevance_map, k=5)
    assert bad_ndcg < suboptimal_ndcg


def test_metrics_no_answer_accuracy() -> None:
    """Verify no-answer query scoring thresholding."""
    assert calculate_no_answer_accuracy([], score_threshold=0.01) == 1.0
    assert calculate_no_answer_accuracy([0.002, 0.001], score_threshold=0.01) == 1.0
    assert calculate_no_answer_accuracy([0.05, 0.001], score_threshold=0.01) == 0.0


def test_metrics_aggregation_by_category() -> None:
    """Verify query aggregation produces both overall and category breakdown."""
    records = [
        {"id": "q1", "category": "identifier", "recall_at_1": 1.0, "recall_at_3": 1.0, "recall_at_5": 1.0, "mrr": 1.0, "ndcg_at_5": 1.0},
        {"id": "q2", "category": "concept", "recall_at_1": 0.0, "recall_at_3": 0.5, "recall_at_5": 1.0, "mrr": 0.5, "ndcg_at_5": 0.7},
    ]
    summary = aggregate_query_metrics(records)
    assert summary["total_queries"] == 2
    assert "identifier" in summary["by_category"]
    assert "concept" in summary["by_category"]
    assert summary["by_category"]["identifier"]["recall_at_1"] == 1.0
    assert summary["by_category"]["concept"]["recall_at_1"] == 0.0
    assert summary["overall"]["recall_at_1"] == 0.5


def test_retrieval_dataset_structure_and_validity() -> None:
    """Verify that dataset.json exists and conforms to the benchmark schema."""
    assert DEFAULT_DATASET_PATH.exists()
    with open(DEFAULT_DATASET_PATH, encoding="utf-8") as f:
        data = json.load(f)

    assert data["version"] == "1.0.0"
    assert "queries" in data
    assert len(data["queries"]) >= 10

    categories = set()
    for q in data["queries"]:
        assert "id" in q
        assert "query" in q
        assert "category" in q
        assert "expect_no_answer" in q
        assert "expected_targets" in q
        categories.add(q["category"])

    assert "identifier" in categories
    assert "concept" in categories
    assert "flow" in categories
    assert "no_answer" in categories


def test_in_memory_fixture_retriever_indexing_and_search() -> None:
    """Verify that InMemoryFixtureRetriever correctly indexes fixture codebases."""
    retriever = InMemoryFixtureRetriever.load_from_fixtures(REPO_ROOT)
    assert len(retriever.docs) >= 5

    # 1. Exact symbol search
    sym_results = retriever.search("require_admin", mode="symbol_only")
    assert len(sym_results) > 0
    assert sym_results[0]["symbol"] == "require_admin"

    # 2. Keyword search
    kw_results = retriever.search("authorization header", mode="keyword_only")
    assert len(kw_results) > 0

    # 3. Hybrid RRF fusion
    fused_results = retriever.search("require_admin", mode="fused")
    assert len(fused_results) > 0
    assert fused_results[0]["symbol"] == "require_admin"


def test_harness_benchmark_runner_and_fusion_advantage() -> None:
    """Verify that the evaluation harness runs all modes and proves the hybrid fusion advantage."""
    report = run_benchmark(dataset_path=DEFAULT_DATASET_PATH, repo_root=REPO_ROOT)

    assert report["query_count"] >= 10
    assert "symbol_only" in report["modes"]
    assert "keyword_only" in report["modes"]
    assert "vector_only" in report["modes"]
    assert "fused" in report["modes"]
    assert "fused_expanded_with_expansion" in report["modes"]

    fused_ndcg = report["modes"]["fused"]["overall"]["ndcg_at_5"]
    symbol_ndcg = report["modes"]["symbol_only"]["overall"]["ndcg_at_5"]
    keyword_ndcg = report["modes"]["keyword_only"]["overall"]["ndcg_at_5"]
    vector_ndcg = report["modes"]["vector_only"]["overall"]["ndcg_at_5"]

    # Fused hybrid retrieval should outperform single-channel retrieval on the benchmark
    assert fused_ndcg > symbol_ndcg
    assert fused_ndcg >= keyword_ndcg
    assert fused_ndcg >= vector_ndcg
