"""Current caller identity and permissions endpoints (docs/03 §11.1)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import UserPermissionsResponse, UserProfileResponse
from app.core.auth_context import AuthContext
from app.domain.auth import (
    PERMISSION_AUTHENTICATED,
    declare_permission,
    get_auth_context,
    get_db_session,
    require_permission,
)
from app.domain.users.service import UserService

router = APIRouter(
    prefix="/me",
    tags=["Identity"],
    dependencies=[Depends(get_auth_context)],
)


@router.get(
    "",
    response_model=UserProfileResponse,
    summary="Get current user profile",
    description="Retrieve the profile of the currently authenticated user.",
)
@declare_permission(PERMISSION_AUTHENTICATED)
async def get_my_profile(
    ctx: AuthContext = Depends(require_permission(PERMISSION_AUTHENTICATED)),
    session: AsyncSession = Depends(get_db_session),
) -> UserProfileResponse:
    service = UserService(session)
    user = await service.get_user_by_id(ctx, ctx.user_id)
    return UserProfileResponse.model_validate(user)


@router.get(
    "/permissions",
    response_model=UserPermissionsResponse,
    summary="Get current permissions",
    description="Retrieve effective caller permissions for the active workspace and optional project.",
)
@declare_permission(PERMISSION_AUTHENTICATED)
async def get_my_permissions(
    project_id: UUID | None = Query(
        default=None, description="Optional project ID to check effective project permissions"
    ),
    ctx: AuthContext = Depends(require_permission(PERMISSION_AUTHENTICATED)),
) -> UserPermissionsResponse:
    return UserPermissionsResponse(
        user_id=ctx.user_id,
        workspace_id=ctx.workspace_id,
        workspace_role=ctx.workspace_role,
        project_id=ctx.project_id or project_id,
        project_role=ctx.project_role,
        permissions=sorted(list(ctx.permissions)),
    )
