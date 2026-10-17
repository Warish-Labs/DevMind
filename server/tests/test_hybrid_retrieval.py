"""Tests verifying hybrid retrieval, Reciprocal Rank Fusion (RRF), relationship expansion, context pack assembly, and search API (docs/04 §7-§8, docs/11 M5-08)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext
from app.core.ids import generate_uuid7
from app.domain.auth import PERM_BRAIN_READ, PERM_PROJECT_READ
from app.domain.brain.retrieval_service import (
    BrainCitation,
    BrainSearchItem,
    BrainSearchRequest,
    RetrievalService,
)
from app.llm.embedding_adapter import FakeEmbeddingAdapter
from app.main import create_app
from app.persistence.models.brain import (
    CodeChunk,
    CodeRelationship,
    CodeSymbol,
    EmbeddingSpace,
    FileVersion,
    ProjectFile,
)
from app.persistence.models.project import Project
from app.persistence.models.workspace import WorkspaceMembership


def _make_auth_ctx(workspace_id: UUID | None = None, user_id: UUID | None = None) -> AuthContext:
    return AuthContext(
        user_id=user_id or generate_uuid7(),
        clerk_user_id="user_clerk_retrieval_test",
        email="retrieval_test@example.com",
        workspace_id=workspace_id or generate_uuid7(),
        workspace_role="member",
        permissions=frozenset({PERM_PROJECT_READ, PERM_BRAIN_READ}),
    )


def test_retrieval_service_config_loading() -> None:
    """Verify that RetrievalService loads retrieval.yaml or falls back to valid defaults."""
    session = AsyncMock(spec=AsyncSession)
    service = RetrievalService(session)
    assert service.config["fusion"]["rrf_k"] == 60
    assert "symbol" in service.config["fusion"]["weights"]
    assert "keyword" in service.config["fusion"]["weights"]
    assert "vector" in service.config["fusion"]["weights"]
    assert service.config["context_pack"]["default_token_budget"] == 2000


def test_context_pack_builder_token_budget_and_formatting() -> None:
    """Verify context pack merges, formats code blocks, attaches citations, and respects budget."""
    session = AsyncMock(spec=AsyncSession)
    service = RetrievalService(session)

    item1 = BrainSearchItem(
        id=generate_uuid7(),
        kind="chunk",
        path="src/auth/guard.ts",
        start_line=10,
        end_line=25,
        symbol_key="guard.require_auth",
        content="export function requireAuth() { checkToken(); }",
        score=0.032,
        matched_by=["symbol", "keyword"],
        citation=BrainCitation(
            file_version_id=generate_uuid7(),
            path="src/auth/guard.ts",
            start_line=10,
            end_line=25,
            symbol_key="guard.require_auth",
            content_hash="hash_guard_01",
        ),
        is_expanded=False,
    )

    item2 = BrainSearchItem(
        id=generate_uuid7(),
        kind="chunk",
        path="src/routes/admin.ts",
        start_line=1,
        end_line=40,
        symbol_key="admin.users",
        content="router.get('/admin/users', requireAuth, (req, res) => { res.send(users); });",
        score=0.016,
        matched_by=["vector"],
        citation=BrainCitation(
            file_version_id=generate_uuid7(),
            path="src/routes/admin.ts",
            start_line=1,
            end_line=40,
            symbol_key="admin.users",
            content_hash="hash_admin_01",
        ),
        is_expanded=False,
    )

    # 1. Normal budget includes both items
    pack = service._build_context_pack([item1, item2], token_budget=2000)
    assert pack.item_count == 2
    assert "src/auth/guard.ts:10-25" in pack.formatted_context
    assert "src/routes/admin.ts:1-40" in pack.formatted_context
    assert "```typescript" in pack.formatted_context
    assert len(pack.citations) == 2

    # 2. Strict budget (e.g. 20 tokens) only accommodates the first block
    pack_small = service._build_context_pack([item1, item2], token_budget=25)
    assert pack_small.item_count == 1
    assert len(pack_small.citations) == 1
    assert "src/auth/guard.ts" in pack_small.formatted_context


@pytest.mark.asyncio
async def test_retrieval_service_multi_channel_fusion() -> None:
    """Verify that multi-channel RRF correctly boosts items matching multiple channels."""
    session = AsyncMock(spec=AsyncSession)
    project_id = generate_uuid7()
    workspace_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id)

    # Mock Project File & FileVersion
    file_obj = ProjectFile(
        id=generate_uuid7(),
        project_id=project_id,
        path="src/routes/admin.ts",
        language="typescript",
    )
    version_obj = FileVersion(
        id=generate_uuid7(),
        file_id=file_obj.id,
        content_hash="hash_admin_ver",
    )
    version_obj.file = file_obj

    # Symbol result
    symbol = CodeSymbol(
        id=generate_uuid7(),
        project_id=project_id,
        file_version_id=version_obj.id,
        symbol_key="routes.admin_users",
        name="admin_users",
        qualified_name="routes.admin.admin_users",
        kind="route_handler",
        signature="router.get('/admin/users')",
        start_line=7,
        end_line=20,
        is_current=True,
    )
    symbol.file_version = version_obj

    # Chunk result
    chunk = CodeChunk(
        id=generate_uuid7(),
        workspace_id=workspace_id,
        project_id=project_id,
        file_version_id=version_obj.id,
        symbol_id=symbol.id,
        content="router.get('/admin/users', requireAuth, (req, res) => {})",
        content_hash="hash_chunk_01",
        start_line=7,
        end_line=20,
        kind="function",
        search_text="admin users router get require auth",
        is_current=True,
    )
    chunk.file_version = version_obj

    service = RetrievalService(session, embedding_adapter=FakeEmbeddingAdapter())

    # Mock repository methods
    service.repo.search_symbols = AsyncMock(return_value=[symbol])
    service.repo.search_chunks_text = AsyncMock(return_value=[chunk])
    service.repo.get_active_embedding_space = AsyncMock(
        return_value=EmbeddingSpace(
            id=generate_uuid7(),
            provider_id="fake",
            model_id="fake-embed-v1",
            dimension=64,
            status="active",
        )
    )
    service.repo.search_chunks_vector = AsyncMock(return_value=[(chunk, 0.95)])
    service.repo.get_relationships_for_symbols = AsyncMock(return_value=[])

    request = BrainSearchRequest(
        query="admin users",
        modes=["symbol", "keyword", "vector"],
        limit=5,
        expand_relationships=False,
    )

    response = await service.search(ctx, project_id, request)

    assert response.query == "admin users"
    assert len(response.items) >= 2

    # Chunk matched in both keyword and vector channels
    chunk_item = next(it for it in response.items if it.id == chunk.id)
    assert "keyword" in chunk_item.matched_by
    assert "vector" in chunk_item.matched_by
    # RRF score for item in 2 channels is higher than rank 1 in single channel (1/(60+1) + 1/(60+1) > 1/(60+1))
    assert chunk_item.score > (1.0 / 61.0)


@pytest.mark.asyncio
async def test_retrieval_relationship_expansion() -> None:
    """Verify that relationship expansion discovers and attaches 1-hop connected symbols."""
    session = AsyncMock(spec=AsyncSession)
    project_id = generate_uuid7()
    ctx = _make_auth_ctx()

    file_obj = ProjectFile(
        id=generate_uuid7(),
        project_id=project_id,
        path="src/admin.ts",
        language="typescript",
    )
    version_obj = FileVersion(
        id=generate_uuid7(),
        file_id=file_obj.id,
        content_hash="hash_01",
    )
    version_obj.file = file_obj

    root_symbol = CodeSymbol(
        id=generate_uuid7(),
        project_id=project_id,
        file_version_id=version_obj.id,
        symbol_key="admin_func",
        name="admin_func",
        qualified_name="admin.admin_func",
        kind="function",
        start_line=1,
        end_line=10,
        is_current=True,
    )
    root_symbol.file_version = version_obj

    called_symbol = CodeSymbol(
        id=generate_uuid7(),
        project_id=project_id,
        file_version_id=version_obj.id,
        symbol_key="auth_guard",
        name="auth_guard",
        qualified_name="auth.auth_guard",
        kind="function",
        start_line=20,
        end_line=30,
        is_current=True,
    )
    called_symbol.file_version = version_obj

    service = RetrievalService(session, embedding_adapter=FakeEmbeddingAdapter())
    service.repo.search_symbols = AsyncMock(return_value=[root_symbol])
    service.repo.search_chunks_text = AsyncMock(return_value=[])
    service.repo.get_active_embedding_space = AsyncMock(return_value=None)

    # 1-hop caller relationship
    rel = CodeRelationship(
        project_id=project_id,
        from_symbol_id=root_symbol.id,
        to_symbol_id=called_symbol.id,
        kind="calls",
        is_current=True,
    )
    service.repo.get_relationships_for_symbols = AsyncMock(return_value=[rel])
    service.repo.list_current_symbols = AsyncMock(return_value=[root_symbol, called_symbol])

    request = BrainSearchRequest(
        query="admin",
        modes=["symbol"],
        limit=5,
        expand_relationships=True,
    )

    response = await service.search(ctx, project_id, request)

    # One direct hit and one expanded item
    assert len(response.items) == 2
    expanded = next(it for it in response.items if it.is_expanded)
    assert expanded.id == called_symbol.id
    assert expanded.matched_by == ["relationship_expansion"]


@pytest.mark.asyncio
async def test_brain_search_api_endpoint() -> None:
    """Verify POST /api/v1/projects/{pid}/brain/search executes search and checks permissions."""
    app = create_app()
    project_id = generate_uuid7()
    workspace_id = generate_uuid7()
    user_id = generate_uuid7()

    ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_clerk_search_api",
        email="search_api@example.com",
        workspace_id=workspace_id,
        workspace_role="member",
        permissions=frozenset({PERM_PROJECT_READ, PERM_BRAIN_READ}),
    )

    # Mock Project & Membership
    mock_project = Project(
        id=project_id,
        workspace_id=workspace_id,
        name="Search API Test Project",
        slug="search-api-test",
    )

    mock_ws_membership = WorkspaceMembership(
        workspace_id=workspace_id,
        user_id=user_id,
        role="member",
    )

    mock_session = AsyncMock(spec=AsyncSession)

    def _execute_mock(stmt):
        mock_res = MagicMock()
        stmt_str = str(stmt).lower()
        if "from projects" in stmt_str:
            mock_res.scalars.return_value.first.return_value = mock_project
            mock_res.scalars.return_value.all.return_value = [mock_project]
        elif "from workspace_memberships" in stmt_str:
            mock_res.scalars.return_value.first.return_value = mock_ws_membership
        else:
            mock_res.scalars.return_value.first.return_value = None
            mock_res.scalars.return_value.all.return_value = []
            mock_res.all.return_value = []
        return mock_res

    mock_session.execute = AsyncMock(side_effect=_execute_mock)
    mock_session.get = AsyncMock(return_value=None)

    from app.domain.auth.dependencies import get_auth_context, get_db_session

    app.dependency_overrides[get_auth_context] = lambda: ctx
    app.dependency_overrides[get_db_session] = lambda: mock_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Valid Search Request
        payload = {
            "query": "authentication check",
            "modes": ["symbol", "keyword"],
            "limit": 5,
            "expand_relationships": False,
            "token_budget": 1000,
        }
        resp = await client.post(f"/api/v1/projects/{project_id}/brain/search", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "authentication check"
        assert "context_pack" in data
        assert "items" in data

        # 2. Invalid project (Not Found)
        other_pid = generate_uuid7()

        def _execute_missing_project(stmt):
            mock_res = MagicMock()
            mock_res.scalars.return_value.first.return_value = None
            mock_res.scalars.return_value.all.return_value = []
            return mock_res

        mock_session.execute = AsyncMock(side_effect=_execute_missing_project)
        resp_nf = await client.post(f"/api/v1/projects/{other_pid}/brain/search", json=payload)
        assert resp_nf.status_code == 404
