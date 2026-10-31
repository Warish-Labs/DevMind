"""Unit tests for Project Mentor specialist agent and LangGraph workflow (docs/01 CAP-08, CAP-09, docs/05 §6.8)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.auth_context import SystemContext
from app.core.ids import generate_uuid7
from app.llm.models import LLMGenerationResponse
from app.orchestration.mentor import (
    ProjectMentorAgent,
    run_mentor_specialist,
)
from app.orchestration.state import SpecialistTask
from app.persistence.models.mentor import ProjectEvaluation, ProjectTask
from app.persistence.models.project import Project


@pytest.fixture
def test_ctx() -> SystemContext:
    return SystemContext(reason="Project Mentor unit test")


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.mark.asyncio
async def test_recommend_next_task_empty_backlog(
    mock_session: AsyncMock,
    test_ctx: SystemContext,
) -> None:
    """Verify mentor returns an informative message when backlog has no pending tasks."""
    agent = ProjectMentorAgent(session=mock_session)
    pid = generate_uuid7()

    mock_project = Project(
        id=pid, workspace_id=generate_uuid7(), name="Test Project", slug="test-proj"
    )
    agent.project_repo.get_by_id = AsyncMock(return_value=mock_project)
    agent.task_repo.load_project_dag = AsyncMock()
    mock_dag = MagicMock()
    mock_dag.rank_tasks.return_value = []
    agent.task_repo.load_project_dag.return_value = mock_dag

    resp = await agent.recommend_next_task(test_ctx, pid)

    assert resp.recommended_task is None
    assert resp.rank == 0
    assert resp.total_pending_tasks == 0
    assert "No active or pending tasks" in resp.reason


@pytest.mark.asyncio
async def test_recommend_next_task_with_dependencies_deterministic(
    mock_session: AsyncMock,
    test_ctx: SystemContext,
) -> None:
    """Verify topological DAG ranking prioritizes unblocked tasks and calculates downstream impact."""
    agent = ProjectMentorAgent(session=mock_session)
    pid = generate_uuid7()
    wid = generate_uuid7()

    task1_id = generate_uuid7()
    task2_id = generate_uuid7()

    mock_project = Project(id=pid, workspace_id=wid, name="Test Project", slug="test-proj")
    agent.project_repo.get_by_id = AsyncMock(return_value=mock_project)

    # Task 1 (DB model)
    task1_db = ProjectTask(
        id=task1_id,
        workspace_id=wid,
        project_id=pid,
        title="Setup Database Migrations",
        status="open",
        priority="critical",
        source="user",
    )
    task1_db.dependencies = []
    task1_db.dependents = []

    # Mock TaskDAG
    mock_dag = MagicMock()
    mock_ranked_1 = MagicMock()
    mock_ranked_1.task.id = task1_id
    mock_ranked_1.task.title = "Setup Database Migrations"
    mock_ranked_1.task.priority = "critical"
    mock_ranked_1.rank = 1
    mock_ranked_1.score = 420.0
    mock_ranked_1.is_ready = True
    mock_ranked_1.downstream_impact_count = 2
    mock_ranked_1.recommendation_reason = (
        "Critical prerequisite task unblocking 2 downstream work items."
    )

    mock_ranked_2 = MagicMock()
    mock_ranked_2.task.id = task2_id
    mock_ranked_2.task.title = "Implement User Profile API"
    mock_ranked_2.task.priority = "high"
    mock_ranked_2.rank = 2
    mock_ranked_2.score = 300.0
    mock_ranked_2.is_ready = False
    mock_ranked_2.unmet_dependencies = [task1_id]
    mock_ranked_2.downstream_impact_count = 0
    mock_ranked_2.recommendation_reason = "Blocked by 1 unmet prerequisite task."

    mock_dag.rank_tasks.return_value = [mock_ranked_1, mock_ranked_2]
    agent.task_repo.load_project_dag = AsyncMock(return_value=mock_dag)
    agent.task_repo.get_by_id = AsyncMock(return_value=task1_db)

    resp = await agent.recommend_next_task(test_ctx, pid)

    assert resp.recommended_task is not None
    assert resp.recommended_task.id == task1_id
    assert resp.recommended_task.title == "Setup Database Migrations"
    assert resp.rank == 1
    assert resp.is_ready is True
    assert resp.downstream_impact_count == 2
    assert resp.unblocked_count == 1
    assert resp.total_pending_tasks == 2
    assert "Setup Database Migrations" in resp.narrative


@pytest.mark.asyncio
async def test_recommend_next_task_with_llm_narrative(
    mock_session: AsyncMock,
    test_ctx: SystemContext,
) -> None:
    """Verify LLM narrative is invoked and parsed when router is available."""
    mock_router = AsyncMock()
    mock_prompt_loader = MagicMock()
    mock_prompt_loader.load.return_value = MagicMock(
        messages=[{"role": "user", "content": "test"}],
        system_instruction="System",
    )

    llm_payload = {
        "summary": "Setup Database Migrations",
        "recommended_action": "Run alembic upgrade head",
        "rationale": "Setting up core migrations stabilizes schema evolution.",
        "confidence": 0.95,
    }
    mock_router.generate.return_value = LLMGenerationResponse(
        content=json.dumps(llm_payload),
        finish_reason="stop",
        provider_id="google",
        model_id="gemini-2.5-flash",
    )

    agent = ProjectMentorAgent(
        session=mock_session,
        router=mock_router,
        prompt_loader=mock_prompt_loader,
    )
    pid = generate_uuid7()
    wid = generate_uuid7()
    task_id = generate_uuid7()

    agent.project_repo.get_by_id = AsyncMock(
        return_value=Project(id=pid, workspace_id=wid, name="Test", slug="test")
    )
    task_db = ProjectTask(
        id=task_id,
        workspace_id=wid,
        project_id=pid,
        title="Setup Migrations",
        status="open",
        priority="high",
        source="user",
    )
    task_db.dependencies = []
    task_db.dependents = []

    mock_dag = MagicMock()
    mock_ranked = MagicMock()
    mock_ranked.task.id = task_id
    mock_ranked.task.title = "Setup Migrations"
    mock_ranked.task.priority = "high"
    mock_ranked.rank = 1
    mock_ranked.score = 300.0
    mock_ranked.is_ready = True
    mock_ranked.downstream_impact_count = 1
    mock_ranked.recommendation_reason = "High priority."
    mock_dag.rank_tasks.return_value = [mock_ranked]

    agent.task_repo.load_project_dag = AsyncMock(return_value=mock_dag)
    agent.task_repo.get_by_id = AsyncMock(return_value=task_db)

    resp = await agent.recommend_next_task(test_ctx, pid)

    assert resp.recommended_task is not None
    assert "Setting up core migrations" in resp.narrative
    assert "Run alembic upgrade head" in resp.narrative
    assert mock_router.generate.called


@pytest.mark.asyncio
async def test_evaluate_project_health_scoring_and_persistence(
    mock_session: AsyncMock,
    test_ctx: SystemContext,
) -> None:
    """Verify evaluate_project_health aggregates signals, computes dimensions, and saves scorecard."""
    agent = ProjectMentorAgent(session=mock_session)
    pid = generate_uuid7()
    wid = generate_uuid7()
    eval_id = generate_uuid7()

    mock_project = Project(id=pid, workspace_id=wid, name="Test Project", slug="test-proj")
    agent.project_repo.get_by_id = AsyncMock(return_value=mock_project)

    # Empty signals
    agent.task_repo.list_by_project = AsyncMock(return_value=[])
    mock_dag = MagicMock()
    mock_dag.detect_cycles.return_value = []
    agent.task_repo.load_project_dag = AsyncMock(return_value=mock_dag)
    agent.brain_repo.list_findings = AsyncMock(return_value=[])
    agent.bug_repo.list_by_project = AsyncMock(return_value=[])
    agent.living_doc_repo.list_documents_by_project = AsyncMock(return_value=[MagicMock()])
    agent.living_doc_repo.list_drift_items_by_project = AsyncMock(return_value=[])

    # Mock eval repo persistence
    mock_eval_record = ProjectEvaluation(
        id=eval_id,
        workspace_id=wid,
        project_id=pid,
        overall_score=94.5,
        dimension_scores={
            "security": 100.0,
            "code_quality": 100.0,
            "testing": 85.0,
            "documentation": 100.0,
            "functionality": 90.0,
            "architecture": 100.0,
            "narrative": "Healthy baseline.",
            "functionality_confidence": "high",
        },
        verdict="ready_with_warnings",
        blockers=[],
        warnings=[{"title": "No CI test execution recorded"}],
        positive_indicators=["Zero open security findings detected"],
        rubric_version="1.0",
    )
    agent.eval_repo.create_evaluation = AsyncMock(return_value=mock_eval_record)

    resp = await agent.evaluate_project_health(
        ctx=test_ctx,
        project_id=pid,
        feature_checklist=[{"name": "Auth flow", "completed": True}],
    )

    assert resp.id == eval_id
    assert resp.overall_score == 94.5
    assert resp.verdict == "ready_with_warnings"
    assert resp.functionality_confidence == "high"
    assert resp.dimension_scores["security"] == 100.0
    assert len(resp.warnings) == 1
    assert agent.eval_repo.create_evaluation.called


@pytest.mark.asyncio
async def test_run_mentor_specialist_node(mock_session: AsyncMock) -> None:
    """Verify run_mentor_specialist handles recommend and evaluate actions in RunState."""
    pid = str(generate_uuid7())
    wid = generate_uuid7()

    # State
    state = {
        "run_id": "run_12345678",
        "project_id": pid,
        "workspace_id": str(wid),
    }

    # Test recommend action
    task_rec = SpecialistTask(
        specialist="mentor",
        task_id="mentor_task_rec",
        status="pending",
        params={"action": "recommend"},
    )

    # Patch inside ProjectMentorAgent
    with (
        pytest.MonkeyPatch.context() as mp,
    ):
        mock_rec_response = MagicMock()
        mock_rec_response.recommended_task = MagicMock(title="Fix Bug", priority="high")
        mock_rec_response.rank = 1
        mock_rec_response.narrative = "Focus on fixing this bug first."

        mp.setattr(
            ProjectMentorAgent,
            "recommend_next_task",
            AsyncMock(return_value=mock_rec_response),
        )

        result = await run_mentor_specialist(
            state=state,
            task=task_rec,
            session=mock_session,
        )

        assert task_rec.status == "completed"
        assert "Fix Bug" in result["final_response"]
        assert len(result["plan"]) == 1
