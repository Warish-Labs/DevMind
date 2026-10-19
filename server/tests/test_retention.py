"""Tests for Retention policies, effective windows, sweep jobs, and API endpoints (M9-04, docs/03 §3.1, docs/07 §9, ADR-026)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from starlette.testclient import TestClient

from app.core.auth_context import AuthContext
from app.core.errors import ValidationError
from app.core.ids import generate_uuid7
from app.domain.auth import (
    PERM_PROJECT_READ,
    PERM_PROJECT_UPDATE,
    PERM_WORKSPACE_MANAGE,
    PERM_WORKSPACE_READ,
)
from app.domain.auth.dependencies import get_auth_context
from app.domain.retention.retention_service import (
    DEFAULT_RETENTION_DAYS,
    EffectiveRetentionSummary,
    RetentionPolicyItem,
    RetentionService,
    RetentionSweepReport,
)
from app.main import create_app
from app.persistence.models.project import Project
from app.persistence.models.retention import RetentionPolicy
from app.persistence.repositories.brain_repo import BrainRepository
from app.persistence.repositories.retention_repo import RetentionRepository
from app.workers.scheduler import run_retention_sweep_job


def _make_auth_ctx(
    workspace_id: UUID | None = None,
    user_id: UUID | None = None,
    role: str = "maintainer",
    permissions: frozenset[str] | None = None,
) -> AuthContext:
    perms = permissions or frozenset(
        {PERM_WORKSPACE_READ, PERM_WORKSPACE_MANAGE, PERM_PROJECT_READ, PERM_PROJECT_UPDATE}
    )
    return AuthContext(
        user_id=user_id or generate_uuid7(),
        clerk_user_id="user_clerk_retention_test",
        email="retention_test@example.com",
        workspace_id=workspace_id or generate_uuid7(),
        workspace_role=role,
        permissions=perms,
    )


def test_retention_policy_model_attributes() -> None:
    """Verify RetentionPolicy model properties and defaults."""
    wid = generate_uuid7()
    pid = generate_uuid7()
    pol_id = generate_uuid7()
    now = datetime.now(UTC)

    policy = RetentionPolicy(
        id=pol_id,
        workspace_id=wid,
        project_id=pid,
        kind="job_events",
        days=15,
        created_at=now,
        updated_at=now,
    )

    assert policy.id == pol_id
    assert policy.workspace_id == wid
    assert policy.project_id == pid
    assert policy.kind == "job_events"
    assert policy.days == 15


@pytest.mark.asyncio
async def test_retention_repo_workspace_and_project_isolation() -> None:
    """Verify RetentionRepository validates workspace context."""
    session = AsyncMock()
    repo = RetentionRepository(session)
    wid = generate_uuid7()
    other_wid = generate_uuid7()

    ctx = _make_auth_ctx(workspace_id=wid)

    # Calling with different workspace_id should raise PermissionError
    with pytest.raises(PermissionError, match="cannot access"):
        await repo.list_workspace_policies(ctx, other_wid)


@pytest.mark.asyncio
async def test_retention_service_workspace_defaults_and_override() -> None:
    """Verify RetentionService returns default ADR-026 windows and saves overrides."""
    wid = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=wid)

    service = RetentionService()

    # 1. Mock empty database policies -> verify interim defaults
    mock_policy = RetentionPolicy(
        id=generate_uuid7(),
        workspace_id=wid,
        project_id=None,
        kind="job_events",
        days=14,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with patch(
        "app.domain.retention.retention_service.RetentionRepository.list_workspace_policies",
        new_callable=AsyncMock,
    ) as mock_list:
        mock_list.return_value = []
        summary = await service.get_workspace_retention(ctx, wid)
        assert isinstance(summary, EffectiveRetentionSummary)
        cat_map = {c.kind: c for c in summary.categories}
        assert cat_map["job_events"].days == DEFAULT_RETENTION_DAYS["job_events"]
        assert cat_map["job_events"].is_custom is False
        assert cat_map["job_events"].source == "default"

    # 2. Update workspace policy
    with (
        patch(
            "app.domain.retention.retention_service.RetentionRepository.upsert_policy",
            new_callable=AsyncMock,
        ) as mock_upsert,
        patch(
            "app.domain.retention.retention_service.AuditEventRepository.record",
            new_callable=AsyncMock,
        ) as mock_audit,
    ):
        mock_upsert.return_value = mock_policy
        res = await service.update_workspace_retention(ctx, wid, "job_events", 14)
        assert isinstance(res, RetentionPolicyItem)
        assert res.days == 14
        assert res.kind == "job_events"
        mock_audit.assert_called_once()
        assert mock_audit.call_args.kwargs["action"] == "retention.workspace_updated"


@pytest.mark.asyncio
async def test_retention_service_project_override_and_reset() -> None:
    """Verify project-level override takes precedence and reset restores workspace policy."""
    wid = generate_uuid7()
    pid = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=wid)
    service = RetentionService()

    project = Project(
        id=pid,
        workspace_id=wid,
        name="Test Project",
        slug="test-proj",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    p_override = RetentionPolicy(
        id=generate_uuid7(),
        workspace_id=wid,
        project_id=pid,
        kind="snapshots",
        days=45,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with (
        patch(
            "app.domain.retention.retention_service.ProjectRepository.get_by_id",
            new_callable=AsyncMock,
        ) as mock_get_p,
        patch(
            "app.domain.retention.retention_service.RetentionRepository.list_workspace_policies",
            new_callable=AsyncMock,
        ) as mock_ws_list,
        patch(
            "app.domain.retention.retention_service.RetentionRepository.list_project_policies",
            new_callable=AsyncMock,
        ) as mock_p_list,
    ):
        mock_get_p.return_value = project
        mock_ws_list.return_value = []
        mock_p_list.return_value = [p_override]

        summary = await service.get_project_retention(ctx, pid)
        cat_map = {c.kind: c for c in summary.categories}
        assert cat_map["snapshots"].days == 45
        assert cat_map["snapshots"].is_custom is True
        assert cat_map["snapshots"].source == "project_override"

    # Reset project override
    with (
        patch(
            "app.domain.retention.retention_service.ProjectRepository.get_by_id",
            new_callable=AsyncMock,
        ) as mock_get_p,
        patch(
            "app.domain.retention.retention_service.RetentionRepository.delete_policy",
            new_callable=AsyncMock,
        ) as mock_del,
        patch(
            "app.domain.retention.retention_service.AuditEventRepository.record",
            new_callable=AsyncMock,
        ) as mock_audit,
    ):
        mock_get_p.return_value = project
        mock_del.return_value = True

        deleted = await service.reset_project_retention(ctx, pid, "snapshots")
        assert deleted is True
        mock_audit.assert_called_once()
        assert mock_audit.call_args.kwargs["action"] == "retention.project_reset"


@pytest.mark.asyncio
async def test_retention_service_validation() -> None:
    """Verify validation errors for invalid category or negative days."""
    wid = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=wid)
    service = RetentionService()

    with pytest.raises(ValidationError, match="Unknown retention category"):
        await service.update_workspace_retention(ctx, wid, "invalid_kind", 30)

    with pytest.raises(ValidationError, match="at least 1 day"):
        await service.update_workspace_retention(ctx, wid, "job_events", 0)


@pytest.mark.asyncio
async def test_brain_repo_sweep_project_retention() -> None:
    """Verify BrainRepository.sweep_project_retention executes delete queries for cutoffs."""
    session = AsyncMock()
    repo = BrainRepository(session)
    wid = generate_uuid7()
    pid = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=wid)

    # Mock project access
    project = Project(id=pid, workspace_id=wid, name="Test", slug="test")
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = project
    mock_result.scalars.return_value.all.return_value = []
    mock_result.rowcount = 4
    session.execute = AsyncMock(return_value=mock_result)

    now = datetime.now(UTC)
    cutoffs = {
        "job_events": now - timedelta(days=30),
        "ephemeral_snippets": now - timedelta(days=7),
        "snapshots": now - timedelta(days=90),
        "checkpoints": now - timedelta(days=30),
    }

    counts = await repo.sweep_project_retention(ctx, pid, cutoffs)
    assert isinstance(counts, dict)
    assert "job_events" in counts
    assert "evidence_snippets" in counts
    assert "snapshots" in counts
    assert "checkpoints" in counts


@pytest.mark.asyncio
async def test_scheduler_run_retention_sweep_job() -> None:
    """Verify scheduler entry point runs sweep across all projects."""
    with patch(
        "app.workers.scheduler.RetentionService.execute_retention_sweep",
        new_callable=AsyncMock,
    ) as mock_sweep:
        mock_sweep.return_value = [
            RetentionSweepReport(
                project_id=str(generate_uuid7()),
                swept_at=datetime.now(UTC).isoformat(),
                purged_counts={"job_events": 5, "snapshots": 2},
                effective_windows={"job_events": 30},
            )
        ]

        await run_retention_sweep_job()
        mock_sweep.assert_called_once()


def test_retention_api_routes() -> None:
    """Verify REST API routes for workspace and project retention settings."""
    app = create_app()
    client = TestClient(app)

    wid = generate_uuid7()
    pid = generate_uuid7()
    auth_ctx = _make_auth_ctx(workspace_id=wid)
    app.dependency_overrides[get_auth_context] = lambda: auth_ctx

    # 1. GET /api/v1/workspaces/{wid}/retention
    with patch(
        "app.domain.retention.retention_service.RetentionService.get_workspace_retention",
        new_callable=AsyncMock,
    ) as mock_get:
        mock_get.return_value = EffectiveRetentionSummary(
            workspace_id=str(wid),
            categories=[],
        )
        resp = client.get(f"/api/v1/workspaces/{wid}/retention")
        assert resp.status_code == 200
        assert resp.json()["workspace_id"] == str(wid)

    # 2. PUT /api/v1/workspaces/{wid}/retention/{kind}
    with patch(
        "app.domain.retention.retention_service.RetentionService.update_workspace_retention",
        new_callable=AsyncMock,
    ) as mock_upd:
        now_str = datetime.now(UTC).isoformat()
        mock_upd.return_value = RetentionPolicyItem(
            id=str(generate_uuid7()),
            workspace_id=str(wid),
            project_id=None,
            kind="job_events",
            days=15,
            is_override=False,
            created_at=now_str,
            updated_at=now_str,
        )
        resp = client.put(
            f"/api/v1/workspaces/{wid}/retention/job_events",
            json={"days": 15},
        )
        assert resp.status_code == 200
        assert resp.json()["days"] == 15

    # 3. GET /api/v1/projects/{pid}/retention
    with patch(
        "app.domain.retention.retention_service.RetentionService.get_project_retention",
        new_callable=AsyncMock,
    ) as mock_p_get:
        mock_p_get.return_value = EffectiveRetentionSummary(
            workspace_id=str(wid),
            project_id=str(pid),
            categories=[],
        )
        resp = client.get(f"/api/v1/projects/{pid}/retention")
        assert resp.status_code == 200
        assert resp.json()["project_id"] == str(pid)

    # 4. POST /api/v1/projects/{pid}/retention/sweep
    with patch(
        "app.domain.retention.retention_service.RetentionService.execute_retention_sweep",
        new_callable=AsyncMock,
    ) as mock_sweep:
        now_str = datetime.now(UTC).isoformat()
        mock_sweep.return_value = [
            RetentionSweepReport(
                project_id=str(pid),
                swept_at=now_str,
                purged_counts={"job_events": 10},
                effective_windows={"job_events": 30},
            )
        ]
        resp = client.post(f"/api/v1/projects/{pid}/retention/sweep")
        assert resp.status_code == 200
        assert resp.json()["project_id"] == str(pid)
        assert resp.json()["purged_counts"]["job_events"] == 10
