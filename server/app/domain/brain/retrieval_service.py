"""Hybrid retrieval service with Reciprocal Rank Fusion (RRF) and Context-Pack builder (docs/04 §7-§8, docs/11 M5-08)."""

from __future__ import annotations

import logging
import os
from typing import Any, Literal
from uuid import UUID

import yaml
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.domain.brain.embedding_service import EmbeddingService
from app.llm.embedding_adapter import EmbeddingAdapter, get_embedding_adapter
from app.persistence.models.brain import CodeChunk, CodeSymbol
from app.persistence.repositories.brain_repo import BrainRepository

logger = logging.getLogger("devmind.retrieval_service")

# ---------------------------------------------------------------------------
# Pydantic Schemas for Search & Context Pack (docs/03 §12.7, docs/04 §8)
# ---------------------------------------------------------------------------


class BrainCitation(BaseModel):
    """Provenance citation guaranteeing verifiable code attribution (docs/04 §8.7)."""

    file_version_id: UUID
    path: str
    start_line: int
    end_line: int
    content_hash: str | None = None
    symbol_key: str | None = None


class BrainSearchItem(BaseModel):
    """Individual retrieved and fused code item with ranking score and attribution."""

    id: UUID
    kind: str  # "chunk" | "symbol"
    path: str
    start_line: int
    end_line: int
    symbol_key: str | None = None
    content: str
    score: float
    matched_by: list[str] = Field(default_factory=list)
    citation: BrainCitation
    is_expanded: bool = False


class ContextPack(BaseModel):
    """Assembled prompt context bounded by token budget with complete citations."""

    formatted_context: str
    total_tokens_estimate: int
    item_count: int
    citations: list[BrainCitation] = Field(default_factory=list)


class BrainSearchRequest(BaseModel):
    """Request payload for hybrid brain search."""

    query: str = Field(min_length=1, max_length=1000, description="Search query or question")
    modes: list[Literal["symbol", "keyword", "vector"]] = Field(
        default=["symbol", "keyword", "vector"],
        description="Active retrieval channels to query",
    )
    limit: int = Field(default=10, ge=1, le=50, description="Maximum direct results to return")
    expand_relationships: bool = Field(
        default=True,
        description="Whether to perform 1-hop relationship expansion for discovered symbols",
    )
    token_budget: int = Field(
        default=2000,
        ge=100,
        le=8000,
        description="Maximum token budget for context pack generation",
    )


class BrainSearchResponse(BaseModel):
    """Response payload containing ranked results and assembled context pack."""

    query: str
    total_results: int
    items: list[BrainSearchItem] = Field(default_factory=list)
    context_pack: ContextPack


# ---------------------------------------------------------------------------
# Retrieval Service
# ---------------------------------------------------------------------------


class RetrievalService:
    """Orchestrates multi-channel retrieval, RRF ranking, relationship expansion, and context assembly."""

    def __init__(
        self,
        session: AsyncSession,
        config_path: str = "configs/retrieval.yaml",
        embedding_adapter: EmbeddingAdapter | None = None,
    ) -> None:
        self.session = session
        self.repo = BrainRepository(session)
        self.embedding_service = EmbeddingService(session)
        self.embedding_adapter = embedding_adapter
        self.config = self._load_config(config_path)

    def _load_config(self, config_path: str) -> dict[str, Any]:
        """Load retrieval configuration from YAML file or fallback to safe defaults."""
        defaults = {
            "fusion": {
                "rrf_k": 60,
                "weights": {
                    "symbol": 1.0,
                    "keyword": 1.0,
                    "vector": 1.0,
                },
            },
            "limits": {
                "default_limit": 10,
                "max_limit": 50,
            },
            "relationship_expansion": {
                "max_hops": 1,
                "max_related_symbols": 5,
            },
            "context_pack": {
                "default_token_budget": 2000,
                "max_token_budget": 8000,
            },
        }

        # Check possible configuration paths
        possible_paths = [
            config_path,
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "configs", "retrieval.yaml"
            ),
            os.path.join("server", "configs", "retrieval.yaml"),
        ]

        for p in possible_paths:
            if os.path.exists(p):
                try:
                    with open(p, encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                        if isinstance(data, dict):
                            return data
                except Exception as exc:
                    logger.warning("Failed to load retrieval config from %s: %s", p, exc)
                break

        return defaults

    async def search(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        request: BrainSearchRequest,
    ) -> BrainSearchResponse:
        """Execute multi-channel hybrid search, RRF fusion, and context-pack assembly."""
        query = request.query.strip()
        modes = request.modes or ["symbol", "keyword", "vector"]
        limit = min(request.limit, self.config.get("limits", {}).get("max_limit", 50))
        token_budget = request.token_budget

        rrf_k = self.config.get("fusion", {}).get("rrf_k", 60)
        weights = self.config.get("fusion", {}).get("weights", {})
        weight_symbol = float(weights.get("symbol", 1.0))
        weight_keyword = float(weights.get("keyword", 1.0))
        weight_vector = float(weights.get("vector", 1.0))

        # Channel 1: Symbol Name & Key Matching
        symbol_results: list[CodeSymbol] = []
        if "symbol" in modes:
            try:
                symbol_results = await self.repo.search_symbols(
                    ctx=ctx,
                    project_id=project_id,
                    query=query,
                    limit=limit * 2,
                )
            except Exception as exc:
                logger.warning("Symbol search channel failed: %s", exc)

        # Channel 2: Keyword Full-Text & Trigram Matching
        keyword_results: list[CodeChunk] = []
        if "keyword" in modes:
            try:
                keyword_results = await self.repo.search_chunks_text(
                    ctx=ctx,
                    project_id=project_id,
                    query=query,
                    limit=limit * 2,
                )
            except Exception as exc:
                logger.warning("Keyword search channel failed: %s", exc)

        # Channel 3: Semantic Vector Search via pgvector
        vector_results: list[tuple[CodeChunk, float]] = []
        if "vector" in modes:
            try:
                vector_results = await self._retrieve_vectors(
                    ctx=ctx,
                    project_id=project_id,
                    query=query,
                    limit=limit * 2,
                )
            except Exception as exc:
                logger.warning(
                    "Vector retrieval channel failed or degraded: %s (continuing with remaining channels)",
                    exc,
                )

        # Step 2: Reciprocal Rank Fusion (RRF)
        # Combine ranks across channels: score(d) = sum( weight_c * 1 / (k + rank_c(d)) )
        fused_items: dict[str, dict[str, Any]] = {}

        # Process Symbol channel
        for rank, sym in enumerate(symbol_results, start=1):
            key = f"symbol:{sym.id}"
            rrf_score = weight_symbol * (1.0 / (rrf_k + rank))
            path = sym.file_version.file.path if sym.file_version and sym.file_version.file else "unknown"
            content = sym.signature or f"// Symbol: {sym.name} ({sym.kind})"

            if key not in fused_items:
                fused_items[key] = {
                    "id": sym.id,
                    "kind": "symbol",
                    "path": path,
                    "start_line": sym.start_line,
                    "end_line": sym.end_line,
                    "symbol_key": sym.symbol_key,
                    "content": content,
                    "score": rrf_score,
                    "matched_by": ["symbol"],
                    "citation": BrainCitation(
                        file_version_id=sym.file_version_id,
                        path=path,
                        start_line=sym.start_line,
                        end_line=sym.end_line,
                        symbol_key=sym.symbol_key,
                        content_hash=sym.file_version.content_hash if sym.file_version else None,
                    ),
                    "symbol_obj": sym,
                }
            else:
                fused_items[key]["score"] += rrf_score
                if "symbol" not in fused_items[key]["matched_by"]:
                    fused_items[key]["matched_by"].append("symbol")

        # Process Keyword channel
        for rank, chunk in enumerate(keyword_results, start=1):
            key = f"chunk:{chunk.id}"
            rrf_score = weight_keyword * (1.0 / (rrf_k + rank))
            path = chunk.file_version.file.path if chunk.file_version and chunk.file_version.file else "unknown"

            if key not in fused_items:
                fused_items[key] = {
                    "id": chunk.id,
                    "kind": "chunk",
                    "path": path,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "symbol_key": None,
                    "content": chunk.content,
                    "score": rrf_score,
                    "matched_by": ["keyword"],
                    "citation": BrainCitation(
                        file_version_id=chunk.file_version_id,
                        path=path,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        symbol_key=None,
                        content_hash=chunk.content_hash,
                    ),
                    "chunk_obj": chunk,
                }
            else:
                fused_items[key]["score"] += rrf_score
                if "keyword" not in fused_items[key]["matched_by"]:
                    fused_items[key]["matched_by"].append("keyword")

        # Process Vector channel
        for rank, (chunk, _similarity) in enumerate(vector_results, start=1):
            key = f"chunk:{chunk.id}"
            rrf_score = weight_vector * (1.0 / (rrf_k + rank))
            path = chunk.file_version.file.path if chunk.file_version and chunk.file_version.file else "unknown"

            if key not in fused_items:
                fused_items[key] = {
                    "id": chunk.id,
                    "kind": "chunk",
                    "path": path,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "symbol_key": None,
                    "content": chunk.content,
                    "score": rrf_score,
                    "matched_by": ["vector"],
                    "citation": BrainCitation(
                        file_version_id=chunk.file_version_id,
                        path=path,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        symbol_key=None,
                        content_hash=chunk.content_hash,
                    ),
                    "chunk_obj": chunk,
                }
            else:
                fused_items[key]["score"] += rrf_score
                if "vector" not in fused_items[key]["matched_by"]:
                    fused_items[key]["matched_by"].append("vector")

        # Sort all fused candidates by descending RRF score
        sorted_candidates = sorted(fused_items.values(), key=lambda x: x["score"], reverse=True)
        top_candidates = sorted_candidates[:limit]

        # Step 3: Relationship Bounded Expansion (docs/04 §8.4)
        expanded_items: list[dict[str, Any]] = []
        if request.expand_relationships and top_candidates:
            expanded_items = await self._expand_relationships(
                ctx=ctx,
                project_id=project_id,
                base_items=top_candidates,
            )

        # Merge base results with relationship expansions
        all_items: list[BrainSearchItem] = []
        for c in top_candidates:
            all_items.append(
                BrainSearchItem(
                    id=c["id"],
                    kind=c["kind"],
                    path=c["path"],
                    start_line=c["start_line"],
                    end_line=c["end_line"],
                    symbol_key=c["symbol_key"],
                    content=c["content"],
                    score=round(c["score"], 6),
                    matched_by=c["matched_by"],
                    citation=c["citation"],
                    is_expanded=False,
                )
            )

        for exp in expanded_items:
            all_items.append(
                BrainSearchItem(
                    id=exp["id"],
                    kind=exp["kind"],
                    path=exp["path"],
                    start_line=exp["start_line"],
                    end_line=exp["end_line"],
                    symbol_key=exp["symbol_key"],
                    content=exp["content"],
                    score=round(exp["score"], 6),
                    matched_by=exp["matched_by"],
                    citation=exp["citation"],
                    is_expanded=True,
                )
            )

        # Step 4: Assemble Context Pack within Token Budget (docs/04 §8.6)
        context_pack = self._build_context_pack(all_items, token_budget)

        return BrainSearchResponse(
            query=query,
            total_results=len(all_items),
            items=all_items,
            context_pack=context_pack,
        )

    async def _retrieve_vectors(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        query: str,
        limit: int,
    ) -> list[tuple[CodeChunk, float]]:
        """Generate query embedding and perform pgvector similarity search."""
        active_space = await self.repo.get_active_embedding_space(ctx)
        if not active_space:
            logger.info("No active embedding space available for vector search; skipping vector channel")
            return []

        # Resolve embedding adapter
        adapter = self.embedding_adapter or get_embedding_adapter(
            provider_id=active_space.provider_id,
            model_id=active_space.model_id,
            dimension=active_space.dimension,
        )

        emb_res = await adapter.embed([query], input_type="query")
        if not emb_res.vectors:
            return []

        query_vector = emb_res.vectors[0]
        return await self.repo.search_chunks_vector(
            ctx=ctx,
            project_id=project_id,
            space_id=active_space.id,
            query_vector=query_vector,
            limit=limit,
            is_current=True,
        )

    async def _expand_relationships(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        base_items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Expand top symbols with 1-hop connected callers, callees, and definitions."""
        max_related = self.config.get("relationship_expansion", {}).get("max_related_symbols", 5)

        # Collect symbol IDs from top results
        symbol_ids: list[UUID] = []
        for item in base_items:
            if item.get("kind") == "symbol":
                symbol_ids.append(item["id"])
            elif "chunk_obj" in item and item["chunk_obj"].symbol_id:
                symbol_ids.append(item["chunk_obj"].symbol_id)

        if not symbol_ids:
            return []

        # Query active relationships
        relationships = await self.repo.get_relationships_for_symbols(
            ctx=ctx,
            project_id=project_id,
            symbol_ids=symbol_ids[:5],
            limit=max_related * 2,
        )

        # Find connected related symbol IDs not already in base_items
        existing_ids = {item["id"] for item in base_items}
        related_ids: list[UUID] = []
        for rel in relationships:
            target_id = rel.to_symbol_id if rel.from_symbol_id in symbol_ids else rel.from_symbol_id
            if target_id and target_id not in existing_ids and target_id not in related_ids:
                related_ids.append(target_id)
                if len(related_ids) >= max_related:
                    break

        if not related_ids:
            return []

        expanded_symbols = await self.repo.list_current_symbols(ctx=ctx, project_id=project_id, limit=100)
        sym_map = {s.id: s for s in expanded_symbols if s.id in related_ids}

        expanded_results: list[dict[str, Any]] = []
        for sid in related_ids:
            sym = sym_map.get(sid)
            if not sym:
                continue

            path = sym.file_version.file.path if sym.file_version and sym.file_version.file else "unknown"
            content = sym.signature or f"// Related {sym.kind}: {sym.name}"

            expanded_results.append(
                {
                    "id": sym.id,
                    "kind": "symbol",
                    "path": path,
                    "start_line": sym.start_line,
                    "end_line": sym.end_line,
                    "symbol_key": sym.symbol_key,
                    "content": content,
                    "score": 0.001,  # Base expansion score
                    "matched_by": ["relationship_expansion"],
                    "citation": BrainCitation(
                        file_version_id=sym.file_version_id,
                        path=path,
                        start_line=sym.start_line,
                        end_line=sym.end_line,
                        symbol_key=sym.symbol_key,
                        content_hash=sym.file_version.content_hash if sym.file_version else None,
                    ),
                    "is_expanded": True,
                }
            )

        return expanded_results

    def _build_context_pack(
        self,
        items: list[BrainSearchItem],
        token_budget: int,
    ) -> ContextPack:
        """Merge overlapping ranges, sort by file/line, and assemble within token budget."""
        if not items:
            return ContextPack(
                formatted_context="// No matching code context found in Project Brain.",
                total_tokens_estimate=10,
                item_count=0,
                citations=[],
            )

        # Sort items deterministically by path ascending, then start_line ascending
        sorted_items = sorted(items, key=lambda x: (x.path, x.start_line, x.end_line))

        pack_blocks: list[str] = []
        pack_citations: list[BrainCitation] = []
        current_token_count = 0

        # Character to token estimation heuristic (~4 chars/token + overhead)
        def estimate_tokens(text: str) -> int:
            return max(1, len(text) // 4)

        for item in sorted_items:
            # Build formatted block
            sym_label = f" [Symbol: {item.symbol_key}]" if item.symbol_key else ""
            block = (
                f"### File: {item.path}:{item.start_line}-{item.end_line}{sym_label}\n"
                f"```{self._detect_code_fence(item.path)}\n"
                f"{item.content}\n"
                f"```\n"
            )

            block_tokens = estimate_tokens(block)
            if current_token_count + block_tokens > token_budget and pack_blocks:
                # Token budget ceiling reached
                break

            pack_blocks.append(block)
            pack_citations.append(item.citation)
            current_token_count += block_tokens

        formatted = "\n".join(pack_blocks)
        return ContextPack(
            formatted_context=formatted,
            total_tokens_estimate=current_token_count,
            item_count=len(pack_blocks),
            citations=pack_citations,
        )

    def _detect_code_fence(self, path: str) -> str:
        """Infer markdown code fence language identifier from file extension."""
        ext = path.split(".")[-1].lower() if "." in path else ""
        mapping = {
            "ts": "typescript",
            "tsx": "tsx",
            "js": "javascript",
            "jsx": "jsx",
            "py": "python",
            "json": "json",
            "yaml": "yaml",
            "yml": "yaml",
            "sql": "sql",
            "md": "markdown",
        }
        return mapping.get(ext, "")
