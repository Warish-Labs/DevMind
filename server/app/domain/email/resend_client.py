"""Resend transactional email client (docs/01 FR-PLT-05, docs/10 §11, ADR-014)."""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any

import httpx

from app.core.settings import get_settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


class ResendEmailClient:
    """Async client for sending transactional emails via Resend with safe mock fallback."""

    def __init__(self, api_key: str | None = None, from_address: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.resend_api_key
        self.from_address = from_address or getattr(
            settings, "email_from", "invitations@warishlabs.in"
        )

    def _is_configured(self) -> bool:
        """Check if a real Resend API key is configured."""
        if not self.api_key:
            return False
        if self.api_key.startswith("re_REPLACE") or "placeholder" in self.api_key.lower():
            return False
        return True

    async def send_email(
        self,
        *,
        to: str,
        subject: str,
        html_content: str,
        text_content: str | None = None,
    ) -> dict[str, Any]:
        """Send a transactional email, falling back to mock delivery if unconfigured."""
        email_hash = hashlib.sha256(to.lower().encode("utf-8")).hexdigest()[:12]

        if not self._is_configured():
            mock_id = f"mock-msg-{uuid.uuid4()}"
            logger.info(
                "Resend unconfigured or using placeholder; simulating transactional email delivery (recipient_hash=%s, subject=%s, mock_id=%s)",
                email_hash,
                subject,
                mock_id,
                extra={
                    "recipient_hash": email_hash,
                    "subject": subject,
                    "mock_message_id": mock_id,
                },
            )
            return {"id": mock_id, "status": "simulated"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "from": self.from_address,
            "to": [to],
            "subject": subject,
            "html": html_content,
        }
        if text_content:
            payload["text"] = text_content

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(RESEND_API_URL, headers=headers, json=payload)
                if resp.status_code >= 400:
                    logger.warning(
                        "Resend API returned non-success status code %d (recipient_hash=%s)",
                        resp.status_code,
                        email_hash,
                        extra={"status_code": resp.status_code, "recipient_hash": email_hash},
                    )
                    return {"id": f"err-{resp.status_code}", "status": "failed", "error": resp.text}
                data = resp.json()
                logger.info(
                    "Transactional email sent via Resend (msg_id=%s, recipient_hash=%s)",
                    data.get("id"),
                    email_hash,
                    extra={"message_id": data.get("id"), "recipient_hash": email_hash},
                )
                return data
        except Exception as exc:
            logger.error(
                "Failed to dispatch email via Resend API: %s (recipient_hash=%s)",
                str(exc),
                email_hash,
                extra={"error": str(exc), "recipient_hash": email_hash},
            )
            return {"id": "err-exception", "status": "failed", "error": str(exc)}

    async def send_workspace_invitation(
        self,
        *,
        to_email: str,
        workspace_name: str,
        inviter_name: str,
        role: str,
        accept_url: str,
        expires_days: int = 7,
    ) -> dict[str, Any]:
        """Send formatted workspace invitation email."""
        subject = f"You've been invited to join {workspace_name} on DevMind"

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0b0f19; color: #f1f5f9; padding: 24px; }}
    .container {{ max-width: 540px; margin: 0 auto; background: #131b2e; border: 1px solid #1e293b; border-radius: 8px; padding: 32px; }}
    .logo {{ color: #20e3a2; font-size: 20px; font-weight: 700; letter-spacing: -0.5px; margin-bottom: 24px; }}
    h1 {{ font-size: 18px; font-weight: 600; color: #ffffff; margin-top: 0; }}
    p {{ font-size: 14px; line-height: 1.6; color: #94a3b8; }}
    .btn {{ display: inline-block; background-color: #20e3a2; color: #0b0f19; font-size: 14px; font-weight: 600; text-decoration: none; padding: 10px 20px; border-radius: 6px; margin: 20px 0; }}
    .footer {{ font-size: 12px; color: #64748b; margin-top: 24px; border-top: 1px solid #1e293b; pt: 16px; }}
    code {{ font-family: monospace; color: #38bdf8; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="logo">DevMind</div>
    <h1>Join {workspace_name}</h1>
    <p><strong>{inviter_name}</strong> has invited you to join the <strong>{workspace_name}</strong> workspace on DevMind with the role of <code>{role}</code>.</p>
    <p>DevMind provides evidence-grounded AI coding intelligence, change-impact blast radius, and automated review checklists.</p>
    <p>
      <a href="{accept_url}" class="btn">Accept Invitation</a>
    </p>
    <p>This invitation link will expire in {expires_days} days.</p>
    <div class="footer">
      If you did not expect this invitation, you can safely ignore this email.
    </div>
  </div>
</body>
</html>
"""
        text_content = f"""
DevMind — Join {workspace_name}

{inviter_name} has invited you to join the {workspace_name} workspace on DevMind with the role of {role}.

Accept your invitation here:
{accept_url}

This invitation link will expire in {expires_days} days.

If you did not expect this invitation, you can safely ignore this email.
"""

        return await self.send_email(
            to=to_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
        )
