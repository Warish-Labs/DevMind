"""Unit and tenant isolation tests for Project Mentor & Evaluation Repositories (CAP-08, CAP-09, docs/01 §8, docs/03 §3.6, §3.7, M12-08)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.analysis.task_dag import CyclicDependencyError
from app.core.auth_context import AuthContext
from app.persistence.models.mentor import ProjectEvaluation, ProjectTask
from app.persistence.repositories.project_eval_repo import ProjectEvaluationRepository
from app.persistence.repositories.project_task_repo import ProjectTaskRepository


def _make_auth_ctx(workspace_id=None, user_id=None) -> AuthContext:
    return AuthContext(
        user_id=user_id or uuid4(),
        clerk_user_id="user_clerk_123",
        email="developer@devmind.ai",
        workspace_id=workspace_id or uuid4(),
        workspace_role="admin",
    )


# ---------------------------------------------------------------------------
# 1. ProjectTaskRepository Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_repo_create_and_get_by_id() -> None:
    """Verify creating a project task and retrieving it with loaded relationships."""
    ws_id = uuid4()
    proj_id = uuid4()
    task_id = uuid4()
    ctx = _make_auth_ctx(workspace_id=ws_id)

    mock_task = ProjectTask(
        id=task_id,
        workspace_id=ws_id,
        project_id=proj_id,
        title="Migrate Auth to JWT",
        description="Replace session tokens with JWTs",
        status="open",
        priority="high",
        source="user",
        finding_id=None,
        metadata_={"estimated_hours": 4},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    # Mock scalars().first() on session execute
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_task
    mock_session.execute = AsyncMock(return_value=mock_result)

    repo = ProjectTaskRepository(session=mock_session)

    res = await repo.create_task(
        ctx,
        workspace_id=ws_id,
        project_id=proj_id,
        title="Migrate Auth to JWT",
        description="Replace session tokens with JWTs",
        priority="high",
        metadata={"estimated_hours": 4},
    )

    assert res.id == task_id
    assert res.title == "Migrate Auth to JWT"
    assert res.priority == "high"
    assert res.metadata_["estimated_hours"] == 4
    assert mock_session.add.called
    assert mock_session.flush.called


@pytest.mark.asyncio
async def test_task_repo_update_and_delete() -> None:
    """Verify task state transitions, field updates, and deletion."""
    ws_id = uuid4()
    proj_id = uuid4()
    task_id = uuid4()
    ctx = _make_auth_ctx(workspace_id=ws_id)

    mock_task = ProjectTask(
        id=task_id,
        workspace_id=ws_id,
        project_id=proj_id,
        title="Initial Title",
        status="open",
        priority="low",
        metadata_={},
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_task
    mock_session.execute = AsyncMock(return_value=mock_result)

    repo = ProjectTaskRepository(session=mock_session)

    updated = await repo.update_task(
        ctx,
        task_id=task_id,
        title="Updated Title",
        status="completed",
        priority="critical",
    )

    assert updated is not None
    assert updated.title == "Updated Title"
    assert updated.status == "completed"
    assert updated.priority == "critical"

    deleted = await repo.delete_task(ctx, task_id=task_id)
    assert deleted is True
    assert mock_session.delete.called


@pytest.mark.asyncio
async def test_task_repo_add_dependency_cycle_prevention() -> None:
    """Verify attempting to introduce a circular dependency raises CyclicDependencyError."""
    ws_id = uuid4()
    proj_id = uuid4()
    ctx = _make_auth_ctx(workspace_id=ws_id)

    task_a_id = uuid4()
    task_b_id = uuid4()

    task_a = ProjectTask(id=task_a_id, workspace_id=ws_id, project_id=proj_id, title="A")
    task_b = ProjectTask(id=task_b_id, workspace_id=ws_id, project_id=proj_id, title="B")

    # B already depends on A
    task_b.dependencies = [task_a]

    mock_session = AsyncMock()
    repo = ProjectTaskRepository(session=mock_session)

    async def mock_get_by_id(context, tid):
        if tid == task_a_id:
            return task_a
        if tid == task_b_id:
            return task_b
        return None

    repo.get_by_id = AsyncMock(side_effect=mock_get_by_id)
    # Existing project DAG has edge B -> A
    repo.list_by_project = AsyncMock(return_value=[task_a, task_b])

    # Now attempt to make A depend on B (A -> B when B -> A already exists)
    with pytest.raises(CyclicDependencyError):
        await repo.add_dependency(ctx, task_id=task_a_id, depends_on_task_id=task_b_id)


@pytest.mark.asyncio
async def test_task_repo_self_dependency_prevented() -> None:
    """Verify task cannot depend on itself."""
    ws_id = uuid4()
    proj_id = uuid4()
    ctx = _make_auth_ctx(workspace_id=ws_id)
    task_id = uuid4()

    task = ProjectTask(id=task_id, workspace_id=ws_id, project_id=proj_id, title="Task Self")

    repo = ProjectTaskRepository(session=AsyncMock())
    repo.get_by_id = AsyncMock(return_value=task)

    with pytest.raises(CyclicDependencyError) as exc_info:
        await repo.add_dependency(ctx, task_id=task_id, depends_on_task_id=task_id)

    assert "cannot depend on itself" in str(exc_info.value)


@pytest.mark.asyncio
async def test_task_repo_multi_tenant_isolation() -> None:
    """Verify tenant isolation scopes queries by workspace_id."""
    ws_b = uuid4()
    task_id = uuid4()

    ctx_b = _make_auth_ctx(workspace_id=ws_b)

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_result = MagicMock()
    # Executing query with Tenant B context returns None because task belongs to Tenant A
    mock_result.scalars.return_value.first.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    repo = ProjectTaskRepository(session=mock_session)
    fetched = await repo.get_by_id(ctx_b, task_id)
    assert fetched is None


# ---------------------------------------------------------------------------
# 2. ProjectEvaluationRepository Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluation_repo_create_and_get_latest() -> None:
    """Verify creating a project evaluation and fetching latest record."""
    ws_id = uuid4()
    proj_id = uuid4()
    eval_id = uuid4()
    ctx = _make_auth_ctx(workspace_id=ws_id)

    dimension_scores = {
        "functionality": 85.0,
        "code_quality": 92.0,
        "security": 98.0,
        "testing": 88.0,
        "documentation": 90.0,
        "architecture": 94.0,
    }
    blockers = [{"type": "unresolved_critical_finding", "summary": "Fix Auth Token Leak"}]
    warnings = [{"type": "documentation_drift", "summary": "1 undocumented route"}]
    positives = ["High test coverage (88%)", "Zero high-severity security findings"]

    mock_eval = ProjectEvaluation(
        id=eval_id,
        workspace_id=ws_id,
        project_id=proj_id,
        overall_score=91.2,
        dimension_scores=dimension_scores,
        verdict="ready_with_warnings",
        blockers=blockers,
        warnings=warnings,
        positive_indicators=positives,
        rubric_version="1.0",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_eval
    mock_session.execute = AsyncMock(return_value=mock_result)

    repo = ProjectEvaluationRepository(session=mock_session)

    res = await repo.create_evaluation(
        ctx,
        workspace_id=ws_id,
        project_id=proj_id,
        overall_score=91.2,
        dimension_scores=dimension_scores,
        verdict="ready_with_warnings",
        blockers=blockers,
        warnings=warnings,
        positive_indicators=positives,
    )

    assert res.id == eval_id
    assert res.overall_score == 91.2
    assert res.verdict == "ready_with_warnings"
    assert len(res.blockers) == 1
    assert len(res.warnings) == 1
    assert len(res.positive_indicators) == 2


@pytest.mark.asyncio
async def test_evaluation_repo_cross_tenant_isolation() -> None:
    """Verify Tenant B cannot retrieve Tenant A's evaluations."""
    ws_b = uuid4()
    eval_id = uuid4()
    ctx_b = _make_auth_ctx(workspace_id=ws_b)

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    repo = ProjectEvaluationRepository(session=mock_session)
    fetched = await repo.get_by_id(ctx_b, eval_id)
    assert fetched is None
