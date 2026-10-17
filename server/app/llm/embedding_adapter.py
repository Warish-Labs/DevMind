"""Embedding provider adapters and deterministic fake provider (docs/04 §10, docs/05 §5, docs/11 M5-06)."""

from __future__ import annotations

import abc
import hashlib
import math
from typing import Literal

from pydantic import BaseModel, Field

EmbeddingInputType = Literal["document", "query"]


class EmbeddingResult(BaseModel):
    """Result of an embedding operation across multiple texts."""

    vectors: list[list[float]] = Field(description="Normalized float vectors for each input text")
    provider_id: str = Field(description="Embedding provider identifier")
    model_id: str = Field(description="Model identifier")
    dimension: int = Field(description="Vector dimension")
    token_count: int = Field(default=0, description="Estimated or reported token count")


class EmbeddingAdapter(abc.ABC):
    """Abstract interface for embedding generation separate from generation LLMs (docs/04 §10)."""

    @property
    @abc.abstractmethod
    def provider_id(self) -> str:
        """Provider identifier (e.g. 'openai', 'fastembed', 'fake')."""

    @property
    @abc.abstractmethod
    def model_id(self) -> str:
        """Model identifier (e.g. 'text-embedding-3-small', 'fake-embed-v1')."""

    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        """Embedding dimension (e.g. 1536, 384, 64)."""

    @abc.abstractmethod
    async def embed(
        self,
        texts: list[str],
        input_type: EmbeddingInputType = "document",
    ) -> EmbeddingResult:
        """Generate embedding vectors for the given texts."""


class FakeEmbeddingAdapter(EmbeddingAdapter):
    """Deterministic, zero-cost embedding adapter for testing and CI (ADR-046 Free Tiers).

    Produces reproducible, L2-normalized vectors using SHA-256 hash seeds.
    """

    def __init__(
        self,
        model_id: str = "fake-embed-v1",
        dimension: int = 64,
    ) -> None:
        self._provider_id = "fake"
        self._model_id = model_id
        self._dimension = dimension

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def dimension(self) -> int:
        return self._dimension

    def _generate_vector(self, text: str, input_type: EmbeddingInputType) -> list[float]:
        """Generate a deterministic unit vector from text and input_type."""
        prefix = f"{input_type}:{self._model_id}:"
        raw_seed = f"{prefix}{text}".encode()

        # Derive pseudorandom floats deterministically using SHA-256 iterations
        raw_floats: list[float] = []
        counter = 0
        while len(raw_floats) < self._dimension:
            digest = hashlib.sha256(raw_seed + counter.to_bytes(4, byteorder="big")).digest()
            # 32 bytes = 8 x 4-byte integers
            for i in range(0, 32, 4):
                if len(raw_floats) >= self._dimension:
                    break
                val = int.from_bytes(digest[i : i + 4], byteorder="big", signed=True)
                raw_floats.append(val / 2147483648.0)
            counter += 1

        # L2-normalize
        norm = math.sqrt(sum(x * x for x in raw_floats))
        if norm == 0.0:
            norm = 1.0
        return [round(x / norm, 6) for x in raw_floats]

    async def embed(
        self,
        texts: list[str],
        input_type: EmbeddingInputType = "document",
    ) -> EmbeddingResult:
        """Deterministically embed a batch of texts."""
        if not texts:
            return EmbeddingResult(
                vectors=[],
                provider_id=self.provider_id,
                model_id=self.model_id,
                dimension=self.dimension,
                token_count=0,
            )

        vectors = [self._generate_vector(t, input_type) for t in texts]
        token_count = sum(max(1, len(t) // 4) for t in texts)

        return EmbeddingResult(
            vectors=vectors,
            provider_id=self.provider_id,
            model_id=self.model_id,
            dimension=self.dimension,
            token_count=token_count,
        )


def get_embedding_adapter(
    provider_id: str = "fake",
    model_id: str = "fake-embed-v1",
    dimension: int = 64,
) -> EmbeddingAdapter:
    """Factory creating an embedding adapter instance."""
    if provider_id == "fake":
        return FakeEmbeddingAdapter(model_id=model_id, dimension=dimension)

    raise ValueError(f"Unsupported embedding provider: {provider_id}")
