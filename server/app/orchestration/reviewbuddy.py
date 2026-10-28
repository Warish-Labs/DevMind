"""ReviewBuddy specialist workflow, checklist execution, and LangGraph integration (docs/01 CAP-05, docs/05 §6.4).

Per docs/05 §6.4 (ReviewBuddy specification):
1. Loads project review rules (built-in checklist + custom rules).
2. Runs deterministic structural analysis (ReviewBuddyAnalyzer) on code diff or files.
3. Evaluates 5 checklist categories: validation, error handling, auth, tests, docs, plus custom rules.
4. Generates located findings with exact line numbers and code snippets.
5. Verifies grounding through EvidenceVerifier.
6. Emits verified findings, remediation proposals, and review summary.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, TypedDict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.evidence_verifier import EvidenceVerifier
from app.analysis.review_buddy import ReviewBuddyAnalyzer, ReviewChecklistFinding
from app.core.auth_context import SystemContext
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
from app.persistence.repositories.review_rule_repo import (
    DEFAULT_CHECKLIST_RULES,
    ReviewRuleRepository,
)

logger = logging.getLogger("devmind.orchestration.reviewbuddy")


class ReviewBuddyState(TypedDict, total=False):
    """Execution state for ReviewBuddy specialist."""

    project_id: str
    workspace_id: str
    diff: str | None
    files: list[dict[str, Any]]
    rules: list[dict[str, Any]]
    draft_findings: list[DraftFinding]
    verified_findings: list[VerifiedFinding]
    proposals: list[Proposal]
    hypotheses: list[Hypothesis]
    summary_report: str
    usage: Annotated[UsageTotals, merge_usage_totals]
    errors: Annotated[list[NodeError], append_items]


class ReviewBuddyAgent:
    """Specialist agent implementing the ReviewBuddy checklist engine."""

    def __init__(
        self,
        router: LLMGatewayRouter | None = None,
        prompt_loader: PromptLoader | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        self.router = router
        self.prompt_loader = prompt_loader
        self.session = session
        self.verifier = EvidenceVerifier()

    async def run(self, state: ReviewBuddyState) -> dict[str, Any]:
        """Execute review rules against provided diff or files."""
        rules = state.get("rules") or DEFAULT_CHECKLIST_RULES
        analyzer = ReviewBuddyAnalyzer(rules=rules)

        raw_findings: list[ReviewChecklistFinding] = []
        diff = state.get("diff")
        files = state.get("files") or []

        if diff:
            raw_findings = analyzer.evaluate_diff(diff)
        elif files:
            raw_findings = analyzer.evaluate_files(files)

        draft_findings: list[DraftFinding] = []
        proposals: list[Proposal] = []

        for idx, rf in enumerate(raw_findings):
            draft = DraftFinding(
                draft_id=f"draft_review_{idx + 1}",
                finding_type=rf.category,
                title=rf.title,
                file_path=rf.file_path,
                line_range=(rf.start_line, rf.end_line),
                rule_id=rf.rule_id,
                severity=rf.severity,
                evidence_refs=[f"{rf.file_path}:{rf.start_line}-{rf.end_line}"],
                explanation=rf.message,
            )
            draft_findings.append(draft)

            if rf.suggested_fix:
                proposals.append(
                    Proposal(
                        proposal_type="diff_patch",
                        title=f"Fix {rf.title}",
                        description=rf.suggested_fix,
                        diff_content=None,
                        gated=True,
                    )
                )

        # Evidence verification step
        verified_findings: list[VerifiedFinding] = []
        for df in draft_findings:
            v_res = self.verifier.verify_draft_finding(df)
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

        # Assemble summary report
        total_eval = len(rules)
        total_found = len(verified_findings)
        summary = (
            f"ReviewBuddy evaluated {total_eval} checklist rules: "
            f"{total_found} finding(s) detected across changed code."
        )

        return {
            "draft_findings": draft_findings,
            "verified_findings": verified_findings,
            "proposals": proposals,
            "hypotheses": [],
            "summary_report": summary,
            "usage": UsageTotals(),
        }


async def run_reviewbuddy_specialist(
    state: RunState,
    router: LLMGatewayRouter | None = None,
    prompt_loader: PromptLoader | None = None,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Execute ReviewBuddy as a specialist node inside AgentManager."""
    project_id_str = state.get("project_id", "")
    workspace_id_str = state.get("workspace_id", "")
    params = state["request"].params

    diff = params.get("diff")
    files = params.get("files", [])
    rules = params.get("rules")

    # If rules not passed in params and session available, load from database
    if rules is None and session and project_id_str:
        try:
            pid = UUID(project_id_str)
            sys_ctx = SystemContext(reason="reviewbuddy_specialist_run")
            repo = ReviewRuleRepository(session)
            db_rules = await repo.list_rules_by_project(sys_ctx, pid, enabled_only=True)
            if not db_rules:
                wid = UUID(workspace_id_str) if workspace_id_str else pid
                db_rules = await repo.seed_default_rules(sys_ctx, wid, pid)
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
                }
                for r in db_rules
            ]
        except Exception as exc:
            logger.warning(
                "Could not load database review rules for project %s: %s", project_id_str, exc
            )
            rules = DEFAULT_CHECKLIST_RULES

    agent = ReviewBuddyAgent(
        router=router,
        prompt_loader=prompt_loader,
        session=session,
    )

    init_state: ReviewBuddyState = {
        "project_id": project_id_str,
        "workspace_id": workspace_id_str,
        "diff": diff,
        "files": files,
        "rules": rules or DEFAULT_CHECKLIST_RULES,
    }

    res = await agent.run(init_state)

    plan = list(state.get("plan", []))
    task = next((t for t in plan if t.specialist == "reviewbuddy"), None)
    task_id = task.task_id if task else f"reviewbuddy_{state.get('run_id', 'run')[:8]}"

    completed_task = SpecialistTask(
        specialist="reviewbuddy",
        task_id=task_id,
        status="completed",
        input_refs=[
            f"{d.file_path}:{d.line_range[0]}-{d.line_range[1]}"
            for d in res.get("draft_findings", [])
        ],
        params=params,
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
