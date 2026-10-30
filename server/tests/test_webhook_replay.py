"""Tests for GitHub webhook replay fixtures, signature verification, and delivery idempotency (docs/03 §10, docs/07 §11, M11-08)."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.settings import Settings
from app.domain.auth import get_db_session
from app.domain.webhooks.github_webhook_service import GitHubWebhookService
from app.main import create_app
from app.persistence.models.github import GitHubRepositoryBinding

TEST_SECRET = "test_webhook_secret_key_devmind_12345"


def sign_payload(secret: str, body: bytes) -> str:
    """Compute HMAC-SHA256 signature for GitHub webhook payload."""
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


@pytest.fixture
def webhook_settings() -> Settings:
    return Settings(
        env="test",
        github_webhook_secret=TEST_SECRET,
    )


@pytest.fixture
def mock_db_session() -> AsyncMock:
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result
    return session


@pytest.fixture
def test_app(webhook_settings: Settings, mock_db_session: AsyncMock) -> Any:
    app = create_app(settings=webhook_settings)

    async def _override_session():
        yield mock_db_session

    app.dependency_overrides[get_db_session] = _override_session
    return app


@pytest.mark.asyncio
async def test_webhook_replay_ping_event_idempotency(test_app: Any, webhook_settings: Settings) -> None:
    """Repeated delivery of a ping event with the same X-GitHub-Delivery must be ignored on second attempt."""
    payload = {"zen": "Mind your turns.", "hook_id": 12345}
    body = json.dumps(payload).encode("utf-8")
    sig = sign_payload(webhook_settings.github_webhook_secret, body)
    delivery_id = f"delivery-ping-{uuid4()}"

    headers = {
        "X-Hub-Signature-256": sig,
        "X-GitHub-Delivery": delivery_id,
        "X-GitHub-Event": "ping",
        "Content-Type": "application/json",
    }

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First delivery -> processed
        res1 = await client.post("/api/v1/webhooks/github", content=body, headers=headers)
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["status"] == "processed"
        assert data1["result"]["status"] == "pong"

        # Replay with same delivery ID -> ignored
        res2 = await client.post("/api/v1/webhooks/github", content=body, headers=headers)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["status"] == "ignored"
        assert data2["reason"] == "duplicate_delivery"
        assert data2["id"] == delivery_id


@pytest.mark.asyncio
async def test_webhook_replay_pull_request_lifecycle_transitions(webhook_settings: Settings) -> None:
    """Simulate realistic PR lifecycle transitions: opened -> synchronize -> closed."""
    session = AsyncMock()
    service = GitHubWebhookService(session=session, settings=webhook_settings)

    project_id = uuid4()
    workspace_id = uuid4()
    binding_id = uuid4()

    mock_repo = MagicMock(spec=GitHubRepositoryBinding)
    mock_repo.id = binding_id
    mock_repo.project_id = project_id
    mock_repo.workspace_id = workspace_id
    mock_repo.full_name = "Warish-Labs/DevMind"

    # Mock repository lookup
    service.repo.get_repository_by_full_name = AsyncMock(return_value=mock_repo)
    service.repo.upsert_pull_request = AsyncMock()

    # 1. Event: opened
    opened_payload = {
        "action": "opened",
        "repository": {"full_name": "Warish-Labs/DevMind"},
        "pull_request": {
            "number": 99,
            "title": "feat: add webhook integration",
            "state": "open",
            "user": {"login": "test-dev"},
            "head": {"sha": "sha_111111", "ref": "feature/webhook"},
            "base": {"sha": "sha_000000", "ref": "main"},
            "diff_url": "https://github.com/Warish-Labs/DevMind/pull/99.diff",
        },
    }
    deliv_1 = f"deliv-{uuid4()}"
    res_opened = await service.handle_event("pull_request", deliv_1, opened_payload)
    assert res_opened["status"] == "processed"
    assert res_opened["mirrored"] is True
    assert res_opened["action"] == "opened"

    # Verify upsert call for opened
    service.repo.upsert_pull_request.assert_called_with(
        ctx=AnyMatch(),
        repository_id=binding_id,
        number=99,
        title="feat: add webhook integration",
        author_login="test-dev",
        head_sha="sha_111111",
        base_sha="sha_000000",
        state="open",
        head_ref="feature/webhook",
        base_ref="main",
        diff_url="https://github.com/Warish-Labs/DevMind/pull/99.diff",
        merged_at=None,
        closed_at=None,
    )

    # 2. Event: synchronize (commit pushed to PR)
    sync_payload = {
        "action": "synchronize",
        "repository": {"full_name": "Warish-Labs/DevMind"},
        "pull_request": {
            "number": 99,
            "title": "feat: add webhook integration",
            "state": "open",
            "user": {"login": "test-dev"},
            "head": {"sha": "sha_222222", "ref": "feature/webhook"},
            "base": {"sha": "sha_000000", "ref": "main"},
            "diff_url": "https://github.com/Warish-Labs/DevMind/pull/99.diff",
        },
    }
    deliv_2 = f"deliv-{uuid4()}"
    res_sync = await service.handle_event("pull_request", deliv_2, sync_payload)
    assert res_sync["status"] == "processed"
    assert res_sync["action"] == "synchronize"

    # Verify updated head SHA
    service.repo.upsert_pull_request.assert_called_with(
        ctx=AnyMatch(),
        repository_id=binding_id,
        number=99,
        title="feat: add webhook integration",
        author_login="test-dev",
        head_sha="sha_222222",
        base_sha="sha_000000",
        state="open",
        head_ref="feature/webhook",
        base_ref="main",
        diff_url="https://github.com/Warish-Labs/DevMind/pull/99.diff",
        merged_at=None,
        closed_at=None,
    )

    # 3. Event: closed
    closed_at_str = "2026-10-31T01:00:00Z"
    closed_payload = {
        "action": "closed",
        "repository": {"full_name": "Warish-Labs/DevMind"},
        "pull_request": {
            "number": 99,
            "title": "feat: add webhook integration",
            "state": "closed",
            "user": {"login": "test-dev"},
            "head": {"sha": "sha_222222", "ref": "feature/webhook"},
            "base": {"sha": "sha_000000", "ref": "main"},
            "diff_url": "https://github.com/Warish-Labs/DevMind/pull/99.diff",
            "merged_at": closed_at_str,
            "closed_at": closed_at_str,
        },
    }
    deliv_3 = f"deliv-{uuid4()}"
    res_closed = await service.handle_event("pull_request", deliv_3, closed_payload)
    assert res_closed["status"] == "processed"
    assert res_closed["action"] == "closed"


@pytest.mark.asyncio
async def test_webhook_replay_push_event(webhook_settings: Settings) -> None:
    """Push event handling returns receipt with commit count and branch ref."""
    session = AsyncMock()
    service = GitHubWebhookService(session=session, settings=webhook_settings)

    payload = {
        "ref": "refs/heads/main",
        "repository": {"full_name": "Warish-Labs/DevMind"},
        "commits": [{"id": "c1"}, {"id": "c2"}, {"id": "c3"}],
    }
    res = await service.handle_event("push", f"push-{uuid4()}", payload)
    assert res["status"] == "received"
    assert res["event"] == "push"
    assert res["commits"] == 3
    assert res["ref"] == "refs/heads/main"


@pytest.mark.asyncio
async def test_webhook_replay_installation_events(webhook_settings: Settings) -> None:
    """App installation and repository modification events are received."""
    session = AsyncMock()
    service = GitHubWebhookService(session=session, settings=webhook_settings)

    # Installation created
    inst_payload = {
        "action": "created",
        "installation": {"id": 8888, "account": {"login": "Warish-Labs"}},
    }
    res_inst = await service.handle_event("installation", f"inst-{uuid4()}", inst_payload)
    assert res_inst["status"] == "received"
    assert res_inst["installation_id"] == 8888

    # Repositories added
    repo_payload = {
        "action": "added",
        "installation": {"id": 8888},
        "repositories_added": [{"full_name": "Warish-Labs/DevMind"}],
        "repositories_removed": [],
    }
    res_repos = await service.handle_event("installation_repositories", f"repo-{uuid4()}", repo_payload)
    assert res_repos["status"] == "received"
    assert res_repos["repositories_added"] == ["Warish-Labs/DevMind"]


@pytest.mark.asyncio
async def test_webhook_signature_tampered_payload_rejected(test_app: Any, webhook_settings: Settings) -> None:
    """Signature computed on payload A must fail when received with tampered payload B."""
    original_body = b'{"action": "opened", "number": 1}'
    tampered_body = b'{"action": "opened", "number": 99999}'

    # Signature signed against original
    sig = sign_payload(webhook_settings.github_webhook_secret, original_body)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/webhooks/github",
            content=tampered_body,
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": f"tamper-{uuid4()}",
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
        )
        assert res.status_code == 401
        assert "Invalid" in res.json()["detail"]


@pytest.mark.asyncio
async def test_webhook_malformed_json_body_rejected(test_app: Any, webhook_settings: Settings) -> None:
    """Malformed non-JSON payload returns 400/422 validation error."""
    malformed_body = b"NOT_VALID_JSON{abc"
    sig = sign_payload(webhook_settings.github_webhook_secret, malformed_body)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/webhooks/github",
            content=malformed_body,
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": f"malformed-{uuid4()}",
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
        )
        assert res.status_code in (400, 422)


class AnyMatch:
    """Helper matcher for mock assertions."""

    def __eq__(self, other: Any) -> bool:
        return True
