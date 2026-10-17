"""Embedding service coordinating chunk embedding, active space management, and batch processing (docs/04 §10, docs/11 M5-06)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.llm.embedding_adapter import EmbeddingAdapter, get_embedding_adapter
from app.persistence.models.brain import CodeChunk, EmbeddingSpace
from app.persistence.repositories.brain_repo import BrainRepository

logger = logging.getLogger("devmind.embedding_service")


class EmbeddingService:
    """Service managing embedding generation and embedding space lifecycle."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = BrainRepository(session)

    async def get_or_create_default_space(
        self,
        ctx: AuthContext | SystemContext,
        provider_id: str = "fake",
        model_id: str = "fake-embed-v1",
        dimension: int = 64,
    ) -> EmbeddingSpace:
        """Get the current active embedding space or provision a default active space."""
        active = await self.repo.get_active_embedding_space(ctx)
        if active:
            return active

        # Provision default active space
        space = await self.repo.create_embedding_space(
            ctx=ctx,
            provider_id=provider_id,
            model_id=model_id,
            dimension=dimension,
            status="active",
            config_hash="sha256:default-fake-space",
        )
        return space

    async def process_embed_chunks(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        space_id: UUID | None = None,
        batch_size: int = 50,
        adapter_override: EmbeddingAdapter | None = None,
    ) -> dict[str, Any]:
        """Embed un-embedded chunks for a project in the active or specified embedding space.

        Args:
            ctx: SystemContext or AuthContext authorizing the operation.
            project_id: Target project UUID.
            space_id: Optional specific embedding space to target.
            batch_size: Maximum number of chunks to process in this run.
            adapter_override: Optional custom adapter instance (useful in tests).

        Returns:
            Dictionary with batch processing statistics and status.
        """
        # 1. Resolve embedding space
        if space_id:
            space = await self.session.get(EmbeddingSpace, space_id)
            if not space:
                raise ValueError(f"Embedding space {space_id} not found")
        else:
            space = await self.get_or_create_default_space(ctx)

        # 2. Retrieve un-embedded chunks
        chunks: list[CodeChunk] = await self.repo.get_unembedded_chunks(
            ctx=ctx,
            project_id=project_id,
            space_id=space.id,
            limit=batch_size,
        )

        if not chunks:
            logger.info(
                "No un-embedded chunks found for project %s in space %s", project_id, space.id
            )
            return {
                "status": "completed",
                "project_id": str(project_id),
                "space_id": str(space.id),
                "chunks_embedded": 0,
                "token_estimate": 0,
            }

        # 3. Resolve embedding adapter
        adapter = adapter_override or get_embedding_adapter(
            provider_id=space.provider_id,
            model_id=space.model_id,
            dimension=space.dimension,
        )

        # 4. Generate embeddings
        texts = [chunk.search_text for chunk in chunks]
        embed_result = await adapter.embed(texts, input_type="document")

        logger.info(
            "Embedded %d chunks for project %s (space=%s, tokens=%d)",
            len(chunks),
            project_id,
            space.id,
            embed_result.token_count,
        )

        return {
            "status": "completed",
            "project_id": str(project_id),
            "space_id": str(space.id),
            "chunks_embedded": len(chunks),
            "token_estimate": embed_result.token_count,
            "dimension": space.dimension,
        }
