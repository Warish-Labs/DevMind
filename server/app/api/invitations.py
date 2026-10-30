"""Invitation acceptance and verification endpoints (docs/01 FR-PLT-05, docs/03 §3.1, ADR-014)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    AcceptInvitationRequest,
    AcceptInvitationResponse,
    VerifyInvitationResponse,
)
from app.core.auth_context import AuthContext
from app.domain.auth import (
    PERMISSION_AUTHENTICATED,
    PERMISSION_PUBLIC,
    declare_permission,
    get_db_session,
    require_permission,
)
from app.domain.workspaces.invitation_service import WorkspaceInvitationService

router = APIRouter(
    prefix="/invitations",
    tags=["Invitations"],
)


@router.get(
    "/verify",
    response_model=VerifyInvitationResponse,
    summary="Verify invitation token",
    description="Verify an invitation token and return preview metadata without consuming the token.",
)
@declare_permission(PERMISSION_PUBLIC)
async def verify_invitation(
    token: str = Query(..., min_length=1, description="Raw invitation token"),
    session: AsyncSession = Depends(get_db_session),
) -> VerifyInvitationResponse:
    service = WorkspaceInvitationService(session)
    data = await service.verify_invitation_token(token)
    return VerifyInvitationResponse.model_validate(data)


@router.post(
    "/accept",
    response_model=AcceptInvitationResponse,
    summary="Accept workspace invitation",
    description="Accept an invitation token with authenticated caller and join the workspace.",
)
@declare_permission(PERMISSION_AUTHENTICATED)
async def accept_invitation(
    payload: AcceptInvitationRequest,
    ctx: AuthContext = Depends(require_permission(PERMISSION_AUTHENTICATED)),
    session: AsyncSession = Depends(get_db_session),
) -> AcceptInvitationResponse:
    service = WorkspaceInvitationService(session)
    data = await service.accept_invitation(ctx, payload.token)
    return AcceptInvitationResponse.model_validate(data)
