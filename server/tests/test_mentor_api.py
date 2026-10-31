"""REST API integration tests for Project Mentor tasks, dependencies, recommendations, and evaluations (docs/01 CAP-08, CAP-09, docs/03 §3.6, §3.7)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth_context import AuthContext
from app.core.ids import generate_uuid7
from app.core.settings import Settings
from app.domain.auth import get_auth_context, get_db_session
from app.domain.mentor.service import ProjectMentorService
from app.main import create_app
from app.persistence.models.mentor import ProjectTask


@pytest.fixture
def api_settings() -> Settings:
    return Settings(
        env="test",
        github_client_id="test_github_client_id",
        github_client_secret="test_github_client_secret",
        encryption_keys=["c3VwZXJfc2VjcmV0X2tleV9mb3JfdGVzdF8zMmJ5dGVzIQ=="],
    )


@pytest.mark.asyncio
async def test_api_tasks_crud_and_recommendation(api_settings: Settings) -> None:
    """Verify task creation, listing, retrieval, update, deletion, and recommendation API endpoints."""
    app = create_app(settings=api_settings)

    wid = generate_uuid7()
    pid = generate_uuid7()
    user_id = generate_uuid7()
    task_id = generate_uuid7()
    now = datetime.now(UTC)

    mock_task = ProjectTask(
        id=task_id,
        workspace_id=wid,
        project_id=pid,
        title="Setup Auth",
        description="Configure Clerk",
        status="open",
        priority="high",
        source="user",
        metadata_={},
        created_at=now,
        updated_at=now,
    )
    mock_task.dependencies = []
    mock_task.dependents = []

    mock_session = AsyncMock()

    auth_ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_123",
        email="test@example.com",
        workspace_id=wid,
        workspace_role="admin",
        project_id=pid,
        project_role="maintainer",
        permissions=frozenset(
            {
                "project:read",
                "project:update",
                "analysis:create",
            }
        ),
    )

    app.dependency_overrides[get_auth_context] = lambda: auth_ctx
    app.dependency_overrides[get_db_session] = lambda: mock_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Mock ProjectMentorService methods
        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            # 1. Create task
            mp.setattr(
                ProjectMentorService,
                "create_task",
                AsyncMock(
                    return_value=MagicMock(
                        id=task_id,
                        workspace_id=wid,
                        project_id=pid,
                        title="Setup Auth",
                        description="Configure Clerk",
                        status="open",
                        priority="high",
                        source="user",
                        finding_id=None,
                        metadata={},
                        depends_on_ids=[],
                        dependent_ids=[],
                        created_at=now,
                        updated_at=now,
                    )
                ),
            )
            create_resp = await client.post(
                f"/api/v1/projects/{pid}/tasks",
                json={
                    "title": "Setup Auth",
                    "description": "Configure Clerk",
                    "priority": "high",
                },
            )
            assert create_resp.status_code == 201
            data = create_resp.json()
            assert data["id"] == str(task_id)
            assert data["title"] == "Setup Auth"

            # 2. List tasks
            mp.setattr(
                ProjectMentorService,
                "list_tasks",
                AsyncMock(
                    return_value=[
                        MagicMock(
                            id=task_id,
                            workspace_id=wid,
                            project_id=pid,
                            title="Setup Auth",
                            description="Configure Clerk",
                            status="open",
                            priority="high",
                            source="user",
                            finding_id=None,
                            metadata={},
                            depends_on_ids=[],
                            dependent_ids=[],
                            created_at=now,
                            updated_at=now,
                        )
                    ]
                ),
            )
            list_resp = await client.get(f"/api/v1/projects/{pid}/tasks")
            assert list_resp.status_code == 200
            tasks_list = list_resp.json()
            assert len(tasks_list) == 1
            assert tasks_list[0]["id"] == str(task_id)

            # 3. Recommend next task
            mock_rec = MagicMock(
                recommended_task=MagicMock(
                    id=task_id,
                    workspace_id=wid,
                    project_id=pid,
                    title="Setup Auth",
                    description="Configure Clerk",
                    status="open",
                    priority="high",
                    source="user",
                    finding_id=None,
                    metadata={},
                    depends_on_ids=[],
                    dependent_ids=[],
                    created_at=now,
                    updated_at=now,
                ),
                rank=1,
                score=350.0,
                is_ready=True,
                downstream_impact_count=2,
                reason="Top priority unblocked item.",
                narrative="Focus on auth setup first.",
                unblocked_count=1,
                total_pending_tasks=1,
            )
            mp.setattr(
                ProjectMentorService, "recommend_next_task", AsyncMock(return_value=mock_rec)
            )
            rec_resp = await client.get(f"/api/v1/projects/{pid}/tasks/recommend")
            assert rec_resp.status_code == 200
            rec_data = rec_resp.json()
            assert rec_data["rank"] == 1
            assert rec_data["recommended_task"]["title"] == "Setup Auth"
            assert rec_data["downstream_impact_count"] == 2

            # 4. Get task detail
            mp.setattr(
                ProjectMentorService,
                "get_task",
                AsyncMock(
                    return_value=MagicMock(
                        id=task_id,
                        workspace_id=wid,
                        project_id=pid,
                        title="Setup Auth",
                        description="Configure Clerk",
                        status="open",
                        priority="high",
                        source="user",
                        finding_id=None,
                        metadata={},
                        depends_on_ids=[],
                        dependent_ids=[],
                        created_at=now,
                        updated_at=now,
                    )
                ),
            )
            detail_resp = await client.get(f"/api/v1/projects/{pid}/tasks/{task_id}")
            assert detail_resp.status_code == 200
            assert detail_resp.json()["id"] == str(task_id)

            # 5. Update task
            mp.setattr(
                ProjectMentorService,
                "update_task",
                AsyncMock(
                    return_value=MagicMock(
                        id=task_id,
                        workspace_id=wid,
                        project_id=pid,
                        title="Setup Auth & MFA",
                        description="Configure Clerk",
                        status="in_progress",
                        priority="critical",
                        source="user",
                        finding_id=None,
                        metadata={},
                        depends_on_ids=[],
                        dependent_ids=[],
                        created_at=now,
                        updated_at=now,
                    )
                ),
            )
            patch_resp = await client.patch(
                f"/api/v1/projects/{pid}/tasks/{task_id}",
                json={"title": "Setup Auth & MFA", "status": "in_progress", "priority": "critical"},
            )
            assert patch_resp.status_code == 200
            assert patch_resp.json()["title"] == "Setup Auth & MFA"
            assert patch_resp.json()["status"] == "in_progress"

            # 6. Delete task
            mp.setattr(ProjectMentorService, "delete_task", AsyncMock(return_value=True))
            del_resp = await client.delete(f"/api/v1/projects/{pid}/tasks/{task_id}")
            assert del_resp.status_code == 204


@pytest.mark.asyncio
async def test_api_task_dependencies_and_cycle_prevention(api_settings: Settings) -> None:
    """Verify linking task dependencies and catching circular dependency cycles (409 Conflict)."""
    app = create_app(settings=api_settings)

    wid = generate_uuid7()
    pid = generate_uuid7()
    user_id = generate_uuid7()
    task_a = generate_uuid7()
    task_b = generate_uuid7()
    now = datetime.now(UTC)

    mock_session = AsyncMock()
    auth_ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_123",
        email="test@example.com",
        workspace_id=wid,
        workspace_role="admin",
        project_id=pid,
        project_role="maintainer",
        permissions=frozenset({"project:read", "project:update"}),
    )

    app.dependency_overrides[get_auth_context] = lambda: auth_ctx
    app.dependency_overrides[get_db_session] = lambda: mock_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with pytest.MonkeyPatch.context() as mp:
            # 1. Add valid dependency
            mp.setattr(
                ProjectMentorService,
                "add_dependency",
                AsyncMock(
                    return_value=MagicMock(
                        task_id=task_b,
                        depends_on_task_id=task_a,
                        created_at=now,
                    )
                ),
            )
            dep_resp = await client.post(
                f"/api/v1/projects/{pid}/tasks/{task_b}/dependencies",
                json={"depends_on_task_id": str(task_a)},
            )
            assert dep_resp.status_code == 201
            assert dep_resp.json()["task_id"] == str(task_b)
            assert dep_resp.json()["depends_on_task_id"] == str(task_a)

            # 2. Add cyclic dependency -> raises ConflictError (409)
            from app.core.errors import ConflictError

            mp.setattr(
                ProjectMentorService,
                "add_dependency",
                AsyncMock(
                    side_effect=ConflictError(
                        detail="Cyclic dependency detected: task_a -> task_b -> task_a"
                    )
                ),
            )
            cycle_resp = await client.post(
                f"/api/v1/projects/{pid}/tasks/{task_a}/dependencies",
                json={"depends_on_task_id": str(task_b)},
            )
            assert cycle_resp.status_code == 409
            assert "Cyclic dependency" in cycle_resp.json()["detail"]

            # 3. Remove dependency
            mp.setattr(ProjectMentorService, "remove_dependency", AsyncMock(return_value=True))
            del_dep_resp = await client.delete(
                f"/api/v1/projects/{pid}/tasks/{task_b}/dependencies/{task_a}"
            )
            assert del_dep_resp.status_code == 204


@pytest.mark.asyncio
async def test_api_project_evaluations(api_settings: Settings) -> None:
    """Verify running evaluations, retrieving latest scorecard, and listing historical evaluations."""
    app = create_app(settings=api_settings)

    wid = generate_uuid7()
    pid = generate_uuid7()
    user_id = generate_uuid7()
    eval_id = generate_uuid7()
    now = datetime.now(UTC)

    mock_session = AsyncMock()
    auth_ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_123",
        email="test@example.com",
        workspace_id=wid,
        workspace_role="admin",
        project_id=pid,
        project_role="maintainer",
        permissions=frozenset({"project:read", "project:update", "analysis:create"}),
    )

    app.dependency_overrides[get_auth_context] = lambda: auth_ctx
    app.dependency_overrides[get_db_session] = lambda: mock_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with pytest.MonkeyPatch.context() as mp:
            mock_eval_response = MagicMock(
                id=eval_id,
                workspace_id=wid,
                project_id=pid,
                snapshot_id=None,
                overall_score=92.0,
                dimension_scores={
                    "security": 100.0,
                    "code_quality": 90.0,
                    "testing": 85.0,
                    "documentation": 95.0,
                    "functionality": 90.0,
                    "architecture": 100.0,
                },
                verdict="ready",
                blockers=[],
                warnings=[{"title": "Low test coverage"}],
                positive_indicators=["Zero open vulnerabilities"],
                rubric_version="1.0",
                functionality_confidence="high",
                narrative="Excellent release readiness score.",
                evaluated_by=user_id,
                created_at=now,
                updated_at=now,
            )

            # 1. Run evaluation
            mp.setattr(
                ProjectMentorService, "evaluate_project", AsyncMock(return_value=mock_eval_response)
            )
            run_resp = await client.post(
                f"/api/v1/projects/{pid}/evaluations/run",
                json={
                    "feature_checklist": [
                        {"name": "Core Auth", "completed": True, "is_critical": True}
                    ],
                },
            )
            assert run_resp.status_code == 201
            eval_data = run_resp.json()
            assert eval_data["id"] == str(eval_id)
            assert eval_data["overall_score"] == 92.0
            assert eval_data["verdict"] == "ready"
            assert eval_data["dimension_scores"]["security"] == 100.0

            # 2. Get latest evaluation
            mp.setattr(
                ProjectMentorService,
                "get_latest_evaluation",
                AsyncMock(return_value=mock_eval_response),
            )
            latest_resp = await client.get(f"/api/v1/projects/{pid}/evaluations/latest")
            assert latest_resp.status_code == 200
            assert latest_resp.json()["overall_score"] == 92.0

            # 3. Get evaluation by ID
            mp.setattr(
                ProjectMentorService, "get_evaluation", AsyncMock(return_value=mock_eval_response)
            )
            detail_resp = await client.get(f"/api/v1/projects/{pid}/evaluations/{eval_id}")
            assert detail_resp.status_code == 200
            assert detail_resp.json()["id"] == str(eval_id)

            # 4. List evaluations
            mp.setattr(
                ProjectMentorService,
                "list_evaluations",
                AsyncMock(return_value=[mock_eval_response]),
            )
            list_resp = await client.get(f"/api/v1/projects/{pid}/evaluations")
            assert list_resp.status_code == 200
            evals_list = list_resp.json()
            assert len(evals_list) == 1
            assert evals_list[0]["id"] == str(eval_id)
