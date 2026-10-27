"""Domain service for GitHub repository linking, ingestion, and PR mirroring (FR-BRN-07, CAP-06).

Enforces:
- Tenant isolation: linking scoped to project's workspace.
- Audit event logging on repository linking and unlinking.
- Decrypted credential usage without logging secrets.
- Mirroring PRs into PostgreSQL for fast queryability and change-impact analysis.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import NotFoundError, ValidationError
from app.core.settings import Settings, get_settings
from app.persistence.models.github import GitHubRepositoryBinding, PullRequest
from app.persistence.repositories.audit_repo import AuditEventRepository
from app.persistence.repositories.github_repo import GitHubRepository
from app.persistence.repositories.project_repo import ProjectRepository

logger = logging.getLogger(__name__)

GITHUB_API_BASE_URL = "https://api.github.com"


class GitHubIngestService:
    """Handles GitHub repository binding to projects and pull request ingestion."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.repo = GitHubRepository(session, settings=self.settings)
        self.project_repo = ProjectRepository(session)
        self.audit_repo = AuditEventRepository(session)

    async def link_project_repository(
        self,
        ctx: AuthContext,
        project_id: UUID,
        full_name: str,
        default_branch: str = "main",
    ) -> GitHubRepositoryBinding:
        """Bind a project to a GitHub repository using the caller's active connection."""
        clean_name = full_name.strip()
        if "/" not in clean_name or len(clean_name.split("/")) != 2:
            raise ValidationError(detail="Repository must be in 'owner/repo' format")

        project = await self.project_repo.get_by_id(ctx, project_id)
        if project is None:
            raise NotFoundError(detail=f"Project {project_id} not found")

        # Resolve active GitHub connection for user in workspace
        conn = await self.repo.get_connection(
            ctx=ctx,
            workspace_id=project.workspace_id,
            user_id=ctx.user_id,
            kind="oauth",
        )
        if conn is None:
            raise ValidationError(
                detail="No active GitHub connection found for this workspace. Please connect GitHub first."
            )

        binding = await self.repo.link_repository(
            ctx=ctx,
            project_id=project_id,
            connection_id=conn.id,
            full_name=clean_name,
            default_branch=default_branch,
        )

        try:
            await self.audit_repo.record(
                ctx=ctx,
                action="project.github.linked",
                target_kind="github_repository",
                target_id=str(binding.id),
                actor_id=ctx.user_id,
                workspace_id=project.workspace_id,
                metadata={"full_name": clean_name, "project_id": str(project_id)},
            )
        except Exception as exc:
            logger.warning("Failed to record audit event for GitHub linking: %s", exc)

        logger.info(
            "Project %s linked to GitHub repo %s (binding_id=%s)",
            project_id,
            clean_name,
            binding.id,
        )
        return binding

    async def unlink_project_repository(
        self,
        ctx: AuthContext,
        project_id: UUID,
    ) -> bool:
        """Unlink a GitHub repository from a project."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if project is None:
            raise NotFoundError(detail=f"Project {project_id} not found")

        repo = await self.repo.get_repository_by_project(ctx, project_id)
        if repo is None:
            return False

        unlinked = await self.repo.unlink_repository(ctx, project_id)
        if unlinked:
            try:
                await self.audit_repo.record(
                    ctx=ctx,
                    action="project.github.unlinked",
                    target_kind="github_repository",
                    target_id=str(repo.id),
                    actor_id=ctx.user_id,
                    workspace_id=project.workspace_id,
                    metadata={"full_name": repo.full_name, "project_id": str(project_id)},
                )
            except Exception as exc:
                logger.warning("Failed to record audit event for GitHub unlinking: %s", exc)

        return unlinked

    async def get_project_repository(
        self,
        ctx: AuthContext,
        project_id: UUID,
    ) -> GitHubRepositoryBinding | None:
        """Get active repository binding for a project."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if project is None:
            raise NotFoundError(detail=f"Project {project_id} not found")

        return await self.repo.get_repository_by_project(ctx, project_id)

    async def list_project_pull_requests(
        self,
        ctx: AuthContext,
        project_id: UUID,
        state: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[PullRequest]:
        """List mirrored pull requests for a project."""
        repo = await self.get_project_repository(ctx, project_id)
        if repo is None:
            return []

        return await self.repo.list_pull_requests(
            ctx=ctx,
            repository_id=repo.id,
            state=state,
            limit=limit,
            offset=offset,
        )

    async def get_pull_request_by_id(
        self,
        ctx: AuthContext | SystemContext,
        pr_id: UUID,
    ) -> PullRequest | None:
        """Retrieve mirrored PR by primary key."""
        return await self.repo.get_pull_request_by_id(ctx, pr_id)

    async def sync_pull_requests_from_github(
        self,
        ctx: AuthContext,
        project_id: UUID,
        state: str = "open",
    ) -> list[PullRequest]:
        """Fetch pull requests from GitHub REST API and mirror them to database."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if project is None:
            raise NotFoundError(detail=f"Project {project_id} not found")

        repo_binding = await self.repo.get_repository_by_project(ctx, project_id)
        if repo_binding is None:
            raise ValidationError(detail="Project does not have a linked GitHub repository")

        # Decrypt connection token
        token = await self.repo.get_decrypted_token(
            ctx=ctx,
            workspace_id=project.workspace_id,
            user_id=ctx.user_id,
            kind="oauth",
        )
        if not token:
            raise ValidationError(detail="GitHub access token expired or revoked. Please re-authenticate.")

        url = f"{GITHUB_API_BASE_URL}/repos/{repo_binding.full_name}/pulls?state={state}&per_page=30"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "DevMind-Server",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.error(
                    "GitHub API returned HTTP %d while syncing PRs for %s",
                    resp.status_code,
                    repo_binding.full_name,
                )
                from app.domain.integrations.github_permissions import classify_github_api_error

                raise classify_github_api_error(resp.status_code, resp.json())

            raw_prs: list[dict[str, Any]] = resp.json()

        mirrored_prs: list[PullRequest] = []
        for pr_data in raw_prs:
            pr_num = pr_data.get("number")
            if not pr_num:
                continue

            merged_at = None
            closed_at = None
            if pr_data.get("merged_at"):
                try:
                    merged_at = datetime.fromisoformat(pr_data["merged_at"].replace("Z", "+00:00"))
                except Exception:
                    pass
            if pr_data.get("closed_at"):
                try:
                    closed_at = datetime.fromisoformat(pr_data["closed_at"].replace("Z", "+00:00"))
                except Exception:
                    pass

            pr = await self.repo.upsert_pull_request(
                ctx=ctx,
                repository_id=repo_binding.id,
                number=int(pr_num),
                title=pr_data.get("title", f"Pull Request #{pr_num}"),
                author_login=pr_data.get("user", {}).get("login", "unknown"),
                head_sha=pr_data.get("head", {}).get("sha", ""),
                base_sha=pr_data.get("base", {}).get("sha", ""),
                state=pr_data.get("state", "open"),
                head_ref=pr_data.get("head", {}).get("ref"),
                base_ref=pr_data.get("base", {}).get("ref"),
                diff_url=pr_data.get("diff_url") or pr_data.get("html_url"),
                merged_at=merged_at,
                closed_at=closed_at,
            )
            mirrored_prs.append(pr)

        repo_binding.last_synced_at = datetime.now(UTC)
        await self.session.flush()

        logger.info(
            "Synced %d PRs from GitHub for %s",
            len(mirrored_prs),
            repo_binding.full_name,
        )
        return mirrored_prs
