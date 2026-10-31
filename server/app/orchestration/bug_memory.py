"""BugMemory specialist agent, hybrid error matching, and resolution memory (docs/01 CAP-03, docs/05 §6.6).

Per docs/05 §6.6:
1. Normalizes incoming raw error or stack trace using deterministic ErrorNormalizer.
2. Identifies matching candidates via exact fingerprint, keyword/token overlap, and module hints.
3. Compares top candidates and explains similarity, stating differences and shared characteristics.
4. If similar, provides previous resolutions (cause, fix, files) from historical records.
5. Emits structured proposals for documenting bug resolutions.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.error_normalizer import ErrorNormalizer, NormalizedError
from app.core.auth_context import AuthContext, SystemContext
from app.domain.bug_memory.schemas import (
    BugMatchCandidateResponse,
    BugMatchResponse,
    BugRecordDetailResponse,
    BugResolutionResponse,
    NormalizedErrorSummary,
    ResolutionProposal,
)
from app.llm.models import LLMGenerationRequest
from app.llm.prompt_loader import PromptLoader, default_prompt_loader
from app.llm.repair import extract_json_candidate
from app.llm.router import LLMGatewayRouter
from app.llm.schemas import BugSimilarityExplanation
from app.persistence.models.bug_memory import BugRecord
from app.persistence.repositories.bug_record_repo import BugRecordRepository

logger = logging.getLogger("devmind.orchestration.bug_memory")


class BugMemoryAgent:
    """Specialist agent coordinating bug memory retrieval, error normalization, and similarity explanation."""

    def __init__(
        self,
        session: AsyncSession,
        router: LLMGatewayRouter | None = None,
        prompt_loader: PromptLoader | None = None,
    ) -> None:
        self.session = session
        self.repo = BugRecordRepository(session)
        self.router = router
        self.prompt_loader = prompt_loader or default_prompt_loader

    async def match_and_explain(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        raw_error: str,
        module_hint: str | None = None,
        limit: int = 5,
    ) -> BugMatchResponse:
        """Normalize an error trace, find historical candidate matches, and synthesize similarity explanation."""
        # 1. Deterministic error normalization
        norm: NormalizedError = ErrorNormalizer.normalize(raw_error)
        norm_summary = NormalizedErrorSummary(
            exception_type=norm.exception_type,
            clean_message=norm.clean_message,
            module_hint=norm.module_hint,
            fingerprint=norm.fingerprint,
            normalized_signature=norm.normalized_signature,
        )

        effective_module = module_hint or norm.module_hint

        # 2. Hybrid candidate retrieval from BugRecordRepository
        raw_candidates: list[tuple[BugRecord, float, str]] = await self.repo.search_similar_bugs(
            ctx=ctx,
            project_id=project_id,
            fingerprint=norm.fingerprint,
            normalized_signature=norm.normalized_signature,
            module_hint=effective_module,
            query_text=norm.clean_message,
            limit=limit,
        )

        # 3. Handle zero-match scenario
        if not raw_candidates:
            return BugMatchResponse(
                matched=False,
                normalized_error=norm_summary,
                candidates=[],
                explanation="No similar bugs found in project bug memory.",
                confidence_label="none",
                recommended_fix=None,
            )

        # 4. Convert candidate records to response models
        now = datetime.now(UTC)
        candidate_responses: list[BugMatchCandidateResponse] = []
        for record, score, match_type in raw_candidates:
            resolutions = [
                BugResolutionResponse(
                    id=r.id,
                    bug_record_id=r.bug_record_id,
                    cause=r.cause,
                    fix_summary=r.fix_summary,
                    files=r.files or [],
                    finding_id=r.finding_id,
                    resolved_by=r.resolved_by,
                    created_at=r.created_at or now,
                    updated_at=r.updated_at or now,
                )
                for r in (record.resolutions or [])
            ]
            detail = BugRecordDetailResponse(
                id=record.id,
                workspace_id=record.workspace_id,
                project_id=record.project_id,
                fingerprint=record.fingerprint,
                error_signature=record.error_signature,
                title=record.title,
                summary=record.summary,
                module_hint=record.module_hint,
                occurrence_count=record.occurrence_count,
                resolutions_count=len(resolutions),
                first_seen_at=record.first_seen_at or now,
                last_seen_at=record.last_seen_at or now,
                created_at=record.created_at or now,
                updated_at=record.updated_at or now,
                raw_error=record.raw_error,
                resolutions=resolutions,
            )
            candidate_responses.append(
                BugMatchCandidateResponse(
                    bug=detail,
                    score=score,
                    match_type=match_type,
                )
            )

        # 5. Synthesize comparison & explanation for top candidate
        top_cand = raw_candidates[0][0]
        top_score = raw_candidates[0][1]
        top_match_type = raw_candidates[0][2]

        explanation_text: str
        confidence_label: str
        recommended_fix: str | None = None

        # Resolve latest fix summary if available
        if top_cand.resolutions:
            recommended_fix = top_cand.resolutions[0].fix_summary

        if top_score >= 0.99 or top_match_type == "exact_fingerprint":
            # Exact match deterministic synthesis
            confidence_label = "high"
            res_detail = ""
            if top_cand.resolutions:
                latest_res = top_cand.resolutions[0]
                res_detail = (
                    f" Previous fix for cause '{latest_res.cause}': {latest_res.fix_summary}"
                )
                if latest_res.files:
                    file_names = ", ".join(
                        f.get("path", "") for f in latest_res.files if isinstance(f, dict)
                    )
                    if file_names:
                        res_detail += f" (modified files: {file_names})."
            explanation_text = (
                f"Exact match found for error signature '{top_cand.title}' "
                f"(seen {top_cand.occurrence_count} times in module '{top_cand.module_hint or 'unknown'}').{res_detail}"
            )
        else:
            # Fuzzy match -> Attempt LLM comparison if router is configured
            llm_explanation: BugSimilarityExplanation | None = None
            if self.router and self.prompt_loader:
                try:
                    error_details = (
                        f"Exception Type: {norm.exception_type}\n"
                        f"Message: {norm.clean_message}\n"
                        f"Module: {norm.module_hint or 'unknown'}\n"
                        f"Normalized Signature:\n{norm.normalized_signature}"
                    )
                    cand_details = (
                        f"Title: {top_cand.title}\n"
                        f"Module: {top_cand.module_hint or 'unknown'}\n"
                        f"Occurrence Count: {top_cand.occurrence_count}\n"
                        f"Normalized Signature:\n{top_cand.error_signature}"
                    )
                    res_texts: list[str] = []
                    for idx, res in enumerate(top_cand.resolutions or [], 1):
                        res_texts.append(
                            f"Resolution #{idx}:\n"
                            f"  Cause: {res.cause}\n"
                            f"  Fix: {res.fix_summary}\n"
                            f"  Files: {json.dumps(res.files)}"
                        )
                    previous_resolutions = (
                        "\n\n".join(res_texts) if res_texts else "None documented yet."
                    )

                    rendered = self.prompt_loader.render(
                        task="bug_similarity_explanation",
                        version=1,
                        variables={
                            "error_details": error_details,
                            "candidate_bug": cand_details,
                            "previous_resolutions": previous_resolutions,
                        },
                    )

                    gen_req = LLMGenerationRequest(
                        task="bug_similarity_explanation",
                        messages=rendered.messages,
                    )

                    resp = await self.router.generate(gen_req)
                    raw_content = resp.content or ""
                    if not isinstance(raw_content, str):
                        raw_content = json.dumps(raw_content)

                    json_cand = extract_json_candidate(raw_content)
                    if json_cand:
                        llm_explanation = BugSimilarityExplanation.model_validate_json(json_cand)
                except Exception as ex:
                    logger.warning("LLM bug similarity explanation failed, using fallback: %s", ex)

            if llm_explanation:
                explanation_text = llm_explanation.summary
                confidence_label = llm_explanation.confidence_label
                if llm_explanation.recommended_action:
                    recommended_fix = llm_explanation.recommended_action
            else:
                # Deterministic fallback explanation
                if top_score >= 0.7:
                    confidence_label = "high"
                elif top_score >= 0.4:
                    confidence_label = "medium"
                else:
                    confidence_label = "low"

                shared: list[str] = []
                if (
                    norm.module_hint
                    and top_cand.module_hint
                    and norm.module_hint == top_cand.module_hint
                ):
                    shared.append(f"shared module '{norm.module_hint}'")
                if norm.exception_type in top_cand.error_signature:
                    shared.append(f"same exception type '{norm.exception_type}'")

                shared_desc = ", ".join(shared) if shared else "similar error structure"
                res_desc = ""
                if top_cand.resolutions:
                    res_desc = f" Previous resolution: {top_cand.resolutions[0].fix_summary}."

                explanation_text = f"Similar past issue found '{top_cand.title}' (similarity score: {top_score:.2f}, {shared_desc}).{res_desc}"

        return BugMatchResponse(
            matched=True,
            normalized_error=norm_summary,
            candidates=candidate_responses,
            explanation=explanation_text,
            confidence_label=confidence_label,
            recommended_fix=recommended_fix,
        )

    @staticmethod
    def propose_resolution(
        cause: str,
        fix_summary: str,
        files: list[dict[str, Any]] | None = None,
        finding_id: UUID | None = None,
    ) -> ResolutionProposal:
        """Formulate a validated resolution proposal for a bug record (docs/05 §6.6)."""
        if not cause.strip():
            raise ValueError("Resolution cause cannot be empty")
        if not fix_summary.strip():
            raise ValueError("Resolution fix_summary cannot be empty")

        clean_files: list[dict[str, Any]] = []
        for f in files or []:
            if isinstance(f, dict) and "path" in f:
                clean_files.append({"path": str(f["path"]), "details": f.get("details", "")})
            elif isinstance(f, str):
                clean_files.append({"path": f})

        return ResolutionProposal(
            cause=cause.strip(),
            fix_summary=fix_summary.strip(),
            files=clean_files,
            finding_id=finding_id,
        )
