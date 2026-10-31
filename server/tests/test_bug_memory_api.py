"""REST API tests for Bug Memory endpoints and multi-tenant isolation (docs/01 CAP-03, docs/03 §3.4, §11.1)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.analysis.error_normalizer import ErrorNormalizer
from app.core.auth_context import AuthContext
from app.core.ids import generate_uuid7
from app.core.settings import Settings
from app.domain.auth import get_auth_context, get_db_session
from app.main import create_app
from app.persistence.models.bug_memory import BugRecord, BugResolution
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
async def test_api_list_and_create_bug_record(api_settings: Settings) -> None:
    """Verify listing bug records and creating/upserting error occurrences."""
    app = create_app(settings=api_settings)

    wid = generate_uuid7()
    pid = generate_uuid7()
    user_id = generate_uuid7()

    mock_project = Project(
        id=pid,
        workspace_id=wid,
        name="Test Project",
        slug="test-proj",
    )

    norm = ErrorNormalizer.normalize("ValueError: Invalid payload format in parser.py")
    now = datetime.now(UTC)
    mock_bug = BugRecord(
        id=generate_uuid7(),
        workspace_id=wid,
        project_id=pid,
        fingerprint=norm.fingerprint,
        error_signature=norm.normalized_signature,
        title="ValueError: Invalid payload format",
        summary="Payload validation error",
        module_hint="parser.py",
        occurrence_count=1,
        first_seen_at=now,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
        resolutions=[],
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    async def _mock_exec(query, *args, **kwargs):
        res = MagicMock()
        q_str = str(query)
        if "projects" in q_str:
            res.scalar_one_or_none.return_value = mock_project
            res.scalars.return_value.all.return_value = [mock_project]
        elif "bug_records" in q_str:
            res.scalar_one_or_none.return_value = mock_bug
            res.scalars.return_value.all.return_value = [mock_bug]
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
        permissions=frozenset({"project:read", "analysis:create", "authenticated"}),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. List bugs
        res = await client.get(f"/api/v1/projects/{pid}/bugs")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["title"] == "ValueError: Invalid payload format"
        assert data[0]["fingerprint"] == norm.fingerprint

        # 2. Create/upsert bug
        create_payload = {
            "raw_error": "ValueError: Invalid payload format in parser.py at line 10",
            "title": "ValueError: Invalid payload format",
            "summary": "Reported from client test",
            "module_hint": "parser.py",
        }
        res_post = await client.post(
            f"/api/v1/projects/{pid}/bugs",
            json=create_payload,
        )
        assert res_post.status_code in (200, 201)
        post_data = res_post.json()
        assert post_data["fingerprint"] == norm.fingerprint


@pytest.mark.asyncio
async def test_api_get_bug_detail_and_add_resolution(api_settings: Settings) -> None:
    """Verify retrieving bug details and attaching a verified resolution."""
    app = create_app(settings=api_settings)

    wid = generate_uuid7()
    pid = generate_uuid7()
    bug_id = generate_uuid7()
    user_id = generate_uuid7()
    now = datetime.now(UTC)

    mock_bug = BugRecord(
        id=bug_id,
        workspace_id=wid,
        project_id=pid,
        fingerprint="test_fingerprint_abc",
        error_signature="KeyError in handler.py",
        title="KeyError: 'session'",
        summary="Missing session",
        module_hint="handler.py",
        occurrence_count=3,
        first_seen_at=now,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
        resolutions=[],
    )

    mock_resolution = BugResolution(
        id=generate_uuid7(),
        bug_record_id=bug_id,
        cause="Session expired prematurely",
        fix_summary="Extended TTL and added refresh hook",
        files=[{"path": "handler.py"}],
        created_at=now,
        updated_at=now,
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    async def _mock_exec(query, *args, **kwargs):
        res = MagicMock()
        q_str = str(query)
        if "bug_records" in q_str:
            res.scalar_one_or_none.return_value = mock_bug
            res.scalars.return_value.first.return_value = mock_bug
            res.scalars.return_value.all.return_value = [mock_bug]
        elif "bug_resolutions" in q_str:
            res.scalars.return_value.all.return_value = [mock_resolution]
        return res

    mock_session.execute.side_effect = _mock_exec

    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        user_id=user_id,
        clerk_user_id="user_test_client",
        email="client@example.com",
        workspace_id=wid,
        project_id=pid,
        project_role="member",
        permissions=frozenset({"project:read", "authenticated"}),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Get bug details
        res = await client.get(f"/api/v1/bugs/{bug_id}")
        assert res.status_code == 200
        detail = res.json()
        assert detail["id"] == str(bug_id)
        assert detail["title"] == "KeyError: 'session'"

        # 2. Add resolution
        res_post = await client.post(
            f"/api/v1/bugs/{bug_id}/resolutions",
            json={
                "cause": "Session expired prematurely",
                "fix_summary": "Extended TTL and added refresh hook",
                "files": [{"path": "handler.py"}],
            },
        )
        assert res_post.status_code == 201
        res_data = res_post.json()
        assert res_data["cause"] == "Session expired prematurely"
        assert res_data["fix_summary"] == "Extended TTL and added refresh hook"


@pytest.mark.asyncio
async def test_api_match_bug_endpoint(api_settings: Settings) -> None:
    """Verify bug matching endpoint finds candidates and synthesizes explanation."""
    app = create_app(settings=api_settings)

    wid = generate_uuid7()
    pid = generate_uuid7()
    user_id = generate_uuid7()
    now = datetime.now(UTC)

    mock_project = Project(
        id=pid,
        workspace_id=wid,
        name="Test Project",
        slug="test-proj",
    )

    norm = ErrorNormalizer.normalize(
        "ConnectionRefusedError: [Errno 111] Connection refused in db.py"
    )
    mock_bug = BugRecord(
        id=generate_uuid7(),
        workspace_id=wid,
        project_id=pid,
        fingerprint=norm.fingerprint,
        error_signature=norm.normalized_signature,
        title="ConnectionRefusedError: Connection refused",
        summary="DB port not reachable",
        module_hint="db.py",
        occurrence_count=2,
        first_seen_at=now,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
        resolutions=[],
    )

    mock_session = AsyncMock()

    async def _mock_exec(query, *args, **kwargs):
        res = MagicMock()
        q_str = str(query)
        if "projects" in q_str:
            res.scalar_one_or_none.return_value = mock_project
            res.scalars.return_value.all.return_value = [mock_project]
        elif "bug_records" in q_str:
            res.scalar_one_or_none.return_value = mock_bug
            res.scalars.return_value.all.return_value = [mock_bug]
        return res

    mock_session.execute.side_effect = _mock_exec

    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        user_id=user_id,
        clerk_user_id="user_test_client",
        email="client@example.com",
        workspace_id=wid,
        project_id=pid,
        project_role="member",
        permissions=frozenset({"project:read", "authenticated"}),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/projects/{pid}/bugs/match",
            json={
                "raw_error": "ConnectionRefusedError: [Errno 111] Connection refused in db.py",
                "module_hint": "db.py",
            },
        )
        assert res.status_code == 200
        match_data = res.json()
        assert match_data["matched"] is True
        assert match_data["confidence_label"] == "high"
        assert len(match_data["candidates"]) == 1
        assert "Exact match found" in match_data["explanation"]


@pytest.mark.asyncio
async def test_api_multi_tenant_isolation(api_settings: Settings) -> None:
    """Verify that a user from Workspace B cannot access or modify Workspace A bug records (Rule 4)."""
    app = create_app(settings=api_settings)

    wid_b = generate_uuid7()
    pid_a = generate_uuid7()
    bug_a_id = generate_uuid7()

    mock_session = AsyncMock()

    # When scoped to workspace B, queries for workspace A entities return None
    async def _mock_exec(query, *args, **kwargs):
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        res.scalars.return_value.first.return_value = None
        res.scalars.return_value.all.return_value = []
        return res

    mock_session.execute.side_effect = _mock_exec

    # User belongs to workspace B
    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_attacker",
        email="attacker@example.com",
        workspace_id=wid_b,
        permissions=frozenset({"project:read", "authenticated"}),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Cross-workspace listing
        res_list = await client.get(f"/api/v1/projects/{pid_a}/bugs")
        assert res_list.status_code == 404

        # Cross-workspace bug detail
        res_detail = await client.get(f"/api/v1/bugs/{bug_a_id}")
        assert res_detail.status_code == 404

        # Cross-workspace resolution add
        res_res = await client.post(
            f"/api/v1/bugs/{bug_a_id}/resolutions",
            json={"cause": "exploit", "fix_summary": "hack"},
        )
        assert res_res.status_code == 404


@pytest.mark.asyncio
async def test_api_validation_errors(api_settings: Settings) -> None:
    """Verify that invalid payload formats return RFC 9457 422 Problem Details."""
    app = create_app(settings=api_settings)
    wid = generate_uuid7()
    pid = generate_uuid7()

    app.dependency_overrides[get_db_session] = lambda: AsyncMock()
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_val",
        email="val@example.com",
        workspace_id=wid,
        project_id=pid,
        project_role="member",
        permissions=frozenset({"project:read", "analysis:create", "authenticated"}),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Empty raw_error
        res = await client.post(
            f"/api/v1/projects/{pid}/bugs",
            json={"raw_error": ""},
        )
        assert res.status_code == 422
        problem = res.json()
        assert problem["code"] == "validation.failed"
