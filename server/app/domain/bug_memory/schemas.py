"""Pydantic request and response schemas for Bug Memory (docs/01 CAP-03, docs/03 §3.4, §11.1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BugResolutionBase(BaseModel):
    """Base schema for documented bug resolution."""

    cause: str = Field(min_length=1, description="Root cause analysis of the bug")
    fix_summary: str = Field(
        min_length=1,
        description="Summary of the code modification or architectural fix applied",
    )
    files: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of changed file paths, symbols, and line citations",
    )
    finding_id: UUID | None = Field(
        default=None,
        description="Optional ID of associated security or review finding",
    )


class BugResolutionCreate(BugResolutionBase):
    """Request payload to add a resolution to a bug record."""

    pass


class BugResolutionResponse(BugResolutionBase):
    """Response schema for documented bug resolution."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    bug_record_id: UUID
    resolved_by: UUID | None = None
    created_at: datetime
    updated_at: datetime


class BugRecordCreate(BaseModel):
    """Request payload to log a new or recurring error trace."""

    raw_error: str = Field(
        min_length=1,
        description="Raw error log, exception message, or stack trace snippet",
    )
    title: str | None = Field(
        default=None,
        max_length=255,
        description="Optional human-readable title; auto-generated if omitted",
    )
    summary: str | None = Field(
        default=None,
        description="Optional description or context about the occurrence",
    )
    module_hint: str | None = Field(
        default=None,
        max_length=255,
        description="Optional module or subsystem hint",
    )
    resolution: BugResolutionCreate | None = Field(
        default=None,
        description="Optional initial resolution if logging an already-resolved bug",
    )


class BugRecordResponse(BaseModel):
    """Response schema for a bug record item in list views."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    project_id: UUID
    fingerprint: str
    error_signature: str
    title: str
    summary: str | None = None
    module_hint: str | None = None
    occurrence_count: int
    resolutions_count: int = 0
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class BugRecordDetailResponse(BugRecordResponse):
    """Detailed response schema for a single bug record with historical resolutions."""

    raw_error: str | None = None
    resolutions: list[BugResolutionResponse] = Field(default_factory=list)


class BugMatchRequest(BaseModel):
    """Request payload to search project Bug Memory for similar past issues."""

    raw_error: str = Field(
        min_length=1,
        description="Failing error text, stack trace, or incident log snippet",
    )
    module_hint: str | None = Field(
        default=None,
        description="Optional module hint to prioritize candidates",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum candidate matches to retrieve",
    )


class NormalizedErrorSummary(BaseModel):
    """Normalized signature and canonical characteristics of an input error."""

    exception_type: str
    clean_message: str
    module_hint: str | None = None
    fingerprint: str
    normalized_signature: str


class BugMatchCandidateResponse(BaseModel):
    """Candidate match with similarity score and matching classification."""

    bug: BugRecordDetailResponse
    score: float = Field(ge=0.0, le=1.0, description="Similarity score between 0.0 and 1.0")
    match_type: str = Field(
        description="Classification: exact_fingerprint, fuzzy_signature, or module_match"
    )


class BugMatchResponse(BaseModel):
    """Response payload returned by BugMemory matching and specialist explanation."""

    matched: bool = Field(description="Whether similar historical bugs were found")
    normalized_error: NormalizedErrorSummary
    candidates: list[BugMatchCandidateResponse] = Field(default_factory=list)
    explanation: str = Field(
        description="Synthesized comparison or explanation of similar past incidents and fixes"
    )
    confidence_label: str = Field(
        description="Overall confidence category: high, medium, low, or none"
    )
    recommended_fix: str | None = Field(
        default=None,
        description="Remediation or fix recommendation derived from previous resolutions",
    )


class ResolutionProposal(BaseModel):
    """Structured resolution proposal proposed by agent before confirmation."""

    cause: str
    fix_summary: str
    files: list[dict[str, Any]] = Field(default_factory=list)
    finding_id: UUID | None = None
