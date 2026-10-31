"""Project Task and Dependency repository with cycle prevention (docs/01 CAP-08, docs/03 §3.6)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.analysis.task_dag import CyclicDependencyError, TaskDAG, TaskNode
from app.core.auth_context import AuthContext, SystemContext
from app.persistence.models.mentor import ProjectTask, TaskDependency
from app.persistence.repositories.base import BaseRepository


class ProjectTaskRepository(BaseRepository):
    """Repository managing ProjectTask and TaskDependency persistence with tenant scoping and DAG cycle prevention."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create_task(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        project_id: UUID,
        title: str,
        description: str | None = None,
        status: str = "open",
        priority: str = "medium",
        source: str = "user",
        finding_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        depends_on_ids: list[UUID] | None = None,
    ) -> ProjectTask:
        """Create a new project task and optionally link initial dependencies."""
        self._validate_context(ctx)
        task = ProjectTask(
            workspace_id=workspace_id,
            project_id=project_id,
            title=title,
            description=description,
            status=status,
            priority=priority,
            source=source,
            finding_id=finding_id,
            metadata_=metadata or {},
        )
        self.session.add(task)
        await self.session.flush()

        if depends_on_ids:
            for dep_id in depends_on_ids:
                await self.add_dependency(ctx, task_id=task.id, depends_on_task_id=dep_id)

        # Refresh with loaded dependencies
        return await self.get_by_id(ctx, task.id) or task

    async def get_by_id(
        self,
        ctx: AuthContext | SystemContext,
        task_id: UUID,
    ) -> ProjectTask | None:
        """Retrieve task by ID with dependencies and dependents loaded."""
        self._validate_context(ctx)
        stmt = (
            select(ProjectTask)
            .where(ProjectTask.id == task_id)
            .options(
                selectinload(ProjectTask.dependencies),
                selectinload(ProjectTask.dependents),
                selectinload(ProjectTask.finding),
            )
        )
        stmt = self._scope_workspace_query(stmt, ProjectTask.workspace_id, ctx)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update_task(
        self,
        ctx: AuthContext | SystemContext,
        task_id: UUID,
        *,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProjectTask | None:
        """Update task mutable fields."""
        task = await self.get_by_id(ctx, task_id)
        if not task:
            return None

        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        if status is not None:
            task.status = status
        if priority is not None:
            task.priority = priority
        if metadata is not None:
            task.metadata_ = metadata

        await self.session.flush()
        return task

    async def delete_task(
        self,
        ctx: AuthContext | SystemContext,
        task_id: UUID,
    ) -> bool:
        """Delete task and cascade associated dependency records."""
        task = await self.get_by_id(ctx, task_id)
        if not task:
            return False

        await self.session.delete(task)
        await self.session.flush()
        return True

    async def list_by_project(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        *,
        status: str | None = None,
        priority: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ProjectTask]:
        """List tasks for a project ordered by priority and creation."""
        self._validate_context(ctx)
        stmt = (
            select(ProjectTask)
            .where(ProjectTask.project_id == project_id)
            .options(
                selectinload(ProjectTask.dependencies),
                selectinload(ProjectTask.dependents),
                selectinload(ProjectTask.finding),
            )
            .order_by(desc(ProjectTask.created_at))
            .limit(limit)
            .offset(offset)
        )
        if status:
            stmt = stmt.where(ProjectTask.status == status)
        if priority:
            stmt = stmt.where(ProjectTask.priority == priority)

        stmt = self._scope_workspace_query(stmt, ProjectTask.workspace_id, ctx)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_dependency(
        self,
        ctx: AuthContext | SystemContext,
        task_id: UUID,
        depends_on_task_id: UUID,
    ) -> TaskDependency:
        """Add a dependency relationship after verifying DAG cycle freedom.

        Raises:
            CyclicDependencyError: If adding the dependency would introduce a circular graph cycle.
            ValueError: If either task is not found.
        """
        self._validate_context(ctx)

        # 1. Retrieve both tasks to verify ownership and existence
        task = await self.get_by_id(ctx, task_id)
        depends_on = await self.get_by_id(ctx, depends_on_task_id)

        if not task:
            raise ValueError(f"Task {task_id} not found.")
        if not depends_on:
            raise ValueError(f"Dependency task {depends_on_task_id} not found.")

        # Ensure tasks belong to the same project
        if task.project_id != depends_on.project_id:
            raise ValueError("Cannot link dependencies across different projects.")

        # 2. Check for self-dependency
        if task_id == depends_on_task_id:
            raise CyclicDependencyError(
                cycle_path=[task_id, depends_on_task_id],
                message=f"Task {task_id} cannot depend on itself.",
            )

        # 3. Load full project DAG to perform cycle pre-check
        dag = await self.load_project_dag(ctx, task.project_id)
        # Attempting to add edge in DAG raises CyclicDependencyError if cycle exists
        dag.add_edge(task_id, depends_on_task_id)

        # 4. Check if edge already exists in DB
        stmt = select(TaskDependency).where(
            TaskDependency.task_id == task_id,
            TaskDependency.depends_on_task_id == depends_on_task_id,
        )
        existing = (await self.session.execute(stmt)).scalars().first()
        if existing:
            return existing

        dep = TaskDependency(task_id=task_id, depends_on_task_id=depends_on_task_id)
        self.session.add(dep)
        await self.session.flush()
        return dep

    async def remove_dependency(
        self,
        ctx: AuthContext | SystemContext,
        task_id: UUID,
        depends_on_task_id: UUID,
    ) -> bool:
        """Remove a dependency edge between two tasks."""
        self._validate_context(ctx)
        stmt = delete(TaskDependency).where(
            TaskDependency.task_id == task_id,
            TaskDependency.depends_on_task_id == depends_on_task_id,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return (result.rowcount or 0) > 0

    async def load_project_dag(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
    ) -> TaskDAG:
        """Load all tasks and dependencies for a project into an in-memory TaskDAG."""
        tasks = await self.list_by_project(ctx, project_id, limit=1000)
        dag = TaskDAG()

        for t in tasks:
            finding_sev = None
            if t.finding:
                finding_sev = t.finding.severity

            node = TaskNode(
                id=t.id,
                title=t.title,
                status=t.status,
                priority=t.priority,
                source=t.source,
                finding_id=t.finding_id,
                finding_severity=finding_sev,
                metadata=t.metadata_,
                created_at=t.created_at,
                depends_on={dep.id for dep in t.dependencies},
            )
            dag.add_node(node)

        return dag
