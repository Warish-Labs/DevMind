"""Project Mentor specialist agent, task recommendation, and project evaluation (docs/01 CAP-08, CAP-09, docs/05 §6.8).

Per docs/01 CAP-08 and CAP-09:
1. Recommends the optimal next developer/agent backlog task using deterministic DAG ranking and LLM narrative.
2. Conducts multidimensional project health evaluations and release-readiness audits across 6 core dimensions.
3. Provides actionable recommendations and blocker mitigation strategies.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.eval_scoring import (
    BugRecordInput,
    DocDriftInput,
    EvaluationInputs,
    FeatureChecklistInput,
    FindingInput,
    ProjectEvaluationScorer,
    TaskSummaryInput,
)
from app.analysis.task_dag import RankedTask
from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import NotFoundError
from app.domain.mentor.schemas import (
    ProjectEvaluationResponse,
    ProjectTaskResponse,
    TaskRecommendationResponse,
)
from app.llm.models import LLMGenerationRequest
from app.llm.prompt_loader import PromptLoader, default_prompt_loader
from app.llm.repair import extract_json_candidate
from app.llm.router import LLMGatewayRouter
from app.llm.schemas import (
    MentorRecommendationOutput,
    ProjectEvaluationNarrativeOutput,
)
from app.orchestration.state import (
    DraftFinding,
    NodeError,
    RunState,
    SpecialistTask,
)
from app.persistence.models.mentor import ProjectEvaluation, ProjectTask
from app.persistence.repositories.brain_repo import BrainRepository
from app.persistence.repositories.bug_record_repo import BugRecordRepository
from app.persistence.repositories.living_doc_repo import LivingDocRepository
from app.persistence.repositories.project_eval_repo import ProjectEvaluationRepository
from app.persistence.repositories.project_repo import ProjectRepository
from app.persistence.repositories.project_task_repo import ProjectTaskRepository

logger = logging.getLogger("devmind.orchestration.mentor")


def task_to_response(task: ProjectTask) -> ProjectTaskResponse:
    """Map DB ProjectTask model to Pydantic ProjectTaskResponse."""
    now = datetime.now(UTC)
    depends_on_ids = [d.id for d in (task.dependencies or [])]
    dependent_ids = [d.id for d in (task.dependents or [])]
    return ProjectTaskResponse(
        id=task.id,
        workspace_id=task.workspace_id,
        project_id=task.project_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        source=task.source,
        finding_id=task.finding_id,
        metadata=task.metadata_ or {},
        depends_on_ids=depends_on_ids,
        dependent_ids=dependent_ids,
        created_at=task.created_at or now,
        updated_at=task.updated_at or now,
    )


def evaluation_to_response(
    ev: ProjectEvaluation,
    narrative: str | None = None,
    functionality_confidence: str = "high",
) -> ProjectEvaluationResponse:
    """Map DB ProjectEvaluation model to Pydantic ProjectEvaluationResponse."""
    now = datetime.now(UTC)
    raw_scores = ev.dimension_scores or {}
    flat_scores: dict[str, float] = {}
    for k, v in raw_scores.items():
        if isinstance(v, (int, float)):
            flat_scores[k] = float(v)
        elif isinstance(v, dict) and "score" in v:
            flat_scores[k] = float(v["score"])

    # Extract stored narrative/confidence if not explicitly supplied
    if narrative is None and isinstance(raw_scores, dict):
        narrative = raw_scores.get("narrative")
    if functionality_confidence == "high" and isinstance(raw_scores, dict):
        functionality_confidence = raw_scores.get("functionality_confidence", "high")

    return ProjectEvaluationResponse(
        id=ev.id,
        workspace_id=ev.workspace_id,
        project_id=ev.project_id,
        snapshot_id=ev.snapshot_id,
        overall_score=ev.overall_score,
        dimension_scores=flat_scores,
        verdict=ev.verdict,
        blockers=ev.blockers or [],
        warnings=ev.warnings or [],
        positive_indicators=ev.positive_indicators or [],
        rubric_version=ev.rubric_version,
        functionality_confidence=functionality_confidence,
        narrative=narrative,
        evaluated_by=ev.evaluated_by,
        created_at=ev.created_at or now,
        updated_at=ev.updated_at or now,
    )


class ProjectMentorAgent:
    """Specialist agent coordinating project backlog task recommendations and health evaluations."""

    def __init__(
        self,
        session: AsyncSession,
        router: LLMGatewayRouter | None = None,
        prompt_loader: PromptLoader | None = None,
    ) -> None:
        self.session = session
        self.task_repo = ProjectTaskRepository(session)
        self.eval_repo = ProjectEvaluationRepository(session)
        self.project_repo = ProjectRepository(session)
        self.brain_repo = BrainRepository(session)
        self.bug_repo = BugRecordRepository(session)
        self.living_doc_repo = LivingDocRepository(session)
        self.router = router
        self.prompt_loader = prompt_loader or default_prompt_loader

    async def recommend_next_task(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
    ) -> TaskRecommendationResponse:
        """Deterministically rank pending project tasks via DAG and synthesize mentor guidance."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if not project:
            raise NotFoundError(detail=f"Project {project_id} not found")

        dag = await self.task_repo.load_project_dag(ctx, project_id)
        ranked: list[RankedTask] = dag.rank_tasks()

        if not ranked:
            return TaskRecommendationResponse(
                recommended_task=None,
                rank=0,
                score=0.0,
                is_ready=False,
                downstream_impact_count=0,
                reason="No active or pending tasks in project backlog.",
                narrative="The project backlog is currently clear of pending tasks. All planned work items are completed or cancelled.",
                unblocked_count=0,
                total_pending_tasks=0,
            )

        ready_tasks = [rt for rt in ranked if rt.is_ready]
        blocked_tasks = [rt for rt in ranked if not rt.is_ready]

        # Prioritize top ready task; if all blocked, take top-ranked blocked task
        top_ranked = ready_tasks[0] if ready_tasks else ranked[0]
        db_task = await self.task_repo.get_by_id(ctx, top_ranked.task.id)
        task_response = task_to_response(db_task) if db_task else None

        # LLM or deterministic narrative synthesis
        narrative = await self._synthesize_recommendation_narrative(
            ctx=ctx,
            top_ranked=top_ranked,
            ready_tasks=ready_tasks,
            blocked_tasks=blocked_tasks,
            project_id=project_id,
        )

        return TaskRecommendationResponse(
            recommended_task=task_response,
            rank=top_ranked.rank,
            score=top_ranked.score,
            is_ready=top_ranked.is_ready,
            downstream_impact_count=top_ranked.downstream_impact_count,
            reason=top_ranked.recommendation_reason,
            narrative=narrative,
            unblocked_count=len(ready_tasks),
            total_pending_tasks=len(ranked),
        )

    async def _synthesize_recommendation_narrative(
        self,
        ctx: AuthContext | SystemContext,
        top_ranked: RankedTask,
        ready_tasks: list[RankedTask],
        blocked_tasks: list[RankedTask],
        project_id: UUID,
    ) -> str:
        """Synthesize actionable narrative explaining next task recommendation."""
        # Deterministic fallback text
        readiness_label = (
            "Ready to start immediately"
            if top_ranked.is_ready
            else "Currently blocked by prerequisites"
        )
        impact_label = (
            f"Completing this item will unblock {top_ranked.downstream_impact_count} downstream task(s)."
            if top_ranked.downstream_impact_count > 0
            else "Independent milestone without direct downstream blockers."
        )
        fallback_narrative = (
            f"Recommended task '{top_ranked.task.title}' (Priority: {top_ranked.task.priority.upper()}, "
            f"Rank: #{top_ranked.rank}, Score: {top_ranked.score:.1f}). "
            f"{readiness_label}. {top_ranked.recommendation_reason} {impact_label}"
        )

        if self.router is None or self.prompt_loader is None:
            return fallback_narrative

        try:
            prompt_req = self.prompt_loader.load(
                "mentor_recommendation",
                variables={
                    "task_title": top_ranked.task.title,
                    "task_priority": top_ranked.task.priority,
                    "unblocked_tasks_summary": "\n".join(
                        f"- {t.task.title} (priority: {t.task.priority}, score: {t.score:.1f})"
                        for t in ready_tasks[:5]
                    )
                    or "None",
                    "blocked_tasks_summary": "\n".join(
                        f"- {t.task.title} (prerequisites: {len(t.unmet_dependencies)})"
                        for t in blocked_tasks[:5]
                    )
                    or "None",
                    "project_context": f"Project ID: {project_id}. Total backlog: {len(ready_tasks) + len(blocked_tasks)} tasks.",
                },
            )
            llm_req = LLMGenerationRequest(
                task="mentor_recommendation",
                messages=prompt_req.messages,
            )
            response = await self.router.generate(llm_req)
            if response.content:
                candidate = extract_json_candidate(response.content)
                parsed = json.loads(candidate)
                rec_out = MentorRecommendationOutput.model_validate(parsed)
                return f"{rec_out.summary} {rec_out.rationale} Next action: {rec_out.recommended_action}".strip()
        except Exception as exc:
            logger.warning("LLM mentor recommendation narrative failed; falling back: %s", exc)

        return fallback_narrative

    async def evaluate_project_health(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        *,
        snapshot_id: UUID | None = None,
        feature_checklist: list[dict[str, Any]] | None = None,
        rubric_version: str = "1.0",
        evaluated_by: UUID | None = None,
    ) -> ProjectEvaluationResponse:
        """Run multidimensional health evaluation and store release-readiness verdict."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if not project:
            raise NotFoundError(detail=f"Project {project_id} not found")

        # 1. Gather tasks and DAG summary
        tasks = await self.task_repo.list_by_project(ctx, project_id, limit=1000)
        dag = await self.task_repo.load_project_dag(ctx, project_id)
        cycles = dag.detect_cycles()

        completed_count = sum(1 for t in tasks if t.status == "completed")
        blocked_count = sum(1 for t in tasks if t.status == "blocked")
        task_summary = TaskSummaryInput(
            total_tasks=len(tasks),
            completed_tasks=completed_count,
            blocked_tasks=blocked_count,
            has_cyclic_dependency=bool(cycles),
        )

        # 2. Gather findings
        raw_findings = await self.brain_repo.list_findings(ctx, project_id=project_id, limit=500)
        findings = [
            FindingInput(
                id=str(f.id),
                title=f.title,
                severity=f.severity,
                status=f.status,
                category=f.rule_id or "security",
            )
            for f in raw_findings
        ]

        # 3. Gather recurring bug records
        raw_bugs = await self.bug_repo.list_by_project(ctx, project_id, limit=200)
        bugs = [
            BugRecordInput(
                id=str(b.id),
                title=b.title,
                occurrence_count=b.occurrence_count,
                has_resolution=bool(getattr(b, "resolutions", [])),
            )
            for b in raw_bugs
        ]

        # 4. Gather living doc records and drift
        doc_records = await self.living_doc_repo.list_documents_by_project(ctx, project_id)
        raw_drift = await self.living_doc_repo.list_drift_items_by_project(ctx, project_id)
        drift_items = [
            DocDriftInput(
                id=str(d.id),
                kind=d.kind,
                status=d.status,
                explanation=d.explanation,
            )
            for d in raw_drift
        ]

        # 5. Build feature checklist inputs (OQ-18)
        feature_inputs: list[FeatureChecklistInput] = []
        if feature_checklist:
            for fc in feature_checklist:
                feature_inputs.append(
                    FeatureChecklistInput(
                        name=fc.get("name", "Unnamed Feature"),
                        completed=bool(fc.get("completed", False)),
                        is_critical=bool(fc.get("is_critical", False)),
                    )
                )

        eval_inputs = EvaluationInputs(
            findings=findings,
            bugs=bugs,
            drift_items=drift_items,
            feature_checklist=feature_inputs,
            task_summary=task_summary,
            has_tracked_docs=bool(doc_records),
        )

        # 6. Execute deterministic scoring
        eval_result = ProjectEvaluationScorer.evaluate(eval_inputs)

        # 7. Synthesize narrative
        narrative = await self._synthesize_evaluation_narrative(
            ctx=ctx,
            eval_result=eval_result,
            project_id=project_id,
            rubric_version=rubric_version,
        )

        # 8. Persist evaluation record
        dimension_scores_payload = {
            **eval_result.dimension_scores,
            "narrative": narrative,
            "functionality_confidence": eval_result.functionality_confidence,
        }

        eval_record = await self.eval_repo.create_evaluation(
            ctx=ctx,
            workspace_id=project.workspace_id,
            project_id=project_id,
            overall_score=eval_result.overall_score,
            dimension_scores=dimension_scores_payload,
            verdict=eval_result.verdict,
            blockers=eval_result.blockers,
            warnings=eval_result.warnings,
            positive_indicators=eval_result.positive_indicators,
            snapshot_id=snapshot_id,
            rubric_version=rubric_version,
            evaluated_by=evaluated_by,
        )

        return evaluation_to_response(
            eval_record,
            narrative=narrative,
            functionality_confidence=eval_result.functionality_confidence,
        )

    async def _synthesize_evaluation_narrative(
        self,
        ctx: AuthContext | SystemContext,
        eval_result: Any,
        project_id: UUID,
        rubric_version: str,
    ) -> str:
        """Synthesize evaluation executive summary and recommendations."""
        fallback_narrative = (
            f"Release-readiness evaluated at {eval_result.overall_score:.1f}/100 with verdict '{eval_result.verdict}'. "
            f"Detected {len(eval_result.blockers)} blocker(s) and {len(eval_result.warnings)} warning(s) across "
            f"6 core engineering health dimensions."
        )

        if self.router is None or self.prompt_loader is None:
            return fallback_narrative

        try:
            dim_summary_lines = [
                f"- {dim.replace('_', ' ').title()}: {score:.1f}/100"
                for dim, score in eval_result.dimension_scores.items()
            ]
            prompt_req = self.prompt_loader.load(
                "project_evaluation_narrative",
                variables={
                    "overall_score": f"{eval_result.overall_score:.1f}",
                    "grade": eval_result.verdict,
                    "dimensions_summary": "\n".join(dim_summary_lines),
                    "project_context": f"Project ID: {project_id}, Rubric Version: {rubric_version}, Blockers: {len(eval_result.blockers)}",
                },
            )
            llm_req = LLMGenerationRequest(
                task="project_evaluation_narrative",
                messages=prompt_req.messages,
            )
            response = await self.router.generate(llm_req)
            if response.content:
                candidate = extract_json_candidate(response.content)
                parsed = json.loads(candidate)
                narrative_out = ProjectEvaluationNarrativeOutput.model_validate(parsed)
                recs = (
                    f" Recommendations: {', '.join(narrative_out.key_recommendations)}."
                    if narrative_out.key_recommendations
                    else ""
                )
                return f"{narrative_out.executive_summary} {narrative_out.verdict_rationale}{recs}".strip()
        except Exception as exc:
            logger.warning("LLM evaluation narrative failed; falling back: %s", exc)

        return fallback_narrative


# ---------------------------------------------------------------------------
# LangGraph Specialist Integration (docs/05 §4.1, §6.8)
# ---------------------------------------------------------------------------


async def run_mentor_specialist(
    state: RunState,
    task: SpecialistTask,
    router: LLMGatewayRouter | None = None,
    prompt_loader: PromptLoader | None = None,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Execute ProjectMentor specialist task inside the LangGraph Agent Manager workflow."""
    if session is None:
        return {
            "node_errors": [
                NodeError(
                    node="mentor",
                    error_code="session_missing",
                    message="AsyncSession required for mentor specialist",
                )
            ]
        }

    project_id_raw = state.get("project_id")
    if not project_id_raw:
        return {
            "node_errors": [
                NodeError(
                    node="mentor",
                    error_code="project_id_missing",
                    message="RunState missing project_id",
                )
            ]
        }

    project_id = UUID(project_id_raw) if isinstance(project_id_raw, str) else project_id_raw
    ctx = SystemContext(reason="ProjectMentor specialist workflow execution")

    agent = ProjectMentorAgent(session=session, router=router, prompt_loader=prompt_loader)
    params = task.params or {}
    action = params.get("action", "recommend")

    draft_findings: list[DraftFinding] = []

    if action == "evaluate":
        eval_resp = await agent.evaluate_project_health(
            ctx=ctx,
            project_id=project_id,
            snapshot_id=UUID(params["snapshot_id"]) if "snapshot_id" in params else None,
            feature_checklist=params.get("feature_checklist"),
            rubric_version=params.get("rubric_version", "1.0"),
        )
        task.status = "completed"
        for idx, blocker in enumerate(eval_resp.blockers):
            draft_findings.append(
                DraftFinding(
                    draft_id=f"eval_blocker_{idx}_{eval_resp.id}",
                    finding_type="evaluation_blocker",
                    title=blocker.get("title", "Release Blocker"),
                    file_path=blocker.get("file_path", "project"),
                    line_range=(1, 1),
                    rule_id=f"devmind.evaluation.{blocker.get('dimension', 'general')}",
                    severity="critical",
                    explanation=blocker.get("reason", "Blocker preventing release readiness"),
                )
            )

        response_msg = (
            f"ProjectMentor evaluated project health at {eval_resp.overall_score:.1f}/100 "
            f"({eval_resp.verdict}) with {len(eval_resp.blockers)} blocker(s)."
        )
    else:
        rec_resp = await agent.recommend_next_task(ctx=ctx, project_id=project_id)
        task.status = "completed"
        if rec_resp.recommended_task:
            response_msg = (
                f"ProjectMentor recommended next task #{rec_resp.rank}: '{rec_resp.recommended_task.title}' "
                f"(Priority: {rec_resp.recommended_task.priority.upper()}). {rec_resp.narrative}"
            )
        else:
            response_msg = "ProjectMentor found no pending tasks in project backlog."

    return {
        "plan": [task],
        "draft_findings": draft_findings,
        "final_response": response_msg,
    }
