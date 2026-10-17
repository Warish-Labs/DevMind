"""Tests for GitHub webhook signature verification, delivery deduplication, and event dispatch."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.settings import Settings
from app.main import create_app


@pytest.fixture
def webhook_settings() -> Settings:
    return Settings(
        env="test",
        github_webhook_secret="test_secret_for_github_webhooks_12345",
    )


def _sign_payload(secret: str, body: bytes) -> str:
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


@pytest.mark.asyncio
async def test_github_webhook_missing_signature_rejected(webhook_settings: Settings) -> None:
    """Missing X-Hub-Signature-256 header must return 401."""
    app = create_app(settings=webhook_settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/webhooks/github",
            json={"action": "opened"},
        )
        assert res.status_code == 401
        data = res.json()
        assert "Missing" in data["detail"]


@pytest.mark.asyncio
async def test_github_webhook_invalid_signature_rejected(webhook_settings: Settings) -> None:
    """Invalid HMAC signature must return 401."""
    app = create_app(settings=webhook_settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/webhooks/github",
            content=b'{"action": "opened"}',
            headers={
                "X-Hub-Signature-256": "sha256=invalid_signature_hex_0000000000000000",
                "X-GitHub-Delivery": "delivery-123",
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
        )
        assert res.status_code == 401
        data = res.json()
        assert "Invalid" in data["detail"]


@pytest.mark.asyncio
async def test_github_webhook_ping_event_success(webhook_settings: Settings) -> None:
    """Valid ping event succeeds and returns pong."""
    app = create_app(settings=webhook_settings)
    body = json.dumps({"zen": "Keep it logically awesome.", "hook_id": 9999}).encode("utf-8")
    sig = _sign_payload(webhook_settings.github_webhook_secret, body)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/webhooks/github",
            content=body,
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": "delivery-ping-1",
                "X-GitHub-Event": "ping",
                "Content-Type": "application/json",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "processed"
        assert data["event"] == "ping"
        assert data["result"]["status"] == "pong"


@pytest.mark.asyncio
async def test_github_webhook_pull_request_event_success(webhook_settings: Settings) -> None:
    """Valid pull_request webhook payload processed."""
    app = create_app(settings=webhook_settings)
    payload = {
        "action": "opened",
        "number": 42,
        "pull_request": {"number": 42, "title": "feat: add brain indexing"},
        "repository": {"full_name": "Warish-Labs/DevMind"},
    }
    body = json.dumps(payload).encode("utf-8")
    sig = _sign_payload(webhook_settings.github_webhook_secret, body)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/webhooks/github",
            content=body,
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": "delivery-pr-42",
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "processed"
        assert data["event"] == "pull_request"
        assert data["result"]["number"] == 42


@pytest.mark.asyncio
async def test_github_webhook_duplicate_delivery_ignored(webhook_settings: Settings) -> None:
    """Duplicate X-GitHub-Delivery is gracefully ignored without duplicate execution."""
    app = create_app(settings=webhook_settings)
    body = json.dumps({"zen": "Practicality beats purity."}).encode("utf-8")
    sig = _sign_payload(webhook_settings.github_webhook_secret, body)
    delivery_id = "duplicate-delivery-test-uuid-999"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First delivery: processed
        res1 = await client.post(
            "/api/v1/webhooks/github",
            content=body,
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": delivery_id,
                "X-GitHub-Event": "ping",
                "Content-Type": "application/json",
            },
        )
        assert res1.status_code == 200
        assert res1.json()["status"] == "processed"

        # Duplicate delivery: ignored
        res2 = await client.post(
            "/api/v1/webhooks/github",
            content=body,
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": delivery_id,
                "X-GitHub-Event": "ping",
                "Content-Type": "application/json",
            },
        )
        assert res2.status_code == 200
        assert res2.json()["status"] == "ignored"
        assert res2.json()["reason"] == "duplicate_delivery"
