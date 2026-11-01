"""Unit and specialist agent tests for DeployDoctor (docs/01 CAP-07, docs/05 §6.10)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.auth_context import AuthContext
from app.domain.deployment.schemas import DeploymentDiagnosisRequest
from app.orchestration.deploy_doctor import DeployDoctorAgent, run_deploy_doctor_specialist
from app.orchestration.state import SpecialistTask
from app.persistence.models.deployment import DeploymentIncident
from app.persistence.models.project import Project


def _make_auth_ctx(workspace_id=None, user_id=None) -> AuthContext:
    return AuthContext(
        user_id=user_id or uuid4(),
        clerk_user_id="user_clerk_123",
        email="devops@devmind.ai",
        workspace_id=workspace_id or uuid4(),
        workspace_role="admin",
    )


@pytest.mark.asyncio
async def test_deploy_doctor_diagnose_missing_env_var() -> None:
    """Verify DeployDoctor diagnoses missing environment variable with environment variable cross-check."""
    ws_id = uuid4()
    proj_id = uuid4()
    ctx = _make_auth_ctx(workspace_id=ws_id)

    mock_project = Project(
        id=proj_id,
        workspace_id=ws_id,
        name="web-api",
        slug="web-api",
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    # Mock project repo lookup
    mock_project_result = MagicMock()
    mock_project_result.scalars.return_value.first.return_value = mock_project

    # Mock incident repo lookups
    mock_empty_incident = MagicMock()
    mock_empty_incident.scalar_one_or_none.return_value = None
    mock_scalars = MagicMock()
    mock_scalars.scalars.return_value.all.return_value = []

    mock_session.execute.side_effect = [
        mock_project_result,
        mock_scalars,  # search_similar_incidents
        mock_empty_incident,  # record_incident lookup
    ]

    agent = DeployDoctorAgent(session=mock_session, router=None)

    raw_log = """
[error] Container crashed during boot with DATABASE_URL=postgres://user:Secret123@db:5432/app
KeyError: 'DEVMIND_DATABASE_URL'
"""
    req = DeploymentDiagnosisRequest(
        raw_log=raw_log,
        environment="production",
        service_name="web",
        configured_env_vars=["PORT", "REDIS_URL"],
        example_env_content="DEVMIND_DATABASE_URL=\nREDIS_URL=\n",
    )

    resp = await agent.diagnose(ctx, proj_id, req)

    assert resp.failure_category == "missing_env_var"
    assert resp.confidence >= 0.90
    assert "DEVMIND_DATABASE_URL" in resp.referenced_env_vars
    assert "Secret123" not in resp.probable_cause
    assert resp.is_insufficient_log is False

    # Check env var verification results
    assert resp.env_var_check is not None
    assert "DEVMIND_DATABASE_URL" in resp.env_var_check.referenced_missing
    assert "REDIS_URL" not in resp.env_var_check.referenced_missing

    # Check hypothesis output
    assert len(resp.hypotheses) >= 1
    assert "DEVMIND_DATABASE_URL" in resp.hypotheses[0].probable_cause


@pytest.mark.asyncio
async def test_deploy_doctor_diagnose_database_migration_failure() -> None:
    """Verify DeployDoctor diagnoses database migration failure with citations."""
    ws_id = uuid4()
    proj_id = uuid4()
    ctx = _make_auth_ctx(workspace_id=ws_id)

    mock_project = Project(
        id=proj_id,
        workspace_id=ws_id,
        name="web-api",
        slug="web-api",
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    mock_project_result = MagicMock()
    mock_project_result.scalars.return_value.first.return_value = mock_project
    mock_scalars = MagicMock()
    mock_scalars.scalars.return_value.all.return_value = []
    mock_empty_incident = MagicMock()
    mock_empty_incident.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [
        mock_project_result,
        mock_scalars,
        mock_empty_incident,
    ]

    agent = DeployDoctorAgent(session=mock_session, router=None)

    raw_log = """
[alembic.runtime.migration] Context impl PostgresqlImpl.
FAILED: alembic.util.exc.CommandError: Can't locate revision identified by '0015_bug_memory'
Traceback (most recent call last):
  File "server/app/main.py", line 12, in startup
    run_migrations()
"""
    req = DeploymentDiagnosisRequest(
        raw_log=raw_log,
        environment="staging",
    )

    resp = await agent.diagnose(ctx, proj_id, req)

    assert resp.failure_category == "database_migration_failed"
    assert "0015_bug_memory" in resp.summary
    assert resp.confidence >= 0.90
    assert "alembic upgrade head" in resp.recommended_action
    assert any("server/app/main.py" in str(f) for f in resp.referenced_files)


@pytest.mark.asyncio
async def test_deploy_doctor_empty_and_insufficient_log() -> None:
    """Verify DeployDoctor gracefully flags empty or insufficient logs."""
    ws_id = uuid4()
    proj_id = uuid4()
    ctx = _make_auth_ctx(workspace_id=ws_id)

    mock_project = Project(
        id=proj_id,
        workspace_id=ws_id,
        name="web-api",
        slug="web-api",
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    mock_project_result = MagicMock()
    mock_project_result.scalars.return_value.first.return_value = mock_project
    mock_empty_incident = MagicMock()
    mock_empty_incident.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [
        mock_project_result,
        mock_empty_incident,
    ]

    agent = DeployDoctorAgent(session=mock_session, router=None)

    req = DeploymentDiagnosisRequest(raw_log="   \n  \n")
    resp = await agent.diagnose(ctx, proj_id, req)

    assert resp.is_insufficient_log is True
    assert resp.confidence == 0.0
    assert resp.missing_information_needed is not None
    assert "container logs" in resp.recommended_action.lower()


@pytest.mark.asyncio
async def test_deploy_doctor_correlates_past_incident_resolution() -> None:
    """Verify DeployDoctor retrieves similar past incidents with recorded resolutions."""
    ws_id = uuid4()
    proj_id = uuid4()
    ctx = _make_auth_ctx(workspace_id=ws_id)

    mock_project = Project(
        id=proj_id,
        workspace_id=ws_id,
        name="web-api",
        slug="web-api",
    )

    past_incident = DeploymentIncident(
        id=uuid4(),
        workspace_id=ws_id,
        project_id=proj_id,
        fingerprint="fp_past_port_conflict",
        summary="Port binding conflict",
        probable_cause="Port 8000 already bound",
        resolution="Changed listening port to $PORT in entrypoint",
        error_signature="port_binding_failed:port_8000",
        environment="production",
        failure_category="port_binding_failed",
        occurrence_count=2,
        last_seen_at=datetime.now(UTC),
        resolved_at=datetime.now(UTC),
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    mock_project_result = MagicMock()
    mock_project_result.scalars.return_value.first.return_value = mock_project
    mock_similar_res = MagicMock()
    mock_similar_res.scalars.return_value.all.return_value = [past_incident]
    mock_empty_incident = MagicMock()
    mock_empty_incident.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [
        mock_project_result,
        mock_similar_res,  # search_similar_incidents candidates
        mock_empty_incident,  # record_incident lookup
    ]

    agent = DeployDoctorAgent(session=mock_session, router=None)

    raw_log = """
OSError: [Errno 98] Address already in use: 8000
"""
    req = DeploymentDiagnosisRequest(raw_log=raw_log)
    resp = await agent.diagnose(ctx, proj_id, req)

    assert resp.failure_category == "port_binding_failed"
    assert len(resp.similar_past_incidents) >= 1
    match = resp.similar_past_incidents[0]
    assert match.resolution == "Changed listening port to $PORT in entrypoint"
    assert match.similarity_score >= 0.5


@pytest.mark.asyncio
async def test_run_deploy_doctor_specialist_langgraph_node() -> None:
    """Verify DeployDoctor LangGraph specialist execution."""
    ws_id = uuid4()
    proj_id = uuid4()
    ctx = _make_auth_ctx(workspace_id=ws_id)

    mock_project = Project(
        id=proj_id,
        workspace_id=ws_id,
        name="web-api",
        slug="web-api",
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    mock_project_result = MagicMock()
    mock_project_result.scalars.return_value.first.return_value = mock_project
    mock_scalars = MagicMock()
    mock_scalars.scalars.return_value.all.return_value = []
    mock_empty_incident = MagicMock()
    mock_empty_incident.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [
        mock_project_result,
        mock_scalars,
        mock_empty_incident,
    ]

    state = {
        "run_id": "run_test_12345",
        "project_id": str(proj_id),
        "auth_context": ctx,
        "request": None,
    }

    task = SpecialistTask(
        specialist="deploy_doctor",
        task_id="deploy_doctor_task_1",
        status="running",
        params={
            "raw_log": "ModuleNotFoundError: No module named 'fastapi'\n",
            "environment": "production",
        },
    )

    result = await run_deploy_doctor_specialist(
        state=state,
        task=task,
        session=mock_session,
    )

    assert task.status == "completed"
    assert "final_response" in result
    assert "DEPENDENCY_MISMATCH" in result["final_response"]
    assert result["metadata"]["failure_category"] == "dependency_mismatch"
