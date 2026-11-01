"""DeployDoctor specialist agent and deployment failure diagnosis (docs/01 CAP-07, docs/05 §6.10).

Per docs/01 CAP-07 and docs/05 §6.10:
1. Pre-redacts and sanitizes raw deployment logs from Render, Vercel, Docker, etc.
2. Extracts error signatures, failure categories, and referenced environment variable names.
3. Cross-checks environment variable names (keys only, never values) against schemas.
4. Searches historical incidents and bug records for proven previous resolutions.
5. Employs LLM structured reasoning to synthesize ranked hypotheses, log line citations,
   and code citations, with graceful fallback to deterministic diagnosis.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.env_checker import EnvVarChecker, EnvVarCheckResult
from app.analysis.log_parser import LogParser, ParsedDeploymentLog
from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import NotFoundError
from app.domain.deployment.schemas import (
    DeploymentDiagnosisRequest,
    DeploymentDiagnosisResponse,
    EnvVarCheckResultSchema,
    SimilarIncidentMatch,
)
from app.llm.models import LLMGenerationRequest
from app.llm.prompt_loader import PromptLoader, default_prompt_loader
from app.llm.repair import extract_json_candidate
from app.llm.router import LLMGatewayRouter
from app.llm.schemas import DeploymentDiagnosisOutput, DiagnosisHypothesis
from app.orchestration.state import (
    CitationRef,
    NodeError,
    RunState,
    SpecialistTask,
)
from app.persistence.repositories.incident_repo import DeploymentIncidentRepository
from app.persistence.repositories.project_repo import ProjectRepository

logger = logging.getLogger("devmind.orchestration.deploy_doctor")


class DeployDoctorAgent:
    """Specialist agent diagnosing deployment logs with secret redaction and similarity matching."""

    def __init__(
        self,
        session: AsyncSession,
        router: LLMGatewayRouter | None = None,
        prompt_loader: PromptLoader | None = None,
    ) -> None:
        self.session = session
        self.incident_repo = DeploymentIncidentRepository(session)
        self.project_repo = ProjectRepository(session)
        self.router = router
        self.prompt_loader = prompt_loader or default_prompt_loader

    async def diagnose(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        request: DeploymentDiagnosisRequest,
    ) -> DeploymentDiagnosisResponse:
        """Execute full deployment log diagnosis workflow."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if not project:
            raise NotFoundError(detail=f"Project {project_id} not found")

        workspace_id = project.workspace_id

        # 1. Deterministic log pre-redaction and parsing (CAP-07)
        parsed: ParsedDeploymentLog = LogParser.redact_and_parse(
            raw_log=request.raw_log,
            environment=request.environment,
            service_name=request.service_name,
        )

        now = datetime.now(UTC)

        # 2. Check for empty/insufficient log content
        if (
            not request.raw_log.strip()
            or parsed.failure_category == "unknown"
            and parsed.confidence == 0.0
        ):
            # Upsert placeholder incident or record failure
            incident, is_new, _ = await self.incident_repo.record_incident(
                ctx,
                workspace_id=workspace_id,
                project_id=project_id,
                raw_log=request.raw_log,
                environment=request.environment,
                service_name=request.service_name,
                summary="Insufficient deployment log",
                probable_cause="No usable log content provided",
            )
            return DeploymentDiagnosisResponse(
                incident_id=incident.id,
                is_new_incident=is_new,
                fingerprint=parsed.fingerprint,
                failure_category="unknown",
                confidence=0.0,
                summary="Empty or insufficient log payload provided.",
                probable_cause="The provided log content was empty or lacked actionable failure signals.",
                recommended_action="Paste complete container logs covering startup, build, or runtime crash output.",
                hypotheses=[],
                referenced_env_vars=[],
                env_var_check=None,
                referenced_files=[],
                primary_log_line=None,
                similar_past_incidents=[],
                is_insufficient_log=True,
                missing_information_needed="Please provide full container initialization, dependency build, or application crash stack traces.",
                redaction_count=parsed.redaction_count,
                created_at=now,
            )

        # 3. Environment variable name checking (keys only, never values)
        env_check_result: EnvVarCheckResult = EnvVarChecker.verify_environment_variables(
            referenced_names=parsed.referenced_env_vars,
            configured_names=request.configured_env_vars,
            example_env_content=request.example_env_content,
        )
        env_check_schema = EnvVarCheckResultSchema(
            referenced_names=env_check_result.referenced_names,
            missing_required=env_check_result.missing_required,
            referenced_missing=env_check_result.referenced_missing,
            suspected_typos=[t.to_dict() for t in env_check_result.suspected_typos],
            valid_configured=env_check_result.valid_configured,
            has_issues=env_check_result.has_issues,
        )

        # 4. Search historical incidents for similar fingerprints or failure categories
        similar_raw = await self.incident_repo.search_similar_incidents(
            ctx,
            workspace_id=workspace_id,
            project_id=project_id,
            fingerprint=parsed.fingerprint,
            failure_category=parsed.failure_category,
            error_signature=parsed.error_signature,
            referenced_env_vars=parsed.referenced_env_vars,
            limit=5,
        )

        similar_matches: list[SimilarIncidentMatch] = [
            SimilarIncidentMatch(
                incident_id=inc.id,
                fingerprint=inc.fingerprint,
                summary=inc.summary,
                probable_cause=inc.probable_cause,
                resolution=inc.resolution,
                failure_category=inc.failure_category,
                similarity_score=score,
                match_type=match_type,
                last_seen_at=inc.last_seen_at,
                resolved_at=inc.resolved_at,
            )
            for inc, score, match_type in similar_raw
        ]

        # 5. LLM Synthesis or deterministic fallback
        llm_output = await self._synthesize_diagnosis(
            parsed=parsed,
            env_check=env_check_result,
            similar_matches=similar_matches,
        )

        final_summary = llm_output.summary if llm_output else parsed.summary
        final_cause = (
            llm_output.hypotheses[0].probable_cause
            if (llm_output and llm_output.hypotheses)
            else parsed.probable_cause
        )
        final_action = llm_output.recommended_action if llm_output else parsed.recommended_action
        final_confidence = llm_output.confidence if llm_output else parsed.confidence

        # If LLM generated hypotheses, use them; otherwise create default from deterministic analysis
        if llm_output and llm_output.hypotheses:
            hypotheses = llm_output.hypotheses
        else:
            default_file_cites = [
                f"{f['path']}:{f['line']}"
                for f in parsed.referenced_files
                if f.get("is_project_code")
            ][:3]
            hypotheses = [
                DiagnosisHypothesis(
                    title=parsed.summary,
                    probable_cause=parsed.probable_cause,
                    confidence=parsed.confidence,
                    recommended_action=parsed.recommended_action,
                    log_line_citations=[parsed.primary_log_line] if parsed.primary_log_line else [],
                    file_citations=default_file_cites,
                )
            ]

        # 6. Record or update incident in persistence store
        incident, is_new, _ = await self.incident_repo.record_incident(
            ctx,
            workspace_id=workspace_id,
            project_id=project_id,
            raw_log=request.raw_log,
            environment=request.environment,
            service_name=request.service_name,
            summary=final_summary,
            probable_cause=final_cause,
        )

        return DeploymentDiagnosisResponse(
            incident_id=incident.id,
            is_new_incident=is_new,
            fingerprint=parsed.fingerprint,
            failure_category=parsed.failure_category,
            confidence=final_confidence,
            summary=final_summary,
            probable_cause=final_cause,
            recommended_action=final_action,
            hypotheses=hypotheses,
            referenced_env_vars=parsed.referenced_env_vars,
            env_var_check=env_check_schema,
            referenced_files=parsed.referenced_files,
            primary_log_line=parsed.primary_log_line,
            similar_past_incidents=similar_matches,
            is_insufficient_log=llm_output.is_insufficient_log if llm_output else False,
            missing_information_needed=(
                llm_output.missing_information_needed if llm_output else None
            ),
            redaction_count=parsed.redaction_count,
            created_at=incident.created_at or now,
        )

    async def _synthesize_diagnosis(
        self,
        parsed: ParsedDeploymentLog,
        env_check: EnvVarCheckResult,
        similar_matches: list[SimilarIncidentMatch],
    ) -> DeploymentDiagnosisOutput | None:
        """Invoke LLM gateway for hypothesis ranking, log citations, and root cause narrative."""
        if not self.router:
            return None

        try:
            prompt_template = self.prompt_loader.load("deployment_diagnosis", 1)

            # Build readable summary strings for prompt
            env_check_summary = (
                f"Issues detected: {env_check.has_issues}. "
                f"Missing required: {env_check.missing_required}. "
                f"Referenced but unconfigured: {env_check.referenced_missing}. "
                f"Suspected typos: {[t.to_dict() for t in env_check.suspected_typos]}."
            )

            similar_summary = "None found"
            if similar_matches:
                items_str = []
                for m in similar_matches:
                    res_note = f" (Resolved: {m.resolution})" if m.resolution else " (Unresolved)"
                    items_str.append(
                        f"- [{m.match_type}, sim={m.similarity_score:.2f}] {m.summary}{res_note}"
                    )
                similar_summary = "\n".join(items_str)

            code_frames_str = (
                "\n".join(
                    f"{r['path']}:{r['line']} in {r.get('function') or 'module'}"
                    for r in parsed.referenced_files[:5]
                )
                if parsed.referenced_files
                else "No stack trace frames detected"
            )

            rendered = prompt_template.render(
                {
                    "redacted_log_snippet": parsed.redacted_text[:3000],
                    "failure_category": parsed.failure_category,
                    "deterministic_cause": parsed.probable_cause,
                    "referenced_env_vars": ", ".join(parsed.referenced_env_vars) or "None",
                    "env_var_check_summary": env_check_summary,
                    "similar_past_incidents_summary": similar_summary,
                    "referenced_code_frames": code_frames_str,
                }
            )

            req = LLMGenerationRequest(
                task="deployment_diagnosis",
                prompt=rendered.user_prompt,
                system_prompt=rendered.system_prompt,
                temperature=0.1,
                max_output_tokens=1500,
            )

            resp = await self.router.generate(req)
            data_dict = extract_json_candidate(resp.content)
            if data_dict:
                return DeploymentDiagnosisOutput.model_validate(data_dict)

        except Exception as exc:
            logger.warning(
                "LLM deployment diagnosis synthesis failed, falling back to deterministic: %s", exc
            )

        return None


async def run_deploy_doctor_specialist(
    state: RunState,
    task: SpecialistTask,
    router: LLMGatewayRouter | None = None,
    prompt_loader: PromptLoader | None = None,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Execute DeployDoctor specialist task within LangGraph Agent Manager workflow."""
    if not session:
        return {
            "errors": [
                NodeError(
                    node="deploy_doctor",
                    error_code="missing_session",
                    message="Database session required for DeployDoctor specialist execution.",
                )
            ]
        }

    try:
        raw_log = task.params.get("raw_log", "")
        if not raw_log and state.get("request"):
            raw_log = state["request"].params.get("raw_log", "")

        environment = task.params.get("environment", "production")
        service_name = task.params.get("service_name")
        configured_env_vars = task.params.get("configured_env_vars")
        example_env_content = task.params.get("example_env_content")

        project_id_raw = state.get("project_id")
        project_id = UUID(str(project_id_raw)) if project_id_raw else None
        if not project_id:
            raise ValueError("project_id is required for DeployDoctor execution")

        ctx: AuthContext | SystemContext = state.get("auth_context") or SystemContext()

        agent = DeployDoctorAgent(session=session, router=router, prompt_loader=prompt_loader)
        req = DeploymentDiagnosisRequest(
            raw_log=raw_log,
            environment=environment,
            service_name=service_name,
            configured_env_vars=configured_env_vars,
            example_env_content=example_env_content,
        )

        res: DeploymentDiagnosisResponse = await agent.diagnose(ctx, project_id, req)

        task.status = "completed"

        citations: list[CitationRef] = []
        for file_ref in res.referenced_files:
            citations.append(
                CitationRef(
                    doc_id=str(res.incident_id),
                    path=file_ref["path"],
                    start_line=file_ref["line"],
                    end_line=file_ref["line"],
                    symbol=file_ref.get("function"),
                )
            )

        response_text = f"**Deployment Diagnosis [{res.failure_category.upper()}]**: {res.summary}\n\n**Probable Cause**: {res.probable_cause}\n\n**Recommended Action**: {res.recommended_action}"

        return {
            "final_response": response_text,
            "citations": citations,
            "metadata": {
                "incident_id": str(res.incident_id),
                "fingerprint": res.fingerprint,
                "confidence": res.confidence,
                "failure_category": res.failure_category,
                "redaction_count": res.redaction_count,
            },
        }

    except Exception as exc:
        logger.exception("DeployDoctor specialist execution failed: %s", exc)
        task.status = "failed"
        return {
            "errors": [
                NodeError(
                    node="deploy_doctor",
                    error_code="specialist_failed",
                    message=f"DeployDoctor execution failed: {exc}",
                )
            ]
        }
