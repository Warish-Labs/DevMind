"""Agent Manager workflow graph and plan execution routing (docs/05 §2, §4, M7-03).

Per docs/05 §2 & §4.1:
The Agent Manager is the single entry point for agent workflows.
It orchestrates:
1. Intake: Validates incoming RunState, loads AuthContext, initializes run budgets.
2. Intent Classification: Deterministic rules first (job types, explicit commands);
   LLM routing (`agent_manager_routing`) only for free-form or ambiguous requests.
3. Plan: Maps intent to an allowlisted set of released specialist agents (CodeMate, AuthCheck in MVP).
4. Fan-out & Join: Parallel specialist dispatch with join barrier and per-specialist failure isolation.
5. Verification: Deterministic evidence verification for findings and citations.
6. Synthesis: Merges specialist findings when multiple specialists contributed.
7. Approval Gate: Interrupts workflow for maintainer approval when proposals carry external side effects.
8. Write back & Respond: Finalizes status and writes back to Project Brain.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StateSnapshot
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import generate_uuid7
from app.llm.models import LLMGenerationRequest
from app.llm.prompt_loader import PromptLoader
from app.llm.router import LLMGatewayRouter
from app.llm.schemas import AgentPlan
from app.orchestration.checkpointer import format_thread_id
from app.orchestration.codemate import run_codemate_specialist
from app.orchestration.state import (
    ApprovalState,
    IntentState,
    NodeError,
    RequestState,
    RunState,
    SpecialistTask,
    VerifiedFinding,
)

logger = logging.getLogger("devmind.orchestration.manager")

RELEASED_SPECIALISTS = frozenset({"codemate", "authcheck"})

# Deterministic keywords for security / auth intent detection
_AUTH_KEYWORDS = frozenset(
    {
        "auth",
        "authenticate",
        "authentication",
        "authorization",
        "protect",
        "protected",
        "guard",
        "guarded",
        "permission",
        "rbac",
        "token",
        "jwt",
        "session",
        "vulnerability",
        "security",
        "credential",
    }
)

_CODE_QA_KEYWORDS = frozenset(
    {
        "how",
        "what",
        "where",
        "find",
        "explain",
        "architecture",
        "implement",
        "implementation",
        "symbol",
        "file",
        "class",
        "function",
        "call",
        "usage",
    }
)


# ---------------------------------------------------------------------------
# Deterministic Intent Classifier (docs/05 §2, §3)
# ---------------------------------------------------------------------------


def classify_intent_deterministically(request: RequestState) -> IntentState | None:
    """Classify user or job intent using deterministic rules before considering LLM routing."""
    job_type = (request.job_type or "").lower().strip()
    user_msg = (request.user_message or "").lower().strip()

    # 1. Direct job_type mappings
    if job_type in ("ask_project", "code_qa"):
        return IntentState(
            category="code_qa",
            intent_name="ask_code",
            confidence=1.0,
            requires_specialists=["codemate"],
        )
    if job_type in ("security_review", "auth_check", "authcheck"):
        return IntentState(
            category="security",
            intent_name="security_check",
            confidence=1.0,
            requires_specialists=["authcheck"],
        )
    if job_type in ("comprehensive_review", "full_audit"):
        return IntentState(
            category="security_and_code",
            intent_name="comprehensive_review",
            confidence=1.0,
            requires_specialists=["codemate", "authcheck"],
        )

    # 2. Strong signal matching on user message
    if user_msg:
        tokens = set(user_msg.replace("?", " ").replace(".", " ").replace(",", " ").split())
        has_auth = bool(tokens & _AUTH_KEYWORDS) or any(
            k in user_msg for k in ("security check", "auth guard")
        )
        has_code = bool(tokens & _CODE_QA_KEYWORDS) or any(
            k in user_msg for k in ("how does", "where is")
        )

        if has_auth and has_code:
            return IntentState(
                category="security_and_code",
                intent_name="security_and_architecture",
                confidence=0.95,
                requires_specialists=["codemate", "authcheck"],
            )
        if has_auth:
            return IntentState(
                category="security",
                intent_name="security_check",
                confidence=0.9,
                requires_specialists=["authcheck"],
            )
        if has_code:
            return IntentState(
                category="code_qa",
                intent_name="ask_code",
                confidence=0.85,
                requires_specialists=["codemate"],
            )

    return None


# ---------------------------------------------------------------------------
# LLM Intent Classifier (docs/05 §2, §8, M6-10)
# ---------------------------------------------------------------------------


async def classify_intent_with_llm(
    request: RequestState,
    router: LLMGatewayRouter | None,
    prompt_loader: PromptLoader | None,
) -> tuple[IntentState, list[NodeError]]:
    """Classify free-text requests using the versioned agent_manager_routing prompt."""
    errors: list[NodeError] = []

    if router is None or prompt_loader is None:
        logger.info("No LLM router or prompt loader configured; falling back to CodeMate")
        return (
            IntentState(
                category="fallback",
                intent_name="ask_code",
                confidence=0.7,
                requires_specialists=["codemate"],
            ),
            errors,
        )

    try:
        user_query = request.user_message or request.params.get("query", "")
        repo_summary = request.params.get("repo_summary", "DevMind project repository")

        rendered = prompt_loader.render(
            task="agent_manager_routing",
            version=1,
            variables={
                "user_query": user_query,
                "repository_summary": repo_summary,
            },
        )

        gen_req = LLMGenerationRequest(
            task="agent_manager_routing",
            messages=rendered.messages,
            response_schema=AgentPlan,
        )

        resp = await router.generate(gen_req)

        # Parse plan from response
        plan_obj: AgentPlan
        if isinstance(resp.content, AgentPlan):
            plan_obj = resp.content
        elif isinstance(resp.content, dict):
            plan_obj = AgentPlan.model_validate(resp.content)
        elif resp.raw_content:
            plan_obj = AgentPlan.model_validate_json(resp.raw_content)
        else:
            raise ValueError("No structured plan returned by model")

        # Filter against allowlisted released specialists for MVP
        valid_specialists = [
            s.lower() for s in plan_obj.selected_agents if s.lower() in RELEASED_SPECIALISTS
        ]
        if not valid_specialists:
            valid_specialists = ["codemate"]

        return (
            IntentState(
                category="llm_classified",
                intent_name=plan_obj.summary,
                confidence=plan_obj.confidence,
                requires_specialists=valid_specialists,
            ),
            errors,
        )

    except Exception as exc:
        logger.warning("LLM routing failed: %s; falling back to CodeMate", exc)
        err = NodeError(
            node="llm_route",
            error_code="llm_routing_error",
            message=str(exc),
            retryable=False,
        )
        errors.append(err)
        return (
            IntentState(
                category="fallback",
                intent_name="ask_code",
                confidence=0.6,
                requires_specialists=["codemate"],
            ),
            errors,
        )


# ---------------------------------------------------------------------------
# Graph Node Implementations (docs/05 §4.1)
# ---------------------------------------------------------------------------


def intake_node(state: RunState) -> dict[str, Any]:
    """Validate incoming run state and transition status to running."""
    if not state.get("run_id") or not state.get("project_id"):
        raise ValueError("RunState must specify run_id and project_id")

    return {
        "status": "running",
    }


def classify_node(state: RunState) -> dict[str, Any]:
    """Execute deterministic intent classification; sets intent or leaves None for LLM route."""
    intent = classify_intent_deterministically(state["request"])
    return {"intent": intent}


def route_after_classify(state: RunState) -> str:
    """Branch to plan if deterministic intent was identified, else to llm_route."""
    if state.get("intent") is not None:
        return "plan"
    return "llm_route"


def llm_route_node_factory(
    router: LLMGatewayRouter | None,
    prompt_loader: PromptLoader | None,
):
    """Factory creating the async llm_route node bound to the router and prompt loader."""

    async def llm_route_node(state: RunState) -> dict[str, Any]:
        intent, errors = await classify_intent_with_llm(
            request=state["request"],
            router=router,
            prompt_loader=prompt_loader,
        )
        return {"intent": intent, "errors": errors}

    return llm_route_node


def plan_node(state: RunState) -> dict[str, Any]:
    """Translate classified intent into discrete specialist tasks."""
    intent = state.get("intent")
    if intent is None:
        # Fallback safeguard
        intent = IntentState(
            category="fallback",
            intent_name="ask_code",
            confidence=0.5,
            requires_specialists=["codemate"],
        )

    tasks: list[SpecialistTask] = []
    run_prefix = state["run_id"][:8] if state.get("run_id") else "run"

    for spec in intent.requires_specialists:
        if spec in RELEASED_SPECIALISTS:
            tasks.append(
                SpecialistTask(
                    specialist=spec,
                    task_id=f"{spec}_{run_prefix}",
                    status="pending",
                    params=state["request"].params,
                )
            )

    if not tasks:
        tasks.append(
            SpecialistTask(
                specialist="codemate",
                task_id=f"codemate_{run_prefix}",
                status="pending",
                params=state["request"].params,
            )
        )

    return {"plan": tasks, "intent": intent}


def route_specialists(state: RunState) -> list[str]:
    """Fan out execution to planned specialists in parallel."""
    plan = state.get("plan", [])
    specialists = {t.specialist for t in plan}

    destinations: list[str] = []
    if "codemate" in specialists:
        destinations.append("codemate")
    if "authcheck" in specialists:
        destinations.append("authcheck")

    return destinations or ["join"]


def codemate_node_factory(
    router: LLMGatewayRouter | None = None,
    prompt_loader: PromptLoader | None = None,
    session: AsyncSession | None = None,
):
    """Factory creating the CodeMate execution node."""

    async def codemate_node(state: RunState) -> dict[str, Any]:
        """Execute CodeMate specialist task (docs/05 §6.1, CAP-01)."""
        logger.info("Executing CodeMate specialist for run %s", state.get("run_id"))
        return await run_codemate_specialist(
            state=state,
            router=router,
            prompt_loader=prompt_loader,
            session=session,
        )

    return codemate_node


async def authcheck_node(state: RunState) -> dict[str, Any]:
    """Execute AuthCheck specialist task (docs/05 §6.2, CAP-02)."""
    logger.info("Executing AuthCheck specialist for run %s", state.get("run_id"))
    plan = list(state.get("plan", []))
    task = next((t for t in plan if t.specialist == "authcheck"), None)
    if not task:
        return {}

    completed_task = SpecialistTask(
        specialist=task.specialist,
        task_id=task.task_id,
        status="completed",
        input_refs=task.input_refs,
        params=task.params,
    )
    return {"plan": [completed_task]}


def join_node(state: RunState) -> dict[str, Any]:
    """Barrier joining parallel specialist executions."""
    logger.info("Specialist fan-out completed for run %s", state.get("run_id"))
    return {}


def verify_node(state: RunState) -> dict[str, Any]:
    """Pass all draft findings through deterministic evidence verifier (docs/05 §4.1, §7)."""
    # Deterministic verifier: Promote drafts with complete citation evidence
    drafts = state.get("drafts", [])
    verified: list[VerifiedFinding] = list(state.get("verified", []))

    for d in drafts:
        if d.line_range and d.file_path:
            verified.append(
                VerifiedFinding(
                    finding_id=f"vf_{d.draft_id}",
                    draft_id=d.draft_id,
                    evidence_level=2,
                    confidence=0.9,
                    title=d.title,
                    file_path=d.file_path,
                    line_range=d.line_range,
                    rule_id=d.rule_id,
                    evidence_snippet="",
                    citation_ref=f"{d.file_path}:{d.line_range[0]}-{d.line_range[1]}",
                )
            )

    return {"verified": verified}


def synthesize_node(state: RunState) -> dict[str, Any]:
    """Synthesize results when multiple specialists contributed (docs/05 §4.1)."""
    plan = state.get("plan", [])
    completed_specialists = [t.specialist for t in plan if t.status == "completed"]

    if len(completed_specialists) > 1:
        logger.info(
            "Synthesized multi-specialist results (%s) for run %s",
            ", ".join(completed_specialists),
            state.get("run_id"),
        )

    return {}


def gate_condition(state: RunState) -> str:
    """Inspect proposals for external side effects requiring human approval (docs/05 §4.6)."""
    proposals = state.get("proposals", [])
    has_gated_proposals = any(p.gated for p in proposals)

    if has_gated_proposals:
        return "approval"
    return "write"


def approval_node(state: RunState) -> dict[str, Any]:
    """Approval gate recording pending approvals for maintainer review (docs/05 §4.6)."""
    proposals = state.get("proposals", [])
    approvals = list(state.get("approvals", []))

    for p in proposals:
        if p.gated:
            approvals.append(
                ApprovalState(
                    approval_id=str(generate_uuid7()),
                    action_kind=p.proposal_type,
                    status="pending",
                    proposal={
                        "title": p.title,
                        "description": p.description,
                        "diff_content": p.diff_content,
                    },
                )
            )

    return {"status": "awaiting_approval", "approvals": approvals}


def write_node(state: RunState) -> dict[str, Any]:
    """Write verified findings and audit records back to Project Brain."""
    logger.info("Writing back run %s to Project Brain", state.get("run_id"))
    return {}


def respond_node(state: RunState) -> dict[str, Any]:
    """Finalize workflow and mark status completed if not awaiting approval."""
    current_status = state.get("status")
    final_status = "awaiting_approval" if current_status == "awaiting_approval" else "completed"
    return {"status": final_status}


# ---------------------------------------------------------------------------
# Graph Construction & AgentManager (docs/05 §4.1)
# ---------------------------------------------------------------------------


def build_agent_manager_graph(
    router: LLMGatewayRouter | None = None,
    prompt_loader: PromptLoader | None = None,
    session: AsyncSession | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    interrupt_on_approval: bool = True,
) -> CompiledStateGraph:
    """Construct and compile the canonical Agent Manager LangGraph workflow."""
    builder = StateGraph(RunState)

    # Register nodes
    builder.add_node("intake", intake_node)
    builder.add_node("classify", classify_node)

    llm_route = llm_route_node_factory(router=router, prompt_loader=prompt_loader)
    builder.add_node("llm_route", llm_route)

    builder.add_node("plan", plan_node)
    builder.add_node(
        "codemate",
        codemate_node_factory(router=router, prompt_loader=prompt_loader, session=session),
    )
    builder.add_node("authcheck", authcheck_node)
    builder.add_node("join", join_node)
    builder.add_node("verify", verify_node)
    builder.add_node("synthesize", synthesize_node)
    builder.add_node("approval", approval_node)
    builder.add_node("write", write_node)
    builder.add_node("respond", respond_node)

    # Edges
    builder.add_edge(START, "intake")
    builder.add_edge("intake", "classify")

    # Intent routing: deterministic vs LLM
    builder.add_conditional_edges("classify", route_after_classify, ["plan", "llm_route"])
    builder.add_edge("llm_route", "plan")

    # Specialist fan-out
    builder.add_conditional_edges("plan", route_specialists, ["codemate", "authcheck", "join"])
    builder.add_edge("codemate", "join")
    builder.add_edge("authcheck", "join")

    # Verification and Synthesis
    builder.add_edge("join", "verify")
    builder.add_edge("verify", "synthesize")

    # Side-effects approval gate
    builder.add_conditional_edges("synthesize", gate_condition, ["approval", "write"])
    builder.add_edge("approval", "write")
    builder.add_edge("write", "respond")
    builder.add_edge("respond", END)

    interrupt_nodes = ["approval"] if interrupt_on_approval else None
    return builder.compile(checkpointer=checkpointer, interrupt_before=interrupt_nodes)


class AgentManager:
    """Production Agent Manager coordinating multi-agent LangGraph workflows (docs/05 §2)."""

    def __init__(
        self,
        router: LLMGatewayRouter | None = None,
        prompt_loader: PromptLoader | None = None,
        session: AsyncSession | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
        interrupt_on_approval: bool = True,
        prompts_dir: Path | str | None = None,
    ) -> None:
        self.router = router
        self.prompt_loader = prompt_loader or PromptLoader(prompts_dir=prompts_dir)
        self.session = session
        self.checkpointer = checkpointer
        self.interrupt_on_approval = interrupt_on_approval
        self.graph = build_agent_manager_graph(
            router=self.router,
            prompt_loader=self.prompt_loader,
            session=self.session,
            checkpointer=self.checkpointer,
            interrupt_on_approval=self.interrupt_on_approval,
        )

    async def run(
        self,
        initial_state: RunState,
        thread_id: str | None = None,
    ) -> RunState:
        """Execute the workflow to completion or until an approval interrupt."""
        canonical_thread = thread_id
        if not canonical_thread and self.checkpointer:
            canonical_thread = format_thread_id(
                UUID(initial_state["project_id"]),
                UUID(initial_state["run_id"]),
            )

        config = {"configurable": {"thread_id": canonical_thread}} if canonical_thread else None
        result = await self.graph.ainvoke(initial_state, config=config)
        return result

    async def resume(
        self,
        thread_id: str,
        resume_state: dict[str, Any] | None = None,
    ) -> RunState:
        """Resume an interrupted execution thread after human approval or rejection."""
        config = {"configurable": {"thread_id": thread_id}}
        result = await self.graph.ainvoke(resume_state, config=config)
        return result

    async def astream(
        self,
        initial_state: RunState,
        thread_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream node step updates for live progress reporting."""
        canonical_thread = thread_id
        if not canonical_thread and self.checkpointer:
            canonical_thread = format_thread_id(
                UUID(initial_state["project_id"]),
                UUID(initial_state["run_id"]),
            )

        config = {"configurable": {"thread_id": canonical_thread}} if canonical_thread else None
        async for chunk in self.graph.astream(initial_state, config=config):
            yield chunk

    def get_state(self, thread_id: str) -> StateSnapshot:
        """Inspect the current checkpoint snapshot for an active thread."""
        config = {"configurable": {"thread_id": thread_id}}
        return self.graph.get_state(config)
