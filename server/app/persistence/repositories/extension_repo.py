"""Extension registration and token repository (docs/03 §3.1, ADR-012).

Enforces AuthContext/SystemContext validation on every query.
Never stores or queries raw tokens; relies solely on SHA-256 token hashes.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.persistence.models.extension import ExtensionRegistration, ExtensionToken
from app.persistence.repositories.base import BaseRepository


class ExtensionRepository(BaseRepository):
    """Repository for managing extension installations and scoped tokens."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create_registration(
        self,
        ctx: AuthContext | SystemContext,
        *,
        user_id: UUID,
        name: str,
        platform: str,
        extension_version: str,
    ) -> ExtensionRegistration:
        """Register a new extension installation for a user."""
        self._validate_context(ctx)

        registration = ExtensionRegistration(
            user_id=user_id,
            name=name,
            platform=platform,
            extension_version=extension_version,
            last_seen_at=datetime.now().astimezone(),
        )
        self.session.add(registration)
        await self.session.flush()
        await self.session.refresh(registration)
        return registration

    async def get_registration_by_id(
        self,
        ctx: AuthContext | SystemContext,
        registration_id: UUID,
    ) -> ExtensionRegistration | None:
        """Fetch registration by ID."""
        self._validate_context(ctx)

        stmt = select(ExtensionRegistration).where(ExtensionRegistration.id == registration_id)
        if isinstance(ctx, AuthContext):
            stmt = stmt.where(ExtensionRegistration.user_id == ctx.user_id)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_registrations_for_user(
        self,
        ctx: AuthContext | SystemContext,
        user_id: UUID,
    ) -> list[ExtensionRegistration]:
        """List all active and historical extension registrations for a user."""
        self._validate_context(ctx)

        stmt = (
            select(ExtensionRegistration)
            .where(ExtensionRegistration.user_id == user_id)
            .order_by(ExtensionRegistration.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def touch_registration(
        self,
        ctx: AuthContext | SystemContext,
        registration_id: UUID,
    ) -> None:
        """Update last_seen_at timestamp for an extension registration."""
        self._validate_context(ctx)

        stmt = (
            update(ExtensionRegistration)
            .where(ExtensionRegistration.id == registration_id)
            .values(last_seen_at=func.now(), updated_at=func.now())
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def revoke_registration(
        self,
        ctx: AuthContext | SystemContext,
        registration_id: UUID,
    ) -> bool:
        """Revoke an extension installation and all of its associated tokens."""
        self._validate_context(ctx)

        reg = await self.get_registration_by_id(ctx, registration_id)
        if reg is None or reg.revoked_at is not None:
            return False

        now = datetime.now().astimezone()
        reg.revoked_at = now

        # Revoke all tokens for this registration
        await self.session.execute(
            update(ExtensionToken)
            .where(
                ExtensionToken.registration_id == registration_id,
                ExtensionToken.revoked_at.is_(None),
            )
            .values(revoked_at=now, updated_at=now)
        )
        await self.session.flush()
        return True

    async def create_token(
        self,
        ctx: AuthContext | SystemContext,
        *,
        registration_id: UUID,
        token_hash: str,
        kind: str,
        scope: str,
        expires_at: datetime,
        rotated_from: UUID | None = None,
    ) -> ExtensionToken:
        """Store a new hashed extension token."""
        self._validate_context(ctx)

        token = ExtensionToken(
            registration_id=registration_id,
            token_hash=token_hash,
            kind=kind,
            scope=scope,
            expires_at=expires_at,
            rotated_from=rotated_from,
        )
        self.session.add(token)
        await self.session.flush()
        await self.session.refresh(token)
        return token

    async def get_token_by_hash(
        self,
        ctx: AuthContext | SystemContext,
        token_hash: str,
    ) -> ExtensionToken | None:
        """Find a token by its SHA-256 hash."""
        self._validate_context(ctx)

        stmt = select(ExtensionToken).where(ExtensionToken.token_hash == token_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_token_by_id(
        self,
        ctx: AuthContext | SystemContext,
        token_id: UUID,
    ) -> ExtensionToken | None:
        """Find a token by its UUID."""
        self._validate_context(ctx)

        stmt = select(ExtensionToken).where(ExtensionToken.id == token_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_token(
        self,
        ctx: AuthContext | SystemContext,
        token_id: UUID,
    ) -> bool:
        """Revoke a single token by setting its revoked_at timestamp."""
        self._validate_context(ctx)

        token = await self.get_token_by_id(ctx, token_id)
        if token is None or token.revoked_at is not None:
            return False

        token.revoked_at = datetime.now().astimezone()
        await self.session.flush()
        return True
