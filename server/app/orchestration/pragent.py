"""PRAgent specialist workflow, change impact traversal, and PR intelligence (docs/01 CAP-06, docs/05 §6.5).

Per docs/05 §6.5 (PRAgent specification):
1. Maps changed files and diff to symbols and affected modules.
2. Computes change impact through relationships (callers, importers, routes, tests).
3. Evaluates ReviewBuddy checklist rules against the diff scope.
4. Synthesizes a structured PR summary (purpose, files, affected areas, risks, security, tests, docs).
5. Grounding verified through EvidenceVerifier.
6. Optional comment posting to GitHub gated by human approval.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, TypedDict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.change_impact import ChangeImpactAnalyzer
from app.analysis.evidence_verifier import EvidenceVerifier
from app.analysis.review_buddy import ReviewBuddyAnalyzer
from app.core.auth_context import SystemContext
from app.domain.pr_agent.schemas import ChangeImpactReport, PRSummary
from app.llm.prompt_loader import PromptLoader
from app.llm.router import LLMGatewayRouter
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
from app.persistence.repositories.brain_repo import BrainRepository
from app.persistence.repositories.review_rule_repo import (
    DEFAULT_CHECKLIST_RULES,
    ReviewRuleRepository,
)

logger = logging.getLogger("devmind.orchestration.pragent")


class PRAgentState(TypedDict, total=False):
    """Execution state for PRAgent specialist."""

    project_id: str
    workspace_id: str
    pull_request_id: str | None
    diff: str | None
    changed_files: list[str]
    symbols: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    impact_report: dict[str, Any]
    pr_summary: dict[str, Any]
    draft_findings: list[DraftFinding]
    verified_findings: list[VerifiedFinding]
    proposals: list[Proposal]
    hypotheses: list[Hypothesis]
    summary_report: str
    usage: Annotated[UsageTotals, merge_usage_totals]
    errors: Annotated[list[NodeError], append_items]


class PRAgent:
    """PRAgent coordinator executing change-impact analysis and PR intelligence synthesis."""

    def __init__(
        self,
        router: LLMGatewayRouter | None = None,
        prompt_loader: PromptLoader | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        self.router = router
        self.prompt_loader = prompt_loader
        self.session = session

    async def execute(self, state: PRAgentState) -> dict[str, Any]:
        """Run change-impact traversal, checklist evaluation, and PR intelligence synthesis."""
        project_id_str = state.get("project_id", "")
        diff_text = state.get("diff") or ""
        changed_files = state.get("changed_files") or []

        errors: list[NodeError] = []
        usage = UsageTotals(total_input_tokens=0, total_output_tokens=0, total_cost_units=0.0)

        # 1. Load project context (symbols, relationships, review rules) from DB if session available
        symbols: list[dict[str, Any]] = list(state.get("symbols") or [])
        relationships: list[dict[str, Any]] = list(state.get("relationships") or [])
        rules: list[dict[str, Any]] = list(DEFAULT_CHECKLIST_RULES)

        if self.session and project_id_str:
            try:
                pid = UUID(project_id_str)
                sys_ctx = SystemContext(reason="PRAgent pull request analysis")
                brain_repo = BrainRepository(self.session)
                rule_repo = ReviewRuleRepository(self.session)

                # Fetch active review rules
                db_rules = await rule_repo.list_rules_by_project(
                    ctx=sys_ctx, project_id=pid, enabled_only=True
                )
                if db_rules:
                    rules = [
                        {
                            "rule_id": r.rule_id,
                            "title": r.title,
                            "category": r.category,
                            "severity": r.severity,
                            "scope_selector": r.scope_selector,
                            "check_type": r.check_type,
                            "check_config": r.check_config,
                            "message": r.message,
                            "suggested_fix_template": r.suggested_fix_template,
                            "is_enabled": r.is_enabled,
                            "is_builtin": r.is_builtin,
                        }
                        for r in db_rules
                    ]

                # Fetch symbol graph if not provided
                if not symbols:
                    db_symbols = await brain_repo.list_current_symbols(
                        ctx=sys_ctx, project_id=pid, limit=300
                    )
                    symbols = [
                        {
                            "name": s.name,
                            "kind": s.kind,
                            "symbol_key": s.symbol_key,
                            "file_path": s.file_version.file.path
                            if (s.file_version and s.file_version.file)
                            else "",
                        }
                        for s in db_symbols
                    ]

                if not relationships and symbols:
                    _, db_rels = await brain_repo.get_graph_data(
                        ctx=sys_ctx, project_id=pid, limit=200
                    )
                    relationships = [
                        {
                            "from_symbol_name": r.from_symbol.name if r.from_symbol else "",
                            "to_symbol_name": r.to_symbol.name if r.to_symbol else "",
                            "kind": r.kind,
                        }
                        for r in db_rels
                    ]
            except Exception as exc:
                logger.warning(f"Failed to load full DB context for PRAgent: {exc}")
                errors.append(
                    NodeError(
                        node="pragent_context_fetch",
                        error_code="context_fetch_error",
                        message=f"Context fetch error: {exc}",
                        retryable=True,
                    )
                )

        # 2. Run Change-Impact Analysis Engine
        impact_analyzer = ChangeImpactAnalyzer(
            symbols=symbols,
            relationships=relationships,
        )
        impact_report = impact_analyzer.analyze(
            changed_files=changed_files,
            diff_text=diff_text,
        )

        # 3. Run ReviewBuddy checklist on the diff scope
        review_analyzer = ReviewBuddyAnalyzer(rules=rules)
        checklist_findings = review_analyzer.evaluate_diff(diff_text=diff_text) if diff_text else []

        # 4. Convert checklist findings into DraftFindings and verify evidence
        draft_findings: list[DraftFinding] = []
        for idx, cf in enumerate(checklist_findings):
            df = DraftFinding(
                draft_id=f"draft_pragent_{idx + 1}",
                finding_type=cf.category,
                title=f"[{cf.rule_id}] {cf.title}",
                file_path=cf.file_path,
                line_range=(cf.start_line, cf.end_line),
                rule_id=cf.rule_id,
                severity=cf.severity,
                evidence_refs=[f"{cf.file_path}:{cf.start_line}-{cf.end_line}"],
                explanation=cf.message,
            )
            draft_findings.append(df)

        # Grounding verification
        verifier = EvidenceVerifier()
        verified_findings: list[VerifiedFinding] = []
        for df in draft_findings:
            v_res = verifier.verify_draft_finding(df)
            if v_res.is_verified:
                lvl_str = v_res.verified_level or "E1"
                lvl = int(lvl_str.replace("E", "")) if "E" in lvl_str else 1
                verified_findings.append(
                    VerifiedFinding(
                        draft_id=df.draft_id,
                        is_verified=True,
                        evidence_score=v_res.evidence_score,
                        resolution_notes=v_res.resolution_notes,
                        evidence_level=lvl,
                        confidence=v_res.confidence,
                        title=df.title,
                        file_path=df.file_path,
                        line_range=df.line_range,
                        rule_id=df.rule_id,
                    )
                )

        # 5. Synthesize PRSummary
        pr_summary = self._synthesize_summary(
            changed_files=impact_report.changed_files,
            impact_report=impact_report,
            verified_findings=verified_findings,
        )

        # 6. Formulate summary report narrative
        report_lines = [
            f"### PRAgent Pull Request Analysis — Risk Level: {impact_report.risk_level.upper()}",
            "",
            f"**Purpose**: {pr_summary.purpose}",
            "",
            "#### Impact Set & Affected Areas",
            f"- **Files Modified ({len(impact_report.changed_files)})**: {', '.join(impact_report.changed_files[:10])}{' ...' if len(impact_report.changed_files) > 10 else ''}",
            f"- **Affected Modules ({len(impact_report.affected_modules)})**: {', '.join(impact_report.affected_modules) if impact_report.affected_modules else 'None'}",
            f"- **Affected Routes ({len(impact_report.affected_routes)})**: {', '.join(f'{r.method} {r.path}' for r in impact_report.affected_routes) if impact_report.affected_routes else 'None'}",
            f"- **Affected Tests ({len(impact_report.affected_tests)})**: {', '.join(impact_report.affected_tests) if impact_report.affected_tests else 'None'}",
            "",
            "#### Security & Checklist Findings",
            f"- **Checklist Findings Detected**: {len(verified_findings)} verified findings",
            f"- **Security Summary**: {pr_summary.security_summary}",
            f"- **Testing Concerns**: {'; '.join(pr_summary.testing_concerns) if pr_summary.testing_concerns else 'Adequate'}",
            f"- **Documentation Impact**: {pr_summary.documentation_impact}",
        ]
        summary_report = "\n".join(report_lines)

        # 7. Generate GitHub Comment Proposal (Human Approval Gate per docs/05 §6.5)
        proposals: list[Proposal] = [
            Proposal(
                proposal_type="pr_comment",
                title="Post PRAgent summary comment to PR",
                description=f"Post PRAgent analysis summary comment to PR (Risk: {impact_report.risk_level.upper()})",
                diff_content=None,
                gated=True,
            )
        ]

        return {
            "impact_report": impact_report.model_dump(),
            "pr_summary": pr_summary.model_dump(),
            "draft_findings": draft_findings,
            "verified_findings": verified_findings,
            "proposals": proposals,
            "summary_report": summary_report,
            "usage": usage,
            "errors": errors,
        }

    def _synthesize_summary(
        self,
        changed_files: list[str],
        impact_report: ChangeImpactReport,
        verified_findings: list[VerifiedFinding],
    ) -> PRSummary:
        """Assemble structured PR summary based on change impact and findings."""
        # Derive high-level purpose
        if any("migration" in f.lower() or "alembic" in f.lower() for f in changed_files):
            purpose = "Database schema migration and data model updates"
        elif any("api" in f.lower() or "routes" in f.lower() for f in changed_files):
            purpose = "API endpoint definitions and route updates"
        elif any("test" in f.lower() for f in changed_files) and len(changed_files) == 1:
            purpose = "Test suite additions and verification coverage"
        elif any("doc" in f.lower() or ".md" in f.lower() for f in changed_files):
            purpose = "Documentation updates and operational runbook adjustments"
        else:
            purpose = f"Codebase updates across {len(changed_files)} file(s)"

        # Identify security observations
        sec_findings = [
            f
            for f in verified_findings
            if (f.rule_id and any(k in f.rule_id.lower() for k in ("auth", "sec", "input")))
        ]
        if sec_findings:
            security_summary = f"Flagged {len(sec_findings)} security/input validation concern(s) requiring attention."
        else:
            security_summary = "No critical security or authorization vulnerabilities detected."

        # Testing concerns
        testing_concerns: list[str] = []
        if not impact_report.affected_tests and any(not f.endswith(".md") for f in changed_files):
            testing_concerns.append(
                "No automated test files modified or identified for changed components"
            )

        # Documentation impact
        if any("api/" in f for f in changed_files) and not any(
            "docs/" in f or ".md" in f for f in changed_files
        ):
            doc_impact = "API routes were modified without matching documentation updates"
        else:
            doc_impact = "Documentation reflects current change scope"

        return PRSummary(
            purpose=purpose,
            files_changed=changed_files[:20],
            affected_areas=impact_report.affected_modules,
            risks=impact_report.risk_reasons,
            security_summary=security_summary,
            testing_concerns=testing_concerns,
            documentation_impact=doc_impact,
            risk_level=impact_report.risk_level,
        )


async def run_pragent_specialist(
    state: RunState,
    task: SpecialistTask,
    router: LLMGatewayRouter | None = None,
    prompt_loader: PromptLoader | None = None,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """LangGraph specialist node entry point executing PRAgent."""
    logger.info(f"Executing PRAgent specialist for run {state['run_id']}")

    # Extract diff or changed files from task params or state
    diff = task.params.get("diff") or state.get("metadata", {}).get("diff")
    changed_files = (
        task.params.get("changed_files") or state.get("metadata", {}).get("changed_files") or []
    )

    pr_state: PRAgentState = {
        "project_id": state["project_id"],
        "workspace_id": state["workspace_id"],
        "pull_request_id": task.params.get("pull_request_id"),
        "diff": diff,
        "changed_files": changed_files,
        "symbols": task.params.get("symbols", []),
        "relationships": task.params.get("relationships", []),
    }

    agent = PRAgent(router=router, prompt_loader=prompt_loader, session=session)
    result = await agent.execute(pr_state)

    return {
        "verified_findings": result.get("verified_findings", []),
        "proposals": result.get("proposals", []),
        "hypotheses": [],
        "summary_report": result.get("summary_report", ""),
        "usage": result.get("usage", UsageTotals(0, 0, 0.0)),
        "errors": result.get("errors", []),
    }
