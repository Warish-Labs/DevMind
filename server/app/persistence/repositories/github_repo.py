"""Repository for GitHubConnection persistence and workspace-scoped operations (docs/03 §3.1)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.crypto import EncryptionService
from app.core.errors import ForbiddenError
from app.core.settings import Settings, get_settings
from app.persistence.models.github import (
    GitHubConnection,
    GitHubRepositoryBinding,
    PullRequest,
)
from app.persistence.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class GitHubRepository(BaseRepository):
    """Encapsulates database operations for GitHub credentials and integrations."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        super().__init__(session)
        self.settings = settings or get_settings()
        self.crypto = EncryptionService(self.settings)

    async def upsert_connection(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        user_id: UUID,
        kind: str,
        external_account: str,
        scopes: list[str],
        encrypted_credential: str,
    ) -> GitHubConnection:
        """Upsert a GitHub credential record for a workspace/user."""
        self._validate_context(ctx)

        # Enforce workspace tenancy
        if isinstance(ctx, AuthContext) and ctx.workspace_id and ctx.workspace_id != workspace_id:
            raise ForbiddenError(detail="Cross-workspace GitHub connection access is forbidden")

        stmt = select(GitHubConnection).where(
            GitHubConnection.workspace_id == workspace_id,
            GitHubConnection.user_id == user_id,
            GitHubConnection.kind == kind,
        )
        result = await self.session.execute(stmt)
        conn = result.scalar_one_or_none()

        if conn is not None:
            conn.external_account = external_account
            conn.scopes = scopes
            conn.encrypted_credential = encrypted_credential
            conn.revoked_at = None
            conn.updated_at = datetime.now(UTC)
        else:
            conn = GitHubConnection(
                workspace_id=workspace_id,
                user_id=user_id,
                kind=kind,
                external_account=external_account,
                scopes=scopes,
                encrypted_credential=encrypted_credential,
            )
            self.session.add(conn)

        await self.session.flush()
        return conn

    async def get_connection(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        user_id: UUID,
        kind: str = "oauth",
    ) -> GitHubConnection | None:
        """Retrieve a specific GitHub credential grant if not revoked."""
        self._validate_context(ctx)

        if isinstance(ctx, AuthContext) and ctx.workspace_id and ctx.workspace_id != workspace_id:
            raise ForbiddenError(detail="Cross-workspace GitHub connection access is forbidden")

        stmt = select(GitHubConnection).where(
            GitHubConnection.workspace_id == workspace_id,
            GitHubConnection.user_id == user_id,
            GitHubConnection.kind == kind,
            GitHubConnection.revoked_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_workspace_connections(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
    ) -> Sequence[GitHubConnection]:
        """List active GitHub connections for a workspace."""
        self._validate_context(ctx)

        if isinstance(ctx, AuthContext) and ctx.workspace_id and ctx.workspace_id != workspace_id:
            raise ForbiddenError(detail="Cross-workspace GitHub connection access is forbidden")

        stmt = select(GitHubConnection).where(
            GitHubConnection.workspace_id == workspace_id,
            GitHubConnection.revoked_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def revoke_connection(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        user_id: UUID,
        kind: str = "oauth",
    ) -> bool:
        """Mark a GitHub connection as revoked."""
        self._validate_context(ctx)

        if isinstance(ctx, AuthContext) and ctx.workspace_id and ctx.workspace_id != workspace_id:
            raise ForbiddenError(detail="Cross-workspace GitHub connection access is forbidden")

        stmt = select(GitHubConnection).where(
            GitHubConnection.workspace_id == workspace_id,
            GitHubConnection.user_id == user_id,
            GitHubConnection.kind == kind,
            GitHubConnection.revoked_at.is_(None),
        )
        result = await self.session.execute(stmt)
        conn = result.scalar_one_or_none()
        if conn is None:
            return False

        conn.revoked_at = datetime.now(UTC)
        await self.session.flush()
        return True

    async def get_connection_by_id(
        self,
        ctx: AuthContext | SystemContext,
        connection_id: UUID,
        workspace_id: UUID | None = None,
    ) -> GitHubConnection | None:
        """Retrieve connection by primary key with strict workspace scoping."""
        self._validate_context(ctx)

        stmt = select(GitHubConnection).where(GitHubConnection.id == connection_id)
        if isinstance(ctx, AuthContext) and ctx.workspace_id:
            stmt = stmt.where(GitHubConnection.workspace_id == ctx.workspace_id)
        elif workspace_id:
            stmt = stmt.where(GitHubConnection.workspace_id == workspace_id)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_decrypted_token(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        user_id: UUID,
        kind: str = "oauth",
    ) -> str | None:
        """Retrieve and decrypt stored credential using AES-256-GCM.

        Never logs the plaintext token; logs only the operation metadata.
        """
        conn = await self.get_connection(ctx, workspace_id, user_id, kind=kind)
        if conn is None or not conn.encrypted_credential:
            return None

        logger.debug(
            "Decrypting %s token for workspace_id=%s, user_id=%s",
            kind,
            workspace_id,
            user_id,
        )
        return self.crypto.decrypt(conn.encrypted_credential)

    async def rotate_credential(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        user_id: UUID,
        kind: str = "oauth",
    ) -> GitHubConnection | None:
        """Re-encrypt credential under current primary key (supports key rollover)."""
        conn = await self.get_connection(ctx, workspace_id, user_id, kind=kind)
        if conn is None or not conn.encrypted_credential:
            return None

        decrypted = self.crypto.decrypt(conn.encrypted_credential)
        new_envelope = self.crypto.encrypt(decrypted)
        conn.encrypted_credential = new_envelope
        conn.updated_at = datetime.now(UTC)
        await self.session.flush()

        logger.info(
            "Rotated encryption envelope for %s connection (workspace_id=%s, user_id=%s)",
            kind,
            workspace_id,
            user_id,
        )
        return conn

    # ---------------------------------------------------------------------------
    # GitHub Repository Linking & Mirror Operations (FR-BRN-07)
    # ---------------------------------------------------------------------------

    async def link_repository(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        connection_id: UUID,
        full_name: str,
        default_branch: str = "main",
        external_id: str | None = None,
    ) -> GitHubRepositoryBinding:
        """Bind a project to a GitHub repository."""
        self._validate_context(ctx)

        stmt = select(GitHubRepositoryBinding).where(GitHubRepositoryBinding.project_id == project_id)
        result = await self.session.execute(stmt)
        repo = result.scalar_one_or_none()

        if repo is not None:
            repo.connection_id = connection_id
            repo.full_name = full_name
            repo.default_branch = default_branch
            repo.external_id = external_id
            repo.is_active = True
            repo.updated_at = datetime.now(UTC)
        else:
            repo = GitHubRepositoryBinding(
                project_id=project_id,
                connection_id=connection_id,
                full_name=full_name,
                default_branch=default_branch,
                external_id=external_id,
                is_active=True,
            )
            self.session.add(repo)

        await self.session.flush()
        return repo

    async def get_repository_by_project(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
    ) -> GitHubRepositoryBinding | None:
        """Retrieve active repository binding for a project."""
        self._validate_context(ctx)

        stmt = select(GitHubRepositoryBinding).where(
            GitHubRepositoryBinding.project_id == project_id,
            GitHubRepositoryBinding.is_active.is_(True),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_repository_by_id(
        self,
        ctx: AuthContext | SystemContext,
        repository_id: UUID,
    ) -> GitHubRepositoryBinding | None:
        """Retrieve repository binding by primary key."""
        self._validate_context(ctx)

        stmt = select(GitHubRepositoryBinding).where(GitHubRepositoryBinding.id == repository_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_repository_by_full_name(
        self,
        ctx: AuthContext | SystemContext,
        full_name: str,
    ) -> GitHubRepositoryBinding | None:
        """Retrieve active repository binding by owner/repo name."""
        self._validate_context(ctx)

        stmt = select(GitHubRepositoryBinding).where(
            GitHubRepositoryBinding.full_name == full_name,
            GitHubRepositoryBinding.is_active.is_(True),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def unlink_repository(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
    ) -> bool:
        """Deactivate a project's repository binding."""
        repo = await self.get_repository_by_project(ctx, project_id)
        if repo is None:
            return False

        repo.is_active = False
        repo.updated_at = datetime.now(UTC)
        await self.session.flush()
        return True

    # ---------------------------------------------------------------------------
    # Pull Request Mirror Operations (CAP-06)
    # ---------------------------------------------------------------------------

    async def upsert_pull_request(
        self,
        ctx: AuthContext | SystemContext,
        repository_id: UUID,
        number: int,
        title: str,
        author_login: str,
        head_sha: str,
        base_sha: str,
        state: str = "open",
        head_ref: str | None = None,
        base_ref: str | None = None,
        diff_url: str | None = None,
        merged_at: datetime | None = None,
        closed_at: datetime | None = None,
    ) -> PullRequest:
        """Upsert a mirrored pull request for a repository."""
        self._validate_context(ctx)

        stmt = select(PullRequest).where(
            PullRequest.repository_id == repository_id,
            PullRequest.number == number,
        )
        result = await self.session.execute(stmt)
        pr = result.scalar_one_or_none()

        if pr is not None:
            pr.title = title
            pr.author_login = author_login
            pr.state = state
            pr.head_sha = head_sha
            pr.base_sha = base_sha
            pr.head_ref = head_ref
            pr.base_ref = base_ref
            pr.diff_url = diff_url
            pr.merged_at = merged_at
            pr.closed_at = closed_at
            pr.updated_at = datetime.now(UTC)
        else:
            pr = PullRequest(
                repository_id=repository_id,
                number=number,
                title=title,
                author_login=author_login,
                state=state,
                head_sha=head_sha,
                base_sha=base_sha,
                head_ref=head_ref,
                base_ref=base_ref,
                diff_url=diff_url,
                merged_at=merged_at,
                closed_at=closed_at,
            )
            self.session.add(pr)

        await self.session.flush()
        return pr

    async def get_pull_request(
        self,
        ctx: AuthContext | SystemContext,
        repository_id: UUID,
        number: int,
    ) -> PullRequest | None:
        """Retrieve mirrored PR by repository and PR number."""
        self._validate_context(ctx)

        stmt = select(PullRequest).where(
            PullRequest.repository_id == repository_id,
            PullRequest.number == number,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pull_request_by_id(
        self,
        ctx: AuthContext | SystemContext,
        pr_id: UUID,
    ) -> PullRequest | None:
        """Retrieve mirrored PR by primary key."""
        self._validate_context(ctx)

        stmt = select(PullRequest).where(PullRequest.id == pr_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_pull_requests(
        self,
        ctx: AuthContext | SystemContext,
        repository_id: UUID,
        state: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[PullRequest]:
        """List mirrored PRs for repository with optional state filter."""
        self._validate_context(ctx)

        stmt = select(PullRequest).where(PullRequest.repository_id == repository_id)
        if state:
            stmt = stmt.where(PullRequest.state == state)
        stmt = stmt.order_by(PullRequest.number.desc()).limit(limit).offset(offset)

        result = await self.session.execute(stmt)
        return result.scalars().all()
