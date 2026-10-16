"""Webhook endpoints for external service synchronization (docs/03 §10, docs/07 §11)."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationError, ValidationError
from app.core.settings import Settings, get_settings
from app.domain.auth import PERMISSION_WEBHOOK, declare_permission, get_db_session
from app.domain.webhooks.service import ClerkWebhookService
from app.integrations.clerk_webhook import verify_svix_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post(
    "/clerk",
    status_code=status.HTTP_200_OK,
    summary="Clerk webhook receiver",
    description="Receives and verifies Clerk user lifecycle webhooks (user.created, user.updated, user.deleted).",
)
@declare_permission(PERMISSION_WEBHOOK)
async def clerk_webhook(
    request: Request,
    svix_id: str | None = Header(default=None, alias="svix-id"),
    svix_timestamp: str | None = Header(default=None, alias="svix-timestamp"),
    svix_signature: str | None = Header(default=None, alias="svix-signature"),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Verify Svix signature and process Clerk webhook."""
    # 1. Header presence validation
    if not svix_id or not svix_timestamp or not svix_signature:
        raise AuthenticationError(detail="Missing required Svix webhook headers")

    webhook_secret = settings.clerk_webhook_secret
    if not webhook_secret:
        logger.error("CLERK_WEBHOOK_SECRET is not configured on the server")
        raise AuthenticationError(detail="Webhook receiver not configured")

    # 2. Read raw request body for constant-time HMAC check
    raw_body = await request.body()

    # 3. Verify Svix HMAC signature
    is_valid = verify_svix_signature(
        secret=webhook_secret,
        svix_id=svix_id,
        svix_timestamp=svix_timestamp,
        svix_signature=svix_signature,
        body=raw_body,
    )
    if not is_valid:
        raise AuthenticationError(detail="Invalid webhook signature or expired timestamp")

    # 4. Delivery deduplication
    webhook_service = ClerkWebhookService(session=session, settings=settings)
    is_new = await webhook_service.is_new_delivery(svix_id)
    if not is_new:
        logger.info("Ignoring duplicate webhook delivery: %s", svix_id)
        return {
            "status": "ignored",
            "reason": "duplicate_delivery",
            "id": svix_id,
        }

    # 5. Parse JSON payload
    try:
        payload = json.loads(raw_body)
    except Exception as exc:
        raise ValidationError(detail=f"Malformed webhook JSON payload: {exc}") from exc

    event_type = payload.get("type", "")
    data = payload.get("data", {})

    logger.info("Processing Clerk webhook event: %s (delivery_id=%s)", event_type, svix_id)
    result = await webhook_service.handle_event(event_type, data)
    await session.commit()

    return {
        "status": "processed",
        "id": svix_id,
        "event": event_type,
        "result": result,
    }
