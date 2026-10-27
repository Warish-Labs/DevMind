"""Unit and contract tests for GitHub permissions, degradation, error classification, and security (docs/12 ADR-015).

Verifies:
1. Permission matrix: GitHub App minimal scopes vs OAuth identity scopes.
2. Forbidden scope prevention (principle of least privilege).
3. Permission degradation logic and resolution hints when scopes are revoked or missing.
4. RFC 9457 error classification for GitHub API responses (401, 403, 429).
5. Webhook signature verification and deduplication security.
6. Envelope encryption for GitHub credentials at rest (AES-256-GCM).
7. Human approval gate enforcement for mutating actions.
8. Webhook lifecycle dispatch for installation and installation_repositories.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from unittest.mock import AsyncMock

import pytest

from app.core.crypto import EncryptionService
from app.core.settings import Settings
from app.domain.integrations.github_permissions import (
    FORBIDDEN_SCOPES,
    GITHUB_APP_REQUIRED_PERMISSIONS,
    GITHUB_OAUTH_SCOPES,
    GitHubPermissionDeniedError,
    GitHubPermissionStatus,
    GitHubRateLimitError,
    GitHubTokenRevokedError,
    classify_github_api_error,
    evaluate_app_permissions,
    evaluate_oauth_permissions,
    requires_human_approval,
)
from app.domain.webhooks.github_webhook_service import GitHubWebhookService
from app.persistence.models.github import GitHubConnection


@pytest.fixture
def crypto_settings() -> Settings:
    return Settings(
        env="test",
        encryption_keys=["c3VwZXJfc2VjcmV0X2tleV9mb3JfdGVzdF8zMmJ5dGVzIQ=="],
        github_webhook_secret="contract_test_webhook_secret_key_12345",
    )


# ---------------------------------------------------------------------------
# 1. Permission Matrix & Minimal Scopes Contract
# ---------------------------------------------------------------------------


def test_adr015_minimal_required_permissions() -> None:
    """GitHub App required permissions must only be pull_requests:read, contents:read, metadata:read."""
    assert GITHUB_APP_REQUIRED_PERMISSIONS == {
        "pull_requests": "read",
        "contents": "read",
        "metadata": "read",
    }
    # Write permissions must NOT be required by default in v1
    for perm, level in GITHUB_APP_REQUIRED_PERMISSIONS.items():
        assert level == "read", f"Permission {perm} must be read-only in v1"


def test_adr015_oauth_identity_scopes() -> None:
    """OAuth scopes must include read:user and user:email for identity."""
    assert "read:user" in GITHUB_OAUTH_SCOPES
    assert "user:email" in GITHUB_OAUTH_SCOPES


def test_adr015_forbidden_scopes_rejected() -> None:
    """DevMind must forbid requesting high-risk administrative or destructive scopes."""
    assert "delete_repo" in FORBIDDEN_SCOPES
    assert "admin:org" in FORBIDDEN_SCOPES
    assert "admin:repo_hook" in FORBIDDEN_SCOPES

    # Ensure none of the forbidden scopes are present in required sets
    for forbidden in FORBIDDEN_SCOPES:
        assert forbidden not in GITHUB_APP_REQUIRED_PERMISSIONS
        assert forbidden not in GITHUB_OAUTH_SCOPES


# ---------------------------------------------------------------------------
# 2. Permission Evaluation & Degradation
# ---------------------------------------------------------------------------


def test_evaluate_app_permissions_all_present() -> None:
    """All required App permissions present yields ACTIVE status and can_perform_analysis=True."""
    granted = {"pull_requests": "read", "contents": "read", "metadata": "read"}
    res = evaluate_app_permissions(granted)

    assert res.status == GitHubPermissionStatus.ACTIVE
    assert res.can_perform_analysis is True
    assert res.missing_permissions == []
    assert res.reason is None


def test_evaluate_app_permissions_missing_contents_degraded() -> None:
    """Missing contents:read degrades status and prevents analysis with hint."""
    granted = {"pull_requests": "read", "metadata": "read"}
    res = evaluate_app_permissions(granted)

    assert res.status == GitHubPermissionStatus.DEGRADED
    assert res.can_perform_analysis is False
    assert "contents:read" in res.missing_permissions
    assert "Update GitHub App installation permissions" in (res.resolution_hint or "")


def test_evaluate_app_permissions_missing_pull_requests_degraded() -> None:
    """Missing pull_requests:read degrades status."""
    granted = {"contents": "read", "metadata": "read"}
    res = evaluate_app_permissions(granted)

    assert res.status == GitHubPermissionStatus.DEGRADED
    assert res.can_perform_analysis is False
    assert "pull_requests:read" in res.missing_permissions


def test_evaluate_app_permissions_from_list_format() -> None:
    """Handles list format e.g. ['pull_requests:read', 'contents:read', 'metadata:read']."""
    granted = ["pull_requests:read", "contents:read", "metadata:read"]
    res = evaluate_app_permissions(granted)
    assert res.status == GitHubPermissionStatus.ACTIVE
    assert res.can_perform_analysis is True


def test_evaluate_oauth_permissions_full() -> None:
    """OAuth token with read:user and repo is active."""
    res = evaluate_oauth_permissions(["read:user", "user:email", "repo"])
    assert res.status == GitHubPermissionStatus.ACTIVE
    assert res.can_perform_analysis is True


def test_evaluate_oauth_permissions_missing_repo_degraded() -> None:
    """OAuth token without repo is degraded."""
    res = evaluate_oauth_permissions(["read:user", "user:email"])
    assert res.status == GitHubPermissionStatus.DEGRADED
    assert res.can_perform_analysis is False
    assert "repo" in res.missing_permissions


# ---------------------------------------------------------------------------
# 3. GitHub API Error Classification (RFC 9457)
# ---------------------------------------------------------------------------


def test_classify_github_401_token_revoked() -> None:
    """HTTP 401 maps to integration.github.token_revoked."""
    err = classify_github_api_error(401, {"message": "Bad credentials"})
    assert isinstance(err, GitHubTokenRevokedError)
    assert err.code == "integration.github.token_revoked"
    assert err.status_code == 401
    assert "Bad credentials" in err.detail


def test_classify_github_403_permission_denied() -> None:
    """HTTP 403 maps to integration.github.permission_denied."""
    err = classify_github_api_error(403, {"message": "Resource not accessible by integration"})
    assert isinstance(err, GitHubPermissionDeniedError)
    assert err.code == "integration.github.permission_denied"
    assert err.status_code == 403


def test_classify_github_403_rate_limit() -> None:
    """HTTP 403 with rate limit message maps to integration.github.rate_limited with Retry-After."""
    err = classify_github_api_error(
        403,
        {"message": "API rate limit exceeded for user ID 12345"},
        headers={"x-ratelimit-reset": "1730000000"},
    )
    assert isinstance(err, GitHubRateLimitError)
    assert err.code == "integration.github.rate_limited"
    assert err.status_code == 429
    assert err.headers is not None
    assert "Retry-After" in err.headers


def test_classify_github_404_not_found() -> None:
    """HTTP 404 maps to resource.not_found."""
    err = classify_github_api_error(404, {"message": "Not Found"})
    assert err.code == "resource.not_found"
    assert err.status_code == 404


def test_classify_github_429_rate_limit() -> None:
    """HTTP 429 maps to integration.github.rate_limited."""
    err = classify_github_api_error(
        429,
        {"message": "Too Many Requests"},
        headers={"retry-after": "60"},
    )
    assert isinstance(err, GitHubRateLimitError)
    assert err.code == "integration.github.rate_limited"
    assert err.status_code == 429
    assert err.headers == {"Retry-After": "60"}


# ---------------------------------------------------------------------------
# 4. Human Approval Gate Enforcement
# ---------------------------------------------------------------------------


def test_human_approval_required_for_mutations() -> None:
    """Mutating operations must require human approval per ADR-015."""
    assert requires_human_approval("post_pr_comment") is True
    assert requires_human_approval("merge_pull_request") is True
    assert requires_human_approval("create_review_comment") is True
    assert requires_human_approval("close_pull_request") is True

    # Read-only operations must NOT require approval gate
    assert requires_human_approval("get_pull_request") is False
    assert requires_human_approval("read_tree") is False
    assert requires_human_approval("list_commits") is False


# ---------------------------------------------------------------------------
# 5. Credential Envelope Encryption Contract
# ---------------------------------------------------------------------------


def test_github_credential_envelope_encryption(crypto_settings: Settings) -> None:
    """GitHub tokens must be encrypted with AES-256-GCM envelope; raw token never exposed."""
    crypto = EncryptionService(crypto_settings)
    raw_token = "ghp_liveSecretGitHubPersonalAccessToken998877"

    envelope = crypto.encrypt(raw_token)
    assert envelope.startswith("v1:0:")
    assert raw_token not in envelope

    # Model representation verification
    conn = GitHubConnection(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        kind="oauth",
        external_account="octocat",
        scopes=["read:user", "repo"],
        encrypted_credential=envelope,
    )
    assert conn.encrypted_credential == envelope
    assert raw_token not in repr(conn)

    # Decrypt roundtrip
    decrypted = crypto.decrypt(conn.encrypted_credential)
    assert decrypted == raw_token


# ---------------------------------------------------------------------------
# 6. Webhook Security & Lifecycle Handling
# ---------------------------------------------------------------------------


def test_webhook_hmac_sha256_verification(crypto_settings: Settings) -> None:
    """Webhook service validates HMAC-SHA256 signature against secret."""
    service = GitHubWebhookService(session=AsyncMock(), settings=crypto_settings)
    payload = b'{"zen": "Keep it logically awesome."}'

    # Proper HMAC calculation
    secret = crypto_settings.github_webhook_secret.encode("utf-8")
    sig = "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()

    assert service.verify_signature(sig, payload) is True
    assert service.verify_signature("sha256=forged_signature_000", payload) is False
    assert service.verify_signature(None, payload) is False


@pytest.mark.asyncio
async def test_webhook_installation_events_dispatched(crypto_settings: Settings) -> None:
    """Webhook service dispatches installation and installation_repositories events."""
    service = GitHubWebhookService(session=AsyncMock(), settings=crypto_settings)

    # Test installation suspend
    suspend_res = await service.handle_event(
        event_type="installation",
        delivery_id="delivery-inst-1",
        payload={
            "action": "suspend",
            "installation": {"id": 12345, "account": {"login": "octocat-org"}},
        },
    )
    assert suspend_res["status"] == "received"
    assert suspend_res["event"] == "installation"
    assert suspend_res["action"] == "suspend"
    assert suspend_res["installation_id"] == 12345

    # Test installation_repositories removal
    repo_res = await service.handle_event(
        event_type="installation_repositories",
        delivery_id="delivery-inst-repo-1",
        payload={
            "action": "removed",
            "installation": {"id": 12345},
            "repositories_removed": [{"full_name": "octocat-org/private-repo"}],
            "repositories_added": [],
        },
    )
    assert repo_res["status"] == "received"
    assert repo_res["action"] == "removed"
    assert "octocat-org/private-repo" in repo_res["repositories_removed"]
