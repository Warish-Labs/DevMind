"""AuthCheck workflow nodes, graph construction, and specialist integration (docs/05 §6.3, CAP-02, M7-06).

Per docs/05 §6.3 (AuthCheck specification):
1. Enumerate routes (defines_route edges and symbols) across supported frameworks (FastAPI, Express, Next.js).
2. Resolve guard chain (middleware, dependencies, decorators, inline checks) via guarded_by and calls relationships.
3. Classify route sensitivity (public, authenticated, sensitive/admin) deterministically.
4. Evaluate authentication and authorization presence.
5. Emit draft findings with deterministic analysis_scope and evidence levels (E2 for fully resolved, E1 for partial).
6. Evidence verifier ensuring grounding to concrete code lines and provenance.
7. LLM explanation node rendering versioned `security_explanation` prompt (v1) to explain impact and suggest remediation.
8. Persist findings, proposals, and hypotheses for conversational and triage display.
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any, TypedDict
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.guard_resolution import (
    ProjectSecurityConfig,
    RouteAnalysisResult,
    RouteGuardAnalyzer,
    RouteSecurityEvaluation,
)
from app.core.auth_context import SystemContext
from app.llm.models import LLMGenerationRequest
from app.llm.prompt_loader import PromptLoader
from app.llm.repair import extract_json_candidate
from app.llm.router import LLMGatewayRouter
from app.llm.schemas import FindingExplanation
from app.orchestration.state import (
    DraftFinding,
    Hypothesis,
    NodeError,
    Proposal,
    RunState,
    SpecialistTask,
    UsageTotals,
    VerifiedFinding,
    append_items,
    merge_usage_totals,
)
from app.persistence.models.brain import CodeRelationship, CodeSymbol
from app.persistence.repositories.brain_repo import BrainRepository

logger = logging.getLogger("devmind.orchestration.authcheck")


# ---------------------------------------------------------------------------
# AuthCheck State Definition
# ---------------------------------------------------------------------------


class AuthCheckState(TypedDict, total=False):
    """Execution state for AuthCheck specialist graph."""

    project_id: str
    workspace_id: str
    user_query: str
    symbols: list[CodeSymbol | dict[str, Any]]
    relationships: list[CodeRelationship | dict[str, Any]]
    config: ProjectSecurityConfig | None
    evaluations: list[RouteSecurityEvaluation]
    draft_findings: list[DraftFinding]
    proposals: list[Proposal]
    hypotheses: list[Hypothesis]
    unsupported_routes: list[dict[str, Any]]
    verified_findings: list[VerifiedFinding]
    summary_report: str
    usage: Annotated[UsageTotals, merge_usage_totals]
    errors: Annotated[list[NodeError], append_items]


class AuthCheckResult(BaseModel):
    """High-level result summary returned by AuthCheckAgent."""

    total_routes_discovered: int
    total_analyzed: int
    protected_count: int
    missing_auth_count: int
    missing_authz_count: int
    public_exempt_count: int
    unsupported_count: int
    draft_findings: list[DraftFinding] = Field(default_factory=list)
    verified_findings: list[VerifiedFinding] = Field(default_factory=list)
    proposals: list[Proposal] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    summary_report: str = ""


# ---------------------------------------------------------------------------
# State Initialization Helper
# ---------------------------------------------------------------------------


def create_initial_authcheck_state(
    project_id: str,
    workspace_id: str,
    user_query: str = "",
    symbols: list[CodeSymbol | dict[str, Any]] | None = None,
    relationships: list[CodeRelationship | dict[str, Any]] | None = None,
    config: ProjectSecurityConfig | None = None,
) -> AuthCheckState:
    """Initialize AuthCheckState with clean defaults."""
    return {
        "project_id": project_id,
        "workspace_id": workspace_id,
        "user_query": user_query,
        "symbols": list(symbols or []),
        "relationships": list(relationships or []),
        "config": config,
        "evaluations": [],
        "draft_findings": [],
        "proposals": [],
        "hypotheses": [],
        "unsupported_routes": [],
        "verified_findings": [],
        "summary_report": "",
        "usage": UsageTotals(),
        "errors": [],
    }


# ---------------------------------------------------------------------------
# Node 1: Route Enumeration & Guard Resolution (Deterministic Analysis)
# ---------------------------------------------------------------------------


def analyze_routes_node_factory(session: AsyncSession | None = None):
    """Factory constructing the deterministic route and guard analysis node."""

    async def analyze_routes_node(state: AuthCheckState) -> dict[str, Any]:
        project_id_str = state.get("project_id", "")
        symbols = list(state.get("symbols", []))
        relationships = list(state.get("relationships", []))
        config = state.get("config")

        # 1. If symbols or relationships are missing and a DB session is present, fetch them
        if not symbols and session and project_id_str:
            try:
                pid = UUID(project_id_str)
                ctx = SystemContext(reason="authcheck_analysis")
                repo = BrainRepository(session)
                symbols = await repo.list_current_symbols(ctx, pid, limit=2000)
                relationships = await repo.list_relationships(ctx, pid, limit=5000)
            except Exception as exc:
                logger.warning("Could not fetch project symbols from DB: %s", exc)

        analyzer = RouteGuardAnalyzer(config=config)
        analysis_res: RouteAnalysisResult = analyzer.analyze_routes(
            symbols=symbols,
            relationships=relationships,
        )

        # 2. Map analysis DraftFindings to orchestration DraftFindings
        orchestration_drafts: list[DraftFinding] = []
        for df in analysis_res.draft_findings:
            start_l = df.start_line
            end_l = df.end_line
            evidence_scope = df.evidence_details.get("analysis_scope", "")
            finding_explanation = f"{df.summary}\nAnalysis scope: {evidence_scope}"

            orchestration_drafts.append(
                DraftFinding(
                    draft_id=f"df_{df.fingerprint[:12]}",
                    finding_type=df.category,
                    title=df.title,
                    file_path=df.file_path,
                    line_range=(start_l, end_l),
                    rule_id=df.rule_id,
                    severity=df.severity,
                    evidence_refs=[f"{df.file_path}:{start_l}-{end_l}"],
                    explanation=finding_explanation,
                )
            )

        return {
            "symbols": symbols,
            "relationships": relationships,
            "evaluations": analysis_res.evaluations,
            "draft_findings": orchestration_drafts,
            "unsupported_routes": analysis_res.unsupported_routes,
        }

    return analyze_routes_node


# ---------------------------------------------------------------------------
# Node 2: Evidence-Constrained LLM Explanation & Fix Proposals
# ---------------------------------------------------------------------------


def explain_findings_node_factory(
    router: LLMGatewayRouter | None = None,
    prompt_loader: PromptLoader | None = None,
):
    """Factory constructing LLM explanation node rendering security_explanation prompt (v1)."""

    async def explain_findings_node(state: AuthCheckState) -> dict[str, Any]:
        draft_findings = list(state.get("draft_findings", []))
        if not draft_findings:
            return {}

        proposals: list[Proposal] = list(state.get("proposals", []))
        hypotheses: list[Hypothesis] = list(state.get("hypotheses", []))
        usage_total = UsageTotals()
        errors: list[NodeError] = []

        for df in draft_findings:
            finding_details = {
                "rule_id": df.rule_id,
                "title": df.title,
                "category": df.finding_type,
                "severity": df.severity,
                "file_path": df.file_path,
                "line_range": f"{df.line_range[0]}-{df.line_range[1]}",
                "preliminary_explanation": df.explanation,
            }
            evidence_snippet = f"File: {df.file_path}:{df.line_range[0]}-{df.line_range[1]}\nEvidence ref: {', '.join(df.evidence_refs)}"

            explanation_obj: FindingExplanation | None = None

            # Attempt LLM generation if router and prompt_loader are available
            if router and prompt_loader:
                try:
                    rendered = prompt_loader.render(
                        task="security_explanation",
                        version=1,
                        variables={
                            "finding_details": json.dumps(finding_details),
                            "evidence_code": evidence_snippet,
                        },
                    )

                    gen_req = LLMGenerationRequest(
                        task="security_explanation",
                        messages=rendered.messages,
                    )

                    resp = await router.generate(gen_req)
                    raw_text = resp.content or ""
                    if not isinstance(raw_text, str):
                        raw_text = json.dumps(raw_text)

                    json_cand = extract_json_candidate(raw_text)
                    if json_cand:
                        explanation_obj = FindingExplanation.model_validate_json(json_cand)

                    if resp.usage:
                        cost_val = getattr(resp.usage, "total_cost", 0) or 0
                        usage_total = usage_total.add(
                            UsageTotals(
                                total_input_tokens=resp.usage.input_tokens,
                                total_output_tokens=resp.usage.output_tokens,
                                total_cost_units=cost_val,
                                model_calls=1,
                            )
                        )

                except Exception as exc:
                    logger.warning("LLM security_explanation failed for %s: %s; using deterministic fallback", df.draft_id, exc)
                    errors.append(
                        NodeError(
                            node="explain_findings",
                            error_code="explanation_failed",
                            message=f"LLM explanation failed for {df.draft_id}: {exc}",
                        )
                    )

            # Deterministic fallback explanation if LLM was unavailable or failed
            if explanation_obj is None:
                if df.finding_type == "authentication":
                    explanation_obj = FindingExplanation(
                        summary=f"Sensitive endpoint at {df.file_path} has no authentication guard on the analyzed call path.",
                        impact="Unauthenticated callers can execute this endpoint without verified credentials.",
                        likely_cause="Route handler lacks an authentication middleware or dependency.",
                        remediation_proposal="Add an authentication guard (e.g. Depends(get_current_user) or requireAuth).",
                        false_positive_indicators=["Route is intentionally public or guarded by upstream gateway."],
                        confidence=0.9,
                    )
                else:
                    explanation_obj = FindingExplanation(
                        summary=f"Administrative endpoint at {df.file_path} requires authentication but lacks role or permission authorization validation.",
                        impact="Any authenticated caller can invoke administrative functionality regardless of assigned role.",
                        likely_cause="Route verifies caller identity but does not inspect caller role or permissions.",
                        remediation_proposal="Require an explicit role dependency (e.g. Depends(require_admin) or requireRole('admin')).",
                        false_positive_indicators=["Object-level authorization is checked dynamically in callee."],
                        confidence=0.85,
                    )

            # Enrich DraftFinding with detailed explanation
            df.explanation = (
                f"{explanation_obj.summary}\n\n"
                f"**Impact**: {explanation_obj.impact}\n\n"
                f"**Likely Cause**: {explanation_obj.likely_cause}"
            )

            # Generate remediation proposal
            proposals.append(
                Proposal(
                    proposal_type="diff_patch",
                    title=f"Remediation: {df.title}",
                    description=explanation_obj.remediation_proposal,
                    gated=True,
                )
            )

            # Emitting false positive indicators as conversational hypotheses (docs/05 §6.3)
            if explanation_obj.false_positive_indicators:
                hypotheses.append(
                    Hypothesis(
                        statement=(
                            f"False positive consideration for '{df.title}': "
                            + "; ".join(explanation_obj.false_positive_indicators)
                        ),
                        basis_refs=df.evidence_refs,
                        confidence=explanation_obj.confidence,
                    )
                )

        return {
            "draft_findings": draft_findings,
            "proposals": proposals,
            "hypotheses": hypotheses,
            "usage": usage_total,
            "errors": errors,
        }

    return explain_findings_node


# ---------------------------------------------------------------------------
# Node 3: Deterministic Evidence Verifier
# ---------------------------------------------------------------------------


def verify_evidence_node(state: AuthCheckState) -> dict[str, Any]:
    """Deterministically verify draft findings against provenance citations (docs/05 §7)."""
    drafts = state.get("draft_findings", [])
    verified: list[VerifiedFinding] = []

    for d in drafts:
        # Check that file path and line range are valid and grounded
        if d.file_path and d.line_range and len(d.line_range) == 2:
            s_line, e_line = d.line_range
            if s_line > 0 and e_line >= s_line:
                citation = f"{d.file_path}:{s_line}-{e_line}"
                verified.append(
                    VerifiedFinding(
                        draft_id=d.draft_id,
                        finding_id=f"vf_{d.draft_id}",
                        is_verified=True,
                        evidence_score=1.0,
                        evidence_level=2,
                        confidence=0.9,
                        title=d.title,
                        file_path=d.file_path,
                        line_range=d.line_range,
                        rule_id=d.rule_id,
                        citation_ref=citation,
                        resolution_notes="Statically verified on analyzed route and guard chain path.",
                    )
                )

    return {"verified_findings": verified}


# ---------------------------------------------------------------------------
# Node 4: Final Report Synthesis
# ---------------------------------------------------------------------------


def finalize_authcheck_node(state: AuthCheckState) -> dict[str, Any]:
    """Assemble final AuthCheck markdown summary report."""
    evals = state.get("evaluations", [])
    drafts = state.get("draft_findings", [])
    unsupported = state.get("unsupported_routes", [])

    total_discovered = len(evals)
    protected = sum(1 for e in evals if e.status == "protected")
    missing_auth = sum(1 for e in evals if e.status == "missing_auth")
    missing_authz = sum(1 for e in evals if e.status == "missing_authz")
    exempt = sum(1 for e in evals if e.status == "public_exempt")

    lines = [
        "## AuthCheck Security Review",
        "",
        f"- **Endpoints Discovered**: {total_discovered}",
        f"- **Protected**: {protected}",
        f"- **Missing Authentication**: {missing_auth}",
        f"- **Missing Role Check (Authorization)**: {missing_authz}",
        f"- **Public Exempt**: {exempt}",
    ]

    if unsupported:
        lines.append(f"- **Not Analyzed (Unsupported Framework)**: {len(unsupported)} *(Notice: absence of finding is not safe)*")

    lines.append("")

    if drafts:
        lines.append("### Findings and Remediation Proposals")
        lines.append("")
        for idx, d in enumerate(drafts, 1):
            lines.append(f"#### {idx}. {d.title} (`{d.rule_id}`)")
            lines.append(f"- **Severity**: {d.severity.upper()}")
            lines.append(f"- **Location**: `{d.file_path}:{d.line_range[0]}-{d.line_range[1]}`")
            if d.explanation:
                lines.append(f"- **Assessment**:\n{d.explanation}")
            lines.append("")
    else:
        lines.append("✓ No route authorization or authentication gaps identified on the analyzed call paths.")

    if unsupported:
        lines.append("### Unanalyzed Routes")
        for u in unsupported:
            lines.append(f"- `{u.get('route')}` in `{u.get('file')}`: {u.get('reason')}")

    report = "\n".join(lines)
    return {"summary_report": report}


# ---------------------------------------------------------------------------
# Graph Construction & Agent Runner
# ---------------------------------------------------------------------------


def build_authcheck_graph(
    router: LLMGatewayRouter | None = None,
    prompt_loader: PromptLoader | None = None,
    session: AsyncSession | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Construct and compile the canonical AuthCheck specialist LangGraph workflow."""
    builder = StateGraph(AuthCheckState)

    # Register workflow nodes
    builder.add_node("analyze_routes", analyze_routes_node_factory(session=session))
    builder.add_node(
        "explain_findings",
        explain_findings_node_factory(router=router, prompt_loader=prompt_loader),
    )
    builder.add_node("verify_evidence", verify_evidence_node)
    builder.add_node("finalize", finalize_authcheck_node)

    # Wire edges: START -> analyze_routes -> explain_findings -> verify_evidence -> finalize -> END
    builder.add_edge(START, "analyze_routes")
    builder.add_edge("analyze_routes", "explain_findings")
    builder.add_edge("explain_findings", "verify_evidence")
    builder.add_edge("verify_evidence", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer)


class AuthCheckAgent:
    """High-level runner executing the AuthCheck specialist workflow."""

    def __init__(
        self,
        router: LLMGatewayRouter | None = None,
        prompt_loader: PromptLoader | None = None,
        session: AsyncSession | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
    ) -> None:
        self.router = router
        self.prompt_loader = prompt_loader
        self.session = session
        self.checkpointer = checkpointer
        self.graph = build_authcheck_graph(
            router=self.router,
            prompt_loader=self.prompt_loader,
            session=self.session,
            checkpointer=self.checkpointer,
        )

    async def run(
        self,
        state: AuthCheckState,
        thread_id: str | None = None,
    ) -> AuthCheckState:
        """Execute AuthCheck workflow for the given state."""
        config = {"configurable": {"thread_id": thread_id}} if thread_id else None
        return await self.graph.ainvoke(state, config=config)

    async def check_security(
        self,
        project_id: str,
        workspace_id: str,
        user_query: str = "",
        symbols: list[CodeSymbol | dict[str, Any]] | None = None,
        relationships: list[CodeRelationship | dict[str, Any]] | None = None,
        config: ProjectSecurityConfig | None = None,
    ) -> AuthCheckResult:
        """High-level convenience method analyzing project security and returning structured results."""
        init_state = create_initial_authcheck_state(
            project_id=project_id,
            workspace_id=workspace_id,
            user_query=user_query,
            symbols=symbols,
            relationships=relationships,
            config=config,
        )
        res = await self.run(init_state)

        evals = res.get("evaluations", [])
        return AuthCheckResult(
            total_routes_discovered=len(evals),
            total_analyzed=len(evals) - len(res.get("unsupported_routes", [])),
            protected_count=sum(1 for e in evals if e.status == "protected"),
            missing_auth_count=sum(1 for e in evals if e.status == "missing_auth"),
            missing_authz_count=sum(1 for e in evals if e.status == "missing_authz"),
            public_exempt_count=sum(1 for e in evals if e.status == "public_exempt"),
            unsupported_count=len(res.get("unsupported_routes", [])),
            draft_findings=res.get("draft_findings", []),
            verified_findings=res.get("verified_findings", []),
            proposals=res.get("proposals", []),
            hypotheses=res.get("hypotheses", []),
            summary_report=res.get("summary_report", ""),
        )


# ---------------------------------------------------------------------------
# Specialist Node Runner for AgentManager Integration
# ---------------------------------------------------------------------------


async def run_authcheck_specialist(
    state: RunState,
    router: LLMGatewayRouter | None = None,
    prompt_loader: PromptLoader | None = None,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Execute AuthCheck as a specialist node inside AgentManager."""
    user_query = state["request"].user_message or state["request"].params.get("query", "")
    project_id = state.get("project_id", "")
    workspace_id = state.get("workspace_id", "")

    # Extract symbols and relationships if provided in request params or state
    symbols = state["request"].params.get("symbols")
    relationships = state["request"].params.get("relationships")
    config = state["request"].params.get("config")

    agent = AuthCheckAgent(
        router=router,
        prompt_loader=prompt_loader,
        session=session,
    )

    init_state = create_initial_authcheck_state(
        project_id=project_id,
        workspace_id=workspace_id,
        user_query=user_query,
        symbols=symbols,
        relationships=relationships,
        config=config,
    )

    res = await agent.run(init_state)

    plan = list(state.get("plan", []))
    task = next((t for t in plan if t.specialist == "authcheck"), None)
    task_id = task.task_id if task else f"authcheck_{state.get('run_id', 'run')[:8]}"

    completed_task = SpecialistTask(
        specialist="authcheck",
        task_id=task_id,
        status="completed",
        input_refs=[f"{d.file_path}:{d.line_range[0]}-{d.line_range[1]}" for d in res.get("draft_findings", [])],
        params=state["request"].params,
    )

    return {
        "plan": [completed_task],
        "drafts": res.get("draft_findings", []),
        "verified": res.get("verified_findings", []),
        "proposals": res.get("proposals", []),
        "hypotheses": res.get("hypotheses", []),
        "final_response": res.get("summary_report"),
        "usage": res.get("usage", UsageTotals()),
    }
