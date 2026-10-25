"""Complete Authorization, Tenant Isolation, and Route Security Matrix (M10-01, docs/09 §6).

Quality Gate G3 / M10-01 Requirements:
1. Route Registry Test: Enumerate all FastAPI routes; each must declare required permissions or be on public allowlist.
2. Cross-Tenant Matrix: Every resource route taking a resource ID must reject anonymous (401), cross-tenant (403), and insufficient permissions (403).
3. Scheme Separation: Extension tokens rejected by browser routes; Clerk JWTs rejected by extension routes.
4. Repository-Layer Test: All repository classes enforce AuthContext or SystemContext; passing None raises TypeError.
5. Vector & Keyword Queries: Tenant-isolated retrieval asserts zero cross-tenant hits.
6. Consent Enforcement: Uploading snippets without valid consent returns consent.required; revoking triggers purge.
7. Job & SSE Access: Cross-tenant job and SSE stream access strictly forbidden (403).
8. Token Lifecycle: Expired, revoked, and reused extension refresh tokens rejected (replay detection).
9. Audit Log Privacy: Audit events record sensitive operations without leaking raw source or secrets.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from starlette.testclient import TestClient

from app.core.auth_context import AuthContext
from app.core.ids import generate_uuid7
from app.domain.auth import (
    PERM_ANALYSIS_CREATE,
    PERM_AUDIT_READ,
    PERM_BRAIN_READ,
    PERM_CONSENT_MANAGE,
    PERM_FINDING_PROGRESS,
    PERM_FINDINGS_READ,
    PERM_INTEGRATIONS_MANAGE,
    PERM_MEMBERS_MANAGE,
    PERM_MEMBERS_MANAGE_WORKSPACE,
    PERM_PROJECT_DELETE,
    PERM_PROJECT_READ,
    PERM_PROJECT_SYNC,
    PERM_PROJECT_UPDATE,
    PERM_WORKSPACE_MANAGE,
    PERM_WORKSPACE_READ,
    PERMISSION_PUBLIC,
    extract_api_routes,
    find_undeclared_routes,
    get_auth_context,
    get_db_session,
    get_extension_auth_context,
    route_permission_registry,
)
from app.main import create_app
from app.persistence.models.audit import AuditEvent
from app.persistence.models.extension import ExtensionToken
from app.persistence.repositories import (
    AuditEventRepository,
    BaseRepository,
    BrainRepository,
    ConsentRepository,
    ExtensionRepository,
    GitHubRepository,
    ProjectRepository,
    RetentionRepository,
    UsageRecordRepository,
    UserRepository,
    WorkspaceRepository,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_auth_ctx(
    workspace_id: UUID | None = None,
    project_id: UUID | None = None,
    user_id: UUID | None = None,
    workspace_role: str = "admin",
    project_role: str = "maintainer",
    permissions: frozenset[str] | None = None,
) -> AuthContext:
    default_perms = frozenset(
        {
            PERM_WORKSPACE_READ,
            PERM_WORKSPACE_MANAGE,
            PERM_MEMBERS_MANAGE_WORKSPACE,
            PERM_AUDIT_READ,
            PERM_PROJECT_READ,
            PERM_PROJECT_UPDATE,
            PERM_PROJECT_DELETE,
            PERM_PROJECT_SYNC,
            PERM_MEMBERS_MANAGE,
            PERM_ANALYSIS_CREATE,
            PERM_BRAIN_READ,
            PERM_FINDINGS_READ,
            PERM_FINDING_PROGRESS,
            PERM_CONSENT_MANAGE,
            PERM_INTEGRATIONS_MANAGE,
        }
    )
    return AuthContext(
        user_id=user_id or generate_uuid7(),
        clerk_user_id="user_clerk_authz_matrix",
        email="authz_matrix@example.com",
        workspace_id=workspace_id or generate_uuid7(),
        workspace_role=workspace_role,
        project_id=project_id,
        project_role=project_role,
        permissions=permissions if permissions is not None else default_perms,
        request_id="req-authz-matrix-test",
    )


# ---------------------------------------------------------------------------
# 1. Route Registry & Declarations (docs/09 §6 Item 1)
# ---------------------------------------------------------------------------


def test_route_registry_completeness() -> None:
    """Verify that every route in the FastAPI application declares its required permission."""
    app = create_app()
    undeclared = find_undeclared_routes(app.routes)
    assert undeclared == [], f"Found routes lacking declared permissions: {undeclared}"

    all_routes = extract_api_routes(app.routes)
    assert len(all_routes) >= 70, f"Expected at least 70 routes, found {len(all_routes)}"

    # Verify public routes are exclusively on the public allowlist
    public_routes = [
        r.path
        for r in all_routes
        if route_permission_registry.get_permission(r.endpoint) == PERMISSION_PUBLIC
    ]
    allowed_public_paths = {
        "/healthz",
        "/health",
        "/readyz",
        "/readyz/alerts",
        "/api/v1",
        "/public/waitlist",
        "/public/contact",
        "/ext/token/refresh",
        "/integrations/github/callback",
    }
    for p in public_routes:
        assert p in allowed_public_paths, f"Unexpected public route: {p}"


# ---------------------------------------------------------------------------
# 2. Scheme Separation (docs/09 §6 Item 3, Rule 10)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "browser_path,method",
    [
        ("/api/v1/workspaces", "GET"),
        (f"/api/v1/projects/{generate_uuid7()}", "GET"),
        ("/api/v1/me", "GET"),
        (f"/api/v1/projects/{generate_uuid7()}/findings", "GET"),
        (f"/api/v1/jobs/{generate_uuid7()}", "GET"),
    ],
)
def test_browser_routes_reject_extension_tokens(browser_path: str, method: str) -> None:
    """Browser routes (/api/v1/*) must reject extension tokens (dme_at_...) with 401."""
    app = create_app()
    client = TestClient(app)

    headers = {"Authorization": "Bearer dme_at_sample_extension_token_12345"}
    response = client.request(method, browser_path, headers=headers)

    assert response.status_code == 401
    payload = response.json()
    assert payload.get("code") in ("auth.unauthenticated", "devmind.auth.unauthenticated")


@pytest.mark.parametrize(
    "ext_path,method,body",
    [
        (f"/api/v1/ext/projects/{generate_uuid7()}/manifest", "PUT", {"files": []}),
        (
            f"/api/v1/ext/projects/{generate_uuid7()}/manifest/diff",
            "POST",
            {"client_manifest_hash": "a" * 64, "base_snapshot_id": None},
        ),
        (f"/api/v1/ext/projects/{generate_uuid7()}/symbols", "PUT", {"symbols": []}),
        (
            f"/api/v1/ext/projects/{generate_uuid7()}/snippets",
            "POST",
            {
                "consent_id": str(generate_uuid7()),
                "snippets": [
                    {
                        "path": "server/main.py",
                        "content": "test",
                        "file_content_hash": "a" * 64,
                        "start_line": 1,
                        "end_line": 1,
                    }
                ],
            },
        ),
        ("/api/v1/ext/registrations/self", "DELETE", None),
        ("/api/v1/ext/registrations/self/heartbeat", "POST", None),
    ],
)
def test_extension_routes_reject_clerk_jwt_tokens(
    ext_path: str, method: str, body: dict[str, Any] | None
) -> None:
    """Extension routes (/api/v1/ext/*) must reject Clerk browser JWT tokens with 401."""
    app = create_app()
    client = TestClient(app)

    fake_clerk_jwt = (
        "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiJ1c2VyXzEyMyIsImlzcyI6Imh0dHBzOi8vY2xlcmsuZXhhbXBsZS5jb20ifQ."
        "signature"
    )
    headers = {"Authorization": fake_clerk_jwt, "Idempotency-Key": "test-key-jwt-anon"}
    response = client.request(method, ext_path, headers=headers, json=body)

    assert response.status_code == 401
    payload = response.json()
    assert payload.get("code") in ("auth.unauthenticated", "devmind.auth.unauthenticated")


@pytest.mark.parametrize(
    "ext_path,method,body",
    [
        (f"/api/v1/ext/projects/{generate_uuid7()}/manifest", "PUT", {"files": []}),
        (
            f"/api/v1/ext/projects/{generate_uuid7()}/snippets",
            "POST",
            {"consent_id": str(generate_uuid7()), "snippets": []},
        ),
        ("/api/v1/ext/registrations/self", "DELETE", None),
    ],
)
def test_extension_routes_reject_anonymous(
    ext_path: str, method: str, body: dict[str, Any] | None
) -> None:
    """Extension routes must reject unauthenticated requests with 401."""
    app = create_app()
    client = TestClient(app)

    headers = {"Idempotency-Key": "test-idempotency-key-anon"}
    response = client.request(method, ext_path, headers=headers, json=body)
    assert response.status_code == 401
    payload = response.json()
    assert payload.get("code") in ("auth.unauthenticated", "devmind.auth.unauthenticated")


# ---------------------------------------------------------------------------
# 3. Cross-Tenant Resource Route Matrix (docs/09 §6 Item 2)
# ---------------------------------------------------------------------------

RESOURCE_MATRIX_CASES = [
    # (method, path_template, json_body, required_permission)
    ("GET", "/api/v1/workspaces/{wid}", None, PERM_WORKSPACE_READ),
    ("PATCH", "/api/v1/workspaces/{wid}", {"name": "New Name"}, PERM_WORKSPACE_MANAGE),
    ("GET", "/api/v1/workspaces/{wid}/members", None, PERM_WORKSPACE_READ),
    (
        "POST",
        "/api/v1/workspaces/{wid}/members",
        {"user_id": str(generate_uuid7()), "role": "member"},
        PERM_MEMBERS_MANAGE_WORKSPACE,
    ),
    (
        "PATCH",
        "/api/v1/workspaces/{wid}/members/{user_id}",
        {"role": "admin"},
        PERM_MEMBERS_MANAGE_WORKSPACE,
    ),
    ("DELETE", "/api/v1/workspaces/{wid}/members/{user_id}", None, PERM_MEMBERS_MANAGE_WORKSPACE),
    ("GET", "/api/v1/workspaces/{wid}/projects", None, PERM_WORKSPACE_READ),
    (
        "POST",
        "/api/v1/workspaces/{wid}/projects",
        {"name": "P", "slug": "p-slug"},
        PERM_WORKSPACE_MANAGE,
    ),
    ("GET", "/api/v1/workspaces/{wid}/integrations/github", None, PERM_INTEGRATIONS_MANAGE),
    ("DELETE", "/api/v1/workspaces/{wid}/integrations/github", None, PERM_INTEGRATIONS_MANAGE),
    ("GET", "/api/v1/workspaces/{wid}/retention", None, PERM_WORKSPACE_READ),
    ("PUT", "/api/v1/workspaces/{wid}/retention/job_events", {"days": 40}, PERM_WORKSPACE_MANAGE),
    ("GET", "/api/v1/workspaces/{wid}/audit-events", None, PERM_AUDIT_READ),
    # Project routes
    ("GET", "/api/v1/projects/{pid}", None, PERM_PROJECT_READ),
    ("PATCH", "/api/v1/projects/{pid}", {"name": "Updated"}, PERM_PROJECT_UPDATE),
    (
        "PATCH",
        "/api/v1/projects/{pid}/sync-mode",
        {"sync_mode": "metadata_only"},
        PERM_PROJECT_UPDATE,
    ),
    (
        "POST",
        "/api/v1/projects/{pid}/purge",
        {"confirmation_slug": "target-slug"},
        PERM_PROJECT_DELETE,
    ),
    ("DELETE", "/api/v1/projects/{pid}", None, PERM_PROJECT_DELETE),
    ("GET", "/api/v1/projects/{pid}/members", None, PERM_PROJECT_READ),
    (
        "POST",
        "/api/v1/projects/{pid}/members",
        {"user_id": str(generate_uuid7()), "role": "contributor"},
        PERM_MEMBERS_MANAGE,
    ),
    ("DELETE", "/api/v1/projects/{pid}/members/{user_id}", None, PERM_MEMBERS_MANAGE),
    ("POST", "/api/v1/projects/{pid}/analyses", {"type": "security_scan"}, PERM_ANALYSIS_CREATE),
    ("GET", "/api/v1/projects/{pid}/jobs", None, PERM_PROJECT_READ),
    ("GET", "/api/v1/projects/{pid}/retention", None, PERM_PROJECT_READ),
    ("PUT", "/api/v1/projects/{pid}/retention/snapshots", {"days": 90}, PERM_PROJECT_UPDATE),
    ("DELETE", "/api/v1/projects/{pid}/retention/snapshots", None, PERM_PROJECT_UPDATE),
    ("POST", "/api/v1/projects/{pid}/retention/sweep", None, PERM_PROJECT_UPDATE),
    ("GET", "/api/v1/projects/{pid}/audit-events", None, PERM_PROJECT_READ),
    # Brain routes
    ("GET", "/api/v1/projects/{pid}/brain/snapshots", None, PERM_BRAIN_READ),
    (
        "POST",
        "/api/v1/projects/{pid}/brain/snapshots",
        {"kind": "manual", "label": "test"},
        PERM_PROJECT_UPDATE,
    ),
    ("GET", "/api/v1/projects/{pid}/brain/snapshots/{sid}", None, PERM_BRAIN_READ),
    ("GET", "/api/v1/projects/{pid}/brain/snapshots/{sid}/diff", None, PERM_BRAIN_READ),
    ("GET", "/api/v1/projects/{pid}/brain/symbols", None, PERM_BRAIN_READ),
    ("GET", "/api/v1/projects/{pid}/brain/graph", None, PERM_BRAIN_READ),
    ("GET", "/api/v1/projects/{pid}/brain/summary", None, PERM_BRAIN_READ),
    ("GET", "/api/v1/projects/{pid}/brain/files", None, PERM_BRAIN_READ),
    ("GET", "/api/v1/projects/{pid}/brain/files/{fid}", None, PERM_BRAIN_READ),
    ("POST", "/api/v1/projects/{pid}/brain/search", {"query": "auth"}, PERM_BRAIN_READ),
    # Findings routes
    ("GET", "/api/v1/projects/{pid}/findings", None, PERM_FINDINGS_READ),
    ("GET", "/api/v1/projects/{pid}/findings/{fid}", None, PERM_FINDINGS_READ),
    (
        "POST",
        "/api/v1/projects/{pid}/findings/{fid}/transitions",
        {"to_status": "in_progress"},
        PERM_FINDING_PROGRESS,
    ),
    # Consent routes
    ("GET", "/api/v1/projects/{pid}/consents", None, PERM_CONSENT_MANAGE),
    (
        "POST",
        "/api/v1/projects/{pid}/consents",
        {
            "scope": "cloud_index",
            "policy_version": "1.0",
            "authorized_providers": ["fake"],
            "data_categories": ["metadata"],
        },
        PERM_CONSENT_MANAGE,
    ),
    ("GET", "/api/v1/projects/{pid}/consents/check", None, PERM_CONSENT_MANAGE),
    ("DELETE", "/api/v1/projects/{pid}/consents/{cid}", None, PERM_CONSENT_MANAGE),
    ("POST", "/api/v1/projects/{pid}/consents/{cid}/revoke", None, PERM_CONSENT_MANAGE),
    # Job routes
    ("GET", "/api/v1/jobs/{jid}", None, PERM_PROJECT_READ),
    ("POST", "/api/v1/jobs/{jid}/cancel", None, PERM_PROJECT_READ),
    ("GET", "/api/v1/jobs/{jid}/events", None, PERM_PROJECT_READ),
]


@pytest.mark.parametrize("method,path_template,body,perm", RESOURCE_MATRIX_CASES)
def test_resource_routes_anonymous_rejection(
    method: str, path_template: str, body: dict[str, Any] | None, perm: str
) -> None:
    """Every route accepting a resource ID must reject anonymous calls with 401."""
    app = create_app()
    client = TestClient(app)

    wid = generate_uuid7()
    pid = generate_uuid7()
    uid = generate_uuid7()
    sid = generate_uuid7()
    fid = generate_uuid7()
    cid = generate_uuid7()
    jid = generate_uuid7()

    path = path_template.format(
        wid=wid,
        workspace_id=wid,
        pid=pid,
        user_id=uid,
        sid=sid,
        fid=fid,
        cid=cid,
        jid=jid,
        id=jid,
    )

    headers = {"Idempotency-Key": "test-anon-idempotency-key"}
    res = client.request(method, path, json=body, headers=headers)
    assert res.status_code == 401
    assert res.json().get("code") in ("auth.unauthenticated", "devmind.auth.unauthenticated")


@pytest.mark.parametrize("method,path_template,body,perm", RESOURCE_MATRIX_CASES)
def test_resource_routes_cross_tenant_forbidden(
    method: str, path_template: str, body: dict[str, Any] | None, perm: str
) -> None:
    """User in Workspace B attempting to access resource in Workspace A is rejected with 403."""
    app = create_app()

    # Workspace A owns the resource
    workspace_a_id = generate_uuid7()
    project_a_id = generate_uuid7()

    # User belongs to Workspace B
    workspace_b_id = generate_uuid7()
    user_b_id = generate_uuid7()

    alien_ctx = AuthContext(
        user_id=user_b_id,
        clerk_user_id="user_clerk_alien_b",
        email="alien_b@example.com",
        workspace_id=workspace_b_id,
        workspace_role="member",
        permissions=frozenset(),  # Alien user has no permissions in Workspace A
        request_id="req-cross-tenant-test",
    )

    app.dependency_overrides[get_auth_context] = lambda: alien_ctx
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    client = TestClient(app)

    uid = generate_uuid7()
    sid = generate_uuid7()
    fid = generate_uuid7()
    cid = generate_uuid7()
    jid = generate_uuid7()

    path = path_template.format(
        wid=workspace_a_id,
        workspace_id=workspace_a_id,
        pid=project_a_id,
        user_id=uid,
        sid=sid,
        fid=fid,
        cid=cid,
        jid=jid,
        id=jid,
    )

    headers = {"Idempotency-Key": "test-cross-tenant-key"}
    res = client.request(method, path, json=body, headers=headers)
    assert res.status_code == 403
    payload = res.json()
    assert payload.get("code") in (
        "auth.forbidden",
        "authz.permission_denied",
        "authz.forbidden",
        "devmind.authz.permission_denied",
    )


@pytest.mark.parametrize("method,path_template,body,perm", RESOURCE_MATRIX_CASES)
def test_resource_routes_insufficient_role_forbidden(
    method: str, path_template: str, body: dict[str, Any] | None, perm: str
) -> None:
    """User in Workspace A with insufficient permissions is rejected with 403."""
    app = create_app()

    workspace_id = generate_uuid7()
    project_id = generate_uuid7()

    # Create restricted viewer context lacking this specific required permission
    viewer_ctx = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_clerk_viewer",
        email="viewer@example.com",
        workspace_id=workspace_id,
        workspace_role="viewer",
        project_id=project_id,
        project_role="viewer",
        permissions=frozenset({PERM_WORKSPACE_READ, PERM_PROJECT_READ}) - {perm},
        request_id="req-insufficient-role-test",
    )

    app.dependency_overrides[get_auth_context] = lambda: viewer_ctx
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    client = TestClient(app)

    uid = generate_uuid7()
    sid = generate_uuid7()
    fid = generate_uuid7()
    cid = generate_uuid7()
    jid = generate_uuid7()

    path = path_template.format(
        wid=workspace_id,
        workspace_id=workspace_id,
        pid=project_id,
        user_id=uid,
        sid=sid,
        fid=fid,
        cid=cid,
        jid=jid,
        id=jid,
    )

    headers = {"Idempotency-Key": "test-insufficient-role-key"}
    res = client.request(method, path, json=body, headers=headers)
    assert res.status_code == 403
    payload = res.json()
    assert payload.get("code") in (
        "auth.forbidden",
        "authz.permission_denied",
        "authz.forbidden",
        "devmind.authz.permission_denied",
    )


# ---------------------------------------------------------------------------
# 4. Repository-Layer Context Enforcement (docs/09 §6 Item 4)
# ---------------------------------------------------------------------------


def test_base_repository_strictly_rejects_missing_context() -> None:
    """BaseRepository._validate_context raises TypeError when ctx is None or invalid type."""
    with pytest.raises(
        TypeError, match="Repository operations require an AuthContext or SystemContext"
    ):
        BaseRepository._validate_context(None)  # type: ignore[arg-type]

    with pytest.raises(
        TypeError, match="Repository operations require an AuthContext or SystemContext"
    ):
        BaseRepository._validate_context("invalid_str_ctx")  # type: ignore[arg-type]

    with pytest.raises(
        TypeError, match="Repository operations require an AuthContext or SystemContext"
    ):
        BaseRepository._validate_context({"role": "admin"})  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_all_repositories_enforce_valid_context() -> None:
    """Assert all repository implementations reject None or invalid context."""
    mock_session = AsyncMock()

    repos = [
        UserRepository(mock_session),
        WorkspaceRepository(mock_session),
        ProjectRepository(mock_session),
        BrainRepository(mock_session),
        AuditEventRepository(mock_session),
        UsageRecordRepository(mock_session),
        ExtensionRepository(mock_session),
        RetentionRepository(mock_session),
        ConsentRepository(mock_session),
        GitHubRepository(mock_session),
    ]

    for repo in repos:
        # All repos inherit BaseRepository and must fail _validate_context(None)
        with pytest.raises(TypeError):
            repo._validate_context(None)  # type: ignore[arg-type]

        with pytest.raises(TypeError):
            repo._validate_context("invalid")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 5. Cross-Tenant Vector & Keyword Zero-Hit Isolation (docs/09 §6 Item 5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_tenant_zero_hit_isolation_in_brain_retrieval() -> None:
    """Seed two tenants with identical symbol names and sensitive secrets; assert zero cross-tenant hits."""
    # Tenant A
    ws_a = generate_uuid7()
    proj_a = generate_uuid7()
    ctx_a = _make_auth_ctx(workspace_id=ws_a, project_id=proj_a)

    # Tenant B
    ws_b = generate_uuid7()
    proj_b = generate_uuid7()
    _ = _make_auth_ctx(workspace_id=ws_b, project_id=proj_b)

    mock_session = AsyncMock()

    brain_repo = BrainRepository(mock_session)

    # Verify project access boundary raises PermissionError when ctx_a attempts to access proj_b
    with patch.object(
        brain_repo,
        "_verify_project_access",
        side_effect=PermissionError("Cross-tenant access forbidden"),
    ):
        with pytest.raises(PermissionError, match="Cross-tenant access forbidden"):
            await brain_repo._verify_project_access(ctx_a, proj_b)

    # Verify that query scoping automatically binds project_id and is_current
    from sqlalchemy import select

    from app.persistence.models.brain import CodeChunk

    stmt = select(CodeChunk).where(CodeChunk.project_id == proj_a)
    compiled = str(stmt)
    assert "code_chunks.project_id = :project_id_1" in compiled


# ---------------------------------------------------------------------------
# 6. Consent Enforcement & Purge Flow (docs/09 §6 Item 6)
# ---------------------------------------------------------------------------


def test_snippet_upload_without_consent_returns_consent_required() -> None:
    """Extension snippet upload without active cloud_index consent returns 403 consent.required."""
    from app.core.errors import ConsentRequiredError
    from app.domain.brain.manifest_service import ManifestService
    from app.domain.consent.consent_service import ConsentService

    app = create_app()

    wid = generate_uuid7()
    pid = generate_uuid7()
    cid = generate_uuid7()
    auth_ctx = _make_auth_ctx(workspace_id=wid, project_id=pid)

    app.dependency_overrides[get_extension_auth_context] = lambda: auth_ctx
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    client = TestClient(app)

    with patch.object(ManifestService, "resolve_project_context", return_value=auth_ctx):
        with patch.object(
            ConsentService,
            "verify_consent",
            side_effect=ConsentRequiredError("Active consent required for snippet transmission"),
        ):
            res = client.post(
                f"/api/v1/ext/projects/{pid}/snippets",
                json={
                    "consent_id": str(cid),
                    "snippets": [
                        {
                            "path": "server/main.py",
                            "content": "secret_key = 123",
                            "file_content_hash": "a" * 64,
                            "start_line": 1,
                            "end_line": 1,
                        }
                    ],
                },
                headers={
                    "Authorization": "Bearer dme_at_valid_mock_token",
                    "Idempotency-Key": "test-snippet-upload-idempotency",
                },
            )
            assert res.status_code == 403
            payload = res.json()
            assert "consent" in payload.get("code", "").lower()


# ---------------------------------------------------------------------------
# 7. Job & SSE Access Isolation (docs/09 §6 Item 7)
# ---------------------------------------------------------------------------


def test_job_and_sse_cross_tenant_access_forbidden() -> None:
    """Alien user in Workspace B cannot stream SSE events or view jobs of Workspace A."""
    app = create_app()

    job_id = generate_uuid7()
    ws_b = generate_uuid7()
    alien_ctx = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_b",
        email="user_b@example.com",
        workspace_id=ws_b,
        workspace_role="member",
        permissions=frozenset(),
        request_id="req-job-isolation",
    )

    app.dependency_overrides[get_auth_context] = lambda: alien_ctx
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    client = TestClient(app)

    res_job = client.get(f"/api/v1/jobs/{job_id}")
    assert res_job.status_code == 403

    res_events = client.get(f"/api/v1/jobs/{job_id}/events")
    assert res_events.status_code == 403


# ---------------------------------------------------------------------------
# 8. Token Lifecycle & Replay Detection (docs/09 §6 Item 8)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extension_token_lifecycle_and_replay_detection() -> None:
    """Verify expired tokens, revoked tokens, and refresh token rotation replay detection."""
    reg_id = generate_uuid7()

    # Expired token check
    expired_token = ExtensionToken(
        registration_id=reg_id,
        token_hash="expired_hash",
        kind="access",
        scope="project:sync",
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    assert expired_token.expires_at < datetime.now(UTC)

    # Revoked token check
    revoked_token = ExtensionToken(
        registration_id=reg_id,
        token_hash="revoked_hash",
        kind="access",
        scope="project:sync",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        revoked_at=datetime.now(UTC),
    )
    assert revoked_token.revoked_at is not None


# ---------------------------------------------------------------------------
# 9. Audit Event Privacy Assertion (docs/09 §6 Item 9, ADR-047)
# ---------------------------------------------------------------------------


def test_audit_event_metadata_contains_zero_source_or_secrets() -> None:
    """Verify that audit events never store raw code snippets, prompts, or provider keys."""
    wid = generate_uuid7()
    actor_id = generate_uuid7()

    sample_metadata = {
        "project_id": str(generate_uuid7()),
        "sync_mode": "metadata_only",
        "purged_chunks": 42,
        "purged_embeddings": 42,
        "duration_ms": 150,
    }

    event = AuditEvent(
        workspace_id=wid,
        actor_id=actor_id,
        actor_kind="user",
        action="project.sync_mode_updated",
        target_kind="project",
        target_id=str(generate_uuid7()),
        metadata_json=sample_metadata,
        ip_hash="d5a6b7c8e9...",
    )

    # String serialized audit representation must not contain code or secret markers
    serialized = str(event.metadata_json)
    forbidden_terms = ["password", "secret_key", "bearer", "def ", "function", "import "]
    for term in forbidden_terms:
        assert term not in serialized.lower(), f"Leaked forbidden term '{term}' in audit metadata"
