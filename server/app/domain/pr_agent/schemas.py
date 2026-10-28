"""Pydantic schemas for PRAgent pull request intelligence and change impact (docs/01 CAP-06, docs/03 §3.5)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DirectSymbolItem(BaseModel):
    """A code symbol directly touched by a change set."""

    name: str = Field(description="Symbol name")
    kind: str = Field(
        default="function", description="Symbol kind (function, class, variable, route)"
    )
    file_path: str = Field(description="File path where symbol is defined")
    symbol_key: str | None = Field(default=None, description="Unique symbol key")


class AffectedRouteItem(BaseModel):
    """An API route affected by the changes."""

    path: str = Field(description="Route path e.g. /api/v1/projects")
    method: str = Field(default="GET", description="HTTP method")
    handler: str = Field(description="Handler function or endpoint name")
    file_path: str = Field(description="File containing route handler")


class GraphNodeItem(BaseModel):
    """A node in the change impact dependency subgraph."""

    id: str = Field(description="Unique node identifier")
    label: str = Field(description="Human readable node label")
    type: str = Field(description="Node type: file, symbol, route, test, module")
    file_path: str | None = Field(default=None, description="Associated file path")


class GraphEdgeItem(BaseModel):
    """An edge in the change impact dependency subgraph."""

    from_node: str = Field(description="Source node ID")
    to_node: str = Field(description="Target node ID")
    kind: str = Field(description="Relationship kind: imports, calls, defines, tests, affects")


class ChangeImpactReport(BaseModel):
    """Detailed structural and relationship impact of a pull request."""

    model_config = ConfigDict(from_attributes=True)

    changed_files: list[str] = Field(default_factory=list, description="Files directly modified")
    direct_symbols: list[DirectSymbolItem] = Field(
        default_factory=list, description="Symbols in changed files"
    )
    affected_modules: list[str] = Field(
        default_factory=list, description="Modules impacted by modifications"
    )
    affected_routes: list[AffectedRouteItem] = Field(
        default_factory=list, description="API endpoints touched or called"
    )
    affected_tests: list[str] = Field(
        default_factory=list, description="Test files affected or covering modified files"
    )
    dependency_graph_nodes: list[GraphNodeItem] = Field(
        default_factory=list, description="Nodes for impact visualization"
    )
    dependency_graph_edges: list[GraphEdgeItem] = Field(
        default_factory=list, description="Edges for impact visualization"
    )
    risk_level: str = Field(
        default="low", description="Overall risk level: low, medium, high, critical"
    )
    risk_reasons: list[str] = Field(
        default_factory=list, description="Reasons justifying the computed risk level"
    )


class PRSummary(BaseModel):
    """Synthesized intelligence summary for a pull request."""

    model_config = ConfigDict(from_attributes=True)

    purpose: str = Field(description="High-level purpose and narrative of the pull request")
    files_changed: list[str] = Field(default_factory=list, description="Key files changed")
    affected_areas: list[str] = Field(default_factory=list, description="System areas affected")
    risks: list[str] = Field(default_factory=list, description="Identified potential risks")
    security_summary: str = Field(
        default="No critical security risks identified", description="Security assessment summary"
    )
    testing_concerns: list[str] = Field(
        default_factory=list, description="Testing gaps or verification concerns"
    )
    documentation_impact: str = Field(
        default="No documentation changes required",
        description="Documentation drift or updates needed",
    )
    risk_level: str = Field(default="low", description="Computed risk assessment")


class TriggerPRAnalysisRequest(BaseModel):
    """Request payload to initiate or re-run a pull request analysis."""

    diff_override: str | None = Field(
        default=None, description="Optional unified diff to evaluate instead of remote GitHub diff"
    )
    post_comment: bool = Field(
        default=False,
        description="Whether to request posting summary comment to GitHub (requires human approval)",
    )


class PRAnalysisResponse(BaseModel):
    """API response model for a PR analysis result."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    project_id: UUID
    pull_request_id: UUID
    head_sha: str
    job_id: UUID | None = None
    risk_level: str
    summary: dict[str, Any]
    impact: dict[str, Any]
    created_at: datetime | None = None
    updated_at: datetime | None = None
