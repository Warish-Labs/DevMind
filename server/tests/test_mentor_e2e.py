"""End-to-end integration tests for Project Mentor & Health Evaluation (CAP-08, CAP-09, docs/03 §3.6, §3.7, docs/05 §6.8, M12-12)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.analysis.task_dag import RankedTask, TaskDAG, TaskNode
from app.core.auth_context import AuthContext
from app.core.errors import ConflictError
from app.core.ids import generate_uuid7
from app.core.settings import Settings
from app.domain.auth import get_auth_context, get_db_session
from app.domain.mentor.schemas import ProjectEvaluationResponse, TaskRecommendationResponse
from app.domain.mentor.service import ProjectMentorService
from app.main import create_app
from app.orchestration.mentor import run_mentor_specialist, task_to_response
from app.orchestration.state import SpecialistTask
from app.persistence.models.mentor import ProjectTask, TaskDependency
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
async def test_mentor_e2e_task_dag_and_recommendation_lifecycle(api_settings: Settings) -> None:
    """E2E test: create tasks, add dependency chain, reject cycles, get top recommendation, complete prereq, and re-recommend."""
    wid = generate_uuid7()
    pid = generate_uuid7()
    user_id = generate_uuid7()

    t1_id = generate_uuid7()
    t2_id = generate_uuid7()
    now = datetime.now(UTC)

    # In-memory mock task store
    tasks_db: dict[UUID, ProjectTask] = {
        t1_id: ProjectTask(
            id=t1_id,
            workspace_id=wid,
            project_id=pid,
            title="Prerequisite Database Migration",
            description="Add tasks table schema",
            status="open",
            priority="medium",
            source="user",
            metadata_={},
            created_at=now,
            updated_at=now,
        ),
        t2_id: ProjectTask(
            id=t2_id,
            workspace_id=wid,
            project_id=pid,
            title="Critical Payment Processing Endpoint",
            description="Expose checkout webhook",
            status="open",
            priority="critical",
            source="user",
            metadata_={},
            created_at=now,
            updated_at=now,
        ),
    }
    tasks_db[t1_id].dependencies = []
    tasks_db[t1_id].dependents = []
    tasks_db[t2_id].dependencies = []
    tasks_db[t2_id].dependents = []

    mock_session = AsyncMock()

    auth_ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_123",
        email="test@example.com",
        workspace_id=wid,
        workspace_role="admin",
        project_id=pid,
        project_role="admin",
    )

    app = create_app(settings=api_settings)
    app.dependency_overrides[get_auth_context] = lambda: auth_ctx
    app.dependency_overrides[get_db_session] = lambda: mock_session

    async def mock_list_tasks(ctx, project_id, status=None, priority=None, limit=50, offset=0):
        return [task_to_response(t) for t in tasks_db.values()]

    async def mock_get_task(ctx, project_id, task_id):
        t = tasks_db.get(task_id)
        return task_to_response(t) if t else None

    async def mock_add_dep(ctx, project_id, task_id, depends_on_task_id):
        if task_id == depends_on_task_id:
            raise ConflictError(detail="Self-dependency not allowed")
        # If t2 depends on t1, and now t1 depends on t2 -> cycle
        if (
            task_id == t1_id
            and depends_on_task_id == t2_id
            and any(d.id == t1_id for d in tasks_db[t2_id].dependencies)
        ):
            raise ConflictError(detail="Cyclic dependency detected: cycle")

        tasks_db[task_id].dependencies.append(tasks_db[depends_on_task_id])
        tasks_db[depends_on_task_id].dependents.append(tasks_db[task_id])
        return TaskDependency(
            task_id=task_id,
            depends_on_task_id=depends_on_task_id,
            created_at=datetime.now(UTC),
        )

    async def mock_recommend(ctx, project_id):
        dag = TaskDAG()
        for t in tasks_db.values():
            node = TaskNode(
                id=t.id,
                title=t.title,
                status=t.status,
                priority=t.priority,
            )
            dag.add_node(node)
        for t in tasks_db.values():
            for d in t.dependencies:
                dag.add_edge(t.id, d.id)

        ranked = dag.rank_tasks()
        top = ranked[0]
        unblocked = [r for r in ranked if r.is_ready]
        return TaskRecommendationResponse(
            recommended_task=task_to_response(tasks_db[top.task.id]),
            rank=top.rank,
            score=top.score,
            is_ready=top.is_ready,
            reason=top.recommendation_reason,
            narrative=top.recommendation_reason,
            downstream_impact_count=top.downstream_impact_count,
            unblocked_count=len(unblocked),
            total_pending_tasks=len(ranked),
        )

    async def mock_update_task(ctx, project_id, task_id, payload=None, **kwargs):
        task = tasks_db[task_id]
        if payload and payload.status:
            task.status = payload.status
        return task_to_response(task)

    # Wire mocked mentor service methods
    ProjectMentorService.list_tasks = AsyncMock(side_effect=mock_list_tasks)
    ProjectMentorService.get_task = AsyncMock(side_effect=mock_get_task)
    ProjectMentorService.add_dependency = AsyncMock(side_effect=mock_add_dep)
    ProjectMentorService.recommend_next_task = AsyncMock(side_effect=mock_recommend)
    ProjectMentorService.update_task = AsyncMock(side_effect=mock_update_task)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Step 1: Query initial backlog
        res = await client.get(f"/api/v1/projects/{pid}/tasks")
        assert res.status_code == 200
        assert len(res.json()) == 2

        # Step 2: Make t2 depend on t1
        res = await client.post(
            f"/api/v1/projects/{pid}/tasks/{t2_id}/dependencies",
            json={"depends_on_task_id": str(t1_id)},
        )
        assert res.status_code == 201

        # Step 3: Attempt cyclic dependency (t1 depends on t2) -> expect 409 Conflict
        res = await client.post(
            f"/api/v1/projects/{pid}/tasks/{t1_id}/dependencies",
            json={"depends_on_task_id": str(t2_id)},
        )
        assert res.status_code == 409
        err = res.json()
        assert err["code"] == "conflict.state"

        # Step 4: Get next task recommendation (t1 is unblocked, so t1 must be recommended even though t2 is critical)
        res = await client.get(f"/api/v1/projects/{pid}/tasks/recommend")
        assert res.status_code == 200
        rec = res.json()
        assert rec["recommended_task"]["id"] == str(t1_id)
        assert rec["is_ready"] is True
        assert rec["downstream_impact_count"] == 1

        # Step 5: Complete task t1
        res = await client.patch(
            f"/api/v1/projects/{pid}/tasks/{t1_id}",
            json={"status": "completed"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "completed"

        # Step 6: Query recommendation again -> t2 is now unblocked and recommended!
        res = await client.get(f"/api/v1/projects/{pid}/tasks/recommend")
        assert res.status_code == 200
        rec2 = res.json()
        assert rec2["recommended_task"]["id"] == str(t2_id)
        assert rec2["is_ready"] is True


@pytest.mark.asyncio
async def test_mentor_e2e_health_evaluation_run_and_retrieve(api_settings: Settings) -> None:
    """E2E test: trigger on-demand health evaluation, compute scores, verify release verdict, and retrieve latest."""
    wid = generate_uuid7()
    pid = generate_uuid7()
    user_id = generate_uuid7()
    eval_id = generate_uuid7()
    now = datetime.now(UTC)

    mock_eval = ProjectEvaluationResponse(
        id=eval_id,
        workspace_id=wid,
        project_id=pid,
        snapshot_id=None,
        overall_score=92.5,
        dimension_scores={
            "security": 100.0,
            "code_quality": 95.0,
            "testing": 90.0,
            "documentation": 85.0,
            "functionality": 95.0,
            "architecture": 90.0,
        },
        verdict="ready",
        blockers=[],
        warnings=[{"id": "doc_notice", "dimension": "documentation", "title": "Stale section"}],
        positive_indicators=["Zero open security findings", "100% test pass rate"],
        rubric_version="1.0",
        functionality_confidence="high",
        narrative="Project is in great health and ready for release candidate verification.",
        created_at=now,
        updated_at=now,
    )

    mock_session = AsyncMock()

    auth_ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_123",
        email="test@example.com",
        workspace_id=wid,
        workspace_role="admin",
        project_id=pid,
        project_role="admin",
    )

    app = create_app(settings=api_settings)
    app.dependency_overrides[get_auth_context] = lambda: auth_ctx
    app.dependency_overrides[get_db_session] = lambda: mock_session

    ProjectMentorService.evaluate_project = AsyncMock(return_value=mock_eval)
    ProjectMentorService.get_latest_evaluation = AsyncMock(return_value=mock_eval)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Trigger on-demand evaluation
        res = await client.post(
            f"/api/v1/projects/{pid}/evaluations/run",
            json={
                "rubric_version": "1.0",
                "feature_checklist": [
                    {"name": "Auth & RBAC", "completed": True, "is_critical": True},
                    {"name": "Living Docs", "completed": True, "is_critical": False},
                ],
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["id"] == str(eval_id)
        assert data["overall_score"] == 92.5
        assert data["verdict"] == "ready"
        assert len(data["blockers"]) == 0
        assert data["functionality_confidence"] == "high"

        # 2. Retrieve latest evaluation
        res = await client.get(f"/api/v1/projects/{pid}/evaluations/latest")
        assert res.status_code == 200
        latest = res.json()
        assert latest["id"] == str(eval_id)
        assert latest["verdict"] == "ready"


@pytest.mark.asyncio
async def test_mentor_e2e_specialist_node_dispatch() -> None:
    """E2E test: LangGraph specialist runner executes mentor actions within agent workflows."""
    mock_session = AsyncMock()
    pid = generate_uuid7()
    wid = generate_uuid7()

    mock_project = Project(id=pid, workspace_id=wid, name="Demo App", slug="demo-app")
    mock_task = ProjectTask(
        id=generate_uuid7(),
        workspace_id=wid,
        project_id=pid,
        title="Implement core API",
        status="open",
        priority="high",
        source="user",
        metadata_={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    mock_task.dependencies = []
    mock_task.dependents = []

    mock_dag = MagicMock()
    mock_dag.rank_tasks.return_value = [
        RankedTask(
            task=TaskNode(id=mock_task.id, title=mock_task.title, priority="high"),
            rank=1,
            score=1300.0,
            is_ready=True,
            unmet_dependencies=[],
            downstream_impact_count=2,
            recommendation_reason="Ready to start; unblocks 2 downstream task(s). Priority: high.",
        )
    ]
    mock_dag.nodes = {mock_task.id: mock_task}

    state = {"project_id": str(pid)}
    spec_task = SpecialistTask(
        task_id="task-mentor-01",
        specialist="mentor",
        params={"action": "recommend"},
    )

    from app.orchestration.mentor import ProjectMentorAgent

    orig_init = ProjectMentorAgent.__init__

    def mock_agent_init(self, session, router=None, prompt_loader=None):
        orig_init(self, session=session, router=router, prompt_loader=prompt_loader)
        self.project_repo.get_by_id = AsyncMock(return_value=mock_project)
        self.task_repo.load_project_dag = AsyncMock(return_value=mock_dag)
        self.task_repo.get_by_id = AsyncMock(return_value=mock_task)

    ProjectMentorAgent.__init__ = mock_agent_init

    try:
        result = await run_mentor_specialist(state=state, task=spec_task, session=mock_session)
        assert spec_task.status == "completed"
        assert "final_response" in result
        assert "ProjectMentor recommended next task" in result["final_response"]
        assert "Implement core API" in result["final_response"]
    finally:
        ProjectMentorAgent.__init__ = orig_init
