"""Tests verifying chunk storage, repository operations, and tenant isolation (docs/03 §3.2, docs/04 §4, docs/11 M5-05)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext
from app.core.ids import generate_uuid7
from app.persistence.models.brain import CodeChunk
from app.persistence.models.project import Project
from app.persistence.repositories.brain_repo import BrainRepository


def _make_auth_ctx(workspace_id: UUID | None = None, user_id: UUID | None = None) -> AuthContext:
    return AuthContext(
        user_id=user_id or generate_uuid7(),
        clerk_user_id="user_clerk_chunk_test",
        email="chunk_test@example.com",
        workspace_id=workspace_id or generate_uuid7(),
        workspace_role="member",
    )


def test_code_chunk_model_instantiation_and_attributes() -> None:
    """Verify that CodeChunk instantiates with correct column values and defaults."""
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    version_id = generate_uuid7()
    symbol_id = generate_uuid7()

    chunk = CodeChunk(
        workspace_id=workspace_id,
        project_id=project_id,
        file_version_id=version_id,
        symbol_id=symbol_id,
        kind="function",
        start_line=12,
        end_line=45,
        content="async def handle_request(req): return Response(status=200)",
        content_hash="sha256:d41d8cd98f00b204e9800998ecf8427e",
        search_text="// File: app/routes.py\nasync def handle_request(req): return Response(status=200)",
        token_estimate=18,
        redaction_count=0,
        is_current=True,
    )

    assert chunk.workspace_id == workspace_id
    assert chunk.project_id == project_id
    assert chunk.file_version_id == version_id
    assert chunk.symbol_id == symbol_id
    assert chunk.kind == "function"
    assert chunk.start_line == 12
    assert chunk.end_line == 45
    assert chunk.token_estimate == 18
    assert chunk.redaction_count == 0
    assert chunk.is_current is True
    assert chunk.content_hash.startswith("sha256:")


@pytest.mark.asyncio
async def test_brain_repo_create_chunks() -> None:
    """Verify batch insertion of code chunks with workspace association and project access validation."""
    session = AsyncMock(spec=AsyncSession)
    repo = BrainRepository(session)

    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    version_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id)

    # Mock project lookup
    mock_project = Project(
        id=project_id,
        workspace_id=workspace_id,
        name="test-project",
        slug="test-proj",
    )
    repo._verify_project_access = AsyncMock(return_value=mock_project)  # type: ignore[method-assign]

    chunks_data = [
        {
            "file_version_id": version_id,
            "symbol_id": None,
            "kind": "module_prelude",
            "start_line": 1,
            "end_line": 10,
            "content": "import sys\nimport os\n",
            "content_hash": "sha256:11111111",
            "search_text": "# File: test.py\nimport sys\nimport os\n",
            "token_estimate": 8,
            "redaction_count": 0,
            "is_current": True,
        },
        {
            "file_version_id": version_id,
            "symbol_id": generate_uuid7(),
            "kind": "function",
            "start_line": 12,
            "end_line": 25,
            "content": "def run():\n    return 42\n",
            "content_hash": "sha256:22222222",
            "search_text": "# File: test.py\ndef run():\n    return 42\n",
            "token_estimate": 10,
            "redaction_count": 1,
            "is_current": True,
        },
    ]

    result = await repo.create_chunks(ctx, project_id, chunks_data)

    assert len(result) == 2
    assert session.add.call_count == 2
    session.flush.assert_awaited_once()

    c1, c2 = result
    assert c1.workspace_id == workspace_id
    assert c1.project_id == project_id
    assert c1.kind == "module_prelude"
    assert c1.content_hash == "sha256:11111111"
    assert c1.redaction_count == 0

    assert c2.workspace_id == workspace_id
    assert c2.kind == "function"
    assert c2.redaction_count == 1


@pytest.mark.asyncio
async def test_brain_repo_create_chunks_empty() -> None:
    """Verify create_chunks returns empty list immediately when input list is empty."""
    session = AsyncMock(spec=AsyncSession)
    repo = BrainRepository(session)
    ctx = _make_auth_ctx()

    result = await repo.create_chunks(ctx, generate_uuid7(), [])
    assert result == []
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_brain_repo_list_chunks() -> None:
    """Verify list_chunks queries by project, version, and current flag."""
    session = AsyncMock(spec=AsyncSession)
    repo = BrainRepository(session)

    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    version_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id)

    mock_project = Project(id=project_id, workspace_id=workspace_id)
    repo._verify_project_access = AsyncMock(return_value=mock_project)  # type: ignore[method-assign]

    mock_chunk = CodeChunk(
        workspace_id=workspace_id,
        project_id=project_id,
        file_version_id=version_id,
        kind="function",
        start_line=1,
        end_line=20,
        content="fn",
        content_hash="sha256:fn",
        search_text="fn",
        token_estimate=5,
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_chunk]
    session.execute.return_value = mock_result

    chunks = await repo.list_chunks(ctx, project_id, file_version_id=version_id, is_current=True)
    assert len(chunks) == 1
    assert chunks[0].kind == "function"
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_brain_repo_search_chunks_text() -> None:
    """Verify search_chunks_text returns matching chunks or short-circuits on empty query."""
    session = AsyncMock(spec=AsyncSession)
    repo = BrainRepository(session)

    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id)

    mock_project = Project(id=project_id, workspace_id=workspace_id)
    repo._verify_project_access = AsyncMock(return_value=mock_project)  # type: ignore[method-assign]

    # Empty query short-circuit
    res_empty = await repo.search_chunks_text(ctx, project_id, "   ")
    assert res_empty == []

    # Valid query
    mock_chunk = CodeChunk(
        workspace_id=workspace_id,
        project_id=project_id,
        file_version_id=generate_uuid7(),
        kind="class",
        start_line=1,
        end_line=50,
        content="class DatabaseService:",
        content_hash="sha256:dbsvc",
        search_text="class DatabaseService:",
        token_estimate=25,
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_chunk]
    session.execute.return_value = mock_result

    res = await repo.search_chunks_text(ctx, project_id, "DatabaseService")
    assert len(res) == 1
    assert res[0].kind == "class"


@pytest.mark.asyncio
async def test_brain_repo_supersede_versions_marks_chunks_non_current() -> None:
    """Verify that supersede_file_versions executes update statements for CodeChunk."""
    session = AsyncMock(spec=AsyncSession)
    repo = BrainRepository(session)

    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    v1 = generate_uuid7()
    v2 = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id)

    repo._verify_project_access = AsyncMock(
        return_value=Project(id=project_id, workspace_id=workspace_id)
    )  # type: ignore[method-assign]

    mock_res = MagicMock()
    mock_res.rowcount = 4
    session.execute.return_value = mock_res

    res = await repo.mark_symbols_non_current_for_versions(ctx, project_id, [v1, v2])
    assert res == 4
    # Three update queries: CodeSymbol, CodeRelationship, CodeChunk
    assert session.execute.await_count == 3
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_cross_tenant_chunk_access_rejected() -> None:
    """Verify cross-tenant operations on chunks are strictly rejected."""
    session = AsyncMock(spec=AsyncSession)
    repo = BrainRepository(session)

    tenant_b_ws = generate_uuid7()
    project_id = generate_uuid7()

    ctx_b = _make_auth_ctx(workspace_id=tenant_b_ws)

    # When querying Project for tenant B with tenant A's project, none is returned
    mock_exec_res = MagicMock()
    mock_exec_res.scalars.return_value.first.return_value = None
    session.execute.return_value = mock_exec_res

    with pytest.raises(PermissionError, match="Access denied: project"):
        await repo.create_chunks(
            ctx_b,
            project_id,
            [
                {
                    "file_version_id": generate_uuid7(),
                    "kind": "function",
                    "start_line": 1,
                    "end_line": 10,
                    "content": "x",
                    "content_hash": "sha256:x",
                    "search_text": "x",
                    "token_estimate": 1,
                }
            ],
        )

    with pytest.raises(PermissionError, match="Access denied: project"):
        await repo.list_chunks(ctx_b, project_id)

    with pytest.raises(PermissionError, match="Access denied: project"):
        await repo.search_chunks_text(ctx_b, project_id, "foo")
