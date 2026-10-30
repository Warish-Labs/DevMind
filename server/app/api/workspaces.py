"""Workspace REST endpoints (docs/03 §11.1)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    AddWorkspaceMemberRequest,
    CreateInvitationRequest,
    CreateInvitationResponse,
    CreateWorkspaceRequest,
    UpdateWorkspaceMemberRequest,
    UpdateWorkspaceRequest,
    WorkspaceInvitationResponse,
    WorkspaceMemberResponse,
    WorkspaceResponse,
)
from app.core.auth_context import AuthContext
from app.domain.auth import (
    PERM_MEMBERS_MANAGE_WORKSPACE,
    PERM_WORKSPACE_MANAGE,
    PERM_WORKSPACE_READ,
    PERMISSION_AUTHENTICATED,
    declare_permission,
    get_auth_context,
    get_db_session,
    require_permission,
)
from app.domain.workspaces.invitation_service import WorkspaceInvitationService
from app.domain.workspaces.service import WorkspaceService

router = APIRouter(
    prefix="/workspaces",
    tags=["Workspaces"],
    dependencies=[Depends(get_auth_context)],
)


@router.get(
    "",
    response_model=list[WorkspaceResponse],
    summary="List user workspaces",
    description="List all active workspaces accessible to the authenticated caller.",
)
@declare_permission(PERMISSION_AUTHENTICATED)
async def list_workspaces(
    ctx: AuthContext = Depends(require_permission(PERMISSION_AUTHENTICATED)),
    session: AsyncSession = Depends(get_db_session),
) -> list[WorkspaceResponse]:
    service = WorkspaceService(session)
    workspaces = await service.list_user_workspaces(ctx, ctx.user_id)
    return [WorkspaceResponse.model_validate(ws) for ws in workspaces]


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create workspace",
    description="Create a new workspace and assign the authenticated caller as owner.",
)
@declare_permission(PERMISSION_AUTHENTICATED)
async def create_workspace(
    payload: CreateWorkspaceRequest,
    ctx: AuthContext = Depends(require_permission(PERMISSION_AUTHENTICATED)),
    session: AsyncSession = Depends(get_db_session),
) -> WorkspaceResponse:
    service = WorkspaceService(session)
    ws = await service.create_workspace(
        ctx,
        name=payload.name,
        slug=payload.slug,
        kind=payload.kind,
    )
    return WorkspaceResponse.model_validate(ws)


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Get workspace",
    description="Retrieve workspace details by identifier.",
)
@declare_permission(PERM_WORKSPACE_READ)
async def get_workspace(
    workspace_id: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_WORKSPACE_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> WorkspaceResponse:
    service = WorkspaceService(session)
    ws = await service.get_workspace(ctx, workspace_id)
    return WorkspaceResponse.model_validate(ws)


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Update workspace",
    description="Update mutable workspace attributes (name, slug, kind). Requires admin or owner role.",
)
@declare_permission(PERM_WORKSPACE_MANAGE)
async def update_workspace(
    workspace_id: UUID,
    payload: UpdateWorkspaceRequest,
    ctx: AuthContext = Depends(require_permission(PERM_WORKSPACE_MANAGE)),
    session: AsyncSession = Depends(get_db_session),
) -> WorkspaceResponse:
    service = WorkspaceService(session)
    ws = await service.update_workspace(
        ctx,
        workspace_id,
        name=payload.name,
        slug=payload.slug,
        kind=payload.kind,
    )
    return WorkspaceResponse.model_validate(ws)


@router.get(
    "/{workspace_id}/members",
    response_model=list[WorkspaceMemberResponse],
    summary="List workspace members",
    description="List all members belonging to the specified workspace.",
)
@declare_permission(PERM_WORKSPACE_READ)
async def list_workspace_members(
    workspace_id: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_WORKSPACE_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> list[WorkspaceMemberResponse]:
    service = WorkspaceService(session)
    memberships = await service.list_members(ctx, workspace_id)
    return [WorkspaceMemberResponse.model_validate(m) for m in memberships]


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add workspace member",
    description="Add a user as a member to the workspace with specified role.",
)
@declare_permission(PERM_MEMBERS_MANAGE_WORKSPACE)
async def add_workspace_member(
    workspace_id: UUID,
    payload: AddWorkspaceMemberRequest,
    ctx: AuthContext = Depends(require_permission(PERM_MEMBERS_MANAGE_WORKSPACE)),
    session: AsyncSession = Depends(get_db_session),
) -> WorkspaceMemberResponse:
    service = WorkspaceService(session)
    membership = await service.add_member(
        ctx,
        workspace_id=workspace_id,
        user_id=payload.user_id,
        role=payload.role,
    )
    return WorkspaceMemberResponse.model_validate(membership)


@router.patch(
    "/{workspace_id}/members/{user_id}",
    response_model=WorkspaceMemberResponse,
    summary="Update workspace member role",
    description="Update the role of an existing workspace member.",
)
@declare_permission(PERM_MEMBERS_MANAGE_WORKSPACE)
async def update_workspace_member(
    workspace_id: UUID,
    user_id: UUID,
    payload: UpdateWorkspaceMemberRequest,
    ctx: AuthContext = Depends(require_permission(PERM_MEMBERS_MANAGE_WORKSPACE)),
    session: AsyncSession = Depends(get_db_session),
) -> WorkspaceMemberResponse:
    service = WorkspaceService(session)
    membership = await service.update_member_role(
        ctx,
        workspace_id=workspace_id,
        user_id=user_id,
        role=payload.role,
    )
    return WorkspaceMemberResponse.model_validate(membership)


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove workspace member",
    description="Remove a member from the workspace.",
)
@declare_permission(PERM_MEMBERS_MANAGE_WORKSPACE)
async def remove_workspace_member(
    workspace_id: UUID,
    user_id: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_MEMBERS_MANAGE_WORKSPACE)),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    service = WorkspaceService(session)
    await service.remove_member(ctx, workspace_id=workspace_id, user_id=user_id)


# Workspace Invitations (FR-PLT-05, ADR-014)


@router.get(
    "/{workspace_id}/invitations",
    response_model=list[WorkspaceInvitationResponse],
    summary="List workspace invitations",
    description="List active/pending invitations for the specified workspace.",
)
@declare_permission(PERM_WORKSPACE_READ)
async def list_workspace_invitations(
    workspace_id: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_WORKSPACE_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> list[WorkspaceInvitationResponse]:
    service = WorkspaceInvitationService(session)
    invitations = await service.list_invitations(ctx, workspace_id)
    return [WorkspaceInvitationResponse.model_validate(inv) for inv in invitations]


@router.post(
    "/{workspace_id}/invitations",
    response_model=CreateInvitationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create workspace invitation",
    description="Issue an invitation to join the workspace and send email notification via Resend.",
)
@declare_permission(PERM_MEMBERS_MANAGE_WORKSPACE)
async def create_workspace_invitation(
    workspace_id: UUID,
    payload: CreateInvitationRequest,
    ctx: AuthContext = Depends(require_permission(PERM_MEMBERS_MANAGE_WORKSPACE)),
    session: AsyncSession = Depends(get_db_session),
) -> CreateInvitationResponse:
    service = WorkspaceInvitationService(session)
    invitation, _raw_token, accept_url = await service.create_invitation(
        ctx,
        workspace_id=workspace_id,
        email=payload.email,
        role=payload.role,
    )
    return CreateInvitationResponse(
        invitation=WorkspaceInvitationResponse.model_validate(invitation),
        accept_url=accept_url,
    )


@router.delete(
    "/{workspace_id}/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke workspace invitation",
    description="Revoke a pending workspace invitation.",
)
@declare_permission(PERM_MEMBERS_MANAGE_WORKSPACE)
async def revoke_workspace_invitation(
    workspace_id: UUID,
    invitation_id: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_MEMBERS_MANAGE_WORKSPACE)),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    service = WorkspaceInvitationService(session)
    await service.revoke_invitation(
        ctx,
        workspace_id=workspace_id,
        invitation_id=invitation_id,
    )
