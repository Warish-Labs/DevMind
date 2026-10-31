"""Domain service coordinating Project Mentor tasks, dependency DAG operations, and evaluations (docs/01 CAP-08, CAP-09, docs/03 §3.6, §3.7)."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.task_dag import CyclicDependencyError
from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.domain.mentor.schemas import (
    ProjectEvaluationResponse,
    ProjectEvaluationRunRequest,
    ProjectTaskCreate,
    ProjectTaskResponse,
    ProjectTaskUpdate,
    TaskDependencyResponse,
    TaskRecommendationResponse,
)
from app.llm.prompt_loader import PromptLoader
from app.llm.router import LLMGatewayRouter
from app.orchestration.mentor import (
    ProjectMentorAgent,
    evaluation_to_response,
    task_to_response,
)
from app.persistence.repositories.project_eval_repo import ProjectEvaluationRepository
from app.persistence.repositories.project_repo import ProjectRepository
from app.persistence.repositories.project_task_repo import ProjectTaskRepository

logger = logging.getLogger("devmind.domain.mentor")


class ProjectMentorService:
    """Service handling backlog task lifecycle, DAG dependency validation, and health evaluations."""

    def __init__(
        self,
        session: AsyncSession,
        router: LLMGatewayRouter | None = None,
        prompt_loader: PromptLoader | None = None,
    ) -> None:
        self.session = session
        self.task_repo = ProjectTaskRepository(session)
        self.eval_repo = ProjectEvaluationRepository(session)
        self.project_repo = ProjectRepository(session)
        self.agent = ProjectMentorAgent(
            session=session,
            router=router,
            prompt_loader=prompt_loader,
        )

    async def _verify_project(self, ctx: AuthContext | SystemContext, project_id: UUID) -> None:
        project = await self.project_repo.get_by_id(ctx, project_id)
        if not project:
            raise NotFoundError(detail=f"Project {project_id} not found")

    async def create_task(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        payload: ProjectTaskCreate,
    ) -> ProjectTaskResponse:
        """Create a new project task with optional initial dependencies."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if not project:
            raise NotFoundError(detail=f"Project {project_id} not found")

        try:
            task = await self.task_repo.create_task(
                ctx=ctx,
                workspace_id=project.workspace_id,
                project_id=project_id,
                title=payload.title,
                description=payload.description,
                status="open",
                priority=payload.priority,
                source=payload.source,
                finding_id=payload.finding_id,
                metadata=payload.metadata,
                depends_on_ids=payload.depends_on_ids,
            )
        except CyclicDependencyError as exc:
            raise ConflictError(detail=str(exc)) from exc
        except ValueError as exc:
            raise ValidationError(detail=str(exc)) from exc

        return task_to_response(task)

    async def get_task(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        task_id: UUID,
    ) -> ProjectTaskResponse:
        """Retrieve task by ID verifying project affiliation."""
        await self._verify_project(ctx, project_id)
        task = await self.task_repo.get_by_id(ctx, task_id)
        if not task or task.project_id != project_id:
            raise NotFoundError(detail=f"Task {task_id} not found for project {project_id}")
        return task_to_response(task)

    async def list_tasks(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        *,
        status: str | None = None,
        priority: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ProjectTaskResponse]:
        """List tasks for a project with optional status/priority filters."""
        await self._verify_project(ctx, project_id)
        tasks = await self.task_repo.list_by_project(
            ctx=ctx,
            project_id=project_id,
            status=status,
            priority=priority,
            limit=limit,
            offset=offset,
        )
        return [task_to_response(t) for t in tasks]

    async def update_task(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        task_id: UUID,
        payload: ProjectTaskUpdate,
    ) -> ProjectTaskResponse:
        """Update mutable fields of a project task."""
        await self._verify_project(ctx, project_id)
        task = await self.task_repo.get_by_id(ctx, task_id)
        if not task or task.project_id != project_id:
            raise NotFoundError(detail=f"Task {task_id} not found for project {project_id}")

        updated = await self.task_repo.update_task(
            ctx=ctx,
            task_id=task_id,
            title=payload.title,
            description=payload.description,
            status=payload.status,
            priority=payload.priority,
            metadata=payload.metadata,
        )
        if not updated:
            raise NotFoundError(detail=f"Task {task_id} not found")
        return task_to_response(updated)

    async def delete_task(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        task_id: UUID,
    ) -> bool:
        """Delete a task and its dependency edges."""
        await self._verify_project(ctx, project_id)
        task = await self.task_repo.get_by_id(ctx, task_id)
        if not task or task.project_id != project_id:
            raise NotFoundError(detail=f"Task {task_id} not found for project {project_id}")
        return await self.task_repo.delete_task(ctx, task_id)

    async def add_dependency(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        task_id: UUID,
        depends_on_task_id: UUID,
    ) -> TaskDependencyResponse:
        """Add a dependency relationship after cycle check."""
        await self._verify_project(ctx, project_id)
        try:
            dep = await self.task_repo.add_dependency(
                ctx=ctx,
                task_id=task_id,
                depends_on_task_id=depends_on_task_id,
            )
            return TaskDependencyResponse(
                task_id=dep.task_id,
                depends_on_task_id=dep.depends_on_task_id,
                created_at=dep.created_at,
            )
        except CyclicDependencyError as exc:
            raise ConflictError(detail=str(exc)) from exc
        except ValueError as exc:
            raise ValidationError(detail=str(exc)) from exc

    async def remove_dependency(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        task_id: UUID,
        depends_on_task_id: UUID,
    ) -> bool:
        """Remove a dependency edge."""
        await self._verify_project(ctx, project_id)
        return await self.task_repo.remove_dependency(
            ctx=ctx,
            task_id=task_id,
            depends_on_task_id=depends_on_task_id,
        )

    async def recommend_next_task(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
    ) -> TaskRecommendationResponse:
        """Analyze project task DAG and recommend optimal next task."""
        await self._verify_project(ctx, project_id)
        return await self.agent.recommend_next_task(ctx, project_id)

    async def evaluate_project(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        payload: ProjectEvaluationRunRequest,
    ) -> ProjectEvaluationResponse:
        """Run multidimensional release-readiness evaluation on project."""
        await self._verify_project(ctx, project_id)
        user_id = getattr(ctx, "user_id", None)
        return await self.agent.evaluate_project_health(
            ctx=ctx,
            project_id=project_id,
            snapshot_id=payload.snapshot_id,
            feature_checklist=payload.feature_checklist,
            rubric_version=payload.rubric_version,
            evaluated_by=user_id,
        )

    async def get_latest_evaluation(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
    ) -> ProjectEvaluationResponse:
        """Retrieve the latest health evaluation scorecard for project."""
        await self._verify_project(ctx, project_id)
        latest = await self.eval_repo.get_latest_by_project(ctx, project_id)
        if not latest:
            raise NotFoundError(detail=f"No evaluation records found for project {project_id}")
        return evaluation_to_response(latest)

    async def get_evaluation(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        evaluation_id: UUID,
    ) -> ProjectEvaluationResponse:
        """Retrieve a specific evaluation record by ID."""
        await self._verify_project(ctx, project_id)
        eval_record = await self.eval_repo.get_by_id(ctx, evaluation_id)
        if not eval_record or eval_record.project_id != project_id:
            raise NotFoundError(
                detail=f"Evaluation {evaluation_id} not found for project {project_id}"
            )
        return evaluation_to_response(eval_record)

    async def list_evaluations(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ProjectEvaluationResponse]:
        """List historical evaluations for project."""
        await self._verify_project(ctx, project_id)
        records = await self.eval_repo.list_by_project(
            ctx=ctx,
            project_id=project_id,
            limit=limit,
            offset=offset,
        )
        return [evaluation_to_response(r) for r in records]
