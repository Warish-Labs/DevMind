"""Extension REST endpoints under /api/v1/ext (docs/03 §11.2, ADR-012).

Adheres to:
- Rule 10: Extension routes under /ext/* use DevMind extension tokens.
- ADR-012: DevMind-issued opaque tokens, hashed at rest, rotating refresh.
- ADR-047: Never logs secrets or raw tokens.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    ExtensionHeartbeatResponse,
    ExtensionRefreshTokenRequest,
    ExtensionTokenRequest,
    ExtensionTokenResponse,
)
from app.core.auth_context import AuthContext, SystemContext
from app.domain.auth import (
    PERMISSION_AUTHENTICATED,
    PERMISSION_PUBLIC,
    declare_permission,
    get_auth_context,
    get_db_session,
    get_extension_auth_context,
)
from app.domain.extension.service import ExtensionService

router = APIRouter(
    prefix="/ext",
    tags=["Extension"],
)


@router.post(
    "/token",
    response_model=ExtensionTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue extension access and refresh tokens",
)
@declare_permission(PERMISSION_AUTHENTICATED)
async def issue_extension_token(
    payload: ExtensionTokenRequest,
    ctx: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> ExtensionTokenResponse:
    """Issue a new scoped extension access and rotating refresh token for an authenticated user.

    The user initiates sign-in from the browser/CLI, authenticating with Clerk, and this
    endpoint registers the extension installation and issues DevMind-scoped tokens (ADR-012).
    """
    service = ExtensionService(session)
    reg, access_token, refresh_token, expires_in = await service.register_and_issue_tokens(
        ctx,
        name=payload.name,
        platform=payload.platform,
        extension_version=payload.extension_version,
        scope=payload.scope,
    )

    return ExtensionTokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=expires_in,
        refresh_token=refresh_token,
        scope=payload.scope,
        registration_id=reg.id,
    )


@router.post(
    "/token/refresh",
    response_model=ExtensionTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate extension refresh token and issue new access token",
)
@declare_permission(PERMISSION_PUBLIC)
async def refresh_extension_token(
    payload: ExtensionRefreshTokenRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ExtensionTokenResponse:
    """Rotate an extension refresh token.

    Issues a new access token and a new rotating refresh token.
    If a previously rotated token is reused, the entire extension registration is
    immediately revoked (replay detection per docs/07 §3).
    """
    service = ExtensionService(session)
    sys_ctx = SystemContext(reason="extension_token_refresh")

    reg, access_token, refresh_token, expires_in = await service.refresh_tokens(
        sys_ctx,
        raw_refresh_token=payload.refresh_token,
    )

    return ExtensionTokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=expires_in,
        refresh_token=refresh_token,
        scope="project:sync",
        registration_id=reg.id,
    )


@router.post(
    "/registrations/self/heartbeat",
    response_model=ExtensionHeartbeatResponse,
    status_code=status.HTTP_200_OK,
    summary="Record heartbeat for active extension installation",
)
@declare_permission(PERMISSION_AUTHENTICATED)
async def record_heartbeat(
    request: Request,
    ctx: AuthContext = Depends(get_extension_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> ExtensionHeartbeatResponse:
    """Record extension activity and verify token validity."""
    reg = getattr(request.state, "extension_registration", None)
    reg_id = reg.id if reg else ctx.user_id

    service = ExtensionService(session)
    if reg is not None:
        await service.record_heartbeat(ctx, reg.id)

    return ExtensionHeartbeatResponse(
        status="ok",
        registration_id=reg_id,
        last_seen_at=datetime.now(UTC),
    )


@router.delete(
    "/registrations/self",
    status_code=status.HTTP_200_OK,
    summary="Revoke current extension registration",
)
@declare_permission(PERMISSION_AUTHENTICATED)
async def revoke_self_registration(
    request: Request,
    ctx: AuthContext = Depends(get_extension_auth_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Revoke the current extension registration and all of its issued tokens."""
    service = ExtensionService(session)
    reg = getattr(request.state, "extension_registration", None)
    if reg is not None:
        await service.revoke_registration(ctx, reg.id)

    return {"status": "revoked"}
