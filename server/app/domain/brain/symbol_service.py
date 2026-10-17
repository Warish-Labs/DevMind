"""Code symbol and architectural relationship domain service (docs/03 §3.2, docs/04 §4).

Provides:
1. Batch extraction ingestion of semantic symbols with transactional is_current invariant.
2. Batch relationship ingestion with automatic symbol key resolution and edge linkage.
3. Graph derivation and traversal across call graphs, route definitions, guards, and imports.
4. Cross-tenant isolation on all symbol and graph operations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import ValidationError
from app.domain.brain.context import resolve_project_context
from app.persistence.models.brain import FileVersion
from app.persistence.repositories.brain_repo import BrainRepository

VALID_SYMBOL_KINDS = frozenset(
    {
        "function",
        "method",
        "class",
        "route_handler",
        "server_action",
        "model",
        "constant",
        "module",
    }
)

VALID_RELATIONSHIP_KINDS = frozenset(
    {
        "imports",
        "calls",
        "defines_route",
        "guarded_by",
        "reads_model",
        "writes_model",
        "tests",
        "documents",
    }
)


class CodeSymbolPayload(BaseModel):
    """Payload representing an extracted program symbol."""

    file_version_id: UUID
    symbol_key: str = Field(min_length=1, max_length=512)
    name: str = Field(min_length=1, max_length=255)
    qualified_name: str = Field(min_length=1, max_length=512)
    kind: str = Field(
        description="function | method | class | route_handler | server_action | model | constant | module"
    )
    signature: str | None = None
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    framework_tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BatchSymbolsRequest(BaseModel):
    """Payload for batch uploading code symbols from an extension scan."""

    symbols: list[CodeSymbolPayload] = Field(default_factory=list)


class CodeSymbolItem(BaseModel):
    """Serialized code symbol representation."""

    id: UUID
    project_id: UUID
    file_version_id: UUID
    symbol_key: str
    name: str
    qualified_name: str
    kind: str
    signature: str | None = None
    start_line: int
    end_line: int
    framework_tags: list[str] = Field(default_factory=list)
    is_current: bool
    created_at: datetime


class BatchSymbolsResponse(BaseModel):
    """Result receipt for batch symbol ingestion."""

    upserted: int
    superseded_marked_non_current: int
    symbols: list[CodeSymbolItem] = Field(default_factory=list)


class CodeRelationshipPayload(BaseModel):
    """Payload representing a typed structural edge between symbols."""

    file_version_id: UUID
    from_symbol_id: UUID | None = None
    from_symbol_key: str | None = None
    to_symbol_id: UUID | None = None
    to_symbol_key: str | None = None
    to_external: str | None = None
    kind: str = Field(
        description="imports | calls | defines_route | guarded_by | reads_model | writes_model | tests | documents"
    )
    resolution: str = Field(default="resolved", description="resolved | inferred | unresolved")


class BatchRelationshipsRequest(BaseModel):
    """Payload for batch uploading structural code relationships."""

    relationships: list[CodeRelationshipPayload] = Field(default_factory=list)


class CodeRelationshipItem(BaseModel):
    """Serialized structural relationship edge."""

    id: UUID
    project_id: UUID
    from_symbol_id: UUID
    to_symbol_id: UUID | None = None
    to_external: str | None = None
    kind: str
    resolution: str
    file_version_id: UUID
    is_current: bool
    created_at: datetime


class BatchRelationshipsResponse(BaseModel):
    """Result receipt for batch relationship ingestion."""

    upserted: int
    resolved_count: int
    relationships: list[CodeRelationshipItem] = Field(default_factory=list)


class GraphNode(BaseModel):
    """Node in the architectural symbol graph."""

    id: UUID
    symbol_key: str
    name: str
    kind: str
    start_line: int
    end_line: int


class GraphEdge(BaseModel):
    """Edge in the architectural symbol graph."""

    id: UUID
    from_symbol_id: UUID
    to_symbol_id: UUID | None = None
    to_external: str | None = None
    kind: str
    resolution: str


class GraphResponse(BaseModel):
    """Project architectural knowledge graph structure."""

    project_id: UUID
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class SymbolService:
    """Domain service managing code symbols, structural relationships, and architectural graphs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = BrainRepository(session)

    async def resolve_project_context(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
    ) -> AuthContext | SystemContext:
        """Resolve and verify tenant workspace context for caller on target project."""
        return await resolve_project_context(self.session, ctx, project_id)

    async def upsert_symbols(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        payload: BatchSymbolsRequest,
    ) -> BatchSymbolsResponse:
        """Batch upsert code symbols with transactional is_current invariant (docs/03 §3.2)."""
        if not payload.symbols:
            return BatchSymbolsResponse(upserted=0, superseded_marked_non_current=0, symbols=[])

        for sym in payload.symbols:
            if sym.kind not in VALID_SYMBOL_KINDS:
                raise ValidationError(
                    detail=f"Invalid symbol kind '{sym.kind}'. Must be one of {sorted(VALID_SYMBOL_KINDS)}"
                )

        # 1. Identify distinct file_version_ids in this batch
        version_ids = list({s.file_version_id for s in payload.symbols})

        # 2. Find file_ids for these versions to locate older versions of the same files
        stmt_files = select(FileVersion.file_id).where(FileVersion.id.in_(version_ids))
        file_ids = list((await self.session.execute(stmt_files)).scalars().all())

        superseded_count = 0
        if file_ids:
            # Query older file_version_ids for these files that are not in the incoming batch
            stmt_older = select(FileVersion.id).where(
                FileVersion.file_id.in_(file_ids),
                FileVersion.id.notin_(version_ids),
            )
            older_version_ids = list((await self.session.execute(stmt_older)).scalars().all())
            if older_version_ids:
                superseded_count = await self.repo.mark_symbols_non_current_for_versions(
                    ctx, project_id, older_version_ids
                )

        # 3. Format symbol records and insert
        symbols_data = [
            {
                "file_version_id": s.file_version_id,
                "symbol_key": s.symbol_key,
                "name": s.name,
                "qualified_name": s.qualified_name,
                "kind": s.kind,
                "signature": s.signature,
                "start_line": s.start_line,
                "end_line": s.end_line,
                "framework_tags": s.framework_tags,
                "metadata": s.metadata,
                "is_current": True,
            }
            for s in payload.symbols
        ]

        created_symbols = await self.repo.batch_upsert_symbols(ctx, project_id, symbols_data)

        # 4. Resolve any pending edges that target these newly uploaded symbols
        await self.repo.resolve_relationships(ctx, project_id)

        items = [
            CodeSymbolItem(
                id=sym.id,
                project_id=sym.project_id,
                file_version_id=sym.file_version_id,
                symbol_key=sym.symbol_key,
                name=sym.name,
                qualified_name=sym.qualified_name,
                kind=sym.kind,
                signature=sym.signature,
                start_line=sym.start_line,
                end_line=sym.end_line,
                framework_tags=sym.framework_tags,
                is_current=sym.is_current,
                created_at=sym.created_at,
            )
            for sym in created_symbols
        ]

        return BatchSymbolsResponse(
            upserted=len(items),
            superseded_marked_non_current=superseded_count,
            symbols=items,
        )

    async def upsert_relationships(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        payload: BatchRelationshipsRequest,
    ) -> BatchRelationshipsResponse:
        """Batch upsert relationships with key resolution and edge linkage."""
        if not payload.relationships:
            return BatchRelationshipsResponse(upserted=0, resolved_count=0, relationships=[])

        for rel in payload.relationships:
            if rel.kind not in VALID_RELATIONSHIP_KINDS:
                raise ValidationError(
                    detail=f"Invalid relationship kind '{rel.kind}'. Must be one of {sorted(VALID_RELATIONSHIP_KINDS)}"
                )

        # 1. Resolve any symbol keys to IDs if symbol keys were provided instead of IDs
        needed_keys: set[str] = set()
        for rel in payload.relationships:
            if rel.from_symbol_id is None and rel.from_symbol_key:
                needed_keys.add(rel.from_symbol_key)
            if rel.to_symbol_id is None and rel.to_symbol_key:
                needed_keys.add(rel.to_symbol_key)

        key_to_id: dict[str, UUID] = {}
        if needed_keys:
            symbols = await self.repo.get_symbols_by_keys(ctx, project_id, list(needed_keys))
            key_to_id = {s.symbol_key: s.id for s in symbols}

        # 2. Build relationships data rows
        rels_data: list[dict[str, Any]] = []
        for rel in payload.relationships:
            from_id = rel.from_symbol_id or (
                key_to_id.get(rel.from_symbol_key) if rel.from_symbol_key else None
            )
            if from_id is None:
                raise ValidationError(
                    detail="Relationship requires a valid from_symbol_id or an existing from_symbol_key"
                )

            to_id = rel.to_symbol_id or (
                key_to_id.get(rel.to_symbol_key) if rel.to_symbol_key else None
            )
            to_ext = rel.to_external or (rel.to_symbol_key if to_id is None else None)

            resolution = rel.resolution
            if to_id is not None:
                resolution = "resolved"
            elif to_ext is not None and resolution == "resolved":
                resolution = "unresolved"

            rels_data.append(
                {
                    "from_symbol_id": from_id,
                    "to_symbol_id": to_id,
                    "to_external": to_ext,
                    "kind": rel.kind,
                    "resolution": resolution,
                    "file_version_id": rel.file_version_id,
                    "is_current": True,
                }
            )

        created_rels = await self.repo.batch_upsert_relationships(ctx, project_id, rels_data)

        # 3. Attempt to resolve any remaining unresolved edges
        resolved_count = await self.repo.resolve_relationships(ctx, project_id)

        items = [
            CodeRelationshipItem(
                id=r.id,
                project_id=r.project_id,
                from_symbol_id=r.from_symbol_id,
                to_symbol_id=r.to_symbol_id,
                to_external=r.to_external,
                kind=r.kind,
                resolution=r.resolution,
                file_version_id=r.file_version_id,
                is_current=r.is_current,
                created_at=r.created_at,
            )
            for r in created_rels
        ]

        return BatchRelationshipsResponse(
            upserted=len(items),
            resolved_count=resolved_count,
            relationships=items,
        )

    async def list_current_symbols(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        kind: str | None = None,
        limit: int = 100,
    ) -> list[CodeSymbolItem]:
        """List active current symbols in a project."""
        symbols = await self.repo.list_current_symbols(ctx, project_id, kind=kind, limit=limit)
        return [
            CodeSymbolItem(
                id=s.id,
                project_id=s.project_id,
                file_version_id=s.file_version_id,
                symbol_key=s.symbol_key,
                name=s.name,
                qualified_name=s.qualified_name,
                kind=s.kind,
                signature=s.signature,
                start_line=s.start_line,
                end_line=s.end_line,
                framework_tags=s.framework_tags,
                is_current=s.is_current,
                created_at=s.created_at,
            )
            for s in symbols
        ]

    async def get_graph(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        root_symbol_key: str | None = None,
        depth: int = 2,
        limit: int = 200,
    ) -> GraphResponse:
        """Derive and return the architectural graph structure."""
        symbols, relationships = await self.repo.get_graph_data(
            ctx,
            project_id=project_id,
            root_symbol_key=root_symbol_key,
            depth=depth,
            limit=limit,
        )

        nodes = [
            GraphNode(
                id=s.id,
                symbol_key=s.symbol_key,
                name=s.name,
                kind=s.kind,
                start_line=s.start_line,
                end_line=s.end_line,
            )
            for s in symbols
        ]

        edges = [
            GraphEdge(
                id=r.id,
                from_symbol_id=r.from_symbol_id,
                to_symbol_id=r.to_symbol_id,
                to_external=r.to_external,
                kind=r.kind,
                resolution=r.resolution,
            )
            for r in relationships
        ]

        return GraphResponse(
            project_id=project_id,
            nodes=nodes,
            edges=edges,
        )
