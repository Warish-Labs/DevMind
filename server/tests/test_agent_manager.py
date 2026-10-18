"""Tests for Agent Manager graph and plan execution routing (docs/05 §2, §4, M7-03).

Verifies:
1. Deterministic intent classification (job_type mappings and strong keyword signals).
2. LLM intent classification with schema validation and allowlisted specialist filtering.
3. Execution routing: single specialist (CodeMate), single specialist (AuthCheck), and parallel fan-out (both).
4. Deterministic bypass of LLM route when intent is classified deterministically.
5. Checkpointed approval gate interrupt and resume on side-effect proposals.
6. Async streaming and state snapshot inspectability.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.core.ids import generate_uuid7
from app.llm.models import LLMGenerationResponse
from app.llm.router import LLMGatewayRouter
from app.llm.schemas import AgentPlan
from app.orchestration.checkpointer import format_thread_id
from app.orchestration.manager import (
    AgentManager,
    classify_intent_deterministically,
    classify_intent_with_llm,
)
from app.orchestration.state import (
    Proposal,
    RequestState,
    RunState,
    create_initial_run_state,
)


def _create_test_state(
    job_type: str = "ask_project",
    user_message: str | None = None,
    params: dict | None = None,
) -> RunState:
    run_id = str(generate_uuid7())
    project_id = str(generate_uuid7())
    workspace_id = str(generate_uuid7())
    return create_initial_run_state(
        run_id=run_id,
        job_id=str(generate_uuid7()),
        project_id=project_id,
        workspace_id=workspace_id,
        actor_id="user_clerk_test",
        job_type=job_type,
        params=params or {},
        user_message=user_message,
    )


# ---------------------------------------------------------------------------
# Intent Classification Tests (docs/05 §2.1)
# ---------------------------------------------------------------------------


def test_classify_intent_deterministically_job_types() -> None:
    """Verify deterministic intent classification on explicit job types."""
    # 1. CodeMate / ask_project
    req_ask = RequestState(job_type="ask_project", user_message="General question")
    intent_ask = classify_intent_deterministically(req_ask)
    assert intent_ask is not None
    assert intent_ask.category == "code_qa"
    assert intent_ask.requires_specialists == ["codemate"]
    assert intent_ask.confidence == 1.0

    # 2. AuthCheck / security_review
    req_sec = RequestState(job_type="security_review", user_message="Scan endpoints")
    intent_sec = classify_intent_deterministically(req_sec)
    assert intent_sec is not None
    assert intent_sec.category == "security"
    assert intent_sec.requires_specialists == ["authcheck"]
    assert intent_sec.confidence == 1.0

    # 3. Comprehensive review / both
    req_comp = RequestState(job_type="comprehensive_review")
    intent_comp = classify_intent_deterministically(req_comp)
    assert intent_comp is not None
    assert intent_comp.category == "security_and_code"
    assert set(intent_comp.requires_specialists) == {"codemate", "authcheck"}


def test_classify_intent_deterministically_keyword_heuristics() -> None:
    """Verify keyword signals on free-form user messages when job_type is generic."""
    # Auth keyword -> AuthCheck
    req1 = RequestState(
        job_type="chat", user_message="Is this endpoint guarded by permission check?"
    )
    intent1 = classify_intent_deterministically(req1)
    assert intent1 is not None
    assert intent1.requires_specialists == ["authcheck"]

    # Code question -> CodeMate
    req2 = RequestState(
        job_type="chat", user_message="How does the file chunking implementation work?"
    )
    intent2 = classify_intent_deterministically(req2)
    assert intent2 is not None
    assert intent2.requires_specialists == ["codemate"]

    # Both auth and architecture signals -> both
    req3 = RequestState(
        job_type="chat", user_message="Explain how the authentication architecture and tokens work"
    )
    intent3 = classify_intent_deterministically(req3)
    assert intent3 is not None
    assert set(intent3.requires_specialists) == {"codemate", "authcheck"}

    # Ambiguous / greeting without signals -> returns None (prompts LLM routing)
    req4 = RequestState(job_type="chat", user_message="Hello, can you help me?")
    intent4 = classify_intent_deterministically(req4)
    assert intent4 is None


@pytest.mark.asyncio
async def test_classify_intent_with_llm_success() -> None:
    """Verify LLM routing parses AgentPlan and filters allowlisted specialists."""
    mock_router = AsyncMock(spec=LLMGatewayRouter)
    mock_plan = AgentPlan(
        summary="Audit security guards and explain code flow",
        steps=["Inspect route guards", "Explain caller functions"],
        confidence=0.92,
        # Includes unreleased specialist to verify filtering
        selected_agents=["AuthCheck", "ReviewBuddy", "DeployDoctor"],
        is_safe=True,
    )
    mock_resp = MagicMock(spec=LLMGenerationResponse)
    mock_resp.content = mock_plan
    mock_resp.raw_content = None
    mock_router.generate.return_value = mock_resp

    mock_loader = MagicMock()
    mock_loader.render.return_value = MagicMock(messages=[])

    req = RequestState(job_type="chat", user_message="Examine permissions and deployment")
    intent, errors = await classify_intent_with_llm(
        req, router=mock_router, prompt_loader=mock_loader
    )

    assert len(errors) == 0
    assert intent.category == "llm_classified"
    assert intent.intent_name == "Audit security guards and explain code flow"
    assert intent.confidence == 0.92
    # Only AuthCheck is released in MVP; ReviewBuddy and DeployDoctor are filtered out
    assert intent.requires_specialists == ["authcheck"]


@pytest.mark.asyncio
async def test_classify_intent_with_llm_fallback_on_error() -> None:
    """Verify LLM routing gracefully falls back to CodeMate when router errors."""
    mock_router = AsyncMock(spec=LLMGatewayRouter)
    mock_router.generate.side_effect = RuntimeError("Provider timeout")

    mock_loader = MagicMock()
    mock_loader.render.return_value = MagicMock(messages=[])

    req = RequestState(job_type="chat", user_message="Complex question")
    intent, errors = await classify_intent_with_llm(
        req, router=mock_router, prompt_loader=mock_loader
    )

    assert len(errors) == 1
    assert errors[0].node == "llm_route"
    assert intent.category == "fallback"
    assert intent.requires_specialists == ["codemate"]


# ---------------------------------------------------------------------------
# Manager Graph Workflow Tests (docs/05 §4.1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_manager_deterministic_codemate_route() -> None:
    """Verify deterministic ask_project request executes CodeMate and bypasses llm_route."""
    manager = AgentManager(router=None, prompt_loader=None, interrupt_on_approval=False)
    state = _create_test_state(
        job_type="ask_project", user_message="How does vector indexing work?"
    )

    res = await manager.run(state)

    assert res["status"] == "completed"
    assert res["intent"] is not None
    assert res["intent"].category == "code_qa"
    assert len(res["plan"]) == 1
    assert res["plan"][0].specialist == "codemate"
    assert res["plan"][0].status == "completed"
    # Verify llm_route was never invoked (no errors logged)
    assert len(res["errors"]) == 0


@pytest.mark.asyncio
async def test_agent_manager_deterministic_authcheck_route() -> None:
    """Verify deterministic security_review request executes AuthCheck."""
    manager = AgentManager(router=None, prompt_loader=None, interrupt_on_approval=False)
    state = _create_test_state(job_type="security_review", user_message="Audit route authorization")

    res = await manager.run(state)

    assert res["status"] == "completed"
    assert res["intent"] is not None
    assert res["intent"].category == "security"
    assert len(res["plan"]) == 1
    assert res["plan"][0].specialist == "authcheck"
    assert res["plan"][0].status == "completed"


@pytest.mark.asyncio
async def test_agent_manager_parallel_specialist_fanout() -> None:
    """Verify comprehensive_review executes both CodeMate and AuthCheck in parallel fan-out."""
    manager = AgentManager(router=None, prompt_loader=None, interrupt_on_approval=False)
    state = _create_test_state(job_type="comprehensive_review")

    res = await manager.run(state)

    assert res["status"] == "completed"
    assert len(res["plan"]) == 2
    specialist_statuses = {t.specialist: t.status for t in res["plan"]}
    assert specialist_statuses == {"codemate": "completed", "authcheck": "completed"}


@pytest.mark.asyncio
async def test_agent_manager_llm_route_branching() -> None:
    """Verify ambiguous requests take the llm_route branch before planning."""
    mock_router = AsyncMock(spec=LLMGatewayRouter)
    mock_plan = AgentPlan(
        summary="Explain symbols",
        steps=["Search symbols"],
        confidence=0.88,
        selected_agents=["CodeMate"],
        is_safe=True,
    )
    mock_resp = MagicMock(spec=LLMGenerationResponse)
    mock_resp.content = mock_plan
    mock_resp.raw_content = None
    mock_router.generate.return_value = mock_resp

    mock_loader = MagicMock()
    mock_loader.render.return_value = MagicMock(messages=[])

    manager = AgentManager(
        router=mock_router, prompt_loader=mock_loader, interrupt_on_approval=False
    )
    # Ambiguous query with no deterministic keyword
    state = _create_test_state(
        job_type="chat", user_message="Tell me something interesting about this project"
    )

    res = await manager.run(state)

    assert res["status"] == "completed"
    assert res["intent"] is not None
    assert res["intent"].category == "llm_classified"
    assert res["plan"][0].specialist == "codemate"
    assert res["plan"][0].status == "completed"


@pytest.mark.asyncio
async def test_agent_manager_approval_gate_interrupt_and_resume() -> None:
    """Verify approval gate interrupts execution on side-effect proposals and resumes after review."""
    checkpointer = InMemorySaver()
    manager = AgentManager(checkpointer=checkpointer, interrupt_on_approval=True)

    state = _create_test_state(job_type="security_review")
    # Attach a gated proposal that requires human approval (e.g. diff patch)
    state["proposals"] = [
        Proposal(
            proposal_type="diff_patch",
            title="Add missing @require_auth decorator",
            description="Patch unprotected endpoint",
            diff_content="+ @require_auth\n  def sensitive_api():",
            gated=True,
        )
    ]

    thread_id = format_thread_id(UUID(state["project_id"]), UUID(state["run_id"]))

    # 1. Run until approval interrupt
    interrupted_res = await manager.run(state, thread_id=thread_id)

    # Check that state stopped before approval node and status is awaiting_approval
    assert interrupted_res["status"] in ("running", "awaiting_approval")

    # Inspect checkpoint snapshot
    snapshot = manager.get_state(thread_id)
    assert snapshot.next == ("approval",)

    # 2. Resume execution through the approval gate
    resumed_res = await manager.resume(thread_id, resume_state=None)

    assert resumed_res["status"] in ("completed", "awaiting_approval")
    assert len(resumed_res["approvals"]) == 1
    appr = resumed_res["approvals"][0]
    assert appr.action_kind == "diff_patch"
    assert appr.status == "pending"
    assert "Add missing @require_auth" in appr.proposal["title"]


@pytest.mark.asyncio
async def test_agent_manager_astream_progress() -> None:
    """Verify astream yields step chunks during execution."""
    manager = AgentManager(router=None, prompt_loader=None, interrupt_on_approval=False)
    state = _create_test_state(job_type="ask_project", user_message="How does search work?")

    chunks = []
    async for chunk in manager.astream(state):
        chunks.append(chunk)

    assert len(chunks) > 0
    node_names = set().union(*[c.keys() for c in chunks])
    assert "intake" in node_names
    assert "classify" in node_names
    assert "plan" in node_names
    assert "codemate" in node_names
    assert "respond" in node_names
