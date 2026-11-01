"""Integration tests for Deployment Diagnosis and Incident REST API endpoints (docs/01 CAP-07, docs/03 §3.4)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth_context import AuthContext
from app.core.errors import ForbiddenError
from app.core.ids import generate_uuid7
from app.core.settings import Settings
from app.domain.auth import get_auth_context, get_db_session
from app.domain.deployment.schemas import (
    DeploymentDiagnosisResponse,
    DeploymentIncidentListResponse,
    DeploymentIncidentResponse,
    EnvVarCheckResultSchema,
)
from app.domain.deployment.service import DeploymentService
from app.llm.schemas import DiagnosisHypothesis
from app.main import create_app


@pytest.fixture
def api_settings() -> Settings:
    return Settings(
        env="test",
        github_client_id="test_github_client_id",
        github_client_secret="test_github_client_secret",
        encryption_keys=["c3VwZXJfc2VjcmV0X2tleV9mb3JfdGVzdF8zMmJ5dGVzIQ=="],
    )


@pytest.mark.asyncio
async def test_api_diagnose_deployment(api_settings: Settings) -> None:
    """Verify POST /projects/{project_id}/deployment-diagnoses diagnoses logs and returns hypotheses."""
    app = create_app(settings=api_settings)

    wid = generate_uuid7()
    pid = generate_uuid7()
    user_id = generate_uuid7()
    inc_id = generate_uuid7()
    now = datetime.now(UTC)

    auth_ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_123",
        email="dev@devmind.ai",
        workspace_id=wid,
        workspace_role="admin",
        project_id=pid,
        project_role="maintainer",
        permissions=frozenset({"project:read", "analysis:create", "project:update"}),
    )

    mock_session = AsyncMock()
    app.dependency_overrides[get_auth_context] = lambda: auth_ctx
    app.dependency_overrides[get_db_session] = lambda: mock_session

    mock_resp = DeploymentDiagnosisResponse(
        incident_id=inc_id,
        is_new_incident=True,
        fingerprint="fp_test_12345",
        failure_category="missing_env_var",
        confidence=0.98,
        summary="Missing required environment variable: DEVMIND_DATABASE_URL",
        probable_cause="DEVMIND_DATABASE_URL is required by Settings",
        recommended_action="Set DEVMIND_DATABASE_URL in Render dashboard",
        hypotheses=[
            DiagnosisHypothesis(
                title="Missing DEVMIND_DATABASE_URL",
                probable_cause="Not set in environment",
                confidence=0.98,
                recommended_action="Set variable and redeploy",
                log_line_citations=[4],
                file_citations=["server/app/main.py:45"],
            )
        ],
        referenced_env_vars=["DEVMIND_DATABASE_URL"],
        env_var_check=EnvVarCheckResultSchema(
            referenced_names=["DEVMIND_DATABASE_URL"],
            referenced_missing=["DEVMIND_DATABASE_URL"],
            has_issues=True,
        ),
        referenced_files=[{"path": "server/app/main.py", "line": 45, "is_project_code": True}],
        primary_log_line=4,
        similar_past_incidents=[],
        is_insufficient_log=False,
        redaction_count=1,
        created_at=now,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                DeploymentService,
                "diagnose_log",
                AsyncMock(return_value=mock_resp),
            )

            resp = await client.post(
                f"/api/v1/projects/{pid}/deployment-diagnoses",
                json={
                    "raw_log": "KeyError: 'DEVMIND_DATABASE_URL'\n",
                    "environment": "production",
                    "service_name": "api",
                },
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["incident_id"] == str(inc_id)
            assert data["failure_category"] == "missing_env_var"
            assert data["confidence"] == 0.98
            assert len(data["hypotheses"]) == 1
            assert data["hypotheses"][0]["log_line_citations"] == [4]


@pytest.mark.asyncio
async def test_api_list_and_get_incidents(api_settings: Settings) -> None:
    """Verify GET /projects/{project_id}/deployment-incidents list and retrieve by ID."""
    app = create_app(settings=api_settings)

    wid = generate_uuid7()
    pid = generate_uuid7()
    inc_id = generate_uuid7()
    user_id = generate_uuid7()
    now = datetime.now(UTC)

    auth_ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_123",
        email="dev@devmind.ai",
        workspace_id=wid,
        workspace_role="admin",
        project_id=pid,
        project_role="maintainer",
        permissions=frozenset({"project:read"}),
    )

    mock_session = AsyncMock()
    app.dependency_overrides[get_auth_context] = lambda: auth_ctx
    app.dependency_overrides[get_db_session] = lambda: mock_session

    inc_item = DeploymentIncidentResponse(
        id=inc_id,
        workspace_id=wid,
        project_id=pid,
        fingerprint="fp_abc123",
        summary="Alembic revision missing",
        probable_cause="Migration 0015 missing",
        resolution="Applied migration",
        error_signature="database_migration_failed",
        environment="staging",
        service_name="backend",
        failure_category="database_migration_failed",
        log_snippet="FAILED: alembic CommandError",
        occurrence_count=3,
        last_seen_at=now,
        resolved_at=now,
        resolved_by=user_id,
        created_at=now,
        updated_at=now,
        metadata={},
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                DeploymentService,
                "list_incidents",
                AsyncMock(
                    return_value=DeploymentIncidentListResponse(
                        items=[inc_item],
                        total=1,
                        limit=50,
                        offset=0,
                    )
                ),
            )
            mp.setattr(
                DeploymentService,
                "get_incident",
                AsyncMock(return_value=inc_item),
            )

            # 1. List
            list_resp = await client.get(
                f"/api/v1/projects/{pid}/deployment-incidents",
                params={"environment": "staging", "category": "database_migration_failed"},
            )
            assert list_resp.status_code == 200
            list_data = list_resp.json()
            assert list_data["total"] == 1
            assert len(list_data["items"]) == 1
            assert list_data["items"][0]["fingerprint"] == "fp_abc123"

            # 2. Get by ID
            get_resp = await client.get(f"/api/v1/projects/{pid}/deployment-incidents/{inc_id}")
            assert get_resp.status_code == 200
            assert get_resp.json()["id"] == str(inc_id)


@pytest.mark.asyncio
async def test_api_update_resolution_and_delete(api_settings: Settings) -> None:
    """Verify PATCH resolution and DELETE incident endpoints."""
    app = create_app(settings=api_settings)

    wid = generate_uuid7()
    pid = generate_uuid7()
    inc_id = generate_uuid7()
    user_id = generate_uuid7()
    now = datetime.now(UTC)

    auth_ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_123",
        email="dev@devmind.ai",
        workspace_id=wid,
        workspace_role="admin",
        project_id=pid,
        project_role="maintainer",
        permissions=frozenset({"project:update", "project:delete"}),
    )

    mock_session = AsyncMock()
    app.dependency_overrides[get_auth_context] = lambda: auth_ctx
    app.dependency_overrides[get_db_session] = lambda: mock_session

    resolved_item = DeploymentIncidentResponse(
        id=inc_id,
        workspace_id=wid,
        project_id=pid,
        fingerprint="fp_abc123",
        summary="Port binding conflict",
        probable_cause="Port 8000 already bound",
        resolution="Configured application to bind to PORT env variable",
        error_signature="port_binding_failed",
        environment="production",
        service_name="web",
        failure_category="port_binding_failed",
        log_snippet="OSError: Address already in use",
        occurrence_count=1,
        last_seen_at=now,
        resolved_at=now,
        resolved_by=user_id,
        created_at=now,
        updated_at=now,
        metadata={},
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                DeploymentService,
                "update_resolution",
                AsyncMock(return_value=resolved_item),
            )
            mp.setattr(
                DeploymentService,
                "delete_incident",
                AsyncMock(return_value=True),
            )

            # 1. Update resolution
            patch_resp = await client.patch(
                f"/api/v1/projects/{pid}/deployment-incidents/{inc_id}/resolution",
                json={"resolution": "Configured application to bind to PORT env variable"},
            )
            assert patch_resp.status_code == 200
            assert "bind to PORT" in patch_resp.json()["resolution"]

            # 2. Delete incident
            del_resp = await client.delete(f"/api/v1/projects/{pid}/deployment-incidents/{inc_id}")
            assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_api_cross_tenant_rejection(api_settings: Settings) -> None:
    """Verify that cross-tenant access returns 403 or 404."""
    app = create_app(settings=api_settings)

    wid_a = generate_uuid7()
    pid_b = generate_uuid7()
    user_id = generate_uuid7()

    auth_ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_123",
        email="dev@devmind.ai",
        workspace_id=wid_a,
        workspace_role="admin",
        project_id=None,
        permissions=frozenset({"project:read", "analysis:create"}),
    )

    mock_session = AsyncMock()
    app.dependency_overrides[get_auth_context] = lambda: auth_ctx
    app.dependency_overrides[get_db_session] = lambda: mock_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                DeploymentService,
                "diagnose_log",
                AsyncMock(
                    side_effect=ForbiddenError(
                        detail="Cross-workspace incident access is forbidden"
                    )
                ),
            )

            resp = await client.post(
                f"/api/v1/projects/{pid_b}/deployment-diagnoses",
                json={"raw_log": "Error log"},
            )
            assert resp.status_code == 403
            assert "forbidden" in resp.json()["detail"].lower()
