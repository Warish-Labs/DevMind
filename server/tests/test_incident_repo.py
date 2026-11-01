"""Unit and tenant isolation tests for Deployment Incident Repository (docs/01 CAP-07, docs/03 §3.4, M12-14)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.auth_context import AuthContext
from app.core.errors import ForbiddenError
from app.persistence.models.deployment import DeploymentIncident
from app.persistence.repositories.incident_repo import DeploymentIncidentRepository


def _make_auth_ctx(workspace_id=None, user_id=None) -> AuthContext:
    return AuthContext(
        user_id=user_id or uuid4(),
        clerk_user_id="user_clerk_123",
        email="devops@devmind.ai",
        workspace_id=workspace_id or uuid4(),
        workspace_role="admin",
    )


@pytest.mark.asyncio
async def test_incident_repo_record_new_incident() -> None:
    """Verify recording a new deployment failure with automatic secret redaction."""
    ws_id = uuid4()
    proj_id = uuid4()
    ctx = _make_auth_ctx(workspace_id=ws_id)

    raw_log = """
[error] Container startup failed with DATABASE_URL=postgres://user:SuperSecret123@db:5432/app
KeyError: 'DEVMIND_DATABASE_URL'
"""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    # No existing record
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    repo = DeploymentIncidentRepository(mock_session)
    incident, is_new, parsed = await repo.record_incident(
        ctx,
        workspace_id=ws_id,
        project_id=proj_id,
        raw_log=raw_log,
        environment="production",
        service_name="web",
    )

    assert is_new is True
    assert incident.workspace_id == ws_id
    assert incident.project_id == proj_id
    assert incident.failure_category == "missing_env_var"
    assert "SuperSecret123" not in incident.log_snippet
    assert "[REDACTED:" in incident.log_snippet
    assert incident.occurrence_count == 1
    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_incident_repo_deduplicate_recurring_failure() -> None:
    """Verify that recurring identical failure fingerprints increment occurrence count without duplication."""
    ws_id = uuid4()
    proj_id = uuid4()
    ctx = _make_auth_ctx(workspace_id=ws_id)

    existing_incident = DeploymentIncident(
        id=uuid4(),
        workspace_id=ws_id,
        project_id=proj_id,
        fingerprint="test_fp_123",
        summary="Missing required environment variable",
        probable_cause="Settings validation failed",
        error_signature="missing_env_var:DATABASE_URL",
        environment="production",
        failure_category="missing_env_var",
        occurrence_count=1,
        last_seen_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    raw_log = "KeyError: 'DATABASE_URL'\n"

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    # Return existing record
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_incident
    mock_session.execute.return_value = mock_result

    repo = DeploymentIncidentRepository(mock_session)
    incident, is_new, parsed = await repo.record_incident(
        ctx,
        workspace_id=ws_id,
        project_id=proj_id,
        raw_log=raw_log,
        environment="production",
    )

    assert is_new is False
    assert incident.occurrence_count == 2
    mock_session.add.assert_not_called()
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_incident_repo_get_by_id_and_fingerprint() -> None:
    """Verify retrieving incidents by ID and fingerprint with workspace scoping."""
    ws_id = uuid4()
    proj_id = uuid4()
    inc_id = uuid4()
    ctx = _make_auth_ctx(workspace_id=ws_id)

    mock_incident = DeploymentIncident(
        id=inc_id,
        workspace_id=ws_id,
        project_id=proj_id,
        fingerprint="fp_abc123",
        summary="Alembic revision missing",
        probable_cause="Migration failed",
        error_signature="database_migration_failed",
        environment="staging",
        failure_category="database_migration_failed",
        occurrence_count=3,
        last_seen_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_incident
    mock_session.execute.return_value = mock_result

    repo = DeploymentIncidentRepository(mock_session)

    # By ID
    res_id = await repo.get_incident(
        ctx,
        workspace_id=ws_id,
        project_id=proj_id,
        incident_id=inc_id,
    )
    assert res_id is not None
    assert res_id.id == inc_id

    # By Fingerprint
    res_fp = await repo.get_by_fingerprint(
        ctx,
        workspace_id=ws_id,
        project_id=proj_id,
        fingerprint="fp_abc123",
    )
    assert res_fp is not None
    assert res_fp.fingerprint == "fp_abc123"


@pytest.mark.asyncio
async def test_incident_repo_cross_tenant_isolation_rejection() -> None:
    """Verify that attempting to operate on an alien workspace raises ForbiddenError."""
    ws_tenant_a = uuid4()
    ws_tenant_b = uuid4()
    proj_id = uuid4()
    ctx_a = _make_auth_ctx(workspace_id=ws_tenant_a)

    mock_session = AsyncMock()
    repo = DeploymentIncidentRepository(mock_session)

    # Attempting to record incident for tenant B with tenant A context
    with pytest.raises(ForbiddenError):
        await repo.record_incident(
            ctx_a,
            workspace_id=ws_tenant_b,
            project_id=proj_id,
            raw_log="KeyError: 'ENV'",
        )


@pytest.mark.asyncio
async def test_incident_repo_list_and_filter() -> None:
    """Verify listing deployment incidents with category and environment filtering."""
    ws_id = uuid4()
    proj_id = uuid4()
    ctx = _make_auth_ctx(workspace_id=ws_id)

    inc1 = DeploymentIncident(
        id=uuid4(),
        workspace_id=ws_id,
        project_id=proj_id,
        fingerprint="fp_1",
        summary="Missing ENV",
        probable_cause="Cause 1",
        error_signature="sig 1",
        environment="production",
        failure_category="missing_env_var",
        occurrence_count=1,
        last_seen_at=datetime.now(UTC),
    )

    mock_session = AsyncMock()
    mock_count_res = MagicMock()
    mock_count_res.scalar.return_value = 1
    mock_list_res = MagicMock()
    mock_list_res.scalars.return_value.all.return_value = [inc1]

    mock_session.execute.side_effect = [mock_count_res, mock_list_res]

    repo = DeploymentIncidentRepository(mock_session)
    items, total = await repo.list_incidents(
        ctx,
        workspace_id=ws_id,
        project_id=proj_id,
        environment="production",
        category="missing_env_var",
    )

    assert total == 1
    assert len(items) == 1
    assert items[0].fingerprint == "fp_1"


@pytest.mark.asyncio
async def test_incident_repo_update_resolution_and_delete() -> None:
    """Verify updating resolution documentation and deleting incident."""
    ws_id = uuid4()
    proj_id = uuid4()
    inc_id = uuid4()
    user_id = uuid4()
    ctx = _make_auth_ctx(workspace_id=ws_id, user_id=user_id)

    mock_incident = DeploymentIncident(
        id=inc_id,
        workspace_id=ws_id,
        project_id=proj_id,
        fingerprint="fp_resolve",
        summary="Missing DATABASE_URL",
        probable_cause="Not defined in Render",
        error_signature="missing_env_var:DATABASE_URL",
        environment="production",
        failure_category="missing_env_var",
        resolution=None,
        occurrence_count=1,
        last_seen_at=datetime.now(UTC),
    )

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_incident
    mock_session.execute.return_value = mock_result
    mock_session.flush = AsyncMock()
    mock_session.delete = AsyncMock()

    repo = DeploymentIncidentRepository(mock_session)

    # 1. Update resolution
    updated = await repo.update_resolution(
        ctx,
        workspace_id=ws_id,
        project_id=proj_id,
        incident_id=inc_id,
        resolution="Added DATABASE_URL secret in Render environment dashboard.",
        resolved_by=user_id,
    )
    assert updated is not None
    assert updated.resolution == "Added DATABASE_URL secret in Render environment dashboard."
    assert updated.resolved_by == user_id
    assert updated.resolved_at is not None

    # 2. Delete incident
    deleted = await repo.delete_incident(
        ctx,
        workspace_id=ws_id,
        project_id=proj_id,
        incident_id=inc_id,
    )
    assert deleted is True
    mock_session.delete.assert_called_once_with(mock_incident)


@pytest.mark.asyncio
async def test_incident_repo_search_similar_incidents() -> None:
    """Verify hybrid candidate similarity search across historical incidents."""
    ws_id = uuid4()
    proj_id = uuid4()
    ctx = _make_auth_ctx(workspace_id=ws_id)

    inc1 = DeploymentIncident(
        id=uuid4(),
        workspace_id=ws_id,
        project_id=proj_id,
        fingerprint="exact_target_fp",
        summary="Missing DATABASE_URL",
        failure_category="missing_env_var",
        error_signature="missing_env_var:DATABASE_URL",
        resolution="Set DATABASE_URL in Render",
        metadata_={"referenced_env_vars": ["DATABASE_URL"]},
        last_seen_at=datetime.now(UTC),
    )

    inc2 = DeploymentIncident(
        id=uuid4(),
        workspace_id=ws_id,
        project_id=proj_id,
        fingerprint="different_fp",
        summary="Missing REDIS_URL",
        failure_category="missing_env_var",
        error_signature="missing_env_var:REDIS_URL",
        resolution=None,
        metadata_={"referenced_env_vars": ["REDIS_URL"]},
        last_seen_at=datetime.now(UTC),
    )

    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [inc1, inc2]
    mock_session.execute.return_value = mock_res

    repo = DeploymentIncidentRepository(mock_session)

    # 1. Exact fingerprint match
    matches = await repo.search_similar_incidents(
        ctx,
        workspace_id=ws_id,
        project_id=proj_id,
        fingerprint="exact_target_fp",
    )
    assert len(matches) >= 1
    assert matches[0][0].fingerprint == "exact_target_fp"
    assert matches[0][1] == 1.0
    assert matches[0][2] == "exact_fingerprint"

    # 2. Category match
    matches_cat = await repo.search_similar_incidents(
        ctx,
        workspace_id=ws_id,
        project_id=proj_id,
        failure_category="missing_env_var",
    )
    assert len(matches_cat) == 2
    assert matches_cat[0][1] >= 0.5
