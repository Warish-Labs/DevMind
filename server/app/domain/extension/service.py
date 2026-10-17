"""Extension authentication domain service (ADR-012, docs/03 §11.2, docs/07 §3).

Handles extension token issuance, rotation, expiration, and replay detection revocation.
Never persists raw tokens; all stored tokens are SHA-256 hashed.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import AuthenticationError, NotFoundError
from app.persistence.models.extension import ExtensionRegistration
from app.persistence.repositories.extension_repo import ExtensionRepository

ACCESS_TOKEN_LIFETIME_SECONDS = 3600  # 1 hour
REFRESH_TOKEN_LIFETIME_SECONDS = 30 * 86400  # 30 days


def hash_token(raw_token: str) -> str:
    """Compute SHA-256 hexadecimal digest of raw token string."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_access_token() -> str:
    """Generate cryptographically secure opaque extension access token."""
    return f"dme_at_{secrets.token_urlsafe(32)}"


def generate_refresh_token() -> str:
    """Generate cryptographically secure opaque extension refresh token."""
    return f"dme_rt_{secrets.token_urlsafe(32)}"


class ExtensionService:
    """Domain service managing extension registration lifecycle and token issuance."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ExtensionRepository(session)

    async def register_and_issue_tokens(
        self,
        ctx: AuthContext,
        *,
        name: str,
        platform: str,
        extension_version: str,
        scope: str = "project:sync",
    ) -> tuple[ExtensionRegistration, str, str, int]:
        """Register a new extension installation and issue the initial token pair.

        Returns (registration, raw_access_token, raw_refresh_token, expires_in_seconds).
        """
        # 1. Create extension registration
        registration = await self.repo.create_registration(
            ctx,
            user_id=ctx.user_id,
            name=name,
            platform=platform,
            extension_version=extension_version,
        )

        now = datetime.now(UTC)
        access_expires = now + timedelta(seconds=ACCESS_TOKEN_LIFETIME_SECONDS)
        refresh_expires = now + timedelta(seconds=REFRESH_TOKEN_LIFETIME_SECONDS)

        # 2. Generate raw tokens
        raw_access_token = generate_access_token()
        raw_refresh_token = generate_refresh_token()

        # 3. Store hashed tokens (ADR-012: raw tokens never stored)
        await self.repo.create_token(
            ctx,
            registration_id=registration.id,
            token_hash=hash_token(raw_access_token),
            kind="access",
            scope=scope,
            expires_at=access_expires,
        )
        await self.repo.create_token(
            ctx,
            registration_id=registration.id,
            token_hash=hash_token(raw_refresh_token),
            kind="refresh",
            scope=scope,
            expires_at=refresh_expires,
        )

        return (
            registration,
            raw_access_token,
            raw_refresh_token,
            ACCESS_TOKEN_LIFETIME_SECONDS,
        )

    async def refresh_tokens(
        self,
        sys_ctx: SystemContext,
        raw_refresh_token: str,
    ) -> tuple[ExtensionRegistration, str, str, int]:
        """Rotate refresh token and issue new access token.

        Enforces replay detection (docs/07 §3): Reuse of an already rotated or revoked
        refresh token revokes the entire extension registration immediately.
        """
        if not raw_refresh_token or not raw_refresh_token.startswith("dme_rt_"):
            raise AuthenticationError(
                detail="Invalid extension refresh token format",
            )

        token_hash = hash_token(raw_refresh_token)
        stored_token = await self.repo.get_token_by_hash(sys_ctx, token_hash)

        if stored_token is None or stored_token.kind != "refresh":
            raise AuthenticationError(
                detail="Invalid or unrecognized refresh token",
            )

        # Replay detection: If token was already revoked/rotated, revoke the registration!
        if stored_token.revoked_at is not None:
            await self.repo.revoke_registration(sys_ctx, stored_token.registration_id)
            raise AuthenticationError(
                detail="Token reuse detected. Extension registration has been revoked for security.",
            )

        # Check expiration
        now = datetime.now(UTC)
        if stored_token.expires_at < now:
            raise AuthenticationError(
                detail="Extension refresh token has expired",
            )

        # Check registration status
        registration = await self.repo.get_registration_by_id(sys_ctx, stored_token.registration_id)
        if registration is None or registration.revoked_at is not None:
            raise AuthenticationError(
                detail="Extension registration has been revoked",
            )

        # Rotate: Revoke the old refresh token
        await self.repo.revoke_token(sys_ctx, stored_token.id)

        # Issue new token pair with rotation tracking
        raw_access_token = generate_access_token()
        raw_refresh_token_new = generate_refresh_token()

        access_expires = now + timedelta(seconds=ACCESS_TOKEN_LIFETIME_SECONDS)
        refresh_expires = now + timedelta(seconds=REFRESH_TOKEN_LIFETIME_SECONDS)

        await self.repo.create_token(
            sys_ctx,
            registration_id=registration.id,
            token_hash=hash_token(raw_access_token),
            kind="access",
            scope=stored_token.scope,
            expires_at=access_expires,
        )
        await self.repo.create_token(
            sys_ctx,
            registration_id=registration.id,
            token_hash=hash_token(raw_refresh_token_new),
            kind="refresh",
            scope=stored_token.scope,
            expires_at=refresh_expires,
            rotated_from=stored_token.id,
        )

        # Touch registration timestamp
        await self.repo.touch_registration(sys_ctx, registration.id)

        return (
            registration,
            raw_access_token,
            raw_refresh_token_new,
            ACCESS_TOKEN_LIFETIME_SECONDS,
        )

    async def record_heartbeat(
        self,
        ctx: AuthContext,
        registration_id: UUID,
    ) -> None:
        """Update last_seen_at for an extension registration."""
        reg = await self.repo.get_registration_by_id(ctx, registration_id)
        if reg is None:
            raise NotFoundError(detail=f"Extension registration {registration_id} not found")
        await self.repo.touch_registration(ctx, registration_id)

    async def revoke_registration(
        self,
        ctx: AuthContext,
        registration_id: UUID,
    ) -> None:
        """Revoke an extension registration and its issued tokens."""
        revoked = await self.repo.revoke_registration(ctx, registration_id)
        if not revoked:
            raise NotFoundError(
                detail=f"Extension registration {registration_id} not found or already revoked"
            )
