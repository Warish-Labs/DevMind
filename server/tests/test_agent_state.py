"""Unit and integration tests for LangGraph state schema and checkpointer (docs/05 §4, ADR-006, ADR-037)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.core.settings import Settings
from app.orchestration import (
    ApprovalState,
    BudgetState,
    CheckpointerFactory,
    CitationRef,
    DraftFinding,
    Proposal,
    RunState,
    UsageTotals,
    append_items,
    create_initial_run_state,
    format_thread_id,
    merge_usage_totals,
    parse_thread_id,
)
from app.persistence.models.brain import AgentRun


def test_create_initial_run_state() -> None:
    """Verify that create_initial_run_state constructs a well-formed RunState per docs/05 §4.2."""
    run_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    workspace_id = str(uuid.uuid4())
    actor_id = "user_clerk_123"

    state: RunState = create_initial_run_state(
        run_id=run_id,
        job_id=job_id,
        project_id=project_id,
        workspace_id=workspace_id,
        actor_id=actor_id,
        job_type="ask_project",
        params={"query": "How is authentication handled?"},
        user_message="Explain auth guards",
    )

    assert state["run_id"] == run_id
    assert state["job_id"] == job_id
    assert state["project_id"] == project_id
    assert state["workspace_id"] == workspace_id
    assert state["actor_id"] == actor_id
    assert state["status"] == "running"
    assert state["request"].job_type == "ask_project"
    assert state["request"].user_message == "Explain auth guards"
    assert isinstance(state["usage"], UsageTotals)
    assert state["usage"].total_input_tokens == 0
    assert isinstance(state["budget"], BudgetState)
    assert state["drafts"] == []
    assert state["context_refs"] == []
    assert state["errors"] == []


def test_reducers_append_items() -> None:
    """Verify append_items reducer handles empty lists and appends correctly."""
    assert append_items(None, None) == []
    assert append_items(["a"], None) == ["a"]
    assert append_items(None, ["b"]) == ["b"]
    assert append_items(["a", "b"], ["c", "d"]) == ["a", "b", "c", "d"]


def test_reducers_merge_usage_totals() -> None:
    """Verify merge_usage_totals reducer accumulates token counts and cost units."""
    u1 = UsageTotals(
        total_input_tokens=100, total_output_tokens=50, total_cost_units=200, model_calls=1
    )
    u2 = UsageTotals(
        total_input_tokens=250, total_output_tokens=100, total_cost_units=500, model_calls=2
    )

    merged = merge_usage_totals(u1, u2)
    assert merged.total_input_tokens == 350
    assert merged.total_output_tokens == 150
    assert merged.total_cost_units == 700
    assert merged.model_calls == 3

    # Dict compatibility
    dict_u = {
        "total_input_tokens": 50,
        "total_output_tokens": 20,
        "total_cost_units": 80,
        "model_calls": 1,
    }
    merged_with_dict = merge_usage_totals(merged, dict_u)
    assert merged_with_dict.total_input_tokens == 400
    assert merged_with_dict.model_calls == 4


def test_citation_ref_never_holds_source_code() -> None:
    """Assert that CitationRef holds references/ranges only, never full source bodies (docs/05 §4.2)."""
    ref = CitationRef(
        doc_id="chunk_abc123",
        path="server/app/main.py",
        start_line=10,
        end_line=25,
        symbol="create_app",
        score=0.92,
    )

    assert not hasattr(ref, "content")
    assert not hasattr(ref, "source_code")
    assert not hasattr(ref, "text")
    assert ref.to_citation_string() == "server/app/main.py:10-25"


def test_thread_id_formatting_and_parsing() -> None:
    """Verify canonical thread identifier formatting and parsing."""
    p_id = str(uuid.uuid4())
    r_id = str(uuid.uuid4())

    formatted = format_thread_id(p_id, r_id)
    assert formatted == f"devmind:{p_id}:{r_id}"

    parsed_p, parsed_r = parse_thread_id(formatted)
    assert parsed_p == p_id
    assert parsed_r == r_id

    # Invalid thread IDs
    with pytest.raises(ValueError, match="Invalid thread_id format"):
        parse_thread_id("invalid_thread_id")

    with pytest.raises(ValueError, match="Invalid thread_id format"):
        parse_thread_id("other:p1:r1")


def test_langgraph_statemap_execution_with_inmemory_checkpointer() -> None:
    """Verify StateGraph compilation, execution, and state persistence with InMemorySaver."""
    checkpointer = CheckpointerFactory.create_memory_saver()

    def intake_node(state: RunState) -> dict[str, Any]:
        return {
            "current_node": "intake",
            "context_refs": [
                CitationRef(
                    doc_id="doc_1",
                    path="src/auth.ts",
                    start_line=1,
                    end_line=15,
                )
            ],
            "usage": UsageTotals(total_input_tokens=100, total_output_tokens=20, model_calls=1),
        }

    def specialist_node(state: RunState) -> dict[str, Any]:
        return {
            "current_node": "specialist",
            "drafts": [
                DraftFinding(
                    draft_id="df_1",
                    finding_type="missing_guard",
                    title="Missing route guard in /admin",
                    file_path="src/auth.ts",
                    line_range=(1, 15),
                    rule_id="SEC001",
                    severity="high",
                )
            ],
            "usage": UsageTotals(total_input_tokens=200, total_output_tokens=60, model_calls=1),
        }

    builder = StateGraph(RunState)
    builder.add_node("intake", intake_node)
    builder.add_node("specialist", specialist_node)
    builder.add_edge(START, "intake")
    builder.add_edge("intake", "specialist")
    builder.add_edge("specialist", END)

    graph = builder.compile(checkpointer=checkpointer)

    initial_state = create_initial_run_state(
        run_id="run_test_1",
        job_id="job_test_1",
        project_id="proj_1",
        workspace_id="ws_1",
        actor_id="user_1",
        job_type="security_review",
    )

    thread_id = format_thread_id("proj_1", "run_test_1")
    config = {"configurable": {"thread_id": thread_id}}

    result = graph.invoke(initial_state, config=config)

    assert result["current_node"] == "specialist"
    assert len(result["context_refs"]) == 1
    assert result["context_refs"][0].path == "src/auth.ts"
    assert len(result["drafts"]) == 1
    assert result["drafts"][0].title == "Missing route guard in /admin"
    assert result["usage"].total_input_tokens == 300
    assert result["usage"].total_output_tokens == 80
    assert result["usage"].model_calls == 2

    # Verify checkpointer recorded state
    checkpoint_state = graph.get_state(config)
    assert checkpoint_state is not None
    assert checkpoint_state.values["current_node"] == "specialist"
    assert len(checkpoint_state.values["drafts"]) == 1


def test_langgraph_interrupt_and_resume_with_checkpointer() -> None:
    """Verify human approval interrupt pause and resume via LangGraph checkpointer (docs/05 §4.6)."""
    checkpointer = InMemorySaver()

    def plan_node(state: RunState) -> dict[str, Any]:
        return {
            "current_node": "plan",
            "proposals": [
                Proposal(
                    proposal_type="pr_comment",
                    title="Post security review comment",
                    description="Post comment on PR #12",
                    gated=True,
                )
            ],
            "status": "awaiting_approval",
        }

    def approval_gate_node(state: RunState) -> dict[str, Any]:
        # If approved, move to write; otherwise keep awaiting_approval
        approvals = state.get("approvals", [])
        if approvals and approvals[-1].status == "approved":
            return {"status": "running", "current_node": "approval_gate"}
        return {"status": "awaiting_approval"}

    def apply_node(state: RunState) -> dict[str, Any]:
        return {
            "current_node": "apply",
            "status": "completed",
            "final_response": "PR comment posted successfully",
        }

    builder = StateGraph(RunState)
    builder.add_node("plan", plan_node)
    builder.add_node("approval_gate", approval_gate_node)
    builder.add_node("apply", apply_node)

    builder.add_edge(START, "plan")
    builder.add_edge("plan", "approval_gate")
    builder.add_edge("approval_gate", "apply")
    builder.add_edge("apply", END)

    # Interrupt before approval_gate node to wait for human maintainer decision
    graph = builder.compile(checkpointer=checkpointer, interrupt_before=["approval_gate"])

    thread_id = format_thread_id("proj_gated", "run_gated")
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = create_initial_run_state(
        run_id="run_gated",
        job_id="job_gated",
        project_id="proj_gated",
        workspace_id="ws_gated",
        actor_id="user_maintainer",
        job_type="security_review",
    )

    # 1. Run until approval interrupt
    graph.invoke(initial_state, config=config)
    paused_state = graph.get_state(config)

    assert paused_state.next == ("approval_gate",)
    assert paused_state.values["status"] == "awaiting_approval"
    assert len(paused_state.values["proposals"]) == 1

    # 2. Maintainer approves: update state with ApprovalState(status='approved')
    graph.update_state(
        config,
        {
            "approvals": [
                ApprovalState(
                    approval_id="appr_01",
                    action_kind="pr_comment",
                    status="approved",
                    decided_by="maintainer_bob",
                )
            ]
        },
    )

    # 3. Resume thread execution
    resumed_result = graph.invoke(None, config=config)
    assert resumed_result["status"] == "completed"
    assert resumed_result["final_response"] == "PR comment posted successfully"


def test_agent_run_database_model() -> None:
    """Verify SQLAlchemy AgentRun persistence model attributes and defaults."""
    run_id = uuid.uuid4()
    p_id = uuid.uuid4()
    w_id = uuid.uuid4()
    j_id = uuid.uuid4()
    thread_id = format_thread_id(p_id, run_id)

    model = AgentRun(
        id=run_id,
        project_id=p_id,
        workspace_id=w_id,
        job_id=j_id,
        workflow="agent_manager",
        thread_id=thread_id,
        status="running",
        prompt_versions={"agent_manager_routing": "v1"},
        model_choices={"primary": "google/gemini-2.5-flash"},
        config_hash="abc123hash",
        state_summary={"current_node": "start"},
        usage_totals={"total_input_tokens": 150},
    )

    assert model.id == run_id
    assert model.thread_id == thread_id
    assert model.workflow == "agent_manager"
    assert model.prompt_versions == {"agent_manager_routing": "v1"}
    assert model.__tablename__ == "agent_runs"


def test_checkpointer_factory() -> None:
    """Verify CheckpointerFactory environment resolution and URL handling."""
    settings = Settings(
        env="test",
        database_url="postgresql+psycopg://test:pass@localhost:5432/test_db",
    )

    saver = CheckpointerFactory.create_checkpointer(settings)
    assert isinstance(saver, InMemorySaver)

    direct_url = CheckpointerFactory.get_database_url_for_workers(settings)
    assert direct_url.startswith("postgresql://")
    assert "+psycopg" not in direct_url
