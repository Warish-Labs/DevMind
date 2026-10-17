"""Extension token authentication dependencies for /api/v1/ext/* routes (ADR-012, docs/07 §3).

Enforces Rule 10: Extension routes accept ONLY DevMind extension tokens (Bearer dme_at_...).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import AuthenticationError
from app.domain.auth.dependencies import get_db_session
from app.domain.extension.service import hash_token
from app.persistence.repositories.extension_repo import ExtensionRepository
from app.persistence.repositories.user_repo import UserRepository


async def get_extension_auth_context(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> AuthContext:
    """Extract, hash-verify, and resolve AuthContext from DevMind extension access token.

    Validates:
    1. Header format: 'Bearer dme_at_...'
    2. Token existence, kind='access', not expired, not revoked.
    3. Associated extension registration is not revoked.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.strip():
        raise AuthenticationError(
            detail="Extension access token required",
        )

    parts = auth_header.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationError(
            detail="Invalid authorization header format; expected 'Bearer <token>'",
        )

    raw_token = parts[1].strip()
    if not raw_token.startswith("dme_at_"):
        raise AuthenticationError(
            detail="Invalid extension token format; expected 'dme_at_...'",
        )

    token_hash = hash_token(raw_token)
    sys_ctx = SystemContext(reason="extension_token_verification")
    ext_repo = ExtensionRepository(session)
    user_repo = UserRepository(session)

    token = await ext_repo.get_token_by_hash(sys_ctx, token_hash)
    if token is None or token.kind != "access":
        raise AuthenticationError(
            detail="Invalid or unrecognized extension access token",
        )

    if token.revoked_at is not None:
        raise AuthenticationError(
            detail="Extension access token has been revoked",
        )

    now = datetime.now(UTC)
    if token.expires_at < now:
        raise AuthenticationError(
            detail="Extension access token has expired",
        )

    # Check registration status
    reg = await ext_repo.get_registration_by_id(sys_ctx, token.registration_id)
    if reg is None or reg.revoked_at is not None:
        raise AuthenticationError(
            detail="Extension registration has been revoked",
        )

    # Touch registration
    await ext_repo.touch_registration(sys_ctx, reg.id)

    # Resolve user
    user = await user_repo.get_by_id(sys_ctx, reg.user_id)
    if user is None:
        raise AuthenticationError(
            detail="User associated with extension token not found",
        )

    # Extension scopes become effective permissions
    scope_perms = set(token.scope.split()) if token.scope else {"project:sync"}
    req_id = getattr(request.state, "request_id", None)

    auth_ctx = AuthContext(
        user_id=user.id,
        clerk_user_id=user.clerk_user_id,
        email=user.email,
        workspace_id=None,
        permissions=frozenset(scope_perms),
        request_id=req_id,
    )

    request.state.auth_context = auth_ctx
    request.state.extension_registration = reg
    return auth_ctx
