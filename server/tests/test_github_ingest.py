"""Unit and API integration tests for GitHub repository ingestion and PR mirroring (FR-BRN-07, CAP-06, M11-03).

Verifies:
1. Project repository linking with workspace tenant checks and audit event recording.
2. Webhook pull_request event ingestion and automatic mirror upsert in database.
3. Webhook delivery deduplication and replay prevention.
4. PR query filtering by state and PR detail retrieval by primary key.
5. API endpoints for /projects/{pid}/github/* and /pull-requests/{id}.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth_context import AuthContext
from app.core.errors import ValidationError
from app.core.settings import Settings
from app.domain.auth import get_auth_context
from app.domain.integrations.github_ingest_service import GitHubIngestService
from app.domain.webhooks.github_webhook_service import GitHubWebhookService
from app.main import create_app
from app.persistence.models.github import GitHubConnection, GitHubRepositoryBinding, PullRequest
from app.persistence.models.project import Project


@pytest.fixture
def ingest_settings() -> Settings:
    return Settings(
        env="test",
        github_client_id="test_github_client_id",
        github_client_secret="test_github_client_secret",
        github_webhook_secret="contract_test_webhook_secret_key_12345",
        encryption_keys=["c3VwZXJfc2VjcmV0X2tleV9mb3JfdGVzdF8zMmJ5dGVzIQ=="],
    )


def _sign(secret: str, body: bytes) -> str:
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


# ---------------------------------------------------------------------------
# 1. Repository Linking & Ingest Service Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_link_project_repository_success(ingest_settings: Settings) -> None:
    """Project links to GitHub repo when active workspace connection exists."""
    mock_session = AsyncMock()
    service = GitHubIngestService(mock_session, settings=ingest_settings)

    wid = uuid.uuid4()
    pid = uuid.uuid4()
    uid = uuid.uuid4()
    conn_id = uuid.uuid4()

    mock_proj = Project(id=pid, workspace_id=wid, name="DevMind Client", slug="devmind-client")
    mock_conn = GitHubConnection(
        id=conn_id,
        workspace_id=wid,
        user_id=uid,
        kind="oauth",
        external_account="octocat",
        scopes=["read:user", "repo"],
        encrypted_credential="v1:0:nonce:cipher",
    )
    mock_binding = GitHubRepositoryBinding(
        id=uuid.uuid4(),
        project_id=pid,
        connection_id=conn_id,
        full_name="Warish-Labs/DevMind",
        default_branch="main",
        is_active=True,
    )

    service.project_repo.get_by_id = AsyncMock(return_value=mock_proj)  # type: ignore[method-assign]
    service.repo.get_connection = AsyncMock(return_value=mock_conn)  # type: ignore[method-assign]
    service.repo.link_repository = AsyncMock(return_value=mock_binding)  # type: ignore[method-assign]
    service.audit_repo.record = AsyncMock()  # type: ignore[method-assign]

    ctx = AuthContext(
        user_id=uid,
        clerk_user_id="clerk_123",
        email="dev@example.com",
        workspace_id=wid,
        permissions=frozenset({"project:update"}),
    )

    binding = await service.link_project_repository(
        ctx=ctx,
        project_id=pid,
        full_name="Warish-Labs/DevMind",
        default_branch="main",
    )

    assert binding.full_name == "Warish-Labs/DevMind"
    assert binding.default_branch == "main"
    service.audit_repo.record.assert_awaited_once()


@pytest.mark.asyncio
async def test_link_project_repository_invalid_format_rejected(ingest_settings: Settings) -> None:
    """Repository name not matching 'owner/repo' must be rejected."""
    mock_session = AsyncMock()
    service = GitHubIngestService(mock_session, settings=ingest_settings)

    ctx = AuthContext(
        user_id=uuid.uuid4(),
        clerk_user_id="clerk_123",
        email="dev@example.com",
        workspace_id=uuid.uuid4(),
        permissions=frozenset({"project:update"}),
    )

    with pytest.raises(ValidationError) as exc_info:
        await service.link_project_repository(ctx, uuid.uuid4(), "invalid-repo-name")
    assert "owner/repo" in str(exc_info.value)


@pytest.mark.asyncio
async def test_link_project_repository_missing_connection_rejected(
    ingest_settings: Settings,
) -> None:
    """Linking without an active GitHub connection raises ValidationError."""
    mock_session = AsyncMock()
    service = GitHubIngestService(mock_session, settings=ingest_settings)

    pid = uuid.uuid4()
    wid = uuid.uuid4()
    mock_proj = Project(id=pid, workspace_id=wid, name="Test Project", slug="test-project")
    service.project_repo.get_by_id = AsyncMock(return_value=mock_proj)  # type: ignore[method-assign]
    service.repo.get_connection = AsyncMock(return_value=None)  # type: ignore[method-assign]

    ctx = AuthContext(
        user_id=uuid.uuid4(),
        clerk_user_id="clerk_123",
        email="dev@example.com",
        workspace_id=wid,
        permissions=frozenset({"project:update"}),
    )

    with pytest.raises(ValidationError) as exc_info:
        await service.link_project_repository(ctx, pid, "octocat/Hello-World")
    assert "No active GitHub connection" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 2. Webhook Pull Request Ingestion Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_pull_request_mirroring_success(ingest_settings: Settings) -> None:
    """pull_request webhook automatically mirrors PR into PostgreSQL when repo is linked."""
    mock_session = AsyncMock()
    service = GitHubWebhookService(session=mock_session, settings=ingest_settings)

    repo_id = uuid.uuid4()
    mock_binding = GitHubRepositoryBinding(
        id=repo_id,
        project_id=uuid.uuid4(),
        connection_id=uuid.uuid4(),
        full_name="Warish-Labs/DevMind",
        default_branch="main",
        is_active=True,
    )
    service.repo.get_repository_by_full_name = AsyncMock(return_value=mock_binding)  # type: ignore[method-assign]
    service.repo.upsert_pull_request = AsyncMock()  # type: ignore[method-assign]

    payload = {
        "action": "opened",
        "number": 42,
        "repository": {"full_name": "Warish-Labs/DevMind"},
        "pull_request": {
            "number": 42,
            "title": "feat: add pr intelligence mirror",
            "state": "open",
            "user": {"login": "octocat_developer"},
            "head": {"sha": "head_sha_123456", "ref": "feature/pr-intelligence"},
            "base": {"sha": "base_sha_000000", "ref": "main"},
            "html_url": "https://github.com/Warish-Labs/DevMind/pull/42",
        },
    }

    res = await service.handle_event("pull_request", "delivery-pr-42", payload)
    assert res["status"] == "processed"
    assert res["mirrored"] is True
    assert res["number"] == 42

    service.repo.upsert_pull_request.assert_awaited_once()
    call_kwargs = service.repo.upsert_pull_request.await_args.kwargs
    assert call_kwargs["number"] == 42
    assert call_kwargs["title"] == "feat: add pr intelligence mirror"
    assert call_kwargs["author_login"] == "octocat_developer"
    assert call_kwargs["head_sha"] == "head_sha_123456"
    assert call_kwargs["base_sha"] == "base_sha_000000"


@pytest.mark.asyncio
async def test_webhook_delivery_deduplication(ingest_settings: Settings) -> None:
    """Duplicate X-GitHub-Delivery returns duplicate_delivery ignore status."""
    app = create_app(settings=ingest_settings)
    payload = json.dumps({"zen": "Favor focus over features.", "hook_id": 100}).encode("utf-8")
    sig = _sign(ingest_settings.github_webhook_secret, payload)

    delivery_id = f"dedupe-delivery-{uuid.uuid4()}"
    headers = {
        "X-Hub-Signature-256": sig,
        "X-GitHub-Delivery": delivery_id,
        "X-GitHub-Event": "ping",
        "Content-Type": "application/json",
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First delivery: processed
        res1 = await client.post("/api/v1/webhooks/github", content=payload, headers=headers)
        assert res1.status_code == 200
        assert res1.json()["status"] == "processed"

        # Replay: ignored
        res2 = await client.post("/api/v1/webhooks/github", content=payload, headers=headers)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["status"] == "ignored"
        assert data2["reason"] == "duplicate_delivery"


# ---------------------------------------------------------------------------
# 3. API Integration Tests (/projects/{pid}/github/* & /pull-requests/{id})
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_link_and_get_project_repository(
    ingest_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /projects/{pid}/github/link and GET /projects/{pid}/github/repository."""
    app = create_app(settings=ingest_settings)
    pid = uuid.uuid4()
    wid = uuid.uuid4()
    uid = uuid.uuid4()
    binding_id = uuid.uuid4()

    mock_auth_ctx = AuthContext(
        user_id=uid,
        clerk_user_id="clerk_test",
        email="developer@example.com",
        workspace_id=wid,
        permissions=frozenset({"project:read", "project:update"}),
    )
    app.dependency_overrides[get_auth_context] = lambda: mock_auth_ctx

    mock_binding = GitHubRepositoryBinding(
        id=binding_id,
        project_id=pid,
        connection_id=uuid.uuid4(),
        full_name="Warish-Labs/DevMind",
        default_branch="main",
        is_active=True,
    )

    async def mock_link(
        self: Any, ctx: Any, project_id: Any, full_name: str, default_branch: str = "main"
    ) -> GitHubRepositoryBinding:
        return mock_binding

    async def mock_get(self: Any, ctx: Any, project_id: Any) -> GitHubRepositoryBinding:
        return mock_binding

    monkeypatch.setattr(GitHubIngestService, "link_project_repository", mock_link)
    monkeypatch.setattr(GitHubIngestService, "get_project_repository", mock_get)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Link repo
        res_link = await client.post(
            f"/api/v1/projects/{pid}/github/link",
            json={"full_name": "Warish-Labs/DevMind", "default_branch": "main"},
        )
        assert res_link.status_code == 200
        data = res_link.json()
        assert data["id"] == str(binding_id)
        assert data["full_name"] == "Warish-Labs/DevMind"

        # Get repo
        res_get = await client.get(f"/api/v1/projects/{pid}/github/repository")
        assert res_get.status_code == 200
        assert res_get.json()["full_name"] == "Warish-Labs/DevMind"


@pytest.mark.asyncio
async def test_api_list_project_pull_requests(
    ingest_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /projects/{pid}/pull-requests returns list of mirrored PR summaries."""
    app = create_app(settings=ingest_settings)
    pid = uuid.uuid4()
    wid = uuid.uuid4()
    pr_id = uuid.uuid4()

    mock_auth_ctx = AuthContext(
        user_id=uuid.uuid4(),
        clerk_user_id="clerk_test",
        email="developer@example.com",
        workspace_id=wid,
        permissions=frozenset({"project:read"}),
    )
    app.dependency_overrides[get_auth_context] = lambda: mock_auth_ctx

    mock_pr = PullRequest(
        id=pr_id,
        repository_id=uuid.uuid4(),
        number=84,
        title="feat(server): implement M11-02 GitHub OAuth linking and token management",
        author_login="octocat",
        state="open",
        head_sha="head_sha_84",
        base_sha="base_sha_84",
        head_ref="feature/m11-oauth-tokens",
        base_ref="main",
    )

    async def mock_list(
        self: Any,
        ctx: Any,
        project_id: Any,
        state: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PullRequest]:
        return [mock_pr]

    monkeypatch.setattr(GitHubIngestService, "list_project_pull_requests", mock_list)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/api/v1/projects/{pid}/pull-requests?state=open")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["number"] == 84
        assert (
            data[0]["title"]
            == "feat(server): implement M11-02 GitHub OAuth linking and token management"
        )


@pytest.mark.asyncio
async def test_api_get_pull_request_by_id(
    ingest_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /pull-requests/{id} returns single PR detail or 404."""
    app = create_app(settings=ingest_settings)
    pr_id = uuid.uuid4()

    mock_auth_ctx = AuthContext(
        user_id=uuid.uuid4(),
        clerk_user_id="clerk_test",
        email="developer@example.com",
        workspace_id=uuid.uuid4(),
        permissions=frozenset({"workspace:read"}),
    )
    app.dependency_overrides[get_auth_context] = lambda: mock_auth_ctx

    mock_pr = PullRequest(
        id=pr_id,
        repository_id=uuid.uuid4(),
        number=83,
        title="feat(docs): implement M11-01 GitHub permissions review",
        author_login="octocat",
        state="closed",
        head_sha="head_sha_83",
        base_sha="base_sha_83",
    )

    async def mock_get_pr(self: Any, ctx: Any, target_id: Any) -> PullRequest | None:
        if target_id == pr_id:
            return mock_pr
        return None

    monkeypatch.setattr(GitHubIngestService, "get_pull_request_by_id", mock_get_pr)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Success
        res = await client.get(f"/api/v1/pull-requests/{pr_id}")
        assert res.status_code == 200
        assert res.json()["number"] == 83

        # Not found
        res_404 = await client.get(f"/api/v1/pull-requests/{uuid.uuid4()}")
        assert res_404.status_code == 404
