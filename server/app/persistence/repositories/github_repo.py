"""Repository for GitHubConnection persistence and workspace-scoped operations (docs/03 §3.1)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import ForbiddenError
from app.persistence.models.github import GitHubConnection
from app.persistence.repositories.base import BaseRepository


class GitHubRepository(BaseRepository):
    """Encapsulates database operations for GitHub credentials and integrations."""

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
