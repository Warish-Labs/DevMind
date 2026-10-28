"""Domain schemas for ReviewBuddy checklist and custom project review rules (docs/01 CAP-05, docs/05 §6.4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ScopeSelector(BaseModel):
    """File and language matching selector for review rules."""

    paths: list[str] = Field(
        default_factory=lambda: ["**/*"],
        description="Glob patterns of file paths this rule applies to.",
    )
    languages: list[str] | None = Field(
        default=None,
        description="Language identifiers, e.g. ['python', 'typescript'].",
    )
    ignore: list[str] | None = Field(
        default=None,
        description="Glob patterns to ignore.",
    )

    model_config = ConfigDict(extra="ignore")


class ReviewRuleCreate(BaseModel):
    """Payload for creating a custom review rule."""

    rule_id: str = Field(
        ...,
        min_length=3,
        max_length=64,
        description="Unique rule code within the project, e.g. 'RULE-001' or 'REV-INPUT-02'.",
    )
    title: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Human-readable rule title.",
    )
    category: str = Field(
        default="quality",
        description="Rule category: input_validation, error_handling, authorization, testing, documentation, quality, security, other.",
    )
    severity: str = Field(
        default="medium",
        description="Severity level: critical, high, medium, low, info.",
    )
    scope_selector: ScopeSelector = Field(
        default_factory=ScopeSelector,
        description="Scope selector defining which files this rule checks.",
    )
    check_type: str = Field(
        ...,
        description="Check type: require_validation, require_error_handling, require_auth, require_test, require_docs, pattern_forbidden, pattern_required, custom_regex.",
    )
    check_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration parameters specific to check_type.",
    )
    message: str = Field(
        ...,
        min_length=5,
        description="Explanation message emitted when this rule triggers.",
    )
    suggested_fix_template: str | None = Field(
        default=None,
        description="Optional suggested remediation instruction.",
    )
    is_enabled: bool = Field(
        default=True,
        description="Whether the rule is active during reviews.",
    )


class ReviewRuleUpdate(BaseModel):
    """Payload for updating an existing review rule."""

    title: str | None = Field(default=None, min_length=3, max_length=255)
    category: str | None = None
    severity: str | None = None
    scope_selector: ScopeSelector | None = None
    check_type: str | None = None
    check_config: dict[str, Any] | None = None
    message: str | None = Field(default=None, min_length=5)
    suggested_fix_template: str | None = None
    is_enabled: bool | None = None


class ReviewRuleResponse(BaseModel):
    """API response model for review rules."""

    id: UUID
    workspace_id: UUID
    project_id: UUID
    rule_id: str
    title: str
    category: str
    severity: str
    scope_selector: dict[str, Any]
    check_type: str
    check_config: dict[str, Any]
    message: str
    suggested_fix_template: str | None = None
    is_enabled: bool
    is_builtin: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ChecklistFinding(BaseModel):
    """An individual checklist finding identified by ReviewBuddy."""

    rule_id: str
    title: str
    category: str
    severity: str
    file_path: str
    start_line: int | None = None
    end_line: int | None = None
    message: str
    suggested_fix: str | None = None
    evidence_level: str = "E1"
    snippet: str | None = None


class ChecklistEvaluationRequest(BaseModel):
    """Request payload to evaluate ReviewBuddy checklist against files or unified diff."""

    diff: str | None = Field(
        default=None,
        description="Unified diff content to evaluate against review rules.",
    )
    files: list[dict[str, Any]] | None = Field(
        default=None,
        description="List of file dicts with 'path' and 'content' keys.",
    )


class ChecklistEvaluationSummary(BaseModel):
    """Summary metrics of a review evaluation."""

    total_rules_evaluated: int
    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    info_count: int
    passed_checklist: bool


class ChecklistEvaluationResponse(BaseModel):
    """Full response for a ReviewBuddy checklist evaluation."""

    project_id: UUID
    summary: ChecklistEvaluationSummary
    findings: list[ChecklistFinding]
