"""Public unauthenticated endpoints protected by Cloudflare Turnstile (docs/07 §11).

Endpoints:
- POST /api/v1/public/waitlist: Early access waitlist signup.
- POST /api/v1/public/contact: Contact & inquiry form submission.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Literal

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from app.core.settings import Settings, get_settings
from app.core.turnstile import verify_turnstile_token
from app.domain.auth import PERMISSION_PUBLIC, declare_permission
from app.middleware.rate_limit import rate_limit_class

logger = logging.getLogger(__name__)

EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

router = APIRouter(
    prefix="/public",
    tags=["Public"],
)


class WaitlistSubmissionRequest(BaseModel):
    """Payload for registering on the early access waitlist."""

    email: str = Field(
        ...,
        max_length=255,
        pattern=EMAIL_REGEX,
        description="Developer email address",
    )
    turnstile_token: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Cloudflare Turnstile verification response token",
    )


class WaitlistSubmissionResponse(BaseModel):
    """Response returned upon waitlist registration."""

    status: Literal["received"] = "received"
    message: str = "Thank you for joining the early access waitlist. We will notify you when developer preview builds are ready."
    email: str


class ContactSubmissionRequest(BaseModel):
    """Payload for submitting a contact or inquiry message."""

    name: str = Field(..., min_length=1, max_length=100, description="Sender name")
    email: str = Field(
        ...,
        max_length=255,
        pattern=EMAIL_REGEX,
        description="Sender email address",
    )
    subject: str = Field(..., min_length=1, max_length=100, description="Inquiry subject")
    message: str = Field(..., min_length=1, max_length=2000, description="Message content")
    turnstile_token: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Cloudflare Turnstile verification response token",
    )


class ContactSubmissionResponse(BaseModel):
    """Response returned upon contact message receipt."""

    status: Literal["received"] = "received"
    message: str = "Your inquiry has been received. Our team will review and respond shortly."


@router.post(
    "/waitlist",
    response_model=WaitlistSubmissionResponse,
    status_code=status.HTTP_200_OK,
    summary="Register for early access waitlist",
)
@declare_permission(PERMISSION_PUBLIC)
@rate_limit_class("auth")
async def register_waitlist(
    payload: WaitlistSubmissionRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> WaitlistSubmissionResponse:
    """Submit developer email for early access notification.

    Protected against bot automated submissions via Cloudflare Turnstile and IP rate limiting.
    """
    client_ip = request.client.host if request.client else None
    await verify_turnstile_token(
        token=payload.turnstile_token,
        remote_ip=client_ip,
        settings=settings,
    )

    # Hash email for privacy-safe structured logging (ADR-047)
    email_hash = hashlib.sha256(payload.email.lower().encode("utf-8")).hexdigest()[:12]
    logger.info("Public waitlist submission received (email_hash=%s)", email_hash)

    return WaitlistSubmissionResponse(email=payload.email)


@router.post(
    "/contact",
    response_model=ContactSubmissionResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit contact / inquiry message",
)
@declare_permission(PERMISSION_PUBLIC)
@rate_limit_class("auth")
async def submit_contact(
    payload: ContactSubmissionRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> ContactSubmissionResponse:
    """Submit a contact or architecture inquiry message.

    Protected against bot spam and abuse via Cloudflare Turnstile and IP rate limiting.
    """
    client_ip = request.client.host if request.client else None
    await verify_turnstile_token(
        token=payload.turnstile_token,
        remote_ip=client_ip,
        settings=settings,
    )

    email_hash = hashlib.sha256(payload.email.lower().encode("utf-8")).hexdigest()[:12]
    logger.info(
        "Public contact inquiry received (subject=%s, email_hash=%s)", payload.subject, email_hash
    )

    return ContactSubmissionResponse()
