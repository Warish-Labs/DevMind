"""LangGraph state schema and reducers for DevMind agent workflows (docs/05 §4.2).

Per docs/05 §4.2:
State holds references and small structured values, never code bodies,
so checkpoints stay small and free of source code.
Context text is rebuilt from references inside a node when needed and discarded after.
"""

from __future__ import annotations

import datetime
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Annotated, Any, TypedDict


def append_items[T](left: list[T] | None, right: list[T] | Sequence[T] | None) -> list[T]:
    """Reducer appending incoming items to the state list."""
    res = list(left) if left else []
    if right:
        res.extend(right)
    return res


@dataclass
class UsageTotals:
    """Aggregated token and cost usage tracking across workflow steps (docs/05 §13)."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_units: int = 0
    model_calls: int = 0

    def add(self, other: UsageTotals) -> UsageTotals:
        return UsageTotals(
            total_input_tokens=self.total_input_tokens + other.total_input_tokens,
            total_output_tokens=self.total_output_tokens + other.total_output_tokens,
            total_cost_units=self.total_cost_units + other.total_cost_units,
            model_calls=self.model_calls + other.model_calls,
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_units": self.total_cost_units,
            "model_calls": self.model_calls,
        }


def merge_usage_totals(
    left: UsageTotals | dict[str, int] | None,
    right: UsageTotals | dict[str, int] | None,
) -> UsageTotals:
    """Reducer accumulating LLM token usage and cost units across parallel specialist nodes."""

    def _to_usage(val: UsageTotals | dict[str, int] | None) -> UsageTotals:
        if val is None:
            return UsageTotals()
        if isinstance(val, UsageTotals):
            return val
        return UsageTotals(
            total_input_tokens=val.get("total_input_tokens", 0),
            total_output_tokens=val.get("total_output_tokens", 0),
            total_cost_units=val.get("total_cost_units", 0),
            model_calls=val.get("model_calls", 0),
        )

    u1 = _to_usage(left)
    u2 = _to_usage(right)
    return u1.add(u2)


@dataclass
class RequestState:
    """The incoming user or system request initiating the workflow."""

    job_type: str
    params: dict[str, Any] = field(default_factory=dict)
    user_message: str | None = None


@dataclass
class IntentState:
    """Classified user intent and routing metadata (docs/05 §2.1)."""

    category: str
    intent_name: str
    confidence: float
    requires_specialists: list[str] = field(default_factory=list)


@dataclass
class SpecialistTask:
    """A scoped task unit dispatched to a specialist agent (docs/05 §2.1, §4.1)."""

    specialist: str  # 'codemate', 'authcheck', 'reviewbuddy', etc.
    task_id: str
    status: str = "pending"  # 'pending', 'running', 'completed', 'failed', 'timed_out'
    input_refs: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class CitationRef:
    """Context reference holding file/symbol identifiers without raw source code bodies (docs/05 §4.2)."""

    doc_id: str
    path: str
    start_line: int
    end_line: int
    symbol: str | None = None
    score: float | None = None

    def to_citation_string(self) -> str:
        """Format citation reference, e.g. 'server/app/main.py:10-25'."""
        return f"{self.path}:{self.start_line}-{self.end_line}"


@dataclass
class DraftFinding:
    """A potential finding emitted by a specialist before evidence verification (docs/05 §4.2, §7)."""

    draft_id: str
    finding_type: str
    title: str
    file_path: str
    line_range: tuple[int, int]
    rule_id: str
    severity: str
    evidence_refs: list[str] = field(default_factory=list)
    explanation: str | None = None


@dataclass
class VerifiedFinding:
    """A finding that has passed the deterministic evidence verifier (docs/05 §7)."""

    draft_id: str
    is_verified: bool
    evidence_score: float
    resolution_notes: str | None = None


@dataclass
class Hypothesis:
    """An unverified hypothesis shown only in conversational context (docs/05 §4.2)."""

    statement: str
    basis_refs: list[str] = field(default_factory=list)
    confidence: float = 0.5


@dataclass
class Proposal:
    """A proposal for external side-effects requiring human approval (docs/05 §4.6)."""

    proposal_type: str  # 'pr_comment', 'issue_creation', 'diff_patch'
    title: str
    description: str
    diff_content: str | None = None
    gated: bool = True


@dataclass
class ApprovalState:
    """Human approval gate state (docs/05 §4.6)."""

    approval_id: str
    action_kind: str
    status: str = "pending"  # 'pending', 'approved', 'rejected', 'expired'
    proposal: dict[str, Any] = field(default_factory=dict)
    decided_by: str | None = None
    decided_at: str | None = None


@dataclass
class NodeError:
    """Error record logged by a graph node during execution (docs/05 §4.4)."""

    node: str
    error_code: str
    message: str
    retryable: bool = False
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())


@dataclass
class BudgetState:
    """Token, cost, and time limits configured for this run (docs/05 §4.4)."""

    max_tokens: int = 100_000
    max_cost_units: int = 1_000_000
    max_wall_time_seconds: float = 300.0


class RunState(TypedDict, total=False):
    """LangGraph execution state schema for DevMind agents (docs/05 §4.2).

    Uses reducers (Annotated) for lists and totals that merge across parallel nodes.
    """

    # Identifiers & Tenancy
    run_id: str
    job_id: str
    project_id: str
    workspace_id: str
    actor_id: str
    consent_id: str | None

    # Lifecycle & Execution Status
    status: str  # 'running', 'awaiting_approval', 'completed', 'partially_succeeded', 'failed'
    current_node: str | None

    # Request & Planning
    request: RequestState
    intent: IntentState | None
    plan: list[SpecialistTask]

    # Grounding References (holding IDs/citations, NEVER full source text)
    context_refs: Annotated[list[CitationRef], append_items]

    # Findings & Evidence
    drafts: Annotated[list[DraftFinding], append_items]
    verified: list[VerifiedFinding]
    hypotheses: list[Hypothesis]

    # Proposals & Approval Gates
    proposals: list[Proposal]
    approvals: list[ApprovalState]

    # Output Syntheses
    final_response: str | None

    # Accounting & Guardrails
    errors: Annotated[list[NodeError], append_items]
    usage: Annotated[UsageTotals, merge_usage_totals]
    budget: BudgetState


def create_initial_run_state(
    run_id: str,
    job_id: str,
    project_id: str,
    workspace_id: str,
    actor_id: str,
    job_type: str,
    params: dict[str, Any] | None = None,
    user_message: str | None = None,
    consent_id: str | None = None,
    budget: BudgetState | None = None,
) -> RunState:
    """Create a fully initialized, validated RunState dictionary for starting a graph workflow."""
    return {
        "run_id": run_id,
        "job_id": job_id,
        "project_id": project_id,
        "workspace_id": workspace_id,
        "actor_id": actor_id,
        "consent_id": consent_id,
        "status": "running",
        "current_node": "start",
        "request": RequestState(
            job_type=job_type,
            params=dict(params or {}),
            user_message=user_message,
        ),
        "intent": None,
        "plan": [],
        "context_refs": [],
        "drafts": [],
        "verified": [],
        "hypotheses": [],
        "proposals": [],
        "approvals": [],
        "final_response": None,
        "errors": [],
        "usage": UsageTotals(),
        "budget": budget or BudgetState(),
    }
