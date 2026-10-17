"""DevMind LLM gateway: provider adapters, model router, prompts."""

from app.llm.embedding_adapter import (
    EmbeddingAdapter,
    EmbeddingInputType,
    EmbeddingResult,
    FakeEmbeddingAdapter,
    get_embedding_adapter,
)

__all__ = [
    "EmbeddingAdapter",
    "EmbeddingInputType",
    "EmbeddingResult",
    "FakeEmbeddingAdapter",
    "get_embedding_adapter",
]
