"""Domain service for GitHub OAuth authorization, state verification, and token exchange (docs/03 §11.1).

Enforces:
- Rule 5: Tokens encrypted at rest using AES-256-GCM; never logged.
- Tamper-proof HMAC state validation with 10-minute expiry to prevent CSRF.
- Open-redirect prevention: destination URLs validated against strict origin allowlist.
- Identity binding: tokens associated exclusively with authenticated DevMind user.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Any
from urllib.parse import urlencode, urlparse
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.crypto import EncryptionService
from app.core.errors import AuthenticationError, ValidationError
from app.core.settings import Settings, get_settings
from app.persistence.models.github import GitHubConnection
from app.persistence.repositories.github_repo import GitHubRepository

logger = logging.getLogger(__name__)

GITHUB_OAUTH_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_OAUTH_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_API_URL = "https://api.github.com/user"
STATE_TTL_SECONDS = 600  # 10 minutes


class GitHubOAuthService:
    """Handles GitHub OAuth flows with secure state validation and token management."""

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.repo = GitHubRepository(session)
        self.crypto = EncryptionService(self.settings)

    def _get_signing_secret(self) -> bytes:
        """Derive signing key for OAuth state."""
        if self.settings.github_client_secret:
            return self.settings.github_client_secret.encode("utf-8")
        # Fallback to fixed key in dev/test
        return b"devmind_default_github_oauth_state_signing_key_secret!"

    def validate_return_url(self, return_to: str | None) -> str:
        """Validate destination against allowed frontend origins to prevent open redirects."""
        default_return = (
            "https://devmind.warishlabs.in/settings/integrations"
            if self.settings.is_production
            else "http://localhost:3000/settings/integrations"
        )
        if not return_to:
            return default_return

        try:
            parsed = urlparse(return_to)
            origin = f"{parsed.scheme}://{parsed.netloc}"

            # Canonical allowed origins
            allowed_origins = {
                "https://devmind.warishlabs.in",
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            }
            # Extend from CORS settings if configured
            if isinstance(self.settings.cors_origins, list):
                allowed_origins.update(self.settings.cors_origins)
            elif isinstance(self.settings.cors_origins, str):
                allowed_origins.update([o.strip() for o in self.settings.cors_origins.split(",")])

            if origin in allowed_origins:
                return return_to
        except Exception:
            pass

        logger.warning(
            "Untrusted return_to URL '%s'; falling back to default '%s'", return_to, default_return
        )
        return default_return

    def generate_state(
        self,
        user_id: UUID,
        workspace_id: UUID,
        return_to: str | None = None,
    ) -> str:
        """Generate a signed, tamper-proof, time-bound OAuth state token."""
        safe_return = self.validate_return_url(return_to)
        payload = {
            "uid": str(user_id),
            "wid": str(workspace_id),
            "ret": safe_return,
            "ts": int(time.time()),
            "nonce": secrets.token_hex(16),
        }
        raw_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        payload_b64 = base64.urlsafe_b64encode(raw_json).decode("ascii")

        sig = hmac.new(
            self._get_signing_secret(), payload_b64.encode("ascii"), hashlib.sha256
        ).hexdigest()
        return f"{payload_b64}.{sig}"

    def verify_state(self, state: str) -> dict[str, Any]:
        """Verify HMAC signature and TTL of OAuth state token."""
        if not state or "." not in state:
            raise AuthenticationError(detail="Malformed or missing OAuth state parameter")

        payload_b64, sig = state.split(".", 1)
        expected_sig = hmac.new(
            self._get_signing_secret(), payload_b64.encode("ascii"), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(sig, expected_sig):
            logger.warning("GitHub OAuth state signature mismatch (possible CSRF attempt)")
            raise AuthenticationError(detail="Invalid OAuth state signature")

        try:
            raw_json = base64.urlsafe_b64decode(payload_b64.encode("ascii"))
            data: dict[str, Any] = json.loads(raw_json.decode("utf-8"))
        except Exception as exc:
            raise AuthenticationError(detail="Corrupted OAuth state payload") from exc

        ts = int(data.get("ts", 0))
        if time.time() - ts > STATE_TTL_SECONDS:
            logger.warning("GitHub OAuth state expired (age=%ds)", int(time.time() - ts))
            raise AuthenticationError(
                detail="OAuth state expired. Please re-initiate authorization."
            )

        return data

    def build_authorization_url(
        self,
        ctx: AuthContext,
        workspace_id: UUID,
        callback_url: str,
        return_to: str | None = None,
    ) -> str:
        """Build GitHub OAuth authorization redirect URL."""
        if not self.settings.github_client_id:
            logger.error("DEVMIND_GITHUB_CLIENT_ID is not configured")
            raise ValidationError(detail="GitHub integration is not configured on the server")

        state = self.generate_state(
            user_id=ctx.user_id,
            workspace_id=workspace_id,
            return_to=return_to,
        )

        params = {
            "client_id": self.settings.github_client_id,
            "redirect_uri": callback_url,
            "scope": "read:user user:email repo",
            "state": state,
        }
        return f"{GITHUB_OAUTH_AUTHORIZE_URL}?{urlencode(params)}"

    async def handle_callback(
        self,
        code: str,
        state: str,
        callback_url: str,
    ) -> tuple[str, GitHubConnection]:
        """Process GitHub OAuth callback, exchange token, encrypt at rest, and persist."""
        state_data = self.verify_state(state)
        user_id = UUID(state_data["uid"])
        workspace_id = UUID(state_data["wid"])
        return_to = state_data.get("ret", "https://devmind.warishlabs.in")

        if not self.settings.github_client_id or not self.settings.github_client_secret:
            raise ValidationError(detail="GitHub OAuth credentials not configured")

        # 1. Exchange code for access token with GitHub
        token_payload = {
            "client_id": self.settings.github_client_id,
            "client_secret": self.settings.github_client_secret,
            "code": code,
            "redirect_uri": callback_url,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            token_resp = await client.post(
                GITHUB_OAUTH_TOKEN_URL,
                data=token_payload,
                headers={"Accept": "application/json"},
            )

            if token_resp.status_code != 200:
                logger.error("GitHub token exchange returned HTTP %d", token_resp.status_code)
                raise ValidationError(detail="Failed to exchange authorization code with GitHub")

            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                error_msg = token_data.get(
                    "error_description", token_data.get("error", "Unknown error")
                )
                logger.error("GitHub OAuth token exchange failed: %s", error_msg)
                raise ValidationError(detail=f"GitHub authorization rejected: {error_msg}")

            raw_scope = token_data.get("scope", "")
            scopes = [s.strip() for s in raw_scope.split(",") if s.strip()]

            # 2. Fetch authenticated GitHub user details
            user_resp = await client.get(
                GITHUB_USER_API_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "DevMind-Server",
                },
            )
            if user_resp.status_code != 200:
                logger.error("GitHub /user API returned HTTP %d", user_resp.status_code)
                raise ValidationError(detail="Failed to retrieve GitHub user profile")

            user_data = user_resp.json()
            external_account = user_data.get("login")
            if not external_account:
                raise ValidationError(detail="Invalid GitHub user profile: missing login")

        # 3. Encrypt access token at rest using AES-256-GCM
        encrypted_token = self.crypto.encrypt(access_token)

        # 4. Save connection in repository
        sys_ctx = SystemContext(reason="github_oauth_callback")
        conn = await self.repo.upsert_connection(
            ctx=sys_ctx,
            workspace_id=workspace_id,
            user_id=user_id,
            kind="oauth",
            external_account=external_account,
            scopes=scopes,
            encrypted_credential=encrypted_token,
        )

        logger.info(
            "GitHub OAuth connection established (workspace_id=%s, user_id=%s, account=%s)",
            workspace_id,
            user_id,
            external_account,
        )
        return return_to, conn

    async def list_workspace_connections(
        self,
        ctx: AuthContext,
        workspace_id: UUID,
    ) -> list[GitHubConnection]:
        """List active GitHub connections for workspace (safe summary view)."""
        return await self.repo.list_workspace_connections(ctx, workspace_id)

    async def revoke_connection(
        self,
        ctx: AuthContext,
        workspace_id: UUID,
        user_id: UUID,
        kind: str = "oauth",
    ) -> bool:
        """Revoke a GitHub connection for workspace and user."""
        return await self.repo.revoke_connection(ctx, workspace_id, user_id, kind=kind)
