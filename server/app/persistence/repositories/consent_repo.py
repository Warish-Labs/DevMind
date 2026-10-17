"""Consent repository managing source transmission and indexing consent records (docs/03 §3.5, docs/07 §7)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.ids import generate_uuid7
from app.persistence.models.consent import ConsentRecord
from app.persistence.models.project import Project
from app.persistence.repositories.base import BaseRepository


class ConsentRepository(BaseRepository):
    """Repository managing source-transmission and cloud-indexing consent records.

    Enforces workspace-level and project-level isolation via AuthContext on every operation.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def _verify_project_access(
        self, ctx: AuthContext | SystemContext, project_id: UUID
    ) -> Project:
        """Verify that the caller has access to the target project.

        Raises:
            PermissionError: If caller's workspace does not own the project.
            ValueError: If project does not exist.
        """
        self._validate_context(ctx)
        stmt = select(Project).where(Project.id == project_id)
        if isinstance(ctx, AuthContext):
            if ctx.workspace_id is None:
                raise PermissionError("Access denied: missing workspace context")
            stmt = stmt.where(Project.workspace_id == ctx.workspace_id)

        result = await self.session.execute(stmt)
        project = result.scalars().first()
        if not project:
            stmt_unscoped = select(Project).where(Project.id == project_id)
            unscoped_result = await self.session.execute(stmt_unscoped)
            if unscoped_result.scalars().first():
                raise PermissionError(
                    f"Access denied: project '{project_id}' does not belong to workspace '{getattr(ctx, 'workspace_id', None)}'"
                )
            raise ValueError(f"Project '{project_id}' not found")
        return project

    async def create_consent(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        scope: str,
        provider_ids: list[str] | None = None,
        data_categories: list[str] | None = None,
        granted_for: str = "project",
        policy_version: str = "1.0",
        preview_hash: str | None = None,
        expires_at: datetime | None = None,
    ) -> ConsentRecord:
        """Create a new consent record for the project."""
        project = await self._verify_project_access(ctx, project_id)

        user_id = ctx.user_id if isinstance(ctx, AuthContext) and ctx.user_id else generate_uuid7()

        now = datetime.now(UTC)
        record = ConsentRecord(
            id=generate_uuid7(),
            workspace_id=project.workspace_id,
            project_id=project.id,
            user_id=user_id,
            scope=scope,
            provider_ids=provider_ids or [],
            data_categories=data_categories or [],
            granted_for=granted_for,
            policy_version=policy_version,
            preview_hash=preview_hash,
            granted_at=now,
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_consent(
        self, ctx: AuthContext | SystemContext, project_id: UUID, consent_id: UUID
    ) -> ConsentRecord | None:
        """Retrieve a specific consent record by ID within workspace and project boundaries."""
        project = await self._verify_project_access(ctx, project_id)

        stmt = select(ConsentRecord).where(
            ConsentRecord.id == consent_id,
            ConsentRecord.project_id == project.id,
            ConsentRecord.workspace_id == project.workspace_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_consents(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        active_only: bool = False,
        scope: str | None = None,
    ) -> list[ConsentRecord]:
        """List consent records for a project, optionally filtered by active status or scope."""
        project = await self._verify_project_access(ctx, project_id)

        stmt = (
            select(ConsentRecord)
            .where(
                ConsentRecord.project_id == project.id,
                ConsentRecord.workspace_id == project.workspace_id,
            )
            .order_by(ConsentRecord.created_at.desc())
        )

        if scope:
            stmt = stmt.where(ConsentRecord.scope == scope)

        if active_only:
            now = datetime.now(UTC)
            stmt = stmt.where(
                ConsentRecord.revoked_at.is_(None),
                (ConsentRecord.expires_at.is_(None) | (ConsentRecord.expires_at > now)),
            )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def revoke_consent(
        self, ctx: AuthContext | SystemContext, project_id: UUID, consent_id: UUID
    ) -> ConsentRecord | None:
        """Revoke a consent record immediately."""
        record = await self.get_consent(ctx, project_id, consent_id)
        if not record:
            return None

        now = datetime.now(UTC)
        record.revoked_at = now
        record.updated_at = now
        await self.session.flush()
        return record

    async def has_active_consent(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        scope: str,
        provider_id: str | None = None,
    ) -> bool:
        """Check whether there is an active (unrevoked, unexpired) consent record matching scope and provider."""
        consents = await self.list_consents(ctx, project_id, active_only=True, scope=scope)
        if not consents:
            return False

        if provider_id is None:
            return True

        # If a specific provider was requested, verify that at least one active consent includes it
        for c in consents:
            if not c.provider_ids or provider_id in c.provider_ids:
                return True
        return False
