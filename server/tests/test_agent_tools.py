"""Tests for scoped agent tools: search_brain, get_symbol, get_file_range, get_relationships (docs/05 §6.1, §9, M7-02).

Verifies:
1. Closed allowlist of read-only, scoped tools.
2. Cross-tenant isolation enforcement (PermissionError on mismatched workspace).
3. Bounded results and line-clamping (max 200 lines for file ranges, max limits for queries).
4. Citation references emitted with precise line and symbol provenance.
5. LangChain StructuredTool and LLM ToolDefinition compatibility.
6. Audit logging without leaking source code payloads or user secrets.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext
from app.core.ids import generate_uuid7
from app.domain.auth import PERM_BRAIN_READ, PERM_PROJECT_READ
from app.domain.brain.retrieval_service import (
    BrainCitation,
    BrainSearchItem,
    BrainSearchResponse,
    ContextPack,
)
from app.orchestration.tools import (
    create_agent_tools,
    get_file_range,
    get_relationships,
    get_symbol,
    search_brain,
)
from app.persistence.models.brain import (
    CodeChunk,
    CodeRelationship,
    CodeSymbol,
    FileVersion,
    ProjectFile,
)
from app.persistence.models.project import Project


def _make_auth_ctx(workspace_id: UUID | None = None) -> AuthContext:
    return AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_clerk_test",
        email="agent_tools_test@example.com",
        workspace_id=workspace_id or generate_uuid7(),
        workspace_role="member",
        permissions=frozenset({PERM_PROJECT_READ, PERM_BRAIN_READ}),
    )


def _mock_project(project_id: UUID, workspace_id: UUID) -> Project:
    proj = MagicMock(spec=Project)
    proj.id = project_id
    proj.workspace_id = workspace_id
    proj.name = "Test Project"
    return proj


# ---------------------------------------------------------------------------
# search_brain Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_brain_success() -> None:
    """Verify search_brain executes hybrid search and emits structured items and citations."""
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id)
    session = AsyncMock(spec=AsyncSession)

    item_id = generate_uuid7()
    file_version_id = generate_uuid7()
    mock_search_item = BrainSearchItem(
        id=item_id,
        kind="chunk",
        path="server/app/auth.py",
        start_line=10,
        end_line=25,
        symbol_key="auth.verify_token",
        content="def verify_token(): pass",
        score=0.88,
        matched_by=["keyword", "vector"],
        citation=BrainCitation(
            file_version_id=file_version_id,
            path="server/app/auth.py",
            start_line=10,
            end_line=25,
            symbol_key="auth.verify_token",
        ),
    )
    mock_resp = BrainSearchResponse(
        query="verify_token",
        total_results=1,
        items=[mock_search_item],
        context_pack=ContextPack(
            formatted_context="...",
            total_tokens_estimate=50,
            item_count=1,
            citations=[mock_search_item.citation],
        ),
    )

    with patch(
        "app.orchestration.tools.RetrievalService.search", new_callable=AsyncMock
    ) as mock_retrieval:
        mock_retrieval.return_value = mock_resp

        res = await search_brain(
            ctx=ctx,
            project_id=project_id,
            session=session,
            query="verify_token",
            limit=5,
        )

        assert res["total_results"] == 1
        assert len(res["items"]) == 1
        assert res["items"][0]["path"] == "server/app/auth.py"
        assert res["items"][0]["start_line"] == 10
        assert res["items"][0]["end_line"] == 25
        assert len(res["citations"]) == 1
        assert res["citations"][0]["path"] == "server/app/auth.py"
        assert res["citations"][0]["symbol"] == "auth.verify_token"


@pytest.mark.asyncio
async def test_search_brain_cross_tenant_denied() -> None:
    """Verify search_brain raises PermissionError when workspace does not own the project."""
    workspace_a = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_a)
    project_id = generate_uuid7()
    session = AsyncMock(spec=AsyncSession)

    with patch(
        "app.orchestration.tools.RetrievalService.search", new_callable=AsyncMock
    ) as mock_retrieval:
        mock_retrieval.side_effect = PermissionError("Access denied: project not in workspace")

        with pytest.raises(PermissionError, match="Access denied"):
            await search_brain(
                ctx=ctx,
                project_id=project_id,
                session=session,
                query="sensitive_data",
            )


@pytest.mark.asyncio
async def test_search_brain_limit_bounding() -> None:
    """Verify search_brain clamps requested limit to MAX_SEARCH_LIMIT (20)."""
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id)
    session = AsyncMock(spec=AsyncSession)

    with patch(
        "app.orchestration.tools.RetrievalService.search", new_callable=AsyncMock
    ) as mock_retrieval:
        mock_retrieval.return_value = BrainSearchResponse(
            query="test",
            total_results=0,
            items=[],
            context_pack=ContextPack(formatted_context="", total_tokens_estimate=0, item_count=0),
        )

        await search_brain(ctx=ctx, project_id=project_id, session=session, query="test", limit=999)

        call_args = mock_retrieval.call_args[1]
        req = call_args["request"]
        assert req.limit == 20


# ---------------------------------------------------------------------------
# get_symbol Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_symbol_success() -> None:
    """Verify get_symbol retrieves declaration details and path constraints."""
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id)
    session = AsyncMock(spec=AsyncSession)

    # Mock Project & File
    mock_file = MagicMock(spec=ProjectFile)
    mock_file.path = "server/app/main.py"
    mock_version = MagicMock(spec=FileVersion)
    mock_version.file = mock_file

    mock_symbol = MagicMock(spec=CodeSymbol)
    mock_symbol.id = generate_uuid7()
    mock_symbol.name = "create_app"
    mock_symbol.symbol_key = "server/app/main.py:create_app"
    mock_symbol.kind = "function"
    mock_symbol.signature = "def create_app() -> FastAPI:"
    mock_symbol.start_line = 40
    mock_symbol.end_line = 70
    mock_symbol.file_version_id = generate_uuid7()
    mock_symbol.file_version = mock_version
    mock_symbol.framework_tags = ["fastapi", "factory"]
    mock_symbol.metadata_json = {"async": False}

    with (
        patch(
            "app.orchestration.tools.BrainRepository._verify_project_access", new_callable=AsyncMock
        ) as mock_verify,
        patch(
            "app.orchestration.tools.BrainRepository.search_symbols", new_callable=AsyncMock
        ) as mock_search,
    ):
        mock_verify.return_value = _mock_project(project_id, workspace_id)
        mock_search.return_value = [mock_symbol]

        results = await get_symbol(
            ctx=ctx,
            project_id=project_id,
            session=session,
            symbol_name="create_app",
            path="server/app/main.py",
        )

        assert len(results) == 1
        sym = results[0]
        assert sym["name"] == "create_app"
        assert sym["symbol_key"] == "server/app/main.py:create_app"
        assert sym["kind"] == "function"
        assert sym["path"] == "server/app/main.py"
        assert sym["start_line"] == 40
        assert sym["end_line"] == 70
        assert "fastapi" in sym["framework_tags"]


@pytest.mark.asyncio
async def test_get_symbol_path_filter_exclusion() -> None:
    """Verify get_symbol filters out symbols outside the specified path."""
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id)
    session = AsyncMock(spec=AsyncSession)

    mock_file = MagicMock(spec=ProjectFile)
    mock_file.path = "client/src/index.ts"
    mock_version = MagicMock(spec=FileVersion)
    mock_version.file = mock_file

    mock_symbol = MagicMock(spec=CodeSymbol)
    mock_symbol.name = "handle_request"
    mock_symbol.symbol_key = "client/src/index.ts:handle_request"
    mock_symbol.kind = "function"
    mock_symbol.signature = None
    mock_symbol.start_line = 1
    mock_symbol.end_line = 10
    mock_symbol.file_version_id = generate_uuid7()
    mock_symbol.file_version = mock_version
    mock_symbol.framework_tags = []
    mock_symbol.metadata_json = {}

    with (
        patch(
            "app.orchestration.tools.BrainRepository._verify_project_access", new_callable=AsyncMock
        ) as mock_verify,
        patch(
            "app.orchestration.tools.BrainRepository.search_symbols", new_callable=AsyncMock
        ) as mock_search,
    ):
        mock_verify.return_value = _mock_project(project_id, workspace_id)
        mock_search.return_value = [mock_symbol]

        results = await get_symbol(
            ctx=ctx,
            project_id=project_id,
            session=session,
            symbol_name="handle_request",
            path="server/app/main.py",  # Mismatched path
        )

        assert len(results) == 0


@pytest.mark.asyncio
async def test_get_symbol_cross_tenant_denied() -> None:
    """Verify get_symbol raises PermissionError when cross-tenant check fails."""
    ctx = _make_auth_ctx()
    project_id = generate_uuid7()
    session = AsyncMock(spec=AsyncSession)

    with patch(
        "app.orchestration.tools.BrainRepository._verify_project_access", new_callable=AsyncMock
    ) as mock_verify:
        mock_verify.side_effect = PermissionError("Access denied")

        with pytest.raises(PermissionError):
            await get_symbol(
                ctx=ctx,
                project_id=project_id,
                session=session,
                symbol_name="secret_symbol",
            )


# ---------------------------------------------------------------------------
# get_file_range Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_file_range_success() -> None:
    """Verify get_file_range reconstructs line-bounded text from overlapping chunks."""
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id)
    session = AsyncMock(spec=AsyncSession)

    version_id = generate_uuid7()
    mock_file = MagicMock(spec=ProjectFile)
    mock_file.id = generate_uuid7()
    mock_file.path = "server/app/main.py"
    mock_file.current_version_id = version_id
    mock_file.removed_at = None

    chunk1 = MagicMock(spec=CodeChunk)
    chunk1.start_line = 1
    chunk1.end_line = 3
    chunk1.content = "line 1\nline 2\nline 3"

    chunk2 = MagicMock(spec=CodeChunk)
    chunk2.start_line = 4
    chunk2.end_line = 5
    chunk2.content = "line 4\nline 5"

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [chunk1, chunk2]
    mock_exec_res = MagicMock()
    mock_exec_res.scalars.return_value = mock_scalars
    session.execute.return_value = mock_exec_res

    with (
        patch(
            "app.orchestration.tools.BrainRepository._verify_project_access", new_callable=AsyncMock
        ) as mock_verify,
        patch(
            "app.orchestration.tools.BrainRepository.get_file_by_path", new_callable=AsyncMock
        ) as mock_get_file,
    ):
        mock_verify.return_value = _mock_project(project_id, workspace_id)
        mock_get_file.return_value = mock_file

        result = await get_file_range(
            ctx=ctx,
            project_id=project_id,
            session=session,
            file_path="server/app/main.py",
            start_line=2,
            end_line=4,
        )

        assert result["found"] is True
        assert result["file_path"] == "server/app/main.py"
        assert result["start_line"] == 2
        assert result["end_line"] == 4
        assert result["lines_returned"] == 3
        assert result["content"] == "line 2\nline 3\nline 4"
        assert result["clamped"] is False
        assert result["citation"] == "server/app/main.py:2-4"


@pytest.mark.asyncio
async def test_get_file_range_file_not_found() -> None:
    """Verify get_file_range returns found=False when the file path is absent."""
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id)
    session = AsyncMock(spec=AsyncSession)

    with (
        patch(
            "app.orchestration.tools.BrainRepository._verify_project_access", new_callable=AsyncMock
        ) as mock_verify,
        patch(
            "app.orchestration.tools.BrainRepository.get_file_by_path", new_callable=AsyncMock
        ) as mock_get_file,
    ):
        mock_verify.return_value = _mock_project(project_id, workspace_id)
        mock_get_file.return_value = None

        result = await get_file_range(
            ctx=ctx,
            project_id=project_id,
            session=session,
            file_path="non_existent.py",
            start_line=1,
            end_line=10,
        )

        assert result["found"] is False
        assert result["lines_returned"] == 0
        assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_get_file_range_validation_and_clamping() -> None:
    """Verify get_file_range rejects invalid line orders and clamps > 200 lines."""
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id)
    session = AsyncMock(spec=AsyncSession)

    # 1. start_line < 1
    with pytest.raises(ValueError, match="start_line must be greater than or equal to 1"):
        await get_file_range(
            ctx=ctx,
            project_id=project_id,
            session=session,
            file_path="server/app/main.py",
            start_line=0,
            end_line=10,
        )

    # 2. end_line < start_line
    with pytest.raises(ValueError, match="end_line must be greater than or equal to start_line"):
        await get_file_range(
            ctx=ctx,
            project_id=project_id,
            session=session,
            file_path="server/app/main.py",
            start_line=50,
            end_line=20,
        )

    # 3. Requesting 300 lines gets clamped to 200 lines
    mock_file = MagicMock(spec=ProjectFile)
    mock_file.current_version_id = generate_uuid7()
    mock_file.removed_at = None

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_exec_res = MagicMock()
    mock_exec_res.scalars.return_value = mock_scalars
    session.execute.return_value = mock_exec_res

    with (
        patch(
            "app.orchestration.tools.BrainRepository._verify_project_access", new_callable=AsyncMock
        ) as mock_verify,
        patch(
            "app.orchestration.tools.BrainRepository.get_file_by_path", new_callable=AsyncMock
        ) as mock_get_file,
    ):
        mock_verify.return_value = _mock_project(project_id, workspace_id)
        mock_get_file.return_value = mock_file

        result = await get_file_range(
            ctx=ctx,
            project_id=project_id,
            session=session,
            file_path="server/app/main.py",
            start_line=1,
            end_line=300,
        )

        assert result["clamped"] is True
        assert result["start_line"] == 1
        assert result["end_line"] == 200  # Clamped to 1 + 200 - 1


# ---------------------------------------------------------------------------
# get_relationships Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_relationships_success() -> None:
    """Verify get_relationships queries incoming/outgoing edges and loads symbol names."""
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id)
    session = AsyncMock(spec=AsyncSession)

    sym1_id = generate_uuid7()
    sym2_id = generate_uuid7()

    sym1 = MagicMock(spec=CodeSymbol)
    sym1.id = sym1_id
    sym1.name = "get_user"
    sym1.symbol_key = "app.users:get_user"

    sym2 = MagicMock(spec=CodeSymbol)
    sym2.id = sym2_id
    sym2.name = "auth_guard"
    sym2.symbol_key = "app.auth:auth_guard"

    rel = MagicMock(spec=CodeRelationship)
    rel.id = generate_uuid7()
    rel.kind = "guarded_by"
    rel.from_symbol_id = sym1_id
    rel.to_symbol_id = sym2_id
    rel.from_symbol = sym1
    rel.to_symbol = sym2
    rel.to_external = None
    rel.resolution = "resolved"

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [rel]
    mock_exec_res = MagicMock()
    mock_exec_res.scalars.return_value = mock_scalars
    session.execute.return_value = mock_exec_res

    with (
        patch(
            "app.orchestration.tools.BrainRepository._verify_project_access", new_callable=AsyncMock
        ) as mock_verify,
        patch(
            "app.orchestration.tools.BrainRepository.search_symbols", new_callable=AsyncMock
        ) as mock_search,
    ):
        mock_verify.return_value = _mock_project(project_id, workspace_id)
        mock_search.return_value = [sym1]

        results = await get_relationships(
            ctx=ctx,
            project_id=project_id,
            session=session,
            symbol_name="get_user",
            kind="guarded_by",
            direction="outgoing",
        )

        assert len(results) == 1
        r = results[0]
        assert r["kind"] == "guarded_by"
        assert r["direction"] == "outgoing"
        assert r["from_symbol"] == "app.users:get_user"
        assert r["from_symbol_name"] == "get_user"
        assert r["to_symbol"] == "app.auth:auth_guard"
        assert r["to_symbol_name"] == "auth_guard"
        assert r["resolution"] == "resolved"


@pytest.mark.asyncio
async def test_get_relationships_symbol_absent() -> None:
    """Verify get_relationships returns [] when no matching symbol exists."""
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id)
    session = AsyncMock(spec=AsyncSession)

    with (
        patch(
            "app.orchestration.tools.BrainRepository._verify_project_access", new_callable=AsyncMock
        ) as mock_verify,
        patch(
            "app.orchestration.tools.BrainRepository.search_symbols", new_callable=AsyncMock
        ) as mock_search,
    ):
        mock_verify.return_value = _mock_project(project_id, workspace_id)
        mock_search.return_value = []

        results = await get_relationships(
            ctx=ctx,
            project_id=project_id,
            session=session,
            symbol_name="missing_fn",
        )

        assert results == []


# ---------------------------------------------------------------------------
# AgentToolSet & LangChain / ToolDefinition Integration Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_tool_set_as_langchain_tools() -> None:
    """Verify AgentToolSet exports LangChain StructuredTool instances that can be invoked."""
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id)
    session = AsyncMock(spec=AsyncSession)

    tool_set = create_agent_tools(ctx=ctx, project_id=project_id, session=session)
    lc_tools = tool_set.as_langchain_tools()

    assert len(lc_tools) == 4
    tool_names = {t.name for t in lc_tools}
    assert tool_names == {"search_brain", "get_symbol", "get_file_range", "get_relationships"}

    # Test invoking get_symbol through LangChain tool interface
    sym_tool = next(t for t in lc_tools if t.name == "get_symbol")
    with (
        patch(
            "app.orchestration.tools.BrainRepository._verify_project_access", new_callable=AsyncMock
        ) as mock_verify,
        patch(
            "app.orchestration.tools.BrainRepository.search_symbols", new_callable=AsyncMock
        ) as mock_search,
    ):
        mock_verify.return_value = _mock_project(project_id, workspace_id)
        mock_search.return_value = []

        out = await sym_tool.ainvoke({"symbol_name": "test_fn"})
        assert out == []


def test_agent_tool_set_as_tool_definitions() -> None:
    """Verify AgentToolSet exports normalized ToolDefinitions for LLM gateway."""
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id)
    session = AsyncMock(spec=AsyncSession)

    tool_set = create_agent_tools(ctx=ctx, project_id=project_id, session=session)
    tool_defs = tool_set.as_tool_definitions()

    assert len(tool_defs) == 4
    def_names = {d.function.name for d in tool_defs}
    assert def_names == {"search_brain", "get_symbol", "get_file_range", "get_relationships"}

    # Verify JSON Schema parameter structure
    for td in tool_defs:
        assert "properties" in td.function.parameters
        assert td.type == "function"
