"""Cloudflare Turnstile verification service and helper functions (docs/07 §11).

Implements server-side verification using Cloudflare's official Siteverify API
(https://challenges.cloudflare.com/turnstile/v0/siteverify).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.errors import TurnstileError
from app.core.settings import Settings, get_settings

logger = logging.getLogger(__name__)

# Cloudflare official dummy test keys
CLOUDFLARE_TEST_SECRET_PASS = "1x0000000000000000000000000000000AA"
CLOUDFLARE_TEST_SECRET_FAIL = "2x0000000000000000000000000000000AA"
CLOUDFLARE_TEST_SECRET_DUPLICATE = "3x0000000000000000000000000000000AA"


class TurnstileVerifier:
    """Verifies Turnstile response tokens against Cloudflare Siteverify API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def verify(
        self,
        token: str | None,
        remote_ip: str | None = None,
        idempotency_key: str | None = None,
    ) -> bool:
        """Verify a Turnstile token submitted by a client.

        Raises TurnstileError on validation failure, invalid token, expiry,
        or upstream timeout/service failure (fail-closed security).
        """
        if not token or not token.strip():
            logger.warning("Turnstile verification failed: missing token")
            raise TurnstileError(
                detail="Turnstile challenge token is required",
                code="turnstile.missing_token",
                status_code=400,
                title="Missing Turnstile Token",
            )

        secret_key = self.settings.turnstile_secret_key
        if not secret_key:
            # In local/test environments, default to Cloudflare's dummy test secret if unset
            if self.settings.env in ("local", "test"):
                secret_key = CLOUDFLARE_TEST_SECRET_PASS
            else:
                logger.error(
                    "Turnstile secret key is not configured in %s environment", self.settings.env
                )
                raise TurnstileError(
                    detail="Turnstile verification is not configured on the server",
                    code="turnstile.not_configured",
                    status_code=500,
                    title="Configuration Error",
                )

        payload: dict[str, Any] = {
            "secret": secret_key,
            "response": token.strip(),
        }
        if remote_ip:
            payload["remoteip"] = remote_ip
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key

        try:
            async with httpx.AsyncClient(timeout=self.settings.turnstile_timeout_seconds) as client:
                response = await client.post(
                    self.settings.turnstile_verify_url,
                    data=payload,
                )

                if response.status_code >= 500:
                    logger.error(
                        "Cloudflare Turnstile upstream server error: HTTP %d", response.status_code
                    )
                    raise TurnstileError(
                        detail="Upstream Turnstile verification service failed",
                        code="turnstile.upstream_error",
                        status_code=502,
                        title="Bad Gateway",
                    )

                data = response.json()
        except httpx.TimeoutException as exc:
            logger.warning("Cloudflare Turnstile verification timed out: %s", exc)
            raise TurnstileError(
                detail="Turnstile verification timed out",
                code="turnstile.timeout",
                status_code=504,
                title="Gateway Timeout",
            ) from exc
        except httpx.HTTPError as exc:
            logger.error("Cloudflare Turnstile connection error: %s", exc)
            raise TurnstileError(
                detail="Failed to connect to Turnstile verification service",
                code="turnstile.connection_error",
                status_code=502,
                title="Bad Gateway",
            ) from exc

        success = bool(data.get("success", False))
        if not success:
            error_codes = data.get("error-codes", [])
            logger.warning("Cloudflare Turnstile challenge unsuccessful: %s", error_codes)
            if "timeout-or-duplicate" in error_codes:
                raise TurnstileError(
                    detail="Turnstile token expired or already used",
                    code="turnstile.duplicate_or_expired",
                    status_code=403,
                    title="Turnstile Token Expired",
                    errors=[{"error_codes": error_codes}],
                )
            raise TurnstileError(
                detail="Turnstile verification failed",
                code="turnstile.invalid_token",
                status_code=403,
                title="Turnstile Verification Failed",
                errors=[{"error_codes": error_codes}] if error_codes else None,
            )

        logger.debug("Cloudflare Turnstile challenge passed (hostname=%s)", data.get("hostname"))
        return True


async def verify_turnstile_token(
    token: str | None,
    remote_ip: str | None = None,
    idempotency_key: str | None = None,
    settings: Settings | None = None,
) -> bool:
    """Convenience helper to verify a Turnstile token."""
    verifier = TurnstileVerifier(settings=settings)
    return await verifier.verify(
        token=token,
        remote_ip=remote_ip,
        idempotency_key=idempotency_key,
    )
