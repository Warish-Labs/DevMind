"""Domain service for PRAgent pull request intelligence and change-impact coordination (docs/01 CAP-06, docs/03 §3.5)."""

from __future__ import annotations

import logging
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import NotFoundError
from app.domain.pr_agent.schemas import (
    PRAnalysisResponse,
    TriggerPRAnalysisRequest,
)
from app.orchestration.pragent import PRAgent, PRAgentState
from app.persistence.models.github import PullRequest
from app.persistence.repositories.github_repo import GitHubRepository
from app.persistence.repositories.pr_analysis_repo import PRAnalysisRepository
from app.persistence.repositories.project_repo import ProjectRepository

logger = logging.getLogger(__name__)


class PRAgentService:
    """Coordinates PR analysis execution, change impact derivation, and historical reporting."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = PRAnalysisRepository(session)
        self.github_repo = GitHubRepository(session)
        self.project_repo = ProjectRepository(session)

    async def analyze_pull_request(
        self,
        ctx: AuthContext | SystemContext,
        pull_request_id: UUID,
        request_data: TriggerPRAnalysisRequest | None = None,
    ) -> PRAnalysisResponse:
        """Trigger PRAgent change-impact analysis and PR summary synthesis on a pull request."""
        # 1. Fetch Pull Request record
        pr = await self.github_repo.get_pull_request_by_id(ctx, pull_request_id)
        if pr is None:
            raise NotFoundError(detail=f"Pull request {pull_request_id} not found")

        # 2. Fetch linked GitHub repository binding
        repo_binding = await self.github_repo.get_repository_by_id(ctx, pr.repository_id)
        if repo_binding is None:
            raise NotFoundError(detail=f"Repository binding {pr.repository_id} not found")

        # 3. Verify project access
        project = await self.project_repo.get_by_id(ctx, repo_binding.project_id)
        if project is None:
            raise NotFoundError(detail=f"Project {repo_binding.project_id} not found")

        diff_text = ""
        if request_data and request_data.diff_override:
            diff_text = request_data.diff_override
        elif pr.diff_url:
            diff_text = await self._fetch_diff_from_github(ctx, project.workspace_id, pr)

        # 4. Execute PRAgent orchestration
        pr_agent = PRAgent(session=self.session)
        state: PRAgentState = {
            "project_id": str(project.id),
            "workspace_id": str(project.workspace_id),
            "pull_request_id": str(pr.id),
            "diff": diff_text,
            "changed_files": [],
        }
        result = await pr_agent.execute(state)

        impact_data = result.get("impact_report", {})
        summary_data = result.get("pr_summary", {})
        risk_level = impact_data.get("risk_level", "low")

        # 5. Persist PRAnalysis record
        analysis = await self.repo.create_analysis(
            ctx=ctx,
            workspace_id=project.workspace_id,
            project_id=project.id,
            pull_request_id=pr.id,
            head_sha=pr.head_sha,
            job_id=None,
            risk_level=risk_level,
            summary=summary_data,
            impact=impact_data,
        )

        return PRAnalysisResponse.model_validate(analysis)

    async def get_latest_analysis(
        self,
        ctx: AuthContext | SystemContext,
        pull_request_id: UUID,
    ) -> PRAnalysisResponse:
        """Retrieve the most recent analysis report for a pull request."""
        analysis = await self.repo.get_latest_by_pr(ctx, pull_request_id)
        if analysis is None:
            raise NotFoundError(detail=f"No analysis found for pull request {pull_request_id}")
        return PRAnalysisResponse.model_validate(analysis)

    async def list_analyses(
        self,
        ctx: AuthContext | SystemContext,
        pull_request_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PRAnalysisResponse]:
        """List historical analyses for a pull request."""
        analyses = await self.repo.list_by_pr(ctx, pull_request_id, limit=limit, offset=offset)
        return [PRAnalysisResponse.model_validate(a) for a in analyses]

    async def _fetch_diff_from_github(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        pr: PullRequest,
    ) -> str:
        """Fetch unified diff from GitHub API using decrypted credential if available."""
        if not pr.diff_url:
            return ""

        token = None
        if isinstance(ctx, AuthContext) and ctx.user_id:
            token = await self.github_repo.get_decrypted_token(
                ctx=ctx,
                workspace_id=workspace_id,
                user_id=ctx.user_id,
            )

        headers = {
            "Accept": "application/vnd.github.v3.diff",
            "User-Agent": "DevMind-Agent/1.0",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(pr.diff_url, headers=headers)
                if res.status_code == 200:
                    return res.text
                logger.warning(
                    f"GitHub diff fetch returned status {res.status_code} for PR {pr.number}"
                )
        except Exception as exc:
            logger.warning(f"Error fetching remote diff for PR {pr.number}: {exc}")

        return ""
