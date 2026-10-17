"""Retrieval evaluation metrics module (docs/04 §14, docs/09 §9).

Implements standard IR quality metrics:
- Recall@k
- Mean Reciprocal Rank (MRR)
- Normalized Discounted Cumulative Gain (nDCG@k)
- No-Answer Accuracy
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


def calculate_recall_at_k(
    retrieved_keys: Sequence[str],
    relevant_keys: set[str] | Mapping[str, int],
    k: int = 5,
) -> float:
    """Compute Recall@k: the fraction of relevant targets successfully retrieved in the top k results.

    If there are no relevant targets (e.g. no-answer query), returns 1.0 if top k is empty, else 0.0.
    """
    targets = set(relevant_keys)
    if not targets:
        return 1.0 if not retrieved_keys else 0.0

    top_k = retrieved_keys[:k]
    hits = len(set(top_k) & targets)
    return hits / float(len(targets))


def calculate_mrr(
    retrieved_keys: Sequence[str],
    relevant_keys: set[str] | Mapping[str, int],
    k: int = 10,
) -> float:
    """Compute Reciprocal Rank (RR): reciprocal of the 1-based rank of the first relevant result.

    Returns 0.0 if no relevant target is found within the top k results.
    """
    targets = set(relevant_keys)
    if not targets:
        return 1.0 if not retrieved_keys else 0.0

    for rank, key in enumerate(retrieved_keys[:k], start=1):
        if key in targets:
            return 1.0 / rank
    return 0.0


def calculate_dcg_at_k(
    retrieved_keys: Sequence[str],
    relevance_map: Mapping[str, int],
    k: int = 5,
) -> float:
    """Compute Discounted Cumulative Gain (DCG@k) using graded relevance."""
    dcg = 0.0
    for rank, key in enumerate(retrieved_keys[:k], start=1):
        rel = relevance_map.get(key, 0)
        if rel > 0:
            # Standard formulation: (2^rel - 1) / log2(rank + 1)
            dcg += (math.pow(2, rel) - 1.0) / math.log2(rank + 1)
    return dcg


def calculate_idcg_at_k(
    relevance_map: Mapping[str, int],
    k: int = 5,
) -> float:
    """Compute Ideal Discounted Cumulative Gain (IDCG@k) using sorted relevance scores."""
    sorted_rels = sorted(relevance_map.values(), reverse=True)[:k]
    idcg = 0.0
    for rank, rel in enumerate(sorted_rels, start=1):
        if rel > 0:
            idcg += (math.pow(2, rel) - 1.0) / math.log2(rank + 1)
    return idcg


def calculate_ndcg_at_k(
    retrieved_keys: Sequence[str],
    relevance_map: Mapping[str, int],
    k: int = 5,
) -> float:
    """Compute Normalized Discounted Cumulative Gain (nDCG@k).

    Returns 1.0 if both retrieved and ideal DCG are 0 (e.g. no-answer query).
    """
    if not relevance_map:
        return 1.0 if not retrieved_keys else 0.0

    idcg = calculate_idcg_at_k(relevance_map, k=k)
    if idcg <= 0.0:
        return 1.0

    dcg = calculate_dcg_at_k(retrieved_keys, relevance_map, k=k)
    return dcg / idcg


def calculate_no_answer_accuracy(
    retrieved_scores: Sequence[float],
    score_threshold: float = 0.005,
) -> float:
    """Compute accuracy for unanswerable queries: 1.0 if no retrieved item exceeds threshold, 0.0 otherwise."""
    max_score = max(retrieved_scores) if retrieved_scores else 0.0
    return 1.0 if max_score <= score_threshold else 0.0


def aggregate_query_metrics(
    eval_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate per-query evaluation records into summary metrics broken down by category."""
    if not eval_records:
        return {
            "total_queries": 0,
            "overall": {"recall_at_1": 0.0, "recall_at_3": 0.0, "recall_at_5": 0.0, "mrr": 0.0, "ndcg_at_5": 0.0},
            "by_category": {},
        }

    categories: dict[str, list[Mapping[str, Any]]] = {}
    for rec in eval_records:
        cat = str(rec.get("category", "unknown"))
        categories.setdefault(cat, []).append(rec)

    def _mean(values: Sequence[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    def _summarize(records: Sequence[Mapping[str, Any]]) -> dict[str, float]:
        return {
            "recall_at_1": round(_mean([float(r.get("recall_at_1", 0.0)) for r in records]), 4),
            "recall_at_3": round(_mean([float(r.get("recall_at_3", 0.0)) for r in records]), 4),
            "recall_at_5": round(_mean([float(r.get("recall_at_5", 0.0)) for r in records]), 4),
            "mrr": round(_mean([float(r.get("mrr", 0.0)) for r in records]), 4),
            "ndcg_at_5": round(_mean([float(r.get("ndcg_at_5", 0.0)) for r in records]), 4),
        }

    by_cat_summary = {cat: _summarize(recs) for cat, recs in categories.items()}
    overall_summary = _summarize(eval_records)

    return {
        "total_queries": len(eval_records),
        "overall": overall_summary,
        "by_category": by_cat_summary,
    }
