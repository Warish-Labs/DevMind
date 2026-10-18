"""Scoped retrieval and analysis tools for DevMind agent workflows (docs/05 §6.1, §9, M7-02).

Per docs/05 §9 (Tool execution boundaries):
- Closed set: Only allowlisted tools exist.
- Read-only by default: Retrieval and listing tools are scoped by AuthContext and project.
- No repository code execution: Neither server nor agents execute user code or tests in v1.
- Bounded results: Result counts and sizes are strictly clamped (e.g. max 200 lines for file ranges).
- Argument validation: Inputs validated against Pydantic schemas; IDs re-authorized, never trusted from model output.
- No credentials in tool context: GitHub tokens, API keys, and DB credentials are never visible to models.
- Audit: Tool invocations logged with names, counts, and durations; payloads and sensitive source code are never logged.
"""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth_context import AuthContext, SystemContext
from app.domain.brain.retrieval_service import BrainSearchRequest, RetrievalService
from app.llm.models import ToolDefinition
from app.orchestration.state import CitationRef
from app.persistence.models.brain import (
    CodeChunk,
    CodeRelationship,
    CodeSymbol,
    FileVersion,
)
from app.persistence.repositories.brain_repo import BrainRepository

logger = logging.getLogger("devmind.orchestration.tools")

MAX_FILE_RANGE_LINES = 200
MAX_SEARCH_LIMIT = 20
MAX_SYMBOL_LIMIT = 20
MAX_RELATIONSHIP_LIMIT = 50


# ---------------------------------------------------------------------------
# Tool Input Schemas (docs/05 §9, §10)
# ---------------------------------------------------------------------------


class SearchBrainInput(BaseModel):
    """Input payload for searching the Project Brain."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        min_length=1,
        max_length=500,
        description="Search query or symbol name to look up in the project codebase",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=MAX_SEARCH_LIMIT,
        description=f"Maximum number of context results to return (max {MAX_SEARCH_LIMIT})",
    )


class GetSymbolInput(BaseModel):
    """Input payload for looking up program symbols."""

    model_config = ConfigDict(extra="forbid")

    symbol_name: str = Field(
        min_length=1,
        max_length=255,
        description="Name or identifier of the symbol (function, class, route, etc.)",
    )
    path: str | None = Field(
        default=None,
        description="Optional relative file path filter to disambiguate symbols",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=MAX_SYMBOL_LIMIT,
        description=f"Maximum number of symbols to return (max {MAX_SYMBOL_LIMIT})",
    )


class GetFileRangeInput(BaseModel):
    """Input payload for reading a bounded range of file lines."""

    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(
        min_length=1,
        max_length=1024,
        description="Repository-relative file path",
    )
    start_line: int = Field(
        ge=1,
        description="1-indexed starting line number",
    )
    end_line: int = Field(
        ge=1,
        description=f"1-indexed ending line number (clamped to max {MAX_FILE_RANGE_LINES} lines)",
    )


class GetRelationshipsInput(BaseModel):
    """Input payload for querying architectural symbol relationships."""

    model_config = ConfigDict(extra="forbid")

    symbol_name: str = Field(
        min_length=1,
        max_length=255,
        description="Name or identifier of the symbol to trace relationships for",
    )
    kind: str | None = Field(
        default=None,
        description="Optional relationship kind: 'imports', 'calls', 'defines_route', 'guarded_by', etc.",
    )
    direction: str = Field(
        default="both",
        description="Relationship direction: 'incoming', 'outgoing', or 'both'",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=MAX_RELATIONSHIP_LIMIT,
        description=f"Maximum number of relationships to return (max {MAX_RELATIONSHIP_LIMIT})",
    )


# ---------------------------------------------------------------------------
# Core Tool Invocables (Scoped by AuthContext, project_id, session)
# ---------------------------------------------------------------------------


async def search_brain(
    ctx: AuthContext | SystemContext,
    project_id: UUID,
    session: AsyncSession,
    query: str,
    limit: int = 5,
    modes: list[str] | None = None,
) -> dict[str, Any]:
    """Execute hybrid search over the Project Brain, returning bounded context items and citations."""
    start_t = time.perf_counter()
    bounded_limit = min(max(1, limit), MAX_SEARCH_LIMIT)

    retrieval_svc = RetrievalService(session=session)
    search_req = BrainSearchRequest(
        query=query,
        limit=bounded_limit,
        modes=modes or ["symbol", "keyword", "vector"],  # type: ignore[arg-type]
    )

    resp = await retrieval_svc.search(ctx=ctx, project_id=project_id, request=search_req)

    items: list[dict[str, Any]] = []
    citations: list[CitationRef] = []

    for item in resp.items:
        items.append(
            {
                "id": str(item.id),
                "kind": item.kind,
                "path": item.path,
                "start_line": item.start_line,
                "end_line": item.end_line,
                "symbol_key": item.symbol_key,
                "content": item.content,
                "score": round(item.score, 4),
                "matched_by": item.matched_by,
            }
        )
        citations.append(
            CitationRef(
                doc_id=str(item.id),
                path=item.path,
                start_line=item.start_line,
                end_line=item.end_line,
                symbol=item.symbol_key,
                score=round(item.score, 4),
            )
        )

    duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
    logger.info(
        "tool_executed",
        extra={
            "tool": "search_brain",
            "project_id": str(project_id),
            "result_count": len(items),
            "duration_ms": duration_ms,
        },
    )

    return {
        "items": items,
        "citations": [c.__dict__ for c in citations],
        "total_results": len(items),
        "degraded": resp.degraded,
    }


async def get_symbol(
    ctx: AuthContext | SystemContext,
    project_id: UUID,
    session: AsyncSession,
    symbol_name: str,
    path: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Look up program symbols by name with optional path constraint."""
    start_t = time.perf_counter()
    bounded_limit = min(max(1, limit), MAX_SYMBOL_LIMIT)

    repo = BrainRepository(session)
    # verify_project_access raises PermissionError on cross-tenant mismatch
    await repo._verify_project_access(ctx, project_id)

    raw_symbols = await repo.search_symbols(
        ctx=ctx,
        project_id=project_id,
        query=symbol_name,
        limit=bounded_limit * 2,
    )

    filtered: list[CodeSymbol] = []
    for s in raw_symbols:
        file_path = s.file_version.file.path if (s.file_version and s.file_version.file) else None
        if path and file_path and not (file_path == path or file_path.endswith(path)):
            continue
        filtered.append(s)
        if len(filtered) >= bounded_limit:
            break

    results: list[dict[str, Any]] = []
    for s in filtered:
        file_path = s.file_version.file.path if (s.file_version and s.file_version.file) else None
        results.append(
            {
                "id": str(s.id),
                "name": s.name,
                "symbol_key": s.symbol_key,
                "kind": s.kind,
                "signature": s.signature,
                "path": file_path,
                "start_line": s.start_line,
                "end_line": s.end_line,
                "framework_tags": s.framework_tags,
                "metadata": s.metadata_json,
            }
        )

    duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
    logger.info(
        "tool_executed",
        extra={
            "tool": "get_symbol",
            "project_id": str(project_id),
            "result_count": len(results),
            "duration_ms": duration_ms,
        },
    )

    return results


async def get_file_range(
    ctx: AuthContext | SystemContext,
    project_id: UUID,
    session: AsyncSession,
    file_path: str,
    start_line: int,
    end_line: int,
) -> dict[str, Any]:
    """Read a bounded range of lines (max 200 lines) from a project file."""
    start_t = time.perf_counter()

    if start_line < 1:
        raise ValueError("start_line must be greater than or equal to 1")
    if end_line < start_line:
        raise ValueError("end_line must be greater than or equal to start_line")

    clamped = False
    effective_end = end_line
    if (end_line - start_line + 1) > MAX_FILE_RANGE_LINES:
        effective_end = start_line + MAX_FILE_RANGE_LINES - 1
        clamped = True

    repo = BrainRepository(session)
    await repo._verify_project_access(ctx, project_id)

    file_obj = await repo.get_file_by_path(ctx, project_id, file_path)
    if not file_obj or file_obj.removed_at is not None:
        return {
            "found": False,
            "file_path": file_path,
            "error": f"File '{file_path}' not found in project",
            "content": "",
            "start_line": start_line,
            "end_line": effective_end,
            "lines_returned": 0,
            "clamped": clamped,
            "citation": None,
        }

    version_id = file_obj.current_version_id
    if version_id is None:
        # Fallback to latest version
        ver_stmt = (
            select(FileVersion)
            .where(FileVersion.file_id == file_obj.id)
            .order_by(FileVersion.created_at.desc())
            .limit(1)
        )
        ver_res = await session.execute(ver_stmt)
        latest_ver = ver_res.scalars().first()
        if latest_ver:
            version_id = latest_ver.id

    if not version_id:
        return {
            "found": True,
            "file_path": file_path,
            "content": "",
            "start_line": start_line,
            "end_line": effective_end,
            "lines_returned": 0,
            "clamped": clamped,
            "citation": f"{file_path}:{start_line}-{effective_end}",
        }

    # Query matching overlapping chunks
    stmt = (
        select(CodeChunk)
        .where(
            CodeChunk.project_id == project_id,
            CodeChunk.file_version_id == version_id,
            CodeChunk.is_current.is_(True),
            CodeChunk.end_line >= start_line,
            CodeChunk.start_line <= effective_end,
        )
        .order_by(CodeChunk.start_line.asc())
    )
    result = await session.execute(stmt)
    chunks = list(result.scalars().all())

    line_map: dict[int, str] = {}
    for chunk in chunks:
        chunk_lines = chunk.content.splitlines()
        for idx, line in enumerate(chunk_lines):
            lineno = chunk.start_line + idx
            if start_line <= lineno <= effective_end:
                line_map[lineno] = line

    sorted_lines = [line_map[lineno] for lineno in sorted(line_map.keys())]
    content = "\n".join(sorted_lines)

    duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
    logger.info(
        "tool_executed",
        extra={
            "tool": "get_file_range",
            "project_id": str(project_id),
            "lines_returned": len(sorted_lines),
            "duration_ms": duration_ms,
        },
    )

    return {
        "found": True,
        "file_path": file_path,
        "start_line": start_line,
        "end_line": effective_end,
        "content": content,
        "lines_returned": len(sorted_lines),
        "clamped": clamped,
        "citation": f"{file_path}:{start_line}-{effective_end}",
    }


async def get_relationships(
    ctx: AuthContext | SystemContext,
    project_id: UUID,
    session: AsyncSession,
    symbol_name: str,
    kind: str | None = None,
    direction: str = "both",
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Query architectural call/import/route relationships connected to a symbol."""
    start_t = time.perf_counter()
    bounded_limit = min(max(1, limit), MAX_RELATIONSHIP_LIMIT)

    repo = BrainRepository(session)
    await repo._verify_project_access(ctx, project_id)

    matching_symbols = await repo.search_symbols(
        ctx=ctx,
        project_id=project_id,
        query=symbol_name,
        limit=5,
    )

    if not matching_symbols:
        return []

    symbol_ids = [s.id for s in matching_symbols]

    stmt = (
        select(CodeRelationship)
        .options(
            selectinload(CodeRelationship.from_symbol),
            selectinload(CodeRelationship.to_symbol),
        )
        .where(
            CodeRelationship.project_id == project_id,
            CodeRelationship.is_current.is_(True),
        )
    )

    if direction == "outgoing":
        stmt = stmt.where(CodeRelationship.from_symbol_id.in_(symbol_ids))
    elif direction == "incoming":
        stmt = stmt.where(CodeRelationship.to_symbol_id.in_(symbol_ids))
    else:
        stmt = stmt.where(
            or_(
                CodeRelationship.from_symbol_id.in_(symbol_ids),
                CodeRelationship.to_symbol_id.in_(symbol_ids),
            )
        )

    if kind:
        stmt = stmt.where(CodeRelationship.kind == kind)

    stmt = stmt.limit(bounded_limit)
    res = await session.execute(stmt)
    rels = list(res.scalars().all())

    results: list[dict[str, Any]] = []
    symbol_ids_set = set(symbol_ids)

    for r in rels:
        is_outgoing = r.from_symbol_id in symbol_ids_set
        results.append(
            {
                "id": str(r.id),
                "kind": r.kind,
                "direction": "outgoing" if is_outgoing else "incoming",
                "from_symbol": r.from_symbol.symbol_key if r.from_symbol else None,
                "from_symbol_name": r.from_symbol.name if r.from_symbol else None,
                "to_symbol": r.to_symbol.symbol_key if r.to_symbol else None,
                "to_symbol_name": r.to_symbol.name if r.to_symbol else None,
                "to_external": r.to_external,
                "resolution": r.resolution,
            }
        )

    duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
    logger.info(
        "tool_executed",
        extra={
            "tool": "get_relationships",
            "project_id": str(project_id),
            "result_count": len(results),
            "duration_ms": duration_ms,
        },
    )

    return results


# ---------------------------------------------------------------------------
# Scoped Tool Registry / Factory
# ---------------------------------------------------------------------------


class AgentToolSet:
    """Bound tool collection scoped to an AuthContext and project_id for LangGraph/LangChain execution."""

    def __init__(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        session: AsyncSession,
    ) -> None:
        self.ctx = ctx
        self.project_id = project_id
        self.session = session

    async def search_brain(self, query: str, limit: int = 5) -> dict[str, Any]:
        """Search the Project Brain for relevant code chunks and context."""
        return await search_brain(
            ctx=self.ctx,
            project_id=self.project_id,
            session=self.session,
            query=query,
            limit=limit,
        )

    async def get_symbol(
        self, symbol_name: str, path: str | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Look up program symbols by name."""
        return await get_symbol(
            ctx=self.ctx,
            project_id=self.project_id,
            session=self.session,
            symbol_name=symbol_name,
            path=path,
            limit=limit,
        )

    async def get_file_range(
        self, file_path: str, start_line: int, end_line: int
    ) -> dict[str, Any]:
        """Read a bounded range of file lines."""
        return await get_file_range(
            ctx=self.ctx,
            project_id=self.project_id,
            session=self.session,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
        )

    async def get_relationships(
        self,
        symbol_name: str,
        kind: str | None = None,
        direction: str = "both",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Query architectural call/import/route relationships."""
        return await get_relationships(
            ctx=self.ctx,
            project_id=self.project_id,
            session=self.session,
            symbol_name=symbol_name,
            kind=kind,
            direction=direction,
            limit=limit,
        )

    def as_langchain_tools(self) -> list[BaseTool]:
        """Produce LangChain BaseTool instances for LangGraph agent nodes."""
        return [
            StructuredTool.from_function(
                coroutine=self.search_brain,
                name="search_brain",
                description="Search the Project Brain for relevant code chunks and semantic context.",
                args_schema=SearchBrainInput,
            ),
            StructuredTool.from_function(
                coroutine=self.get_symbol,
                name="get_symbol",
                description="Look up declarations, signatures, and file locations for program symbols.",
                args_schema=GetSymbolInput,
            ),
            StructuredTool.from_function(
                coroutine=self.get_file_range,
                name="get_file_range",
                description="Read a bounded range of lines (max 200 lines) from a project file.",
                args_schema=GetFileRangeInput,
            ),
            StructuredTool.from_function(
                coroutine=self.get_relationships,
                name="get_relationships",
                description="Query architectural call, import, route, and guard relationships for a symbol.",
                args_schema=GetRelationshipsInput,
            ),
        ]

    def as_tool_definitions(self) -> list[ToolDefinition]:
        """Produce normalized ToolDefinitions for LLM gateway adapters."""
        return [
            ToolDefinition.from_params(
                name="search_brain",
                description="Search the Project Brain for relevant code chunks and semantic context.",
                parameters=SearchBrainInput.model_json_schema(),
            ),
            ToolDefinition.from_params(
                name="get_symbol",
                description="Look up declarations, signatures, and file locations for program symbols.",
                parameters=GetSymbolInput.model_json_schema(),
            ),
            ToolDefinition.from_params(
                name="get_file_range",
                description="Read a bounded range of lines (max 200 lines) from a project file.",
                parameters=GetFileRangeInput.model_json_schema(),
            ),
            ToolDefinition.from_params(
                name="get_relationships",
                description="Query architectural call, import, route, and guard relationships for a symbol.",
                parameters=GetRelationshipsInput.model_json_schema(),
            ),
        ]


def create_agent_tools(
    ctx: AuthContext | SystemContext,
    project_id: UUID,
    session: AsyncSession,
) -> AgentToolSet:
    """Create a scoped AgentToolSet bound to an AuthContext and project_id."""
    return AgentToolSet(ctx=ctx, project_id=project_id, session=session)
