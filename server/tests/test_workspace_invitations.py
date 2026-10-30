"""Tests for Workspace Invitations via Resend, token verification, acceptance, and audit logs (M11-07, docs/01 FR-PLT-05, docs/03 §3.1, ADR-014)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from starlette.testclient import TestClient

from app.core.auth_context import AuthContext
from app.core.errors import ConflictError, ValidationError
from app.core.ids import generate_uuid7
from app.domain.auth import (
    PERM_MEMBERS_MANAGE_WORKSPACE,
    PERM_WORKSPACE_READ,
    get_auth_context,
    get_db_session,
)
from app.domain.email.resend_client import ResendEmailClient
from app.domain.workspaces.invitation_service import WorkspaceInvitationService
from app.main import create_app
from app.persistence.models.workspace import Workspace, WorkspaceMembership
from app.persistence.models.workspace_invitation import WorkspaceInvitation


def _make_auth_ctx(
    workspace_id: UUID | None = None,
    user_id: UUID | None = None,
    role: str = "admin",
    permissions: frozenset[str] | None = None,
) -> AuthContext:
    perms = (
        permissions
        if permissions is not None
        else frozenset({PERM_WORKSPACE_READ, PERM_MEMBERS_MANAGE_WORKSPACE})
    )
    return AuthContext(
        user_id=user_id or generate_uuid7(),
        clerk_user_id="user_clerk_invite_test",
        email="admin@example.com",
        workspace_id=workspace_id or generate_uuid7(),
        workspace_role=role,
        permissions=perms,
    )


@pytest.mark.asyncio
async def test_resend_client_mock_dispatch() -> None:
    """When DEVMIND_RESEND_API_KEY is not configured or placeholder, mock delivery is simulated."""
    client = ResendEmailClient(api_key="re_REPLACE_ME")
    result = await client.send_workspace_invitation(
        to_email="dev@example.com",
        workspace_name="Acme Corp",
        inviter_name="Alice Admin",
        role="member",
        accept_url="https://devmind.warishlabs.in/invitations/accept?token=sample",
    )
    assert result["status"] == "simulated"
    assert result["id"].startswith("mock-msg-")


@pytest.mark.asyncio
async def test_invitation_service_lifecycle() -> None:
    """Service handles full lifecycle: create, verify, accept, and audit event recording."""
    session = AsyncMock()
    ws_id = generate_uuid7()
    user_id = generate_uuid7()
    invitee_id = generate_uuid7()

    ctx = _make_auth_ctx(workspace_id=ws_id, user_id=user_id)

    email_client = ResendEmailClient(api_key="re_REPLACE_ME")
    service = WorkspaceInvitationService(session, email_client=email_client)

    # Mock DB models
    mock_workspace = Workspace(id=ws_id, name="Test Space", slug="test-space", kind="team")
    service.workspace_repo.get_by_id = AsyncMock(return_value=mock_workspace)
    service.user_repo.get_by_email = AsyncMock(return_value=None)
    service.user_repo.get_by_id = AsyncMock(return_value=None)
    service.invitation_repo.get_active_by_email = AsyncMock(return_value=None)
    service.audit_repo.record = AsyncMock()

    now = datetime.now(UTC)
    invitation_id = generate_uuid7()

    def fake_create(ctx, *, workspace_id, email, role, token_hash, invited_by, expires_at):
        return WorkspaceInvitation(
            id=invitation_id,
            workspace_id=workspace_id,
            email=email,
            role=role,
            token_hash=token_hash,
            invited_by=invited_by,
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
        )

    service.invitation_repo.create_invitation = AsyncMock(side_effect=fake_create)

    # 1. Create invitation
    invitation, raw_token, accept_url = await service.create_invitation(
        ctx,
        workspace_id=ws_id,
        email="newuser@example.com",
        role="member",
    )

    assert invitation.email == "newuser@example.com"
    assert invitation.role == "member"
    assert raw_token in accept_url
    expected_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    assert invitation.token_hash == expected_hash

    # Verify audit event for creation
    service.audit_repo.record.assert_awaited()
    last_call = service.audit_repo.record.call_args[1]
    assert last_call["action"] == "workspace.invitation.created"
    assert last_call["target_kind"] == "workspace_invitation"
    assert last_call["metadata"]["email"] == "newuser@example.com"

    # 2. Verify invitation preview
    service.invitation_repo.get_by_token_hash = AsyncMock(return_value=invitation)
    preview = await service.verify_invitation_token(raw_token)
    assert preview["workspace_name"] == "Test Space"
    assert preview["email"] == "newuser@example.com"
    assert preview["role"] == "member"

    # 3. Accept invitation
    service.workspace_repo.get_membership = AsyncMock(return_value=None)
    service.workspace_repo.add_member = AsyncMock()
    service.invitation_repo.mark_accepted = AsyncMock(return_value=invitation)

    accept_ctx = _make_auth_ctx(user_id=invitee_id)
    accept_res = await service.accept_invitation(accept_ctx, raw_token)

    assert accept_res["status"] == "accepted"
    assert accept_res["role"] == "member"
    service.workspace_repo.add_member.assert_awaited()
    service.invitation_repo.mark_accepted.assert_awaited_with(invitation)

    # Verify audit event for acceptance
    accept_call = service.audit_repo.record.call_args[1]
    assert accept_call["action"] == "workspace.invitation.accepted"
    assert accept_call["metadata"]["user_id"] == str(invitee_id)


@pytest.mark.asyncio
async def test_invitation_service_conflict_existing_member() -> None:
    """Cannot invite an existing workspace member."""
    session = AsyncMock()
    ws_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=ws_id)
    service = WorkspaceInvitationService(session)

    mock_workspace = Workspace(id=ws_id, name="Test Space", slug="test-space", kind="team")
    service.workspace_repo.get_by_id = AsyncMock(return_value=mock_workspace)

    existing_user = MagicMock(id=generate_uuid7())
    service.user_repo.get_by_email = AsyncMock(return_value=existing_user)
    service.workspace_repo.get_membership = AsyncMock(
        return_value=WorkspaceMembership(workspace_id=ws_id, user_id=existing_user.id, role="member")
    )

    with pytest.raises(ConflictError, match="already a member"):
        await service.create_invitation(
            ctx,
            workspace_id=ws_id,
            email="existing@example.com",
            role="member",
        )


@pytest.mark.asyncio
async def test_invitation_service_conflict_active_invite() -> None:
    """Cannot issue duplicate pending invite for the same email."""
    session = AsyncMock()
    ws_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=ws_id)
    service = WorkspaceInvitationService(session)

    mock_workspace = Workspace(id=ws_id, name="Test Space", slug="test-space", kind="team")
    service.workspace_repo.get_by_id = AsyncMock(return_value=mock_workspace)
    service.user_repo.get_by_email = AsyncMock(return_value=None)
    service.invitation_repo.get_active_by_email = AsyncMock(
        return_value=WorkspaceInvitation(id=generate_uuid7(), workspace_id=ws_id, email="pending@example.com")
    )

    with pytest.raises(ConflictError, match="active invitation"):
        await service.create_invitation(
            ctx,
            workspace_id=ws_id,
            email="pending@example.com",
            role="member",
        )


@pytest.mark.asyncio
async def test_invitation_expired_token_rejected() -> None:
    """Expired tokens are rejected on verify and accept."""
    session = AsyncMock()
    ws_id = generate_uuid7()
    service = WorkspaceInvitationService(session)

    expired_invite = WorkspaceInvitation(
        id=generate_uuid7(),
        workspace_id=ws_id,
        email="expired@example.com",
        role="member",
        token_hash="dummy_hash",
        expires_at=datetime.now(UTC) - timedelta(days=1),
        accepted_at=None,
    )
    service.invitation_repo.get_by_token_hash = AsyncMock(return_value=expired_invite)

    with pytest.raises(ValidationError, match="expired"):
        await service.verify_invitation_token("dummy_token")

    accept_ctx = _make_auth_ctx()
    with pytest.raises(ValidationError, match="expired"):
        await service.accept_invitation(accept_ctx, "dummy_token")


def test_api_list_and_create_workspace_invitations() -> None:
    """Admin can list and create invitations via REST API."""
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    ws_id = generate_uuid7()
    admin_ctx = _make_auth_ctx(workspace_id=ws_id, role="admin")
    app.dependency_overrides[get_auth_context] = lambda: admin_ctx

    client = TestClient(app)

    now = datetime.now(UTC)
    mock_invitation = WorkspaceInvitation(
        id=generate_uuid7(),
        workspace_id=ws_id,
        email="invited@example.com",
        role="viewer",
        token_hash="somehash",
        invited_by=admin_ctx.user_id,
        expires_at=now + timedelta(days=7),
        accepted_at=None,
        created_at=now,
        updated_at=now,
    )

    with patch.object(
        WorkspaceInvitationService, "list_invitations", new_callable=AsyncMock
    ) as mock_list, patch.object(
        WorkspaceInvitationService, "create_invitation", new_callable=AsyncMock
    ) as mock_create:
        mock_list.return_value = [mock_invitation]
        mock_create.return_value = (
            mock_invitation,
            "raw-secret-token",
            "https://devmind.warishlabs.in/invitations/accept?token=raw-secret-token",
        )

        # GET /api/v1/workspaces/{ws_id}/invitations
        res_list = client.get(f"/api/v1/workspaces/{ws_id}/invitations")
        assert res_list.status_code == 200
        invs = res_list.json()
        assert len(invs) == 1
        assert invs[0]["email"] == "invited@example.com"
        assert invs[0]["role"] == "viewer"

        # POST /api/v1/workspaces/{ws_id}/invitations
        res_create = client.post(
            f"/api/v1/workspaces/{ws_id}/invitations",
            json={"email": "invited@example.com", "role": "viewer"},
        )
        assert res_create.status_code == 201
        created_data = res_create.json()
        assert created_data["invitation"]["email"] == "invited@example.com"
        assert "accept_url" in created_data


def test_api_revoke_workspace_invitation() -> None:
    """Admin can revoke an invitation via DELETE endpoint."""
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    ws_id = generate_uuid7()
    inv_id = generate_uuid7()
    admin_ctx = _make_auth_ctx(workspace_id=ws_id, role="admin")
    app.dependency_overrides[get_auth_context] = lambda: admin_ctx

    client = TestClient(app)

    with patch.object(
        WorkspaceInvitationService, "revoke_invitation", new_callable=AsyncMock
    ) as mock_revoke:
        mock_revoke.return_value = True

        res = client.delete(f"/api/v1/workspaces/{ws_id}/invitations/{inv_id}")
        assert res.status_code == 204
        mock_revoke.assert_awaited_once()


def test_api_viewer_cannot_create_or_revoke_invitation() -> None:
    """Viewer role lacks members:manage_workspace permission and is rejected with 403."""
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    ws_id = generate_uuid7()
    inv_id = generate_uuid7()
    # Viewer only has PERM_WORKSPACE_READ
    viewer_ctx = _make_auth_ctx(
        workspace_id=ws_id, role="viewer", permissions=frozenset({PERM_WORKSPACE_READ})
    )
    app.dependency_overrides[get_auth_context] = lambda: viewer_ctx

    client = TestClient(app)

    res_post = client.post(
        f"/api/v1/workspaces/{ws_id}/invitations",
        json={"email": "new@example.com", "role": "member"},
    )
    assert res_post.status_code == 403
    problem_post = res_post.json()
    assert problem_post["code"] == "auth.forbidden"

    res_del = client.delete(f"/api/v1/workspaces/{ws_id}/invitations/{inv_id}")
    assert res_del.status_code == 403
    problem_del = res_del.json()
    assert problem_del["code"] == "auth.forbidden"


def test_api_invitations_verify_and_accept() -> None:
    """Public verify returns preview metadata; authenticated accept adds member."""
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    client = TestClient(app)
    ws_id = generate_uuid7()
    user_id = generate_uuid7()

    with patch.object(
        WorkspaceInvitationService, "verify_invitation_token", new_callable=AsyncMock
    ) as mock_verify, patch.object(
        WorkspaceInvitationService, "accept_invitation", new_callable=AsyncMock
    ) as mock_accept:
        mock_verify.return_value = {
            "invitation_id": str(generate_uuid7()),
            "workspace_id": str(ws_id),
            "workspace_name": "Acme Corp",
            "email": "joiner@example.com",
            "role": "member",
            "inviter_name": "Alice Admin",
            "expires_at": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
        }
        mock_accept.return_value = {
            "status": "accepted",
            "workspace_id": str(ws_id),
            "workspace_name": "Acme Corp",
            "role": "member",
            "user_id": str(user_id),
        }

        # Verify endpoint (public)
        res_verify = client.get("/api/v1/invitations/verify?token=sample-token-123")
        assert res_verify.status_code == 200
        preview = res_verify.json()
        assert preview["workspace_name"] == "Acme Corp"
        assert preview["email"] == "joiner@example.com"

        # Accept endpoint (authenticated)
        auth_ctx = _make_auth_ctx(user_id=user_id)
        app.dependency_overrides[get_auth_context] = lambda: auth_ctx

        res_accept = client.post(
            "/api/v1/invitations/accept",
            json={"token": "sample-token-123"},
        )
        assert res_accept.status_code == 200
        accepted_data = res_accept.json()
        assert accepted_data["status"] == "accepted"
        assert accepted_data["workspace_name"] == "Acme Corp"
