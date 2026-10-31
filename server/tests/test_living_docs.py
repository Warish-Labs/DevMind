"""Unit and isolation tests for Living Documentation parser, drift detector, and repository (CAP-04, M12-03)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.analysis.doc_drift_detector import DocDriftDetector, DriftCandidate
from app.analysis.doc_parser import DocParser
from app.core.auth_context import AuthContext
from app.core.ids import generate_uuid7
from app.persistence.models.living_documentation import DocDriftItem, DocumentationRecord
from app.persistence.repositories.living_doc_repo import LivingDocRepository


@pytest.fixture
def auth_ctx() -> AuthContext:
    return AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_doc_test",
        email="doc_test@devmind.test",
        workspace_id=generate_uuid7(),
        workspace_role="admin",
        permissions=frozenset({"project:read", "project:update"}),
    )


# ---------------------------------------------------------------------------
# 1. Deterministic Markdown DocParser Tests
# ---------------------------------------------------------------------------


def test_doc_parser_markdown_sections_and_title() -> None:
    """Verify that DocParser extracts title and hierarchical sections."""
    doc_text = (
        "# DevMind API Documentation\n\n"
        "Welcome to the developer documentation for DevMind.\n\n"
        "## Authentication\n\n"
        "All requests must include a Bearer token in the `Authorization` header.\n\n"
        "### Token Verification\n\n"
        "Tokens are verified against Clerk public JWKS.\n\n"
        "## Endpoints\n\n"
        "See endpoint listing below.\n"
    )

    parsed = DocParser.parse(doc_text, path="docs/api.md")

    assert parsed.title == "DevMind API Documentation"
    assert parsed.path == "docs/api.md"
    assert len(parsed.content_hash) == 64
    assert len(parsed.sections) == 4

    sec_titles = [s.title for s in parsed.sections]
    assert "Authentication" in sec_titles
    assert "Token Verification" in sec_titles
    assert "Endpoints" in sec_titles


def test_doc_parser_routes_and_symbols_extraction() -> None:
    """Verify that DocParser extracts HTTP endpoints, code symbols, and config keys."""
    doc_text = (
        "# Integration Guide\n\n"
        "To list project bugs, send `GET /api/v1/projects/{pid}/bugs`.\n"
        "To report a bug, dispatch `POST /api/v1/projects/{pid}/bugs` with `BugRecordCreate` payload.\n\n"
        "Internally handled by `BugMemoryService` and `BugRecordRepository`.\n"
        "Ensure `DEVMIND_DATABASE_URL` is set in your environment.\n"
        "Do not use `string` or `true` as symbol names.\n"
    )

    parsed = DocParser.parse(doc_text, path="docs/guide.md")

    # Verify routes
    routes = {r.path for r in parsed.referenced_routes}
    assert "/api/v1/projects/{pid}/bugs" in routes

    # Verify code symbols (excluding stopwords like string, true)
    symbols = {s.symbol_name for s in parsed.referenced_symbols}
    assert "BugRecordCreate" in symbols
    assert "BugMemoryService" in symbols
    assert "BugRecordRepository" in symbols
    assert "string" not in symbols
    assert "true" not in symbols

    # Verify config keys
    assert "DEVMIND_DATABASE_URL" in parsed.referenced_configs

    # Verify JSON export serialization
    json_repr = parsed.to_extracted_symbols_json()
    types = {item["type"] for item in json_repr}
    assert "route" in types
    assert "symbol" in types
    assert "config" in types


# ---------------------------------------------------------------------------
# 2. Deterministic DocDriftDetector Tests
# ---------------------------------------------------------------------------


def test_doc_drift_detector_undocumented_and_removed_routes() -> None:
    """Verify detection of undocumented active routes and obsolete documented routes."""
    doc_text = (
        "# API\n\n"
        "Endpoint `GET /api/v1/projects/{pid}/bugs` lists bugs.\n"
        "Endpoint `DELETE /api/v1/legacy/obsolete-route` was deprecated.\n"
    )
    parsed = DocParser.parse(doc_text, path="README.md")

    known_routes = {
        "/api/v1/projects/{project_id}/bugs",
        "/api/v1/projects/{project_id}/new-undocumented-endpoint",
    }

    drift: list[DriftCandidate] = DocDriftDetector.detect_drift(
        parsed_docs=[parsed],
        known_routes=known_routes,
    )

    kinds = {d.kind for d in drift}
    assert "undocumented_route" in kinds
    assert "removed_route" in kinds

    # Check undocumented route details
    undoc = next(d for d in drift if d.kind == "undocumented_route")
    assert undoc.target_route_path == "/api/v1/projects/{project_id}/new-undocumented-endpoint"
    assert "is active in code but has no corresponding entry" in undoc.explanation

    # Check removed route details
    removed = next(d for d in drift if d.kind == "removed_route")
    assert removed.target_route_path == "/api/v1/legacy/obsolete-route"
    assert "was removed, renamed, or no longer exists" in removed.explanation


def test_doc_drift_detector_missing_symbols_and_stale_sections() -> None:
    """Verify detection of renamed/deleted code symbols and references to deleted files."""
    doc_text = (
        "# Architecture\n\n"
        "The system coordinates via `ValidService` and `ObsoleteLegacyManager`.\n"
        "Configuration details can be reviewed in `server/app/core/deleted_file.py`.\n"
    )
    parsed = DocParser.parse(doc_text, path="docs/arch.md")

    known_routes = set()
    known_symbols = {"ValidService", "AuthContext"}
    known_files = {"docs/arch.md", "server/app/core/settings.py"}

    drift = DocDriftDetector.detect_drift(
        parsed_docs=[parsed],
        known_routes=known_routes,
        known_symbols=known_symbols,
        known_files=known_files,
    )

    kinds = {d.kind for d in drift}
    assert "missing_symbol" in kinds
    assert "stale_section" in kinds

    missing_sym = next(d for d in drift if d.kind == "missing_symbol")
    assert missing_sym.target_symbol_key == "ObsoleteLegacyManager"

    stale_sec = next(d for d in drift if d.kind == "stale_section")
    assert stale_sec.target_symbol_key == "server/app/core/deleted_file.py"


# ---------------------------------------------------------------------------
# 3. LivingDocRepository Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_living_doc_repository_upsert_and_drift_lifecycle(auth_ctx: AuthContext) -> None:
    """Verify LivingDocRepository upsert, drift logging, status update, and tenancy scoping."""
    session = AsyncMock()
    session.add = MagicMock()
    repo = LivingDocRepository(session)

    pid = generate_uuid7()
    doc_path = "docs/overview.md"

    # Mock execute for get_by_id and list
    mock_doc = DocumentationRecord(
        id=generate_uuid7(),
        workspace_id=auth_ctx.workspace_id,
        project_id=pid,
        path=doc_path,
        title="Project Overview",
        kind="architecture",
        current_version_hash="abc123hash",
        content_snapshot="Sample content",
        extracted_symbols=[],
    )

    async def _mock_exec(stmt, *args, **kwargs):
        res = MagicMock()
        q_str = str(stmt)
        if "documentation_records" in q_str:
            res.scalar_one_or_none.return_value = mock_doc
            res.scalars.return_value.all.return_value = [mock_doc]
        elif "doc_drift_items" in q_str:
            mock_drift = DocDriftItem(
                id=generate_uuid7(),
                workspace_id=auth_ctx.workspace_id,
                project_id=pid,
                documentation_record_id=mock_doc.id,
                kind="undocumented_route",
                explanation="Route missing in docs",
                status="detected",
            )
            res.scalar_one_or_none.return_value = mock_drift
            res.scalars.return_value.all.return_value = [mock_drift]
        return res

    session.execute.side_effect = _mock_exec

    # 1. Update existing record (is_new=False)
    doc_rec, is_new = await repo.upsert_document_record(
        ctx=auth_ctx,
        workspace_id=auth_ctx.workspace_id,
        project_id=pid,
        path=doc_path,
        title="Project Overview Updated",
        kind="architecture",
        current_version_hash="def456hash",
    )
    assert is_new is False
    assert doc_rec.title == "Project Overview Updated"
    assert doc_rec.current_version_hash == "def456hash"

    # 2. Record drift item
    drift_item = await repo.record_drift_item(
        ctx=auth_ctx,
        workspace_id=auth_ctx.workspace_id,
        project_id=pid,
        documentation_record_id=mock_doc.id,
        kind="undocumented_route",
        explanation="New route missing from overview",
        target_route_path="/api/v1/test",
    )
    assert drift_item.status == "detected"
    assert drift_item.kind == "undocumented_route"

    # 3. Update drift status
    updated_drift = await repo.update_drift_status(
        ctx=auth_ctx,
        drift_id=drift_item.id,
        status="patch_proposed",
        proposal={"patch_diff": "+ Endpoint added"},
    )
    assert updated_drift is not None
    assert updated_drift.status == "patch_proposed"
    assert updated_drift.proposal == {"patch_diff": "+ Endpoint added"}

    # 4. List by project
    docs = await repo.list_documents_by_project(ctx=auth_ctx, project_id=pid)
    assert len(docs) == 1
    assert docs[0].path == doc_path
