"""Deterministic Topological Dependency DAG Sorter and Cycle Detector for Project Mentor (docs/01 CAP-08, docs/03 §3.6)."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

PRIORITY_WEIGHTS: dict[str, int] = {
    "critical": 400,
    "high": 300,
    "medium": 200,
    "low": 100,
}

FINDING_SEVERITY_WEIGHTS: dict[str, int] = {
    "CRITICAL": 40,
    "HIGH": 30,
    "MEDIUM": 20,
    "LOW": 10,
    "INFO": 0,
}


class CyclicDependencyError(ValueError):
    """Raised when a task dependency creates a cycle in the task graph."""

    def __init__(self, cycle_path: list[UUID] | None = None, message: str | None = None) -> None:
        self.cycle_path = cycle_path or []
        detail = (
            message or f"Cyclic dependency detected: {' -> '.join(str(p) for p in self.cycle_path)}"
        )
        super().__init__(detail)


@dataclass
class TaskNode:
    """In-memory representation of a task node for DAG traversal and ranking."""

    id: UUID
    title: str
    status: str = "open"  # open, in_progress, blocked, completed, cancelled
    priority: str = "medium"  # critical, high, medium, low
    source: str = "user"  # user, agent, finding
    finding_id: UUID | None = None
    finding_severity: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    depends_on: set[UUID] = field(default_factory=set)

    @property
    def is_terminal(self) -> bool:
        """Completed or cancelled tasks are resolved/terminal."""
        return self.status in {"completed", "cancelled"}


@dataclass
class RankedTask:
    """Output item of task ranking with calculated score and blocking explanation."""

    task: TaskNode
    rank: int
    score: float
    is_ready: bool
    unmet_dependencies: list[UUID]
    downstream_impact_count: int
    recommendation_reason: str


class TaskDAG:
    """Directed Acyclic Graph manager for project tasks and dependencies."""

    def __init__(self) -> None:
        self.nodes: dict[UUID, TaskNode] = {}
        # Forward edges: task_id -> set of task_ids that task_id depends on
        self.dependencies: dict[UUID, set[UUID]] = defaultdict(set)
        # Reverse edges: dependency_id -> set of task_ids that depend on dependency_id
        self.dependents: dict[UUID, set[UUID]] = defaultdict(set)

    def add_node(self, node: TaskNode) -> None:
        """Register a task node in the graph."""
        self.nodes[node.id] = node
        for dep in node.depends_on:
            self.add_edge(node.id, dep)

    def add_edge(self, task_id: UUID, depends_on_id: UUID) -> None:
        """Add a dependency edge where task_id depends on depends_on_id.

        Raises:
            CyclicDependencyError: If adding the edge creates a cycle or self-dependency.
        """
        if task_id == depends_on_id:
            raise CyclicDependencyError(
                cycle_path=[task_id, depends_on_id],
                message=f"Task {task_id} cannot depend on itself.",
            )

        # Check if adding this edge forms a cycle:
        # A cycle forms if there is already a path from task_id to depends_on_id
        cycle_path = self._find_path(depends_on_id, task_id)
        if cycle_path is not None:
            full_cycle = [task_id] + cycle_path
            raise CyclicDependencyError(
                cycle_path=full_cycle,
                message=f"Adding dependency from {task_id} to {depends_on_id} creates a cycle: {' -> '.join(str(p) for p in full_cycle)}",
            )

        self.dependencies[task_id].add(depends_on_id)
        self.dependents[depends_on_id].add(task_id)
        if task_id in self.nodes:
            self.nodes[task_id].depends_on.add(depends_on_id)

    def _find_path(self, start: UUID, target: UUID) -> list[UUID] | None:
        """Breadth-first search to find directed dependency path from start to target."""
        if start == target:
            return [start]
        visited: set[UUID] = set()
        queue: deque[tuple[UUID, list[UUID]]] = deque([(start, [start])])

        while queue:
            current, path = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            for dep in self.dependencies.get(current, set()):
                if dep == target:
                    return path + [dep]
                if dep not in visited:
                    queue.append((dep, path + [dep]))

        return None

    def detect_cycle(self) -> list[UUID] | None:
        """Detect any cycle across the entire graph using depth-first search.

        Returns:
            list[UUID] of cycle path if found, None otherwise.
        """
        visited: set[UUID] = set()
        rec_stack: dict[UUID, int] = {}
        current_path: list[UUID] = []

        def dfs(node_id: UUID) -> list[UUID] | None:
            visited.add(node_id)
            rec_stack[node_id] = len(current_path)
            current_path.append(node_id)

            for dep_id in self.dependencies.get(node_id, set()):
                if dep_id not in visited:
                    cycle = dfs(dep_id)
                    if cycle:
                        return cycle
                elif dep_id in rec_stack:
                    idx = rec_stack[dep_id]
                    return current_path[idx:] + [dep_id]

            current_path.pop()
            del rec_stack[node_id]
            return None

        for n_id in self.nodes:
            if n_id not in visited:
                cycle = dfs(n_id)
                if cycle:
                    return cycle

        return None

    def topological_sort(self) -> list[UUID]:
        """Compute topological ordering using Kahn's algorithm (prerequisites first).

        Returns:
            Ordered list of task UUIDs where dependencies appear before dependents.

        Raises:
            CyclicDependencyError: If a cycle exists.
        """
        in_degree: dict[UUID, int] = {
            n_id: len(self.dependencies.get(n_id, set())) for n_id in self.nodes
        }
        queue: deque[UUID] = deque([n_id for n_id, deg in in_degree.items() if deg == 0])
        ordered: list[UUID] = []

        while queue:
            node_id = queue.popleft()
            ordered.append(node_id)

            for dependent_id in self.dependents.get(node_id, set()):
                if dependent_id in in_degree:
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        queue.append(dependent_id)

        if len(ordered) != len(self.nodes):
            cycle = self.detect_cycle()
            raise CyclicDependencyError(cycle_path=cycle or [])

        return ordered

    def count_downstream_dependents(self, task_id: UUID) -> int:
        """Compute the total number of transitive downstream tasks that depend on this task."""
        visited: set[UUID] = set()
        queue: deque[UUID] = deque([task_id])

        while queue:
            curr = queue.popleft()
            for dep in self.dependents.get(curr, set()):
                if dep not in visited and dep in self.nodes:
                    visited.add(dep)
                    queue.append(dep)

        return len(visited)

    def rank_tasks(self) -> list[RankedTask]:
        """Deterministically rank pending tasks by readiness, priority, severity, and dependency impact.

        Ranking hierarchy:
        1. Ready vs Blocked: An unblocked task (whose prerequisites are completed) strictly outranks blocked tasks.
        2. Priority weight: critical (400) > high (300) > medium (200) > low (100).
        3. Finding severity weight: CRITICAL (40) > HIGH (30) > MEDIUM (20) > LOW (10) > INFO (0).
        4. Downstream blast radius: tasks blocking multiple dependents receive a bonus.
        5. Temporal tie-breaker: FIFO by created_at.
        """
        pending_nodes = [node for node in self.nodes.values() if not node.is_terminal]
        scored_items: list[tuple[float, bool, TaskNode, list[UUID], int, str]] = []

        for node in pending_nodes:
            # Check which dependencies are unmet (not completed)
            unmet: list[UUID] = []
            for dep_id in self.dependencies.get(node.id, set()):
                dep_node = self.nodes.get(dep_id)
                # If dependency is missing from graph or not completed, it is unmet
                if dep_node is None or dep_node.status != "completed":
                    unmet.append(dep_id)

            is_ready = len(unmet) == 0
            downstream_count = self.count_downstream_dependents(node.id)

            # Base score
            score = 0.0
            if is_ready:
                score += 1000.0  # Ready bonus ensures unblocked tasks precede blocked tasks

            score += PRIORITY_WEIGHTS.get(node.priority.lower(), 200)
            if node.finding_severity:
                score += FINDING_SEVERITY_WEIGHTS.get(node.finding_severity.upper(), 0)

            # Downstream unblocking multiplier (each blocked dependent adds 15 points)
            score += downstream_count * 15.0

            # Formulate recommendation explanation
            if is_ready:
                if downstream_count > 0:
                    reason = f"Ready to start; unblocks {downstream_count} downstream task(s). Priority: {node.priority}."
                else:
                    reason = (
                        f"Ready to start with no blocking prerequisites. Priority: {node.priority}."
                    )
            else:
                dep_titles = [self.nodes[uid].title for uid in unmet if uid in self.nodes]
                reason = f"Blocked by {len(unmet)} incomplete prerequisite(s): {', '.join(dep_titles[:3])}."

            scored_items.append((score, is_ready, node, unmet, downstream_count, reason))

        # Sort descending by score, tie-break by created_at ascending
        def sort_key(
            item: tuple[float, bool, TaskNode, list[UUID], int, str],
        ) -> tuple[float, float]:
            score_val = item[0]
            created_ts = item[2].created_at.timestamp() if item[2].created_at else 0.0
            return (-score_val, created_ts)

        scored_items.sort(key=sort_key)

        ranked: list[RankedTask] = []
        for idx, (score, is_ready, node, unmet, downstream_count, reason) in enumerate(
            scored_items, start=1
        ):
            ranked.append(
                RankedTask(
                    task=node,
                    rank=idx,
                    score=score,
                    is_ready=is_ready,
                    unmet_dependencies=unmet,
                    downstream_impact_count=downstream_count,
                    recommendation_reason=reason,
                )
            )

        return ranked
