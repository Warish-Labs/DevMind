"""Clerk webhook event handler and user sync service (docs/03 §10, docs/07 §11)."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import SystemContext
from app.core.redis import get_async_redis_client
from app.core.settings import Settings, get_settings
from app.persistence.repositories.user_repo import UserRepository
from app.persistence.repositories.workspace_repo import WorkspaceRepository

logger = logging.getLogger(__name__)

_in_memory_webhook_deliveries: dict[str, float] = {}


class ClerkWebhookService:
    """Service processing verified Clerk webhook events and syncing identity."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.user_repo = UserRepository(session)
        self.workspace_repo = WorkspaceRepository(session)

    async def is_new_delivery(self, delivery_id: str, ttl_seconds: int = 600) -> bool:
        """Check delivery deduplication cache using Redis or in-memory fallback.

        Returns True if delivery is new, False if already seen (replay).
        """
        key = f"{self.settings.redis_key_prefix}webhook:dedupe:{delivery_id}"
        try:
            client = get_async_redis_client(self.settings)
            acquired = await client.set(key, "1", nx=True, ex=ttl_seconds)
            return bool(acquired)
        except Exception as exc:
            logger.debug("Redis webhook dedupe error (%s); falling back to in-memory", exc)
            now = time.time()
            if delivery_id in _in_memory_webhook_deliveries:
                if now < _in_memory_webhook_deliveries[delivery_id]:
                    return False
            _in_memory_webhook_deliveries[delivery_id] = now + ttl_seconds
            return True

    async def handle_event(self, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        """Process Clerk webhook event within a SystemContext."""
        sys_ctx = SystemContext(reason="webhook:clerk")

        match event_type:
            case "user.created":
                return await self._handle_user_created(sys_ctx, data)
            case "user.updated":
                return await self._handle_user_updated(sys_ctx, data)
            case "user.deleted":
                return await self._handle_user_deleted(sys_ctx, data)
            case _:
                logger.info("Ignoring unsupported Clerk webhook event: %s", event_type)
                return {"status": "ignored", "event_type": event_type}

    async def _handle_user_created(
        self, sys_ctx: SystemContext, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Sync created user and auto-provision default personal workspace."""
        clerk_user_id = data.get("id")
        if not clerk_user_id:
            return {"status": "error", "message": "Missing user id in payload"}

        email = self._extract_email(data)
        if not email:
            email = f"{clerk_user_id}@clerk.local"

        name = self._extract_display_name(data) or email.split("@")[0]

        # 1. Ensure user record exists
        user = await self.user_repo.get_by_clerk_user_id(sys_ctx, clerk_user_id)
        if user is None:
            user = await self.user_repo.create(
                sys_ctx,
                clerk_user_id=clerk_user_id,
                email=email,
                display_name=name,
            )

        # 2. Auto-provision personal workspace if not already present
        workspaces = await self.workspace_repo.list_for_user(sys_ctx, user.id)
        has_personal = any(ws.kind == "personal" for ws in workspaces)

        if not has_personal:
            base_slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            if len(base_slug) < 2:
                base_slug = f"user-{user.id.hex[:6]}"
            slug = f"{base_slug[:48]}-{user.id.hex[:6]}"

            ws = await self.workspace_repo.create(
                sys_ctx,
                name=f"{name}'s Workspace",
                slug=slug,
                kind="personal",
                created_by=user.id,
            )
            await self.workspace_repo.add_member(
                sys_ctx,
                workspace_id=ws.id,
                user_id=user.id,
                role="owner",
            )
            logger.info(
                "Provisioned personal workspace for user %s (%s)",
                user.id,
                ws.id,
                extra={"user_id": str(user.id), "workspace_id": str(ws.id)},
            )

        return {"status": "processed", "action": "user.created", "user_id": str(user.id)}

    async def _handle_user_updated(
        self, sys_ctx: SystemContext, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Sync updated user attributes."""
        clerk_user_id = data.get("id")
        if not clerk_user_id:
            return {"status": "error", "message": "Missing user id in payload"}

        user = await self.user_repo.get_by_clerk_user_id(sys_ctx, clerk_user_id)
        if user is None:
            # Fall back to creating if not found
            return await self._handle_user_created(sys_ctx, data)

        email = self._extract_email(data)
        name = self._extract_display_name(data)

        await self.user_repo.update(
            sys_ctx,
            user.id,
            email=email if email else None,
            display_name=name if name else None,
        )

        return {"status": "processed", "action": "user.updated", "user_id": str(user.id)}

    async def _handle_user_deleted(
        self, sys_ctx: SystemContext, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Soft-delete user record."""
        clerk_user_id = data.get("id")
        if not clerk_user_id:
            return {"status": "error", "message": "Missing user id in payload"}

        user = await self.user_repo.get_by_clerk_user_id(sys_ctx, clerk_user_id)
        if user is not None:
            await self.user_repo.soft_delete(sys_ctx, user.id)
            return {"status": "processed", "action": "user.deleted", "user_id": str(user.id)}

        return {"status": "ignored", "action": "user.deleted", "reason": "user_not_found"}

    @staticmethod
    def _extract_email(data: dict[str, Any]) -> str | None:
        """Extract primary or first email address from Clerk payload."""
        email_addresses = data.get("email_addresses", [])
        if not email_addresses:
            return None

        primary_id = data.get("primary_email_address_id")
        if primary_id:
            for item in email_addresses:
                if item.get("id") == primary_id and item.get("email_address"):
                    return str(item["email_address"])

        first = email_addresses[0].get("email_address")
        return str(first) if first else None

    @staticmethod
    def _extract_display_name(data: dict[str, Any]) -> str | None:
        """Extract user display name from Clerk payload."""
        first_name = data.get("first_name") or ""
        last_name = data.get("last_name") or ""
        full_name = f"{first_name} {last_name}".strip()
        return full_name if full_name else None
