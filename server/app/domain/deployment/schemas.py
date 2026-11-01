"""Deployment Diagnosis schemas and API payload contracts (docs/01 CAP-07, docs/03 §3.4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.llm.schemas import DiagnosisHypothesis


class SimilarIncidentMatch(BaseModel):
    """Historical deployment incident similar to the current failure."""

    model_config = ConfigDict(extra="forbid")

    incident_id: UUID
    fingerprint: str
    summary: str
    probable_cause: str
    resolution: str | None = None
    failure_category: str
    similarity_score: float = Field(ge=0.0, le=1.0)
    match_type: str
    last_seen_at: datetime
    resolved_at: datetime | None = None


class EnvVarCheckResultSchema(BaseModel):
    """Analysis of referenced vs configured environment variable names."""

    model_config = ConfigDict(extra="forbid")

    referenced_names: list[str] = Field(default_factory=list)
    missing_required: list[str] = Field(default_factory=list)
    referenced_missing: list[str] = Field(default_factory=list)
    suspected_typos: list[dict[str, Any]] = Field(default_factory=list)
    valid_configured: list[str] = Field(default_factory=list)
    has_issues: bool = False


class DeploymentDiagnosisRequest(BaseModel):
    """Input payload to diagnose a deployment failure log."""

    model_config = ConfigDict(extra="forbid")

    raw_log: str = Field(description="Raw deployment log output from Render, Vercel, Docker, etc.")
    environment: str = Field(
        default="production",
        description="Deployment target environment, e.g. production, staging, preview",
    )
    service_name: str | None = Field(
        default=None,
        description="Name of the failing service or container",
    )
    configured_env_vars: list[str] | None = Field(
        default=None,
        description="Optional list of variable names (keys only, NEVER values) configured on platform",
    )
    example_env_content: str | None = Field(
        default=None,
        description="Optional content of .env.example for schema comparison",
    )
    recent_changes: str | None = Field(
        default=None,
        description="Optional summary of recent git commits or PR changes preceding deployment",
    )


class DeploymentDiagnosisResponse(BaseModel):
    """Complete diagnostic report for a deployment failure incident."""

    model_config = ConfigDict(extra="forbid")

    incident_id: UUID
    is_new_incident: bool
    fingerprint: str
    failure_category: str
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    probable_cause: str
    recommended_action: str
    hypotheses: list[DiagnosisHypothesis] = Field(default_factory=list)
    referenced_env_vars: list[str] = Field(default_factory=list)
    env_var_check: EnvVarCheckResultSchema | None = None
    referenced_files: list[dict[str, Any]] = Field(default_factory=list)
    primary_log_line: int | None = None
    similar_past_incidents: list[SimilarIncidentMatch] = Field(default_factory=list)
    is_insufficient_log: bool = False
    missing_information_needed: str | None = None
    redaction_count: int = 0
    created_at: datetime


class DeploymentIncidentResponse(BaseModel):
    """Persisted deployment incident details."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    workspace_id: UUID
    project_id: UUID
    fingerprint: str
    summary: str
    probable_cause: str
    resolution: str | None = None
    error_signature: str
    environment: str
    service_name: str | None = None
    failure_category: str
    log_snippet: str
    occurrence_count: int
    last_seen_at: datetime
    resolved_at: datetime | None = None
    resolved_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeploymentIncidentListResponse(BaseModel):
    """Paginated collection of deployment incidents."""

    model_config = ConfigDict(extra="forbid")

    items: list[DeploymentIncidentResponse]
    total: int
    limit: int
    offset: int


class DeploymentResolutionUpdate(BaseModel):
    """Payload to document or update the resolution of an incident."""

    model_config = ConfigDict(extra="forbid")

    resolution: str = Field(
        min_length=5,
        max_length=5000,
        description="Documentation of the root cause fix or remediation applied",
    )
