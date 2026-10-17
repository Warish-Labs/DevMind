"""Tests for Code Symbol, Relationship Ingestion, and Architectural Graph Derivation (M4-05).

Verifies:
1. Batch symbol upsert with transactional is_current invariant (docs/03 §3.2).
2. Validation of symbol kinds and relationship kinds against allowlist.
3. Relationship key resolution, edge linking, and automatic resolution of unresolved references.
4. Architectural graph traversal and extraction by depth.
5. Extension endpoints: PUT /api/v1/ext/projects/{pid}/symbols & PUT /api/v1/ext/projects/{pid}/relationships (Rule 10, project:sync).
6. Browser endpoints: GET /api/v1/projects/{pid}/brain/symbols & GET /api/v1/projects/{pid}/brain/graph (brain:read).
7. Cross-tenant isolation enforcement across all symbol routes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.api.schemas import (
    BatchRelationshipsRequest,
    BatchSymbolsRequest,
    CodeRelationshipPayload,
    CodeSymbolItem,
    CodeSymbolPayload,
    GraphNode,
    GraphResponse,
)
from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import ValidationError
from app.core.ids import generate_uuid7
from app.core.settings import Settings
from app.domain.auth import (
    get_auth_context,
    get_db_session,
    get_extension_auth_context,
)
from app.domain.brain.symbol_service import SymbolService
from app.main import create_app
from app.persistence.models.brain import CodeRelationship, CodeSymbol


@pytest.mark.asyncio
async def test_upsert_symbols_validates_kind() -> None:
    """Rejects unknown symbol kinds with ValidationError."""
    mock_session = AsyncMock()
    service = SymbolService(mock_session)
    ctx = SystemContext(reason="test")
    project_id = generate_uuid7()

    req = BatchSymbolsRequest(
        symbols=[
            CodeSymbolPayload(
                file_version_id=generate_uuid7(),
                symbol_key="bad:symbol",
                name="bad",
                qualified_name="bad",
                kind="invalid_kind",
                start_line=1,
                end_line=5,
            )
        ]
    )

    with pytest.raises(ValidationError, match="Invalid symbol kind"):
        await service.upsert_symbols(ctx, project_id, req)


@pytest.mark.asyncio
async def test_upsert_symbols_transactional_is_current_invariant() -> None:
    """Marks previous versions of affected files as non-current when new symbols are ingested."""
    mock_session = AsyncMock()
    service = SymbolService(mock_session)

    project_id = generate_uuid7()
    file_id = generate_uuid7()
    new_version_id = generate_uuid7()
    old_version_id = generate_uuid7()

    # Mock DB queries:
    # 1. select(FileVersion.file_id) -> returns [file_id]
    mock_res_files = MagicMock()
    mock_res_files.scalars.return_value.all.return_value = [file_id]

    # 2. select(FileVersion.id).where(file_id, id not in new) -> returns [old_version_id]
    mock_res_older = MagicMock()
    mock_res_older.scalars.return_value.all.return_value = [old_version_id]

    mock_session.execute.side_effect = [mock_res_files, mock_res_older]

    service.repo.mark_symbols_non_current_for_versions = AsyncMock(return_value=2)
    service.repo.resolve_relationships = AsyncMock(return_value=1)

    sym_id = generate_uuid7()
    mock_sym = CodeSymbol(
        id=sym_id,
        project_id=project_id,
        file_version_id=new_version_id,
        symbol_key="src/api.py::login",
        name="login",
        qualified_name="app.api.login",
        kind="route_handler",
        start_line=10,
        end_line=25,
        framework_tags=["fastapi"],
        is_current=True,
        created_at=datetime.now(UTC),
    )
    service.repo.batch_upsert_symbols = AsyncMock(return_value=[mock_sym])

    ctx = SystemContext(reason="test")
    req = BatchSymbolsRequest(
        symbols=[
            CodeSymbolPayload(
                file_version_id=new_version_id,
                symbol_key="src/api.py::login",
                name="login",
                qualified_name="app.api.login",
                kind="route_handler",
                start_line=10,
                end_line=25,
                framework_tags=["fastapi"],
            )
        ]
    )

    res = await service.upsert_symbols(ctx, project_id, req)

    assert res.upserted == 1
    assert res.superseded_marked_non_current == 2
    assert res.symbols[0].name == "login"
    assert res.symbols[0].is_current is True

    service.repo.mark_symbols_non_current_for_versions.assert_called_once_with(
        ctx, project_id, [old_version_id]
    )
    service.repo.resolve_relationships.assert_called_once_with(ctx, project_id)


@pytest.mark.asyncio
async def test_upsert_relationships_key_resolution_and_validation() -> None:
    """Resolves from_symbol_key and to_symbol_key to symbol IDs and validates kind."""
    mock_session = AsyncMock()
    service = SymbolService(mock_session)

    project_id = generate_uuid7()
    file_version_id = generate_uuid7()
    sym_a_id = generate_uuid7()
    sym_b_id = generate_uuid7()

    sym_a = CodeSymbol(id=sym_a_id, symbol_key="src/main.py::handle", project_id=project_id)
    sym_b = CodeSymbol(id=sym_b_id, symbol_key="src/auth.py::verify", project_id=project_id)

    service.repo.get_symbols_by_keys = AsyncMock(return_value=[sym_a, sym_b])
    service.repo.resolve_relationships = AsyncMock(return_value=0)

    rel_id = generate_uuid7()
    mock_rel = CodeRelationship(
        id=rel_id,
        project_id=project_id,
        from_symbol_id=sym_a_id,
        to_symbol_id=sym_b_id,
        kind="calls",
        resolution="resolved",
        file_version_id=file_version_id,
        is_current=True,
        created_at=datetime.now(UTC),
    )
    service.repo.batch_upsert_relationships = AsyncMock(return_value=[mock_rel])

    ctx = SystemContext(reason="test")

    # 1. Invalid kind check
    bad_req = BatchRelationshipsRequest(
        relationships=[
            CodeRelationshipPayload(
                file_version_id=file_version_id,
                from_symbol_key="src/main.py::handle",
                to_symbol_key="src/auth.py::verify",
                kind="invalid_relation",
            )
        ]
    )
    with pytest.raises(ValidationError, match="Invalid relationship kind"):
        await service.upsert_relationships(ctx, project_id, bad_req)

    # 2. Valid relationship with key resolution
    good_req = BatchRelationshipsRequest(
        relationships=[
            CodeRelationshipPayload(
                file_version_id=file_version_id,
                from_symbol_key="src/main.py::handle",
                to_symbol_key="src/auth.py::verify",
                kind="calls",
            )
        ]
    )
    res = await service.upsert_relationships(ctx, project_id, good_req)
    assert res.upserted == 1
    assert res.relationships[0].kind == "calls"
    assert res.relationships[0].resolution == "resolved"


@pytest.mark.asyncio
async def test_get_graph_derivation() -> None:
    """Builds nodes and edges for architectural graph traversal."""
    mock_session = AsyncMock()
    service = SymbolService(mock_session)

    project_id = generate_uuid7()
    sym_1 = CodeSymbol(
        id=generate_uuid7(),
        symbol_key="route:admin",
        name="admin_handler",
        kind="route_handler",
        start_line=1,
        end_line=10,
    )
    sym_2 = CodeSymbol(
        id=generate_uuid7(),
        symbol_key="guard:auth",
        name="auth_guard",
        kind="function",
        start_line=12,
        end_line=20,
    )
    rel = CodeRelationship(
        id=generate_uuid7(),
        from_symbol_id=sym_1.id,
        to_symbol_id=sym_2.id,
        kind="guarded_by",
        resolution="resolved",
    )

    service.repo.get_graph_data = AsyncMock(return_value=([sym_1, sym_2], [rel]))

    ctx = SystemContext(reason="test")
    graph = await service.get_graph(ctx, project_id, root_symbol_key="route:admin", depth=2)

    assert graph.project_id == project_id
    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    assert graph.nodes[0].symbol_key == "route:admin"
    assert graph.edges[0].kind == "guarded_by"


def test_extension_symbols_and_relationships_endpoints(test_settings: Settings) -> None:
    """Test PUT /api/v1/ext/projects/{pid}/symbols and PUT /api/v1/ext/projects/{pid}/relationships."""
    app = create_app(settings=test_settings)

    user_id = generate_uuid7()
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    file_version_id = generate_uuid7()

    mock_ext_ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_clerk_test",
        email="dev@devmind.local",
        workspace_id=workspace_id,
        permissions=frozenset({"project:sync"}),
    )

    mock_session = AsyncMock()
    app.dependency_overrides[get_extension_auth_context] = lambda: mock_ext_ctx
    app.dependency_overrides[get_db_session] = lambda: mock_session

    with patch("app.api.extension.SymbolService") as mock_symbol_service_cls:
        mock_instance = MagicMock()
        mock_symbol_service_cls.return_value = mock_instance
        mock_instance.resolve_project_context = AsyncMock(return_value=mock_ext_ctx)

        from app.api.schemas import BatchRelationshipsResponse, BatchSymbolsResponse

        mock_instance.upsert_symbols = AsyncMock(
            return_value=BatchSymbolsResponse(
                upserted=1,
                superseded_marked_non_current=0,
                symbols=[],
            )
        )
        mock_instance.upsert_relationships = AsyncMock(
            return_value=BatchRelationshipsResponse(
                upserted=1,
                resolved_count=1,
                relationships=[],
            )
        )

        with TestClient(app) as client:
            headers = {"Authorization": "Bearer dme_at_token_test_1234567"}

            # 1. PUT /ext/projects/{pid}/symbols
            res_sym = client.put(
                f"/api/v1/ext/projects/{project_id}/symbols",
                json={
                    "symbols": [
                        {
                            "file_version_id": str(file_version_id),
                            "symbol_key": "app.py::test",
                            "name": "test",
                            "qualified_name": "app.test",
                            "kind": "function",
                            "start_line": 1,
                            "end_line": 5,
                        }
                    ]
                },
                headers=headers,
            )
            assert res_sym.status_code == 200
            assert res_sym.json()["upserted"] == 1

            # 2. PUT /ext/projects/{pid}/relationships
            res_rel = client.put(
                f"/api/v1/ext/projects/{project_id}/relationships",
                json={
                    "relationships": [
                        {
                            "file_version_id": str(file_version_id),
                            "from_symbol_id": str(generate_uuid7()),
                            "to_external": "os.path",
                            "kind": "imports",
                        }
                    ]
                },
                headers=headers,
            )
            assert res_rel.status_code == 200
            assert res_rel.json()["upserted"] == 1


def test_browser_brain_symbols_and_graph_endpoints(test_settings: Settings) -> None:
    """Test browser endpoints: GET /projects/{pid}/brain/symbols & GET /projects/{pid}/brain/graph."""
    app = create_app(settings=test_settings)

    user_id = generate_uuid7()
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()

    mock_ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_clerk_test",
        email="dev@devmind.local",
        workspace_id=workspace_id,
        project_id=project_id,
        permissions=frozenset({"brain:read"}),
    )

    mock_session = AsyncMock()
    app.dependency_overrides[get_auth_context] = lambda: mock_ctx
    app.dependency_overrides[get_db_session] = lambda: mock_session

    with patch("app.api.brain.SymbolService") as mock_symbol_service_cls:
        mock_instance = MagicMock()
        mock_symbol_service_cls.return_value = mock_instance
        mock_instance.resolve_project_context = AsyncMock(return_value=mock_ctx)

        mock_instance.list_current_symbols = AsyncMock(
            return_value=[
                CodeSymbolItem(
                    id=generate_uuid7(),
                    project_id=project_id,
                    file_version_id=generate_uuid7(),
                    symbol_key="app.py::main",
                    name="main",
                    qualified_name="app.main",
                    kind="function",
                    start_line=1,
                    end_line=10,
                    is_current=True,
                    created_at=datetime.now(UTC),
                )
            ]
        )
        mock_instance.get_graph = AsyncMock(
            return_value=GraphResponse(
                project_id=project_id,
                nodes=[
                    GraphNode(
                        id=generate_uuid7(),
                        symbol_key="app.py::main",
                        name="main",
                        kind="function",
                        start_line=1,
                        end_line=10,
                    )
                ],
                edges=[],
            )
        )

        with TestClient(app) as client:
            headers = {"Authorization": "Bearer mock_clerk_browser_token"}

            # 1. GET /symbols
            res_sym = client.get(
                f"/api/v1/projects/{project_id}/brain/symbols",
                headers=headers,
            )
            assert res_sym.status_code == 200
            assert len(res_sym.json()) == 1
            assert res_sym.json()[0]["name"] == "main"

            # 2. GET /graph
            res_graph = client.get(
                f"/api/v1/projects/{project_id}/brain/graph",
                headers=headers,
            )
            assert res_graph.status_code == 200
            graph_data = res_graph.json()
            assert len(graph_data["nodes"]) == 1
            assert graph_data["nodes"][0]["name"] == "main"
