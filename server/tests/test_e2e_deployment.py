"""End-to-End integration test suite for Deployment Diagnosis (CAP-07, docs/01 §7, docs/03 §3.4, M12-17)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.auth_context import AuthContext
from app.core.errors import ForbiddenError
from app.domain.auth import (
    PERM_PROJECT_READ,
    PERM_PROJECT_UPDATE,
)
from app.domain.deployment.schemas import (
    DeploymentDiagnosisRequest,
    DeploymentResolutionUpdate,
)
from app.domain.deployment.service import DeploymentService
from app.persistence.models.deployment import DeploymentIncident
from app.persistence.models.project import Project


@pytest.mark.asyncio
async def test_e2e_deployment_diagnosis_lifecycle() -> None:
    """E2E test: log ingestion & redaction -> diagnosis -> deduplication -> resolution -> similar retrieval."""
    workspace_id = uuid4()
    project_id = uuid4()
    user_id = uuid4()
    incident_id = uuid4()
    now = datetime.now(UTC)

    ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_clerk_123",
        email="dev@devmind.ai",
        workspace_id=workspace_id,
        workspace_role="admin",
        project_id=project_id,
        project_role="maintainer",
        permissions=frozenset({PERM_PROJECT_READ, PERM_PROJECT_UPDATE}),
    )

    mock_session = AsyncMock()
    service = DeploymentService(session=mock_session)

    mock_project = Project(
        id=project_id,
        workspace_id=workspace_id,
        name="Production Gateway",
        slug="prod-gateway",
    )
    service.project_repo.get_by_id = AsyncMock(return_value=mock_project)
    service.agent.project_repo.get_by_id = AsyncMock(return_value=mock_project)

    # 1. Log ingestion with raw credential secrets and ANSI colors
    raw_crash_log = (
        "\x1b[31m[2026-11-01 10:14:22] ERROR: Failed connection postgresql://postgres:SuperSecretPassword123@neon.tech:5432/devmind\x1b[0m\n"
        "[2026-11-01 10:14:23] ERROR: pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings\n"
        "[2026-11-01 10:14:23]   DATABASE_URL\n"
        "[2026-11-01 10:14:23]     Field required [type=missing, input_value={}, input_type=dict]\n"
        "[2026-11-01 10:14:24] CRITICAL: Container failed to start. Exiting with code 1."
    )

    req = DeploymentDiagnosisRequest(
        raw_log=raw_crash_log,
        environment="production",
        service_name="prod-gateway",
        configured_env_vars=["PORT", "REDIS_URL"],
    )

    initial_incident = DeploymentIncident(
        id=incident_id,
        workspace_id=workspace_id,
        project_id=project_id,
        fingerprint="fp_hash_missing_database_url",
        summary="Missing required environment variable: DATABASE_URL",
        probable_cause="Settings validation failed due to missing DATABASE_URL",
        resolution=None,
        error_signature="MissingEnvVar:DATABASE_URL",
        environment="production",
        service_name="prod-gateway",
        failure_category="missing_env_var",
        log_snippet="ERROR: pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings",
        occurrence_count=1,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
    )

    service.repo.record_incident = AsyncMock(return_value=(initial_incident, True, None))
    service.repo.search_similar_incidents = AsyncMock(return_value=[])
    service.agent.incident_repo.record_incident = AsyncMock(
        return_value=(initial_incident, True, None)
    )
    service.agent.incident_repo.search_similar_incidents = AsyncMock(return_value=[])

    diagnosis = await service.diagnose_log(ctx, project_id, req)

    # Assert sanitization guarantee (ADR-047, docs/07 §6)
    assert "SuperSecretPassword123" not in diagnosis.summary
    assert "SuperSecretPassword123" not in diagnosis.probable_cause
    assert diagnosis.redaction_count >= 1
    assert diagnosis.failure_category == "missing_env_var"
    assert diagnosis.primary_log_line == 2
    assert "DATABASE_URL" in diagnosis.referenced_env_vars
    assert (
        "DATABASE_URL" in diagnosis.env_var_check.referenced_missing
        or "DATABASE_URL" in diagnosis.env_var_check.missing_required
    )

    # 2. Duplicate occurrence increments count
    recurring_incident = DeploymentIncident(
        id=incident_id,
        workspace_id=workspace_id,
        project_id=project_id,
        fingerprint="fp_hash_missing_database_url",
        summary="Missing required environment variable: DATABASE_URL",
        probable_cause="Settings validation failed due to missing DATABASE_URL",
        resolution=None,
        error_signature="MissingEnvVar:DATABASE_URL",
        environment="production",
        service_name="prod-gateway",
        failure_category="missing_env_var",
        log_snippet="ERROR: pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings",
        occurrence_count=2,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
    )
    service.repo.record_incident = AsyncMock(return_value=(recurring_incident, False, None))
    service.agent.incident_repo.record_incident = AsyncMock(
        return_value=(recurring_incident, False, None)
    )

    diag_2 = await service.diagnose_log(ctx, project_id, req)
    assert diag_2.is_new_incident is False
    assert diag_2.incident_id == incident_id

    service.repo.get_incident = AsyncMock(return_value=recurring_incident)
    inc_detail = await service.get_incident(ctx, project_id, incident_id)
    assert inc_detail.occurrence_count == 2

    # 3. Update resolution for the incident
    resolved_incident = DeploymentIncident(
        id=incident_id,
        workspace_id=workspace_id,
        project_id=project_id,
        fingerprint="fp_hash_missing_database_url",
        summary="Missing required environment variable: DATABASE_URL",
        probable_cause="Settings validation failed due to missing DATABASE_URL",
        resolution="Set DATABASE_URL in Render dashboard environment variables",
        resolved_by=user_id,
        resolved_at=now,
        error_signature="MissingEnvVar:DATABASE_URL",
        environment="production",
        service_name="prod-gateway",
        failure_category="missing_env_var",
        log_snippet="ERROR: pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings",
        occurrence_count=2,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
    )
    service.repo.update_resolution = AsyncMock(return_value=resolved_incident)

    resolution_update = DeploymentResolutionUpdate(
        resolution="Set DATABASE_URL in Render dashboard environment variables"
    )
    res_resp = await service.update_resolution(ctx, project_id, incident_id, resolution_update)
    assert res_resp.resolution == "Set DATABASE_URL in Render dashboard environment variables"
    assert res_resp.resolved_by == user_id

    # 4. Search similar incidents retrieves resolved precedent
    service.repo.search_similar_incidents = AsyncMock(
        return_value=[(resolved_incident, 0.95, "exact_fingerprint")]
    )
    similar = await service.repo.search_similar_incidents(
        ctx,
        workspace_id=workspace_id,
        project_id=project_id,
        failure_category="missing_env_var",
    )
    assert len(similar) == 1
    match_inc, score, match_type = similar[0]
    assert match_inc.id == incident_id
    assert score == 0.95
    assert match_inc.resolution == "Set DATABASE_URL in Render dashboard environment variables"


@pytest.mark.asyncio
async def test_e2e_deployment_cross_tenant_isolation() -> None:
    """Verify that alien workspaces cannot access or modify incidents across tenant boundary."""
    workspace_id = uuid4()
    alien_workspace_id = uuid4()
    project_id = uuid4()

    mock_session = AsyncMock()
    service = DeploymentService(session=mock_session)

    alien_ctx = AuthContext(
        user_id=uuid4(),
        clerk_user_id="user_alien_999",
        email="alien@otherorg.com",
        workspace_id=alien_workspace_id,
        workspace_role="admin",
        permissions=frozenset({PERM_PROJECT_READ, PERM_PROJECT_UPDATE}),
    )

    # Attempting to query similar incidents with alien context targeting another workspace must raise ForbiddenError
    with pytest.raises(ForbiddenError):
        await service.repo.search_similar_incidents(
            alien_ctx,
            workspace_id=workspace_id,
            project_id=project_id,
            failure_category="missing_env_var",
        )

    # Attempting to list incidents with alien context
    with pytest.raises(ForbiddenError):
        await service.repo.list_incidents(
            alien_ctx,
            workspace_id=workspace_id,
            project_id=project_id,
        )


def test_e2e_deployment_benchmark_regression_gate() -> None:
    """Evaluation regression gate asserting benchmark passes with composite score >= 0.90."""
    import sys
    from pathlib import Path

    root_dir = Path(__file__).resolve().parent.parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    from evals.deployment.harness import run_deployment_benchmark

    summary = run_deployment_benchmark()
    assert summary.status == "passed"
    assert summary.composite_score >= 0.90
    assert summary.sanitization_metrics.secret_redaction_rate == 1.0
    assert summary.classification_metrics.category_accuracy >= 0.90
    assert summary.env_var_metrics.missing_f1_score >= 0.90
    assert summary.retrieval_metrics.tenant_isolation_rate == 1.0
