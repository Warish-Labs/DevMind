"""Pydantic request and response schemas for Project Mentor and Project Evaluation (docs/01 CAP-08, CAP-09, docs/03 §3.6, §3.7)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Task Schemas
# ---------------------------------------------------------------------------


class ProjectTaskCreate(BaseModel):
    """Payload to create a new backlog or finding-derived task."""

    title: str = Field(min_length=1, max_length=255, description="Task title")
    description: str | None = Field(default=None, description="Detailed instructions or context")
    priority: str = Field(
        default="medium",
        description="Priority level: critical, high, medium, low",
    )
    source: str = Field(
        default="user",
        description="Source of task: user, agent, finding",
    )
    finding_id: UUID | None = Field(
        default=None,
        description="Optional finding ID if created from a security/review finding",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary structured task metadata",
    )
    depends_on_ids: list[UUID] = Field(
        default_factory=list,
        description="Task UUIDs that this task depends on (prerequisites)",
    )


class ProjectTaskUpdate(BaseModel):
    """Payload to update an existing task."""

    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    status: str | None = Field(
        default=None,
        description="open, in_progress, blocked, completed, cancelled",
    )
    priority: str | None = Field(
        default=None,
        description="critical, high, medium, low",
    )
    metadata: dict[str, Any] | None = None


class ProjectTaskResponse(BaseModel):
    """Response representation of a project task."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    project_id: UUID
    title: str
    description: str | None = None
    status: str
    priority: str
    source: str
    finding_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    depends_on_ids: list[UUID] = Field(default_factory=list)
    dependent_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class TaskDependencyCreate(BaseModel):
    """Payload to add a dependency edge."""

    depends_on_task_id: UUID = Field(description="UUID of the prerequisite task")


class TaskDependencyResponse(BaseModel):
    """Response schema for a registered dependency edge."""

    model_config = ConfigDict(from_attributes=True)

    task_id: UUID
    depends_on_task_id: UUID
    created_at: datetime


class TaskRecommendationResponse(BaseModel):
    """AI and DAG-ranked next recommended task with actionable reasoning."""

    recommended_task: ProjectTaskResponse | None = None
    rank: int = 1
    score: float = 0.0
    is_ready: bool = True
    downstream_impact_count: int = 0
    reason: str = Field(description="Deterministic recommendation explanation")
    narrative: str = Field(description="LLM synthesized actionable recommendation guidance")
    unblocked_count: int = 0
    total_pending_tasks: int = 0


# ---------------------------------------------------------------------------
# Evaluation Schemas
# ---------------------------------------------------------------------------


class ProjectEvaluationRunRequest(BaseModel):
    """Request payload to trigger an on-demand project evaluation."""

    snapshot_id: UUID | None = Field(
        default=None,
        description="Optional snapshot UUID to evaluate",
    )
    feature_checklist: list[dict[str, Any]] | None = Field(
        default=None,
        description="Optional user-declared feature checklist adhering to OQ-18",
    )
    rubric_version: str = Field(default="1.0", description="Evaluation rubric version")


class ProjectEvaluationResponse(BaseModel):
    """Multidimensional health scorecard and release-readiness verdict."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    project_id: UUID
    snapshot_id: UUID | None = None
    overall_score: float
    dimension_scores: dict[str, float]
    verdict: str  # ready, ready_with_warnings, not_ready
    blockers: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    positive_indicators: list[str] = Field(default_factory=list)
    rubric_version: str
    functionality_confidence: str = "high"
    narrative: str | None = None
    evaluated_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
