"""Unit tests for AuthCheck workflow nodes, graph execution, and specialist integration (docs/05 §6.3, CAP-02, M7-06).

Tests:
1. Initial state creation with clean defaults.
2. analyze_routes_node extracting endpoints, guard chains, and E2 draft findings.
3. explain_findings_node with LLM rendering security_explanation prompt (v1) and schema validation.
4. explain_findings_node fallback when router is unavailable.
5. verify_evidence_node producing verified findings with grounded citation refs.
6. finalize_authcheck_node assembling structured markdown summary report.
7. Full AuthCheckAgent workflow execution on sample project routes.
8. AgentManager integration running AuthCheck specialist fan-out and updating RunState.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.analysis.guard_resolution import (
    RULE_MISSING_AUTH,
    RULE_MISSING_ROLE_CHECK,
)
from app.llm.models import (
    ChatMessage,
    LLMGenerationResponse,
    TokenUsage,
)
from app.llm.router import LLMGatewayRouter
from app.llm.schemas import FindingExplanation
from app.orchestration.authcheck import (
    AuthCheckAgent,
    AuthCheckResult,
    AuthCheckState,
    analyze_routes_node_factory,
    create_initial_authcheck_state,
    explain_findings_node_factory,
    finalize_authcheck_node,
    run_authcheck_specialist,
    verify_evidence_node,
)
from app.orchestration.manager import AgentManager
from app.orchestration.state import (
    DraftFinding,
    Proposal,
    SpecialistTask,
    create_initial_run_state,
)


def _create_sample_security_graph_data():
    """Create sample symbols and relationships with protected, unprotected, and missing-role routes."""
    route_unprotected_id = uuid4()
    route_missing_role_id = uuid4()
    route_protected_id = uuid4()
    route_public_id = uuid4()
    route_unsupported_id = uuid4()

    auth_guard_id = uuid4()
    role_guard_id = uuid4()

    symbols = [
        # 1. Unprotected sensitive route: DELETE /admin/system
        {
            "id": route_unprotected_id,
            "symbol_key": "delete_system_route",
            "name": "delete_system",
            "kind": "route_handler",
            "start_line": 10,
            "end_line": 25,
            "framework_tags": ["fastapi"],
            "metadata": {
                "path": "app/routes/admin.py",
                "http_method": "DELETE",
                "http_path": "/admin/system",
            },
        },
        # 2. Missing role check: GET /admin/users with authn but no authz
        {
            "id": route_missing_role_id,
            "symbol_key": "get_admin_users_route",
            "name": "get_admin_users",
            "kind": "route_handler",
            "start_line": 30,
            "end_line": 45,
            "framework_tags": ["fastapi"],
            "metadata": {
                "path": "app/routes/admin.py",
                "http_method": "GET",
                "http_path": "/admin/users",
            },
        },
        # 3. Protected route: POST /api/items with authn and authz
        {
            "id": route_protected_id,
            "symbol_key": "create_item_route",
            "name": "create_item",
            "kind": "route_handler",
            "start_line": 50,
            "end_line": 65,
            "framework_tags": ["fastapi"],
            "metadata": {
                "path": "app/routes/items.py",
                "http_method": "POST",
                "http_path": "/api/items",
            },
        },
        # 4. Public route: GET /healthz
        {
            "id": route_public_id,
            "symbol_key": "health_route",
            "name": "health_check",
            "kind": "route_handler",
            "start_line": 1,
            "end_line": 5,
            "framework_tags": ["fastapi"],
            "metadata": {
                "path": "app/main.py",
                "http_method": "GET",
                "http_path": "/healthz",
            },
        },
        # 5. Unsupported framework route
        {
            "id": route_unsupported_id,
            "symbol_key": "django_view",
            "name": "django_view",
            "kind": "function",
            "start_line": 1,
            "end_line": 10,
            "framework_tags": ["django"],
            "metadata": {
                "path": "myproject/views.py",
                "http_method": "GET",
                "http_path": "/unsupported",
                "framework": "django",
            },
        },
        # Guard symbols
        {
            "id": auth_guard_id,
            "symbol_key": "get_current_user",
            "name": "get_current_user",
            "kind": "function",
            "start_line": 1,
            "end_line": 15,
            "metadata": {},
        },
        {
            "id": role_guard_id,
            "symbol_key": "require_admin",
            "name": "require_admin",
            "kind": "function",
            "start_line": 20,
            "end_line": 35,
            "metadata": {},
        },
    ]

    relationships = [
        # route 2 guarded by authn only
        {
            "from_symbol_id": route_missing_role_id,
            "to_symbol_id": auth_guard_id,
            "kind": "guarded_by",
            "resolution": "resolved",
        },
        # route 3 guarded by authn and role check
        {
            "from_symbol_id": route_protected_id,
            "to_symbol_id": auth_guard_id,
            "kind": "guarded_by",
            "resolution": "resolved",
        },
        {
            "from_symbol_id": route_protected_id,
            "to_symbol_id": role_guard_id,
            "kind": "guarded_by",
            "resolution": "resolved",
        },
    ]

    return symbols, relationships


def test_create_initial_authcheck_state():
    state = create_initial_authcheck_state(
        project_id="proj-123",
        workspace_id="ws-456",
        user_query="Run security audit",
    )
    assert state["project_id"] == "proj-123"
    assert state["workspace_id"] == "ws-456"
    assert state["user_query"] == "Run security audit"
    assert state["draft_findings"] == []
    assert state["proposals"] == []
    assert state["hypotheses"] == []
    assert state["summary_report"] == ""


@pytest.mark.asyncio
async def test_analyze_routes_node():
    symbols, relationships = _create_sample_security_graph_data()
    state = create_initial_authcheck_state(
        project_id="proj-123",
        workspace_id="ws-456",
        symbols=symbols,
        relationships=relationships,
    )

    node_func = analyze_routes_node_factory(session=None)
    update = await node_func(state)

    drafts = update["draft_findings"]
    evals = update["evaluations"]
    unsupported = update["unsupported_routes"]
    assert len(evals) == 5

    # Expecting 2 draft findings: missing auth on route 1, missing role on route 2
    assert len(drafts) == 2
    rule_ids = {d.rule_id for d in drafts}
    assert RULE_MISSING_AUTH in rule_ids
    assert RULE_MISSING_ROLE_CHECK in rule_ids

    # Check analysis_scope in finding explanation
    for d in drafts:
        assert "Analysis scope:" in d.explanation
        assert "0 unresolved dependencies" in d.explanation

    # Check unsupported route
    assert len(unsupported) == 1
    assert "Unsupported framework" in unsupported[0]["reason"]


@pytest.mark.asyncio
async def test_explain_findings_node_with_llm():
    """Test explain_findings_node rendering security_explanation prompt and validating FindingExplanation."""
    symbols, relationships = _create_sample_security_graph_data()
    analyze_node = analyze_routes_node_factory(session=None)
    state = create_initial_authcheck_state(
        project_id="proj-123",
        workspace_id="ws-456",
        symbols=symbols,
        relationships=relationships,
    )
    analyzed_state = await analyze_node(state)
    state.update(analyzed_state)

    # Mock router and prompt loader
    mock_prompt_loader = MagicMock()
    mock_rendered = MagicMock()
    mock_rendered.messages = [ChatMessage(role="user", content="Explain finding")]
    mock_prompt_loader.render.return_value = mock_rendered

    mock_router = AsyncMock(spec=LLMGatewayRouter)
    llm_explanation = FindingExplanation(
        summary="Administrative endpoint lacks role check",
        impact="Callers can perform unauthorized admin actions",
        likely_cause="Route does not require admin dependency",
        remediation_proposal="Add Depends(require_admin) to route definition",
        false_positive_indicators=["Object-level authorization handled in callee"],
        confidence=0.92,
    )
    mock_resp = LLMGenerationResponse(
        provider_id="fake",
        model_id="fake-model",
        content=llm_explanation.model_dump_json(),
        raw_content=llm_explanation.model_dump_json(),
        usage=TokenUsage(input_tokens=150, output_tokens=80, total_tokens=230),
    )
    mock_router.generate.return_value = mock_resp

    explain_node = explain_findings_node_factory(
        router=mock_router,
        prompt_loader=mock_prompt_loader,
    )
    update = await explain_node(state)

    proposals = update["proposals"]
    hypotheses = update["hypotheses"]
    usage = update["usage"]

    assert len(proposals) == 2
    assert all(isinstance(p, Proposal) for p in proposals)
    assert any("Depends(require_admin)" in p.description for p in proposals)

    assert len(hypotheses) == 2
    assert any("Object-level authorization" in h.statement for h in hypotheses)

    assert usage.model_calls == 2
    assert usage.total_input_tokens == 300
    assert usage.total_output_tokens == 160


@pytest.mark.asyncio
async def test_explain_findings_node_deterministic_fallback():
    """Test explain_findings_node produces deterministic explanations when router is None."""
    symbols, relationships = _create_sample_security_graph_data()
    analyze_node = analyze_routes_node_factory(session=None)
    state = create_initial_authcheck_state(
        project_id="proj-123",
        workspace_id="ws-456",
        symbols=symbols,
        relationships=relationships,
    )
    analyzed_state = await analyze_node(state)
    state.update(analyzed_state)

    explain_node = explain_findings_node_factory(router=None, prompt_loader=None)
    update = await explain_node(state)

    drafts = update["draft_findings"]
    proposals = update["proposals"]

    assert len(proposals) == 2
    for d in drafts:
        assert "**Impact**:" in d.explanation
        assert "**Likely Cause**:" in d.explanation


def test_verify_evidence_node():
    draft = DraftFinding(
        draft_id="df_1234567890ab",
        finding_type="authorization",
        title="Admin route missing role check",
        file_path="app/routes/admin.py",
        line_range=(30, 45),
        rule_id=RULE_MISSING_ROLE_CHECK,
        severity="high",
        evidence_refs=["app/routes/admin.py:30-45"],
        explanation="Missing role check on admin route",
    )
    state: AuthCheckState = {"draft_findings": [draft]}
    update = verify_evidence_node(state)

    verified = update["verified_findings"]
    assert len(verified) == 1
    vf = verified[0]
    assert vf.draft_id == "df_1234567890ab"
    assert vf.is_verified is True
    assert vf.citation_ref == "app/routes/admin.py:30-45"
    assert vf.evidence_level == 2


def test_finalize_authcheck_node():
    eval_mock = MagicMock()
    eval_mock.status = "protected"
    state: AuthCheckState = {
        "evaluations": [eval_mock],
        "draft_findings": [
            DraftFinding(
                draft_id="df_123",
                finding_type="authorization",
                title="Admin route has no role check",
                file_path="app/routes/admin.py",
                line_range=(10, 20),
                rule_id=RULE_MISSING_ROLE_CHECK,
                severity="high",
                explanation="No authorization check found on analyzed call path.",
            )
        ],
        "unsupported_routes": [
            {"route": "GET /unsupported", "file": "app/views.py", "reason": "Unsupported framework"}
        ],
    }

    update = finalize_authcheck_node(state)
    report = update["summary_report"]

    assert "## AuthCheck Security Review" in report
    assert "**Missing Role Check (Authorization)**: 0" in report
    assert "Admin route has no role check" in report
    assert "Unsupported framework" in report
    assert "absence of finding is not safe" in report


@pytest.mark.asyncio
async def test_full_authcheck_agent_workflow():
    """Test full compiled AuthCheck graph execution via AuthCheckAgent."""
    symbols, relationships = _create_sample_security_graph_data()
    agent = AuthCheckAgent(router=None, prompt_loader=None)

    res: AuthCheckResult = await agent.check_security(
        project_id="018f0000-0000-7000-8000-000000000001",
        workspace_id="018f0000-0000-7000-8000-000000000002",
        symbols=symbols,
        relationships=relationships,
    )

    assert res.total_routes_discovered == 5
    assert res.protected_count == 1
    assert res.missing_auth_count == 1
    assert res.missing_authz_count == 1
    assert res.public_exempt_count == 1
    assert res.unsupported_count == 1

    assert len(res.draft_findings) == 2
    assert len(res.verified_findings) == 2
    assert len(res.proposals) == 2
    assert "AuthCheck Security Review" in res.summary_report


@pytest.mark.asyncio
async def test_run_authcheck_specialist_inside_agent_manager():
    """Test run_authcheck_specialist execution as part of AgentManager workflow."""
    symbols, relationships = _create_sample_security_graph_data()
    run_state = create_initial_run_state(
        run_id="run_authcheck_test_01",
        job_id="job_01",
        project_id="018f0000-0000-7000-8000-000000000001",
        workspace_id="018f0000-0000-7000-8000-000000000002",
        actor_id="user_01",
        job_type="security_review",
        user_message="Audit route authorization",
        params={"symbols": symbols, "relationships": relationships},
    )
    run_state["plan"] = [
        SpecialistTask(specialist="authcheck", task_id="authcheck_01", status="pending")
    ]

    res = await run_authcheck_specialist(run_state)

    completed_tasks = res["plan"]
    assert len(completed_tasks) == 1
    assert completed_tasks[0].status == "completed"
    assert completed_tasks[0].specialist == "authcheck"

    assert len(res["drafts"]) == 2
    assert len(res["verified"]) == 2
    assert len(res["proposals"]) == 2
    assert "AuthCheck Security Review" in res["final_response"]


@pytest.mark.asyncio
async def test_agent_manager_executes_authcheck_graph():
    """Test AgentManager graph end-to-end routing security_review to AuthCheck."""
    symbols, relationships = _create_sample_security_graph_data()
    manager = AgentManager()

    init_state = create_initial_run_state(
        run_id="run_mgr_authcheck_01",
        job_id="job_02",
        project_id="018f0000-0000-7000-8000-000000000001",
        workspace_id="018f0000-0000-7000-8000-000000000002",
        actor_id="user_01",
        job_type="security_review",
        user_message="Check endpoint authorization",
        params={"symbols": symbols, "relationships": relationships},
    )

    final_state = await manager.run(init_state)

    # AgentManager should route to authcheck, run it, pass verify, and reach completed or awaiting_approval
    plan = final_state.get("plan", [])
    auth_task = next((t for t in plan if t.specialist == "authcheck"), None)
    assert auth_task is not None
    assert auth_task.status == "completed"

    assert len(final_state.get("drafts", [])) == 2
    assert len(final_state.get("verified", [])) >= 2
    assert len(final_state.get("proposals", [])) == 2
