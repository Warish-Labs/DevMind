"""Unit tests for Topological Task DAG Sorter and Cycle Detector (CAP-08, docs/01 §8, docs/03 §3.6, M12-08)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.analysis.task_dag import (
    CyclicDependencyError,
    TaskDAG,
    TaskNode,
)


def test_task_dag_linear_topological_sort() -> None:
    """Verify linear dependency chain A -> B -> C sorts correctly."""
    dag = TaskDAG()
    t_a = uuid4()
    t_b = uuid4()
    t_c = uuid4()

    # B depends on A, C depends on B
    dag.add_node(TaskNode(id=t_a, title="Task A"))
    dag.add_node(TaskNode(id=t_b, title="Task B", depends_on={t_a}))
    dag.add_node(TaskNode(id=t_c, title="Task C", depends_on={t_b}))

    order = dag.topological_sort()
    assert order == [t_a, t_b, t_c]
    assert dag.detect_cycle() is None


def test_task_dag_diamond_structure() -> None:
    """Verify diamond dependency graph A -> (B, C) -> D."""
    dag = TaskDAG()
    t_a = uuid4()
    t_b = uuid4()
    t_c = uuid4()
    t_d = uuid4()

    dag.add_node(TaskNode(id=t_a, title="Task A"))
    dag.add_node(TaskNode(id=t_b, title="Task B", depends_on={t_a}))
    dag.add_node(TaskNode(id=t_c, title="Task C", depends_on={t_a}))
    dag.add_node(TaskNode(id=t_d, title="Task D", depends_on={t_b, t_c}))

    order = dag.topological_sort()
    assert order[0] == t_a
    assert order[-1] == t_d
    assert set(order[1:3]) == {t_b, t_c}

    # Transitive downstream counts
    assert dag.count_downstream_dependents(t_a) == 3  # B, C, D
    assert dag.count_downstream_dependents(t_b) == 1  # D
    assert dag.count_downstream_dependents(t_c) == 1  # D
    assert dag.count_downstream_dependents(t_d) == 0


def test_task_dag_self_dependency_rejected() -> None:
    """Verify self-dependency raises CyclicDependencyError immediately."""
    dag = TaskDAG()
    t_a = uuid4()
    dag.add_node(TaskNode(id=t_a, title="Task A"))

    with pytest.raises(CyclicDependencyError) as exc_info:
        dag.add_edge(t_a, t_a)

    assert "cannot depend on itself" in str(exc_info.value)


def test_task_dag_two_node_cycle_rejected() -> None:
    """Verify A -> B and B -> A raises CyclicDependencyError."""
    dag = TaskDAG()
    t_a = uuid4()
    t_b = uuid4()

    dag.add_node(TaskNode(id=t_a, title="Task A"))
    dag.add_node(TaskNode(id=t_b, title="Task B", depends_on={t_a}))

    with pytest.raises(CyclicDependencyError) as exc_info:
        dag.add_edge(t_a, t_b)

    assert "creates a cycle" in str(exc_info.value)


def test_task_dag_multi_hop_cycle_rejected() -> None:
    """Verify A -> B -> C -> D and adding D -> A raises CyclicDependencyError."""
    dag = TaskDAG()
    t_a, t_b, t_c, t_d = uuid4(), uuid4(), uuid4(), uuid4()

    dag.add_node(TaskNode(id=t_a, title="A"))
    dag.add_node(TaskNode(id=t_b, title="B", depends_on={t_a}))
    dag.add_node(TaskNode(id=t_c, title="C", depends_on={t_b}))
    dag.add_node(TaskNode(id=t_d, title="D", depends_on={t_c}))

    with pytest.raises(CyclicDependencyError):
        dag.add_edge(t_a, t_d)


def test_task_dag_ranking_ready_vs_blocked() -> None:
    """Verify ready unblocked tasks always outrank blocked tasks regardless of priority."""
    dag = TaskDAG()
    t_prereq = uuid4()
    t_blocked_crit = uuid4()
    t_ready_low = uuid4()

    now = datetime.now(UTC)

    # Prerequisite is open (not completed)
    dag.add_node(
        TaskNode(
            id=t_prereq,
            title="Database Migration",
            status="open",
            priority="medium",
            created_at=now,
        )
    )
    # Blocked task has CRITICAL priority and high severity finding
    dag.add_node(
        TaskNode(
            id=t_blocked_crit,
            title="Deploy Admin API",
            status="open",
            priority="critical",
            finding_severity="CRITICAL",
            depends_on={t_prereq},
            created_at=now + timedelta(seconds=1),
        )
    )
    # Ready task has LOW priority with no dependencies
    dag.add_node(
        TaskNode(
            id=t_ready_low,
            title="Fix README Typos",
            status="open",
            priority="low",
            created_at=now + timedelta(seconds=2),
        )
    )

    ranked = dag.rank_tasks()

    # Ranked order must be:
    # 1. t_prereq (Ready + unblocks 1 downstream task)
    # 2. t_ready_low (Ready)
    # 3. t_blocked_crit (Blocked by t_prereq)
    assert len(ranked) == 3
    assert ranked[0].task.id == t_prereq
    assert ranked[0].is_ready is True
    assert ranked[0].downstream_impact_count == 1

    assert ranked[1].task.id == t_ready_low
    assert ranked[1].is_ready is True

    assert ranked[2].task.id == t_blocked_crit
    assert ranked[2].is_ready is False
    assert t_prereq in ranked[2].unmet_dependencies


def test_task_dag_ranking_priority_and_severity() -> None:
    """Verify priority and finding severity break ties among ready tasks."""
    dag = TaskDAG()
    t_crit = uuid4()
    t_high_finding = uuid4()
    t_med = uuid4()

    now = datetime.now(UTC)

    dag.add_node(
        TaskNode(
            id=t_crit,
            title="Fix Auth Zero-Day",
            status="open",
            priority="critical",  # 400
            created_at=now,
        )
    )
    dag.add_node(
        TaskNode(
            id=t_high_finding,
            title="Resolve Insecure Route",
            status="open",
            priority="high",  # 300 + 40 (CRITICAL) = 340
            finding_severity="CRITICAL",
            created_at=now,
        )
    )
    dag.add_node(
        TaskNode(
            id=t_med,
            title="Refactor Helper",
            status="open",
            priority="medium",  # 200
            created_at=now,
        )
    )

    ranked = dag.rank_tasks()
    assert [r.task.id for r in ranked] == [t_crit, t_high_finding, t_med]
    assert ranked[0].score > ranked[1].score > ranked[2].score


def test_task_dag_completed_tasks_excluded_from_ranking() -> None:
    """Completed tasks unblock dependents and do not appear in the recommended queue."""
    dag = TaskDAG()
    t_prereq = uuid4()
    t_dependent = uuid4()

    dag.add_node(
        TaskNode(
            id=t_prereq,
            title="Scaffold Migrations",
            status="completed",
        )
    )
    dag.add_node(
        TaskNode(
            id=t_dependent,
            title="Run Seed Data",
            status="open",
            depends_on={t_prereq},
        )
    )

    ranked = dag.rank_tasks()
    assert len(ranked) == 1
    assert ranked[0].task.id == t_dependent
    assert ranked[0].is_ready is True
    assert len(ranked[0].unmet_dependencies) == 0
