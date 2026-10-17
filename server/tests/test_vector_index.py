"""Tests verifying pgvector integration, PGVector type, ChunkEmbedding model, HNSW index query generation, and tenant isolation (docs/03 §3.2, docs/04 §9, docs/11 M5-07)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext
from app.core.ids import generate_uuid7
from app.persistence.models.brain import ChunkEmbedding, CodeChunk
from app.persistence.models.project import Project
from app.persistence.models.vector import PGVector
from app.persistence.repositories.brain_repo import BrainRepository


def _make_auth_ctx(workspace_id: UUID | None = None, user_id: UUID | None = None) -> AuthContext:
    return AuthContext(
        user_id=user_id or generate_uuid7(),
        clerk_user_id="user_clerk_vector_test",
        email="vector_test@example.com",
        workspace_id=workspace_id or generate_uuid7(),
        workspace_role="member",
    )


def test_pgvector_type_serialization_and_deserialization() -> None:
    """Verify PGVector bind and result processors handle float arrays and string representations."""
    vector_type = PGVector(dim=64)
    assert vector_type.get_col_spec() == "vector(64)"

    bind_proc = vector_type.bind_processor(None)
    result_proc = vector_type.result_processor(None, None)

    # 1. Serialization (bind)
    assert bind_proc([0.1, 0.2, -0.3]) == "[0.1,0.2,-0.3]"
    assert bind_proc((1.0, 2.0)) == "[1.0,2.0]"
    assert bind_proc(None) is None

    # 2. Deserialization (result)
    parsed = result_proc("[0.1, 0.2, -0.3]")
    assert parsed == [0.1, 0.2, -0.3]
    assert result_proc(None) is None
    assert result_proc("[]") == []
    assert result_proc([0.5, 0.5]) == [0.5, 0.5]


def test_chunk_embedding_model_instantiation() -> None:
    """Verify ChunkEmbedding model attributes and composite PK."""
    chunk_id = generate_uuid7()
    space_id = generate_uuid7()
    project_id = generate_uuid7()
    vec = [0.1] * 64

    emb = ChunkEmbedding(
        chunk_id=chunk_id,
        space_id=space_id,
        project_id=project_id,
        embedding=vec,
    )
    assert emb.chunk_id == chunk_id
    assert emb.space_id == space_id
    assert emb.project_id == project_id
    assert len(emb.embedding) == 64


@pytest.mark.asyncio
async def test_brain_repo_save_chunk_embeddings() -> None:
    """Verify save_chunk_embeddings persists vectors and returns count."""
    session = AsyncMock(spec=AsyncSession)
    repo = BrainRepository(session)

    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    space_id = generate_uuid7()
    c1 = generate_uuid7()
    c2 = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id)

    mock_project = Project(id=project_id, workspace_id=workspace_id)
    repo._verify_project_access = AsyncMock(return_value=mock_project)  # type: ignore[method-assign]

    data = [(c1, [0.1] * 64), (c2, [0.2] * 64)]
    count = await repo.save_chunk_embeddings(ctx, project_id, space_id, data)

    assert count == 2
    assert session.add.call_count == 2
    session.flush.assert_awaited_once()

    # Empty data short-circuits
    empty_count = await repo.save_chunk_embeddings(ctx, project_id, space_id, [])
    assert empty_count == 0


@pytest.mark.asyncio
async def test_brain_repo_search_chunks_vector() -> None:
    """Verify search_chunks_vector executes cosine distance query and returns (chunk, similarity)."""
    session = AsyncMock(spec=AsyncSession)
    repo = BrainRepository(session)

    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    space_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id)

    mock_project = Project(id=project_id, workspace_id=workspace_id)
    repo._verify_project_access = AsyncMock(return_value=mock_project)  # type: ignore[method-assign]

    # Empty query vector short-circuit
    res_empty = await repo.search_chunks_vector(ctx, project_id, space_id, [])
    assert res_empty == []

    # Valid search
    mock_chunk = CodeChunk(
        id=generate_uuid7(),
        workspace_id=workspace_id,
        project_id=project_id,
        file_version_id=generate_uuid7(),
        kind="function",
        start_line=1,
        end_line=20,
        content="fn",
        content_hash="sha256:fn",
        search_text="fn",
        token_estimate=5,
    )
    # distance = 0.15 -> similarity = 1.0 - 0.15 = 0.85
    mock_result = MagicMock()
    mock_result.all.return_value = [(mock_chunk, 0.15)]
    session.execute.return_value = mock_result

    results = await repo.search_chunks_vector(
        ctx, project_id, space_id, [0.1] * 64, limit=10, is_current=True
    )
    assert len(results) == 1
    chunk, similarity = results[0]
    assert chunk.id == mock_chunk.id
    assert similarity == 0.85


@pytest.mark.asyncio
async def test_brain_repo_get_unembedded_chunks_filters_existing_embeddings() -> None:
    """Verify get_unembedded_chunks issues outer join filtering chunks with existing embeddings."""
    session = AsyncMock(spec=AsyncSession)
    repo = BrainRepository(session)

    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    space_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id)

    mock_project = Project(id=project_id, workspace_id=workspace_id)
    repo._verify_project_access = AsyncMock(return_value=mock_project)  # type: ignore[method-assign]

    mock_chunk = CodeChunk(
        id=generate_uuid7(),
        workspace_id=workspace_id,
        project_id=project_id,
        file_version_id=generate_uuid7(),
        kind="function",
        start_line=1,
        end_line=10,
        content="code",
        content_hash="sha256:code",
        search_text="code",
        token_estimate=2,
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_chunk]
    session.execute.return_value = mock_result

    unembedded = await repo.get_unembedded_chunks(ctx, project_id, space_id, limit=50)
    assert len(unembedded) == 1
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_cross_tenant_vector_operations_rejected() -> None:
    """Verify vector save and search reject callers from another workspace."""
    session = AsyncMock(spec=AsyncSession)
    repo = BrainRepository(session)

    tenant_b_ws = generate_uuid7()
    project_id = generate_uuid7()
    space_id = generate_uuid7()
    ctx_b = _make_auth_ctx(workspace_id=tenant_b_ws)

    mock_exec_res = MagicMock()
    mock_exec_res.scalars.return_value.first.return_value = None
    session.execute.return_value = mock_exec_res

    with pytest.raises(PermissionError, match="Access denied: project"):
        await repo.save_chunk_embeddings(
            ctx_b, project_id, space_id, [(generate_uuid7(), [0.1] * 64)]
        )

    with pytest.raises(PermissionError, match="Access denied: project"):
        await repo.search_chunks_vector(ctx_b, project_id, space_id, [0.1] * 64)
