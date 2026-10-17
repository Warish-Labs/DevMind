"""Tests for Secret Redaction Pipeline and Consented Snippet Upload (M5-03, docs/07 §6, docs/03 §12.4).

Verifies:
1. Server-side Redaction Engine:
   - Detection and deterministic replacement of API keys, private keys, bearer tokens,
     connection strings, webhook secrets, JWTs, and secret assignments.
   - Format invariant: [REDACTED:<type>:<hash8>].
   - Repeat correlation: identical secrets yield identical 8-char SHA-256 slices.
   - Idempotency: already-redacted text is not double-redacted.
   - Parity with client-side extension hasher.
2. Re-check Service:
   - Defense-in-depth: independently catches secrets missed by client and increments counts.
3. Excluded Credential Path Guard:
   - Path-only protection for .env, .pem, .key, id_rsa, etc.
4. Consented Snippet Upload Endpoint (POST /api/v1/ext/projects/{pid}/snippets):
   - Mandatory Idempotency-Key header enforcement.
   - Active consent verification (403 consent.required on missing/revoked/expired consent).
   - Credential file rejection with 422 validation.failed.
   - Line range validation with 422 validation.failed.
   - Successful ingestion with 201 Created and receipt metadata.
   - Tenant isolation and permission enforcement.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID

from starlette.testclient import TestClient

from app.core.auth_context import AuthContext
from app.core.errors import ConsentRequiredError, ForbiddenError
from app.core.ids import generate_uuid7
from app.core.settings import Settings
from app.domain.auth import PERM_PROJECT_SYNC, get_db_session, get_extension_auth_context
from app.domain.brain.redaction_service import (
    RedactionService,
    compute_redacted_token_hash,
    is_excluded_credential_path,
)
from app.main import create_app

# ---------------------------------------------------------------------------
# Unit Tests: Redaction Engine & Hasher
# ---------------------------------------------------------------------------


def test_redact_api_keys_and_tokens() -> None:
    """Verifies deterministic redaction of API keys, webhooks, and JWTs."""
    raw_stripe = "_".join(["sk", "live", "1234567890abcdef12345678"])
    raw_anthropic = "-".join(["sk", "ant", "api03-abcdefghijklmnopqrstuvwxyz1234567890"])
    raw_openai = "-".join(["sk", "abcdefghijklmnopqrstuvwxyz1234567890"])
    raw_github = "_".join(["ghp", "1234567890abcdefghijklmnopqrstuvwxyz"])
    raw_aws = "AKIA1234567890ABCDEF"
    raw_whsec = "_".join(["whsec", "5432109876543210abcdefghijklmnop"])
    raw_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozGz64flt_example_signature_12345"

    text = f"""
    stripe_key = "{raw_stripe}"
    anthropic_key = "{raw_anthropic}"
    openai_key = "{raw_openai}"
    github_pat = "{raw_github}"
    aws_key = "{raw_aws}"
    webhook_secret = "{raw_whsec}"
    auth_token = "{raw_jwt}"
    """

    res = RedactionService.redact(text)

    assert res.redaction_count == 7
    assert res.counts_by_type["api_key"] == 5
    assert res.counts_by_type["token"] == 2

    # Assert raw secrets are completely eliminated
    assert raw_stripe not in res.redacted_text
    assert raw_anthropic not in res.redacted_text
    assert raw_openai not in res.redacted_text
    assert raw_github not in res.redacted_text
    assert raw_aws not in res.redacted_text
    assert raw_whsec not in res.redacted_text
    assert raw_jwt not in res.redacted_text

    # Assert deterministic placeholders
    assert f"[REDACTED:api_key:{compute_redacted_token_hash(raw_stripe)}]" in res.redacted_text
    assert f"[REDACTED:api_key:{compute_redacted_token_hash(raw_anthropic)}]" in res.redacted_text
    assert f"[REDACTED:api_key:{compute_redacted_token_hash(raw_openai)}]" in res.redacted_text
    assert f"[REDACTED:api_key:{compute_redacted_token_hash(raw_github)}]" in res.redacted_text
    assert f"[REDACTED:api_key:{compute_redacted_token_hash(raw_aws)}]" in res.redacted_text
    assert f"[REDACTED:token:{compute_redacted_token_hash(raw_whsec)}]" in res.redacted_text
    assert f"[REDACTED:token:{compute_redacted_token_hash(raw_jwt)}]" in res.redacted_text


def test_redact_private_keys_bearer_and_connection_strings() -> None:
    """Verifies private key blocks, bearer tokens, and connection string password masking."""
    pk_block = (
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0Y1xyz...\n-----END RSA PRIVATE KEY-----"
    )
    raw_bearer = "dme_at_super_secret_bearer_token_12345"
    raw_db_pass = "superSecretPassword123!"

    text = f"""
    const privateKey = `{pk_block}`;
    const header = "Authorization: Bearer {raw_bearer}";
    const dbUrl = "postgres://devmind_user:{raw_db_pass}@localhost:5432/devmind_db";
    """

    res = RedactionService.redact(text)

    assert res.redaction_count == 3
    assert res.counts_by_type["private_key"] == 1
    assert res.counts_by_type["bearer_token"] == 1
    assert res.counts_by_type["connection_string"] == 1

    assert pk_block not in res.redacted_text
    assert raw_bearer not in res.redacted_text
    assert raw_db_pass not in res.redacted_text

    assert f"[REDACTED:private_key:{compute_redacted_token_hash(pk_block)}]" in res.redacted_text
    assert (
        f"Authorization: Bearer [REDACTED:bearer_token:{compute_redacted_token_hash(raw_bearer)}]"
        in res.redacted_text
    )
    assert (
        f"postgres://devmind_user:[REDACTED:connection_string:{compute_redacted_token_hash(raw_db_pass)}]@localhost:5432/devmind_db"
        in res.redacted_text
    )


def test_redact_repeat_correlation_and_idempotency() -> None:
    """Repeat tokens produce identical hash8, and subsequent passes are idempotent."""
    token = "_".join(["sk", "live", "repeattoken1234567890abcdef"])
    text = f"Key1: {token}\nKey2: {token}"

    first_pass = RedactionService.redact(text)
    assert first_pass.redaction_count == 2
    h8 = compute_redacted_token_hash(token)
    assert (
        first_pass.redacted_text == f"Key1: [REDACTED:api_key:{h8}]\nKey2: [REDACTED:api_key:{h8}]"
    )

    # Second pass must not double-redact
    second_pass = RedactionService.redact(first_pass.redacted_text)
    assert second_pass.redaction_count == 0
    assert second_pass.redacted_text == first_pass.redacted_text


def test_redaction_parity_with_extension() -> None:
    """Verifies hash parity with extension implementation for known reference tokens."""
    ref_token = "-".join(["sk", "ant", "test12345678901234567890123456"])
    assert compute_redacted_token_hash(ref_token) == "dbaf8329"


def test_recheck_client_redaction_catches_missed_secrets() -> None:
    """Re-check catches secrets that client scanner missed (defense-in-depth)."""
    # Text with 1 client-redacted secret and 1 unredacted secret
    unredacted_key = "_".join(["sk", "live", "unredactedkey12345678901234"])
    already_redacted_token = "[REDACTED:api_key:abcdef12]"
    text = f"Known: {already_redacted_token}\nMissed: {unredacted_key}"

    redacted_text, total_count, counts_by_type = RedactionService.recheck_client_redaction(
        text, client_redaction_count=1
    )

    assert total_count == 2
    assert counts_by_type.get("api_key") == 1
    assert unredacted_key not in redacted_text
    assert f"[REDACTED:api_key:{compute_redacted_token_hash(unredacted_key)}]" in redacted_text


# ---------------------------------------------------------------------------
# Unit Tests: Excluded Credential Paths
# ---------------------------------------------------------------------------


def test_is_excluded_credential_path() -> None:
    """Verifies that credential and private key paths are strictly path-only."""
    # Should be excluded (path-only)
    assert is_excluded_credential_path(".env") is True
    assert is_excluded_credential_path(".env.local") is True
    assert is_excluded_credential_path(".env.production") is True
    assert is_excluded_credential_path("config/.env") is True
    assert is_excluded_credential_path("secrets/server.key") is True
    assert is_excluded_credential_path("certs/cert.pem") is True
    assert is_excluded_credential_path("id_rsa") is True
    assert is_excluded_credential_path(".ssh/id_rsa.pub") is True
    assert is_excluded_credential_path("credentials.json") is True
    assert is_excluded_credential_path("vault/passwords.kdbx") is True

    # Safe source code and documentation paths
    assert is_excluded_credential_path("src/index.ts") is False
    assert is_excluded_credential_path("backend/app/routes/admin.py") is False
    assert is_excluded_credential_path("README.md") is False
    assert is_excluded_credential_path("package.json") is False


# ---------------------------------------------------------------------------
# API Integration Tests: POST /api/v1/ext/projects/{pid}/snippets
# ---------------------------------------------------------------------------


def _make_ext_ctx(
    workspace_id: UUID,
    user_id: UUID,
    permissions: list[str] | None = None,
) -> AuthContext:
    perms = permissions if permissions is not None else [PERM_PROJECT_SYNC]
    return AuthContext(
        user_id=user_id,
        clerk_user_id="clerk_test_ext",
        email="test_ext@devmind.local",
        workspace_id=workspace_id,
        permissions=frozenset(perms),
    )


def test_post_snippets_missing_idempotency_key(test_settings: Settings) -> None:
    """Route strictly requires Idempotency-Key header per docs/03 §10."""
    pid = generate_uuid7()
    app = create_app(settings=test_settings)
    client = TestClient(app)

    res = client.post(
        f"/api/v1/ext/projects/{pid}/snippets",
        json={"consent_id": str(generate_uuid7()), "snippets": []},
    )
    assert res.status_code == 422
    data = res.json()
    assert data["code"] == "validation.failed"
    assert "Idempotency-Key" in data["detail"]


def test_post_snippets_requires_active_consent(test_settings: Settings) -> None:
    """Fails with 403 consent.required when active consent is missing or revoked."""
    workspace_id = generate_uuid7()
    pid = generate_uuid7()
    user_id = generate_uuid7()
    consent_id = generate_uuid7()

    ctx = _make_ext_ctx(workspace_id=workspace_id, user_id=user_id)
    app = create_app(settings=test_settings)
    app.dependency_overrides[get_extension_auth_context] = lambda: ctx
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    client = TestClient(app)

    with (
        patch(
            "app.domain.brain.manifest_service.ManifestService.resolve_project_context",
            return_value=ctx,
        ),
        patch(
            "app.domain.consent.consent_service.ConsentService.verify_consent",
            side_effect=ConsentRequiredError(
                detail="This operation requires active 'snippet_transmission' consent."
            ),
        ),
    ):
        res = client.post(
            f"/api/v1/ext/projects/{pid}/snippets",
            headers={"Idempotency-Key": "test-key-consent-req"},
            json={
                "consent_id": str(consent_id),
                "snippets": [
                    {
                        "path": "app/main.py",
                        "file_content_hash": "sha256:1234",
                        "start_line": 1,
                        "end_line": 10,
                        "content": "print('hello')",
                        "redaction_count": 0,
                    }
                ],
            },
        )

        assert res.status_code == 403
        data = res.json()
        assert data["code"] == "consent.required"


def test_post_snippets_rejects_credential_path(test_settings: Settings) -> None:
    """Strictly rejects excluded credential files (.env, .pem, etc.) with 422 validation.failed."""
    workspace_id = generate_uuid7()
    pid = generate_uuid7()
    user_id = generate_uuid7()
    consent_id = generate_uuid7()

    ctx = _make_ext_ctx(workspace_id=workspace_id, user_id=user_id)
    app = create_app(settings=test_settings)
    app.dependency_overrides[get_extension_auth_context] = lambda: ctx
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    client = TestClient(app)

    with (
        patch(
            "app.domain.brain.manifest_service.ManifestService.resolve_project_context",
            return_value=ctx,
        ),
        patch(
            "app.domain.consent.consent_service.ConsentService.verify_consent", return_value=None
        ),
    ):
        res = client.post(
            f"/api/v1/ext/projects/{pid}/snippets",
            headers={"Idempotency-Key": "test-key-cred-path"},
            json={
                "consent_id": str(consent_id),
                "snippets": [
                    {
                        "path": "backend/.env.production",
                        "file_content_hash": "sha256:1234",
                        "start_line": 1,
                        "end_line": 5,
                        "content": "DATABASE_URL=postgres://...",
                        "redaction_count": 1,
                    }
                ],
            },
        )

        assert res.status_code == 422
        data = res.json()
        assert data["code"] == "validation.failed"
        assert "excluded credential file" in data["detail"]


def test_post_snippets_rejects_invalid_line_range(test_settings: Settings) -> None:
    """Rejects snippets where start_line > end_line."""
    workspace_id = generate_uuid7()
    pid = generate_uuid7()
    user_id = generate_uuid7()
    consent_id = generate_uuid7()

    ctx = _make_ext_ctx(workspace_id=workspace_id, user_id=user_id)
    app = create_app(settings=test_settings)
    app.dependency_overrides[get_extension_auth_context] = lambda: ctx
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    client = TestClient(app)

    with (
        patch(
            "app.domain.brain.manifest_service.ManifestService.resolve_project_context",
            return_value=ctx,
        ),
        patch(
            "app.domain.consent.consent_service.ConsentService.verify_consent", return_value=None
        ),
    ):
        res = client.post(
            f"/api/v1/ext/projects/{pid}/snippets",
            headers={"Idempotency-Key": "test-key-line-range"},
            json={
                "consent_id": str(consent_id),
                "snippets": [
                    {
                        "path": "app/routes/users.py",
                        "file_content_hash": "sha256:1234",
                        "start_line": 50,
                        "end_line": 20,  # Invalid: end < start
                        "content": "def get_users(): pass",
                        "redaction_count": 0,
                    }
                ],
            },
        )

        assert res.status_code == 422
        data = res.json()
        assert data["code"] == "validation.failed"
        assert "Invalid line range" in data["detail"]


def test_post_snippets_success_with_server_redaction(test_settings: Settings) -> None:
    """Valid consented snippet upload succeeds and runs server-side defense-in-depth redaction."""
    workspace_id = generate_uuid7()
    pid = generate_uuid7()
    user_id = generate_uuid7()
    consent_id = generate_uuid7()

    ctx = _make_ext_ctx(workspace_id=workspace_id, user_id=user_id)
    app = create_app(settings=test_settings)
    app.dependency_overrides[get_extension_auth_context] = lambda: ctx
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    client = TestClient(app)

    # Snippet with an already redacted token AND an unredacted secret the client missed
    unredacted_key = "_".join(["sk", "live", "unredactedkey12345678901234"])
    content = f"client_token = '[REDACTED:api_key:12345678]'\nmissed = '{unredacted_key}'"

    with (
        patch(
            "app.domain.brain.manifest_service.ManifestService.resolve_project_context",
            return_value=ctx,
        ),
        patch(
            "app.domain.consent.consent_service.ConsentService.verify_consent", return_value=None
        ),
    ):
        res = client.post(
            f"/api/v1/ext/projects/{pid}/snippets",
            headers={"Idempotency-Key": "test-key-success-snippet"},
            json={
                "consent_id": str(consent_id),
                "purpose": {"kind": "analysis", "job_type": "security_review"},
                "snippets": [
                    {
                        "path": "backend/app/routes/admin.py",
                        "file_content_hash": "sha256:abcd1234",
                        "start_line": 10,
                        "end_line": 25,
                        "content": content,
                        "redaction_count": 1,
                        "client_redaction_version": "1",
                    }
                ],
            },
        )

        assert res.status_code == 201
        data = res.json()
        assert data["accepted_snippets_count"] == 1
        assert data["total_redaction_count"] == 2
        assert data["server_redactions_added"] == 1
        assert data["receipt_hash"].startswith("sha256:")
        assert len(data["snippets"]) == 1
        assert data["snippets"][0]["path"] == "backend/app/routes/admin.py"
        assert data["snippets"][0]["redaction_count"] == 2


def test_post_snippets_forbidden_for_other_tenant(test_settings: Settings) -> None:
    """Forbidden when caller token belongs to a different workspace/tenant."""
    workspace_id = generate_uuid7()
    pid = generate_uuid7()
    user_id = generate_uuid7()

    ctx = _make_ext_ctx(workspace_id=workspace_id, user_id=user_id)
    app = create_app(settings=test_settings)
    app.dependency_overrides[get_extension_auth_context] = lambda: ctx
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    client = TestClient(app)

    with patch(
        "app.domain.brain.manifest_service.ManifestService.resolve_project_context",
        side_effect=ForbiddenError(
            detail="Access denied: project does not belong to caller workspace"
        ),
    ):
        res = client.post(
            f"/api/v1/ext/projects/{pid}/snippets",
            headers={"Idempotency-Key": "test-key-forbidden-tenant"},
            json={
                "consent_id": str(generate_uuid7()),
                "snippets": [],
            },
        )

        assert res.status_code == 403
        data = res.json()
        assert data["code"] == "auth.forbidden"
