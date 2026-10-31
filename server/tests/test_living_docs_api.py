"""REST API tests for Living Documentation endpoints, DocsAlive drift detection, and approval gates (docs/01 CAP-04, docs/03 §3.4, §11.2)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth_context import AuthContext
from app.core.ids import generate_uuid7
from app.core.settings import Settings
from app.domain.auth import get_auth_context, get_db_session
from app.main import create_app
from app.persistence.models.living_documentation import DocDriftItem, DocumentationRecord
from app.persistence.models.project import Project


@pytest.fixture
def api_settings() -> Settings:
    return Settings(
        env="test",
        github_client_id="test_github_client_id",
        github_client_secret="test_github_client_secret",
        encryption_keys=["c3VwZXJfc2VjcmV0X2tleV9mb3JfdGVzdF8zMmJ5dGVzIQ=="],
    )


@pytest.mark.asyncio
async def test_api_list_and_register_docs(api_settings: Settings) -> None:
    """Verify listing documentation records and registering a new Markdown file."""
    app = create_app(settings=api_settings)

    wid = generate_uuid7()
    pid = generate_uuid7()
    user_id = generate_uuid7()
    doc_id = generate_uuid7()

    mock_project = Project(
        id=pid,
        workspace_id=wid,
        name="Docs Project",
        slug="docs-proj",
    )

    doc_content = "# API Docs\n\n### `GET /api/v1/health`\nHealth check.\n"
    content_hash = hashlib.sha256(doc_content.encode("utf-8")).hexdigest()
    now = datetime.now(UTC)

    mock_doc = DocumentationRecord(
        id=doc_id,
        workspace_id=wid,
        project_id=pid,
        path="docs/api.md",
        title="API Docs",
        kind="api",
        current_version_hash=content_hash,
        content_snapshot=doc_content,
        extracted_symbols=[{"kind": "route", "method": "GET", "path": "/api/v1/health", "line": 3}],
        created_at=now,
        updated_at=now,
    )
    mock_doc.drift_items = []

    mock_session = AsyncMock()

    def _mock_exec(query):
        res = MagicMock()
        q_str = str(query)
        if "projects" in q_str:
            res.scalar_one_or_none.return_value = mock_project
            res.scalars.return_value.all.return_value = [mock_project]
            res.scalars.return_value.first.return_value = mock_project
        elif "documentation_records" in q_str:
            res.scalar_one_or_none.return_value = mock_doc
            res.scalars.return_value.all.return_value = [mock_doc]
            res.scalars.return_value.first.return_value = mock_doc
        return res

    mock_session.execute.side_effect = _mock_exec

    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        user_id=user_id,
        clerk_user_id="user_test_client",
        email="client@example.com",
        workspace_id=wid,
        project_id=pid,
        project_role="maintainer",
        permissions=frozenset(
            {"project:read", "project:update", "analysis:create", "authenticated"}
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. List docs
        res = await client.get(f"/api/v1/projects/{pid}/docs")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["path"] == "docs/api.md"
        assert data[0]["title"] == "API Docs"

        # 2. Register / update doc
        post_payload = {
            "path": "docs/architecture.md",
            "title": "Architecture Overview",
            "kind": "architecture",
            "content": "# Architecture\n\nDefines `UserService` and `AuthContext`.",
        }
        res_post = await client.post(
            f"/api/v1/projects/{pid}/docs",
            json=post_payload,
        )
        assert res_post.status_code == 201
        assert "Location" in res_post.headers


@pytest.mark.asyncio
async def test_api_get_doc_detail(api_settings: Settings) -> None:
    """Verify getting single documentation record details including extracted symbols."""
    app = create_app(settings=api_settings)

    wid = generate_uuid7()
    pid = generate_uuid7()
    doc_id = generate_uuid7()

    mock_project = Project(id=pid, workspace_id=wid, name="Test", slug="test")
    mock_doc = DocumentationRecord(
        id=doc_id,
        workspace_id=wid,
        project_id=pid,
        path="README.md",
        title="Project Readme",
        kind="readme",
        current_version_hash="12345hash",
        content_snapshot="# DevMind\n",
        extracted_symbols=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    mock_doc.drift_items = []

    mock_session = AsyncMock()

    def _mock_exec(query):
        res = MagicMock()
        q_str = str(query)
        if "projects" in q_str:
            res.scalar_one_or_none.return_value = mock_project
            res.scalars.return_value.all.return_value = [mock_project]
            res.scalars.return_value.first.return_value = mock_project
        elif "documentation_records" in q_str:
            res.scalar_one_or_none.return_value = mock_doc
            res.scalars.return_value.all.return_value = [mock_doc]
            res.scalars.return_value.first.return_value = mock_doc
        return res

    mock_session.execute.side_effect = _mock_exec
    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_test",
        email="test@devmind.test",
        workspace_id=wid,
        project_id=pid,
        project_role="viewer",
        permissions=frozenset({"project:read", "authenticated"}),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/api/v1/projects/{pid}/docs/{doc_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == str(doc_id)
        assert data["path"] == "README.md"
        assert data["content_snapshot"] == "# DevMind\n"


@pytest.mark.asyncio
async def test_api_detect_drift_and_list_drift_items(api_settings: Settings) -> None:
    """Verify triggering drift detection and listing drift items with status filters."""
    app = create_app(settings=api_settings)

    wid = generate_uuid7()
    pid = generate_uuid7()
    doc_id = generate_uuid7()
    drift_id = generate_uuid7()

    mock_project = Project(id=pid, workspace_id=wid, name="Drift Proj", slug="drift-proj")
    mock_doc = DocumentationRecord(
        id=doc_id,
        workspace_id=wid,
        project_id=pid,
        path="docs/api.md",
        title="API Reference",
        kind="api",
        current_version_hash="dochash",
        content_snapshot="# API\n",
        extracted_symbols=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    mock_doc.drift_items = []

    mock_drift = DocDriftItem(
        id=drift_id,
        workspace_id=wid,
        project_id=pid,
        documentation_record_id=doc_id,
        kind="undocumented_route",
        target_route_path="POST /api/v1/bugs",
        explanation="Route is active in code but missing from documentation.",
        status="detected",
        proposal={
            "summary": "Document POST /api/v1/bugs",
            "diff_content": "--- a/docs/api.md\n+++ b/docs/api.md\n",
            "proposed_content": "### `POST /api/v1/bugs`",
            "gated": True,
        },
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    mock_drift.documentation_record = mock_doc

    mock_session = AsyncMock()

    def _mock_exec(query):
        res = MagicMock()
        q_str = str(query)
        if "projects" in q_str:
            res.scalar_one_or_none.return_value = mock_project
            res.scalars.return_value.all.return_value = [mock_project]
            res.scalars.return_value.first.return_value = mock_project
        elif "documentation_records" in q_str:
            res.scalar_one_or_none.return_value = mock_doc
            res.scalars.return_value.all.return_value = [mock_doc]
            res.scalars.return_value.first.return_value = mock_doc
        elif "doc_drift_items" in q_str:
            res.scalar_one_or_none.return_value = mock_drift
            res.scalars.return_value.all.return_value = [mock_drift]
            res.scalars.return_value.first.return_value = mock_drift
        return res

    mock_session.execute.side_effect = _mock_exec
    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_test",
        email="test@devmind.test",
        workspace_id=wid,
        project_id=pid,
        project_role="maintainer",
        permissions=frozenset({"project:read", "analysis:create", "authenticated"}),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Trigger drift detection
        drift_req = {
            "known_routes": ["POST /api/v1/bugs", "GET /api/v1/health"],
            "known_symbols": ["BugMemoryService"],
        }
        res_detect = await client.post(
            f"/api/v1/projects/{pid}/docs/detect-drift",
            json=drift_req,
        )
        assert res_detect.status_code == 200
        detect_data = res_detect.json()
        assert detect_data["project_id"] == str(pid)

        # 2. List drift items
        res_list = await client.get(f"/api/v1/projects/{pid}/docs/drift?status=detected")
        assert res_list.status_code == 200, res_list.text
        items = res_list.json()
        assert len(items) == 1
        assert items[0]["kind"] == "undocumented_route"
        assert items[0]["target_route_path"] == "POST /api/v1/bugs"


@pytest.mark.asyncio
async def test_api_approval_gate_lifecycle(api_settings: Settings) -> None:
    """Verify approval, rejection, and gated application lifecycle endpoints."""
    app = create_app(settings=api_settings)

    wid = generate_uuid7()
    pid = generate_uuid7()
    doc_id = generate_uuid7()
    drift_id = generate_uuid7()

    mock_project = Project(id=pid, workspace_id=wid, name="Gate Proj", slug="gate-proj")
    mock_doc = DocumentationRecord(
        id=doc_id,
        workspace_id=wid,
        project_id=pid,
        path="docs/api.md",
        title="API Reference",
        kind="api",
        current_version_hash="dochash1",
        content_snapshot="# API\n",
        extracted_symbols=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_drift = DocDriftItem(
        id=drift_id,
        workspace_id=wid,
        project_id=pid,
        documentation_record_id=doc_id,
        kind="undocumented_route",
        target_route_path="POST /api/v1/bugs",
        explanation="Missing doc",
        status="detected",
        proposal={
            "summary": "Document endpoint",
            "diff_content": "--- a/docs/api.md\n+++ b/docs/api.md\n",
            "proposed_content": "### POST /api/v1/bugs",
            "gated": True,
        },
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    mock_drift.documentation_record = mock_doc

    mock_session = AsyncMock()

    def _mock_exec(query):
        res = MagicMock()
        q_str = str(query)
        if "projects" in q_str:
            res.scalar_one_or_none.return_value = mock_project
            res.scalars.return_value.all.return_value = [mock_project]
            res.scalars.return_value.first.return_value = mock_project
        elif "documentation_records" in q_str:
            res.scalar_one_or_none.return_value = mock_doc
            res.scalars.return_value.all.return_value = [mock_doc]
            res.scalars.return_value.first.return_value = mock_doc
        elif "doc_drift_items" in q_str:
            res.scalar_one_or_none.return_value = mock_drift
            res.scalars.return_value.all.return_value = [mock_drift]
            res.scalars.return_value.first.return_value = mock_drift
        return res

    mock_session.execute.side_effect = _mock_exec
    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_maintainer",
        email="maintainer@devmind.test",
        workspace_id=wid,
        project_id=pid,
        project_role="maintainer",
        permissions=frozenset({"project:read", "project:update", "authenticated"}),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Applying before approval must fail with 409
        res_apply_fail = await client.post(f"/api/v1/docs/drift/{drift_id}/apply")
        assert res_apply_fail.status_code == 409
        err = res_apply_fail.json()
        assert err["code"] == "doc_drift.not_approved"

        # 2. Approve proposal
        res_approve = await client.post(
            f"/api/v1/docs/drift/{drift_id}/approve",
            json={"reason": "Approved by engineering lead"},
        )
        assert res_approve.status_code == 200
        approve_data = res_approve.json()
        assert approve_data["status"] == "approved"

        # Now update mock drift status to approved
        mock_drift.status = "approved"

        # 3. Applying after approval succeeds
        res_apply = await client.post(f"/api/v1/docs/drift/{drift_id}/apply")
        assert res_apply.status_code == 200
        apply_data = res_apply.json()
        assert apply_data["status"] == "applied"
        assert "successfully applied" in apply_data["message"]


@pytest.mark.asyncio
async def test_api_cross_workspace_isolation(api_settings: Settings) -> None:
    """Verify tenant isolation: caller in Workspace B cannot access docs or drift in Workspace A."""
    app = create_app(settings=api_settings)

    wid_b = generate_uuid7()
    pid_a = generate_uuid7()
    doc_id_a = generate_uuid7()
    drift_id_a = generate_uuid7()

    mock_session = AsyncMock()

    def _mock_exec(query):
        # Query scoped by workspace B will return None for workspace A resources
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        res.scalars.return_value.all.return_value = []
        res.scalars.return_value.first.return_value = None
        return res

    mock_session.execute.side_effect = _mock_exec
    app.dependency_overrides[get_db_session] = lambda: mock_session
    # Caller belongs to workspace B
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_workspace_b",
        email="b@example.com",
        workspace_id=wid_b,
        workspace_role="admin",
        permissions=frozenset({"project:read", "project:update", "authenticated"}),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Cannot access workspace A project docs -> 404
        res = await client.get(f"/api/v1/projects/{pid_a}/docs")
        assert res.status_code == 404

        # Cannot get workspace A doc detail -> 404
        res_doc = await client.get(f"/api/v1/projects/{pid_a}/docs/{doc_id_a}")
        assert res_doc.status_code == 404

        # Cannot access workspace A drift item -> 404
        res_drift = await client.get(f"/api/v1/docs/drift/{drift_id_a}")
        assert res_drift.status_code == 404
