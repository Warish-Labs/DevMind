"""Tests verifying the embedding gateway, adapter interface, deterministic fake provider, embedding spaces, and embed_chunks processing (docs/04 §10, docs/05 §5, docs/11 M5-06)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.ids import generate_uuid7
from app.domain.brain.embedding_service import EmbeddingService
from app.llm.embedding_adapter import (
    FakeEmbeddingAdapter,
    get_embedding_adapter,
)
from app.persistence.models.brain import CodeChunk, EmbeddingSpace
from app.persistence.models.project import Project
from app.persistence.repositories.brain_repo import BrainRepository


def _make_auth_ctx(workspace_id: UUID | None = None, user_id: UUID | None = None) -> AuthContext:
    return AuthContext(
        user_id=user_id or generate_uuid7(),
        clerk_user_id="user_clerk_embed_test",
        email="embed_test@example.com",
        workspace_id=workspace_id or generate_uuid7(),
        workspace_role="member",
    )


@pytest.mark.asyncio
async def test_fake_embedding_adapter_deterministic_and_normalized() -> None:
    """Verify that FakeEmbeddingAdapter produces deterministic, L2-normalized vectors."""
    adapter = FakeEmbeddingAdapter(model_id="fake-test-v1", dimension=64)
    assert adapter.provider_id == "fake"
    assert adapter.model_id == "fake-test-v1"
    assert adapter.dimension == 64

    # 1. Determinism on identical input
    res1 = await adapter.embed(["def add(a, b): return a + b"])
    res2 = await adapter.embed(["def add(a, b): return a + b"])
    assert len(res1.vectors) == 1
    assert len(res2.vectors) == 1
    assert res1.vectors[0] == res2.vectors[0]

    # 2. Vector dimension and L2 normalization
    vec = res1.vectors[0]
    assert len(vec) == 64
    magnitude_sq = sum(x * x for x in vec)
    assert abs(magnitude_sq - 1.0) < 1e-3

    # 3. Different texts yield different vectors
    res_other = await adapter.embed(["class DatabasePool: pass"])
    assert res_other.vectors[0] != vec

    # 4. Document vs query distinction
    res_query = await adapter.embed(["def add(a, b): return a + b"], input_type="query")
    assert res_query.vectors[0] != vec

    # 5. Batch processing
    batch = ["first chunk text", "second chunk text", "third chunk text"]
    batch_res = await adapter.embed(batch)
    assert len(batch_res.vectors) == 3
    assert batch_res.token_count > 0

    # 6. Empty batch short-circuit
    empty_res = await adapter.embed([])
    assert empty_res.vectors == []
    assert empty_res.token_count == 0


def test_get_embedding_adapter_factory() -> None:
    """Verify factory returns FakeEmbeddingAdapter and raises on unknown provider."""
    adapter = get_embedding_adapter(provider_id="fake", model_id="fake-v2", dimension=128)
    assert isinstance(adapter, FakeEmbeddingAdapter)
    assert adapter.dimension == 128

    with pytest.raises(ValueError, match="Unsupported embedding provider: unknown"):
        get_embedding_adapter(provider_id="unknown")


def test_embedding_space_model_instantiation() -> None:
    """Verify EmbeddingSpace model attributes and defaults."""
    space = EmbeddingSpace(
        provider_id="fake",
        model_id="fake-embed-v1",
        dimension=64,
        status="active",
        config_hash="sha256:cfg123",
    )
    assert space.provider_id == "fake"
    assert space.model_id == "fake-embed-v1"
    assert space.dimension == 64
    assert space.status == "active"
    assert space.config_hash == "sha256:cfg123"


@pytest.mark.asyncio
async def test_brain_repo_embedding_spaces() -> None:
    """Verify BrainRepository methods for creating, retrieving, and activating embedding spaces."""
    session = AsyncMock(spec=AsyncSession)
    repo = BrainRepository(session)
    sys_ctx = SystemContext(reason="test embedding spaces")

    # 1. Create space
    space = await repo.create_embedding_space(
        ctx=sys_ctx,
        provider_id="fake",
        model_id="fake-embed-v1",
        dimension=64,
        status="building",
        config_hash="sha256:initial",
    )
    assert space.provider_id == "fake"
    assert space.status == "building"
    session.add.assert_called_once()
    session.flush.assert_awaited()

    # 2. Get active space
    mock_active = EmbeddingSpace(
        provider_id="fake",
        model_id="fake-embed-v1",
        dimension=64,
        status="active",
        config_hash="sha256:act",
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_active
    session.execute.return_value = mock_result

    active = await repo.get_active_embedding_space(sys_ctx)
    assert active is not None
    assert active.status == "active"

    # 3. Set active space
    space_id = generate_uuid7()
    activated_space = EmbeddingSpace(
        id=space_id,
        provider_id="fake",
        model_id="fake-embed-v2",
        dimension=128,
        status="active",
        config_hash="sha256:new",
    )
    mock_result_act = MagicMock()
    mock_result_act.scalars.return_value.first.return_value = activated_space
    session.execute.return_value = mock_result_act

    res_act = await repo.set_active_embedding_space(sys_ctx, space_id)
    assert res_act.id == space_id
    assert res_act.status == "active"


@pytest.mark.asyncio
async def test_embedding_service_process_embed_chunks() -> None:
    """Verify EmbeddingService processes un-embedded chunks and returns statistics."""
    session = AsyncMock(spec=AsyncSession)
    service = EmbeddingService(session)

    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id)

    mock_project = Project(id=project_id, workspace_id=workspace_id)
    service.repo._verify_project_access = AsyncMock(return_value=mock_project)  # type: ignore[method-assign]

    space = EmbeddingSpace(
        id=generate_uuid7(),
        provider_id="fake",
        model_id="fake-embed-v1",
        dimension=64,
        status="active",
        config_hash="sha256:space",
    )
    service.repo.get_active_embedding_space = AsyncMock(return_value=space)  # type: ignore[method-assign]

    chunk1 = CodeChunk(
        id=generate_uuid7(),
        workspace_id=workspace_id,
        project_id=project_id,
        file_version_id=generate_uuid7(),
        kind="function",
        start_line=1,
        end_line=10,
        content="def hello(): return 'world'",
        content_hash="sha256:h1",
        search_text="def hello(): return 'world'",
        token_estimate=6,
    )
    chunk2 = CodeChunk(
        id=generate_uuid7(),
        workspace_id=workspace_id,
        project_id=project_id,
        file_version_id=generate_uuid7(),
        kind="class",
        start_line=12,
        end_line=30,
        content="class Greeter: pass",
        content_hash="sha256:h2",
        search_text="class Greeter: pass",
        token_estimate=5,
    )
    service.repo.get_unembedded_chunks = AsyncMock(return_value=[chunk1, chunk2])  # type: ignore[method-assign]
    service.repo.save_chunk_embeddings = AsyncMock(return_value=2)  # type: ignore[method-assign]

    result = await service.process_embed_chunks(
        ctx=ctx,
        project_id=project_id,
        batch_size=50,
    )

    assert result["status"] == "completed"
    assert result["chunks_embedded"] == 2
    assert result["dimension"] == 64
    assert result["token_estimate"] > 0
    service.repo.save_chunk_embeddings.assert_awaited_once()


@pytest.mark.asyncio
async def test_embedding_service_zero_chunks() -> None:
    """Verify EmbeddingService gracefully handles projects with no un-embedded chunks."""
    session = AsyncMock(spec=AsyncSession)
    service = EmbeddingService(session)

    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id)

    mock_project = Project(id=project_id, workspace_id=workspace_id)
    service.repo._verify_project_access = AsyncMock(return_value=mock_project)  # type: ignore[method-assign]

    space = EmbeddingSpace(
        id=generate_uuid7(),
        provider_id="fake",
        model_id="fake-embed-v1",
        dimension=64,
        status="active",
        config_hash="sha256:space",
    )
    service.repo.get_active_embedding_space = AsyncMock(return_value=space)  # type: ignore[method-assign]
    service.repo.get_unembedded_chunks = AsyncMock(return_value=[])  # type: ignore[method-assign]

    result = await service.process_embed_chunks(
        ctx=ctx,
        project_id=project_id,
    )

    assert result["status"] == "completed"
    assert result["chunks_embedded"] == 0
    assert result["token_estimate"] == 0


@pytest.mark.asyncio
async def test_cross_tenant_isolation_on_embedding_service() -> None:
    """Verify that attempting to embed chunks across tenant boundaries raises PermissionError."""
    session = AsyncMock(spec=AsyncSession)
    service = EmbeddingService(session)

    tenant_b_ws = generate_uuid7()
    project_id = generate_uuid7()
    ctx_b = _make_auth_ctx(workspace_id=tenant_b_ws)

    # When looking up project for tenant B, access denied
    mock_exec_res = MagicMock()
    mock_exec_res.scalars.return_value.first.return_value = None
    session.execute.return_value = mock_exec_res

    with pytest.raises(PermissionError, match="Access denied: project"):
        await service.process_embed_chunks(ctx=ctx_b, project_id=project_id)
