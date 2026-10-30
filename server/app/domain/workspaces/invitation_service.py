"""Workspace invitation domain service implementing token issuing, email dispatch, verification, and acceptance (docs/01 FR-PLT-05, docs/03 §3.1, ADR-014)."""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.settings import get_settings
from app.domain.email.resend_client import ResendEmailClient
from app.persistence.models.workspace_invitation import WorkspaceInvitation
from app.persistence.repositories.audit_repo import AuditEventRepository
from app.persistence.repositories.user_repo import UserRepository
from app.persistence.repositories.workspace_invitation_repo import WorkspaceInvitationRepository
from app.persistence.repositories.workspace_repo import WorkspaceRepository

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ALLOWED_ROLES = {"admin", "member", "viewer"}


class WorkspaceInvitationService:
    """Domain service managing workspace invitations and onboarding."""

    def __init__(
        self,
        session: AsyncSession,
        email_client: ResendEmailClient | None = None,
    ) -> None:
        self.session = session
        self.invitation_repo = WorkspaceInvitationRepository(session)
        self.workspace_repo = WorkspaceRepository(session)
        self.user_repo = UserRepository(session)
        self.audit_repo = AuditEventRepository(session)
        self.email_client = email_client or ResendEmailClient()

    @staticmethod
    def validate_email(email: str) -> str:
        """Validate and normalize email string."""
        clean = email.strip().lower()
        if not clean or len(clean) > 255 or not EMAIL_REGEX.match(clean):
            raise ValidationError(detail=f"Invalid email address: '{email}'")
        return clean

    @staticmethod
    def validate_role(role: str) -> str:
        """Validate invited member role."""
        clean = role.strip().lower()
        if clean not in ALLOWED_ROLES:
            raise ValidationError(
                detail=f"Invalid workspace role '{role}'. Allowed roles: {', '.join(sorted(ALLOWED_ROLES))}"
            )
        return clean

    async def create_invitation(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        email: str,
        role: str = "member",
        inviter_name: str | None = None,
    ) -> tuple[WorkspaceInvitation, str, str]:
        """Create a workspace invitation, dispatch transactional email, and record audit event.

        Returns (invitation, raw_token, accept_url).
        """
        clean_email = self.validate_email(email)
        clean_role = self.validate_role(role)

        # Ensure workspace exists
        workspace = await self.workspace_repo.get_by_id(ctx, workspace_id)
        if workspace is None:
            raise NotFoundError(detail=f"Workspace '{workspace_id}' not found")

        # Check if user already exists and is already a member
        existing_user = await self.user_repo.get_by_email(clean_email)
        if existing_user is not None:
            membership = await self.workspace_repo.get_membership(
                ctx, workspace_id=workspace_id, user_id=existing_user.id
            )
            if membership is not None:
                raise ConflictError(
                    detail=f"User '{clean_email}' is already a member of workspace '{workspace.name}'"
                )

        # Check if an active invitation already exists
        existing_invite = await self.invitation_repo.get_active_by_email(
            ctx, workspace_id=workspace_id, email=clean_email
        )
        if existing_invite is not None:
            raise ConflictError(
                detail=f"An active invitation for '{clean_email}' already exists in workspace '{workspace.name}'"
            )

        # Generate cryptographically secure secret token and its SHA-256 hash (ADR-014)
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = datetime.now(UTC) + timedelta(days=7)

        inviter_id = ctx.user_id if isinstance(ctx, AuthContext) else ctx.actor_id

        # Persist invitation
        invitation = await self.invitation_repo.create_invitation(
            ctx,
            workspace_id=workspace_id,
            email=clean_email,
            role=clean_role,
            token_hash=token_hash,
            invited_by=inviter_id,
            expires_at=expires_at,
        )

        # Build accept URL
        settings = get_settings()
        accept_url = f"{settings.app_base_url.rstrip('/')}/invitations/accept?token={raw_token}"

        # Resolve sender display name
        display_inviter = inviter_name
        if not display_inviter and inviter_id:
            inviter_user = await self.user_repo.get_by_id(ctx, inviter_id)
            if inviter_user:
                display_inviter = inviter_user.name or inviter_user.email
        if not display_inviter:
            display_inviter = "A workspace administrator"

        # Dispatch email via Resend
        await self.email_client.send_workspace_invitation(
            to_email=clean_email,
            workspace_name=workspace.name,
            inviter_name=display_inviter,
            role=clean_role,
            accept_url=accept_url,
            expires_days=7,
        )

        # Record audit event (docs/03 §3.5, ADR-014)
        await self.audit_repo.record(
            ctx,
            workspace_id=workspace_id,
            action="workspace.invitation.created",
            target_kind="workspace_invitation",
            target_id=str(invitation.id),
            metadata={
                "email": clean_email,
                "role": clean_role,
                "expires_at": expires_at.isoformat(),
            },
        )

        return invitation, raw_token, accept_url

    async def list_invitations(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        *,
        pending_only: bool = True,
    ) -> list[WorkspaceInvitation]:
        """List invitations for a workspace."""
        await self.workspace_repo.get_by_id(ctx, workspace_id)
        return await self.invitation_repo.list_for_workspace(
            ctx, workspace_id, pending_only=pending_only
        )

    async def revoke_invitation(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        invitation_id: UUID,
    ) -> bool:
        """Revoke a pending workspace invitation."""
        invitation = await self.invitation_repo.get_by_id(ctx, invitation_id)
        if invitation is None or invitation.workspace_id != workspace_id:
            raise NotFoundError(detail=f"Invitation '{invitation_id}' not found")

        deleted = await self.invitation_repo.delete(ctx, invitation_id)
        if deleted:
            await self.audit_repo.record(
                ctx,
                workspace_id=workspace_id,
                action="workspace.invitation.revoked",
                target_kind="workspace_invitation",
                target_id=str(invitation_id),
                metadata={"email": invitation.email, "role": invitation.role},
            )
        return deleted

    async def verify_invitation_token(
        self,
        token: str,
    ) -> dict[str, Any]:
        """Verify invitation token and return metadata for preview screen without consuming token."""
        token = token.strip()
        if not token:
            raise ValidationError(detail="Invitation token is required")

        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        invitation = await self.invitation_repo.get_by_token_hash(token_hash)
        if invitation is None or invitation.accepted_at is not None:
            raise NotFoundError(detail="Invitation token is invalid or has already been accepted")

        now = datetime.now(UTC)
        if invitation.expires_at < now:
            raise ValidationError(detail="This workspace invitation has expired")

        system_ctx = SystemContext(
            reason="verify_invitation_token",
            workspace_id=invitation.workspace_id,
        )
        workspace = await self.workspace_repo.get_by_id(system_ctx, invitation.workspace_id)
        workspace_name = workspace.name if workspace else "DevMind Workspace"

        inviter_name = "A workspace administrator"
        if invitation.invited_by:
            inviter = await self.user_repo.get_by_id(system_ctx, invitation.invited_by)
            if inviter and (inviter.name or inviter.email):
                inviter_name = inviter.name or inviter.email

        return {
            "invitation_id": str(invitation.id),
            "workspace_id": str(invitation.workspace_id),
            "workspace_name": workspace_name,
            "email": invitation.email,
            "role": invitation.role,
            "inviter_name": inviter_name,
            "expires_at": invitation.expires_at.isoformat(),
        }

    async def accept_invitation(
        self,
        ctx: AuthContext,
        token: str,
    ) -> dict[str, Any]:
        """Accept an invitation token with authenticated user, create membership, and record audit event."""
        token = token.strip()
        if not token:
            raise ValidationError(detail="Invitation token is required")

        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        invitation = await self.invitation_repo.get_by_token_hash(token_hash)
        if invitation is None or invitation.accepted_at is not None:
            raise NotFoundError(detail="Invitation token is invalid or has already been accepted")

        now = datetime.now(UTC)
        if invitation.expires_at < now:
            raise ValidationError(detail="This workspace invitation has expired")

        user_id = ctx.user_id
        system_ctx = SystemContext(
            reason="accept_invitation",
            workspace_id=invitation.workspace_id,
            actor_id=user_id,
            actor_kind="user",
        )

        # Check if already a member
        existing_membership = await self.workspace_repo.get_membership(
            system_ctx, workspace_id=invitation.workspace_id, user_id=user_id
        )
        if existing_membership is None:
            await self.workspace_repo.add_member(
                system_ctx,
                workspace_id=invitation.workspace_id,
                user_id=user_id,
                role=invitation.role,
            )

        # Mark invitation as accepted
        await self.invitation_repo.mark_accepted(invitation)

        # Record audit event (docs/03 §3.5, ADR-014)
        await self.audit_repo.record(
            system_ctx,
            workspace_id=invitation.workspace_id,
            action="workspace.invitation.accepted",
            target_kind="workspace_invitation",
            target_id=str(invitation.id),
            actor_id=user_id,
            metadata={
                "user_id": str(user_id),
                "role": invitation.role,
                "email": invitation.email,
            },
        )

        workspace = await self.workspace_repo.get_by_id(system_ctx, invitation.workspace_id)
        workspace_name = workspace.name if workspace else "DevMind Workspace"

        return {
            "status": "accepted",
            "workspace_id": str(invitation.workspace_id),
            "workspace_name": workspace_name,
            "role": invitation.role,
            "user_id": str(user_id),
        }
