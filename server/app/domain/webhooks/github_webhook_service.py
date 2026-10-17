"""Domain service for GitHub webhook signature verification and event handling (docs/03 §10, docs/07 §11)."""

from __future__ import annotations

import hashlib
import hmac
import logging
from collections import OrderedDict
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationError
from app.core.settings import Settings, get_settings

logger = logging.getLogger(__name__)

# Bounded in-memory LRU cache for delivery deduplication
_recent_deliveries: OrderedDict[str, float] = OrderedDict()
MAX_DELIVERY_CACHE_SIZE = 5000


class GitHubWebhookService:
    """Verifies GitHub HMAC signatures and dispatches webhook events."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    def verify_signature(self, signature_header: str | None, raw_body: bytes) -> bool:
        """Verify GitHub HMAC-SHA256 signature from X-Hub-Signature-256 header."""
        secret = self.settings.github_webhook_secret
        if not secret:
            logger.error("DEVMIND_GITHUB_WEBHOOK_SECRET is not configured on the server")
            raise AuthenticationError(detail="GitHub webhook receiver is not configured")

        if not signature_header or not signature_header.startswith("sha256="):
            return False

        received_sig = signature_header[7:].strip()
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(received_sig, expected_sig)

    def is_new_delivery(self, delivery_id: str) -> bool:
        """Check if X-GitHub-Delivery ID has already been processed to prevent duplicates."""
        if not delivery_id:
            return True

        if delivery_id in _recent_deliveries:
            return False

        _recent_deliveries[delivery_id] = 1.0
        if len(_recent_deliveries) > MAX_DELIVERY_CACHE_SIZE:
            _recent_deliveries.popitem(last=False)

        return True

    async def handle_event(
        self,
        event_type: str,
        delivery_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Process verified GitHub webhook event."""
        logger.info(
            "Processing GitHub webhook event (event=%s, delivery_id=%s)",
            event_type,
            delivery_id,
        )

        match event_type:
            case "ping":
                zen = payload.get("zen", "")
                hook_id = payload.get("hook_id")
                return {"status": "pong", "zen": zen, "hook_id": hook_id}

            case "pull_request":
                action = payload.get("action")
                pr = payload.get("pull_request", {})
                pr_number = pr.get("number")
                repo = payload.get("repository", {}).get("full_name")
                logger.info(
                    "GitHub PR event received: %s #%s on %s",
                    action,
                    pr_number,
                    repo,
                )
                return {
                    "status": "received",
                    "event": "pull_request",
                    "action": action,
                    "number": pr_number,
                    "repo": repo,
                }

            case "push":
                ref = payload.get("ref")
                repo = payload.get("repository", {}).get("full_name")
                commits = len(payload.get("commits", []))
                logger.info("GitHub push event received on %s (%s, %d commits)", repo, ref, commits)
                return {
                    "status": "received",
                    "event": "push",
                    "ref": ref,
                    "repo": repo,
                    "commits": commits,
                }

            case _:
                logger.info("Ignoring unhandled GitHub event type: %s", event_type)
                return {
                    "status": "ignored",
                    "event": event_type,
                    "reason": "unhandled_event_type",
                }
