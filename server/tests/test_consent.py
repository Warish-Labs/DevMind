"""Tests for Consent model, repository, service, and API endpoints (M5-01, docs/03 §3.5, §11.1, docs/07 §7)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from starlette.testclient import TestClient

from app.core.auth_context import AuthContext
from app.core.errors import ConsentRequiredError, ValidationError
from app.core.ids import generate_uuid7
from app.domain.auth import PERM_CONSENT_MANAGE
from app.domain.auth.dependencies import get_auth_context
from app.domain.consent.consent_service import (
    ConsentItem,
    ConsentService,
    CreateConsentRequest,
)
from app.main import create_app
from app.persistence.models.consent import ConsentRecord
from app.persistence.models.project import Project
from app.persistence.repositories.consent_repo import ConsentRepository


def _make_auth_ctx(
    workspace_id: UUID | None = None,
    user_id: UUID | None = None,
    role: str = "maintainer",
) -> AuthContext:
    return AuthContext(
        user_id=user_id or generate_uuid7(),
        clerk_user_id="user_clerk_consent_test",
        email="consent_test@example.com",
        workspace_id=workspace_id or generate_uuid7(),
        workspace_role=role,
        permissions=frozenset({PERM_CONSENT_MANAGE}),
    )


def test_consent_record_model_attributes_and_active_state() -> None:
    """Verify ConsentRecord model properties, defaults, and is_active logic."""
    rec_id = generate_uuid7()
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    user_id = generate_uuid7()
    now = datetime.now(UTC)

    # 1. Active consent (no expiry, no revocation)
    consent = ConsentRecord(
        id=rec_id,
        workspace_id=workspace_id,
        project_id=project_id,
        user_id=user_id,
        scope="snippet_transmission",
        provider_ids=["anthropic", "openai"],
        data_categories=["code_snippets"],
        granted_for="project",
        policy_version="1.0",
        preview_hash="sha256:abc123hash",
        granted_at=now,
    )
    assert consent.is_active(now) is True
    assert consent.scope == "snippet_transmission"
    assert consent.provider_ids == ["anthropic", "openai"]
    assert consent.preview_hash == "sha256:abc123hash"

    # 2. Expired consent
    consent.expires_at = now - timedelta(hours=1)
    assert consent.is_active(now) is False

    # 3. Future expiry
    consent.expires_at = now + timedelta(hours=1)
    assert consent.is_active(now) is True

    # 4. Revoked consent
    consent.revoked_at = now
    assert consent.is_active(now) is False


@pytest.mark.asyncio
async def test_consent_repository_methods_and_tenancy() -> None:
    """Verify ConsentRepository operations and strict tenant isolation."""
    workspace_id = generate_uuid7()
    other_workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    user_id = generate_uuid7()

    ctx = _make_auth_ctx(workspace_id=workspace_id, user_id=user_id)
    other_ctx = _make_auth_ctx(workspace_id=other_workspace_id, user_id=user_id)

    mock_project = Project(
        id=project_id,
        workspace_id=workspace_id,
        name="Test Project",
        slug="test-proj",
    )

    now = datetime.now(UTC)
    mock_record = ConsentRecord(
        id=generate_uuid7(),
        workspace_id=workspace_id,
        project_id=project_id,
        user_id=user_id,
        scope="snippet_transmission",
        provider_ids=["anthropic"],
        data_categories=["code_snippets"],
        granted_for="project",
        policy_version="1.0",
        granted_at=now,
    )

    mock_session = AsyncMock()

    # Setup execute returns for project lookup and records
    async def mock_execute(stmt):
        mock_result = MagicMock()
        stmt_str = str(stmt)
        if "FROM projects" in stmt_str:
            params = stmt.compile().params
            ws_param = params.get("workspace_id_1") or params.get("workspace_id")
            if ws_param == workspace_id:
                mock_result.scalars.return_value.first.return_value = mock_project
            elif ws_param is None:
                mock_result.scalars.return_value.first.return_value = mock_project
            else:
                mock_result.scalars.return_value.first.return_value = None
        elif "FROM consent_records" in stmt_str:
            mock_result.scalars.return_value.all.return_value = [mock_record]
            mock_result.scalars.return_value.first.return_value = mock_record
        return mock_result

    mock_session.execute = AsyncMock(side_effect=mock_execute)

    repo = ConsentRepository(mock_session)

    # 1. Successful creation
    created = await repo.create_consent(
        ctx=ctx,
        project_id=project_id,
        scope="snippet_transmission",
        provider_ids=["anthropic"],
    )
    assert created.project_id == project_id
    assert created.workspace_id == workspace_id
    assert created.scope == "snippet_transmission"

    # 2. Cross-tenant access rejection
    with pytest.raises(PermissionError, match="Access denied"):
        await repo.create_consent(
            ctx=other_ctx,
            project_id=project_id,
            scope="snippet_transmission",
        )

    # 3. Listing consents
    records = await repo.list_consents(ctx=ctx, project_id=project_id)
    assert len(records) == 1
    assert records[0].scope == "snippet_transmission"

    # 4. Check active consent
    assert (
        await repo.has_active_consent(
            ctx=ctx,
            project_id=project_id,
            scope="snippet_transmission",
            provider_id="anthropic",
        )
        is True
    )

    assert (
        await repo.has_active_consent(
            ctx=ctx,
            project_id=project_id,
            scope="snippet_transmission",
            provider_id="openai",
        )
        is False
    )

    # 5. Revocation
    revoked = await repo.revoke_consent(ctx=ctx, project_id=project_id, consent_id=mock_record.id)
    assert revoked is not None
    assert revoked.revoked_at is not None


@pytest.mark.asyncio
async def test_consent_service_validation_and_enforcement(monkeypatch) -> None:
    """Verify ConsentService validation, invalid scope handling, and ConsentRequiredError enforcement."""
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    user_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id, user_id=user_id)

    # 1. Validation failure for invalid scope
    with pytest.raises(ValidationError, match="Invalid consent scope"):
        await ConsentService.create_consent(
            ctx=ctx,
            project_id=project_id,
            req=CreateConsentRequest(scope="invalid_scope"),
        )

    # 2. Validation failure for invalid duration
    with pytest.raises(ValidationError, match="Invalid granted_for"):
        await ConsentService.create_consent(
            ctx=ctx,
            project_id=project_id,
            req=CreateConsentRequest(scope="snippet_transmission", granted_for="forever"),
        )

    # 3. verify_consent raises ConsentRequiredError on missing consent
    class FakeConsentRepo:
        def __init__(self, session):
            pass

        async def has_active_consent(self, ctx, project_id, scope, provider_id=None):
            return False

    monkeypatch.setattr("app.domain.consent.consent_service.ConsentRepository", FakeConsentRepo)

    with pytest.raises(ConsentRequiredError) as exc_info:
        await ConsentService.verify_consent(
            ctx=ctx,
            project_id=project_id,
            scope="snippet_transmission",
            provider_id="anthropic",
        )
    assert exc_info.value.code == "consent.required"
    assert exc_info.value.status_code == 403
    assert "snippet_transmission" in exc_info.value.detail


def test_consent_rest_api_endpoints(monkeypatch, test_settings) -> None:
    """Verify GET, POST, DELETE and check consent endpoints with permissions and problem responses."""
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    user_id = generate_uuid7()
    consent_id = generate_uuid7()

    test_ctx = _make_auth_ctx(workspace_id=workspace_id, user_id=user_id, role="maintainer")

    app = create_app(settings=test_settings)
    app.dependency_overrides[get_auth_context] = lambda: test_ctx

    now_iso = datetime.now(UTC).isoformat()
    mock_item = ConsentItem(
        id=str(consent_id),
        workspace_id=str(workspace_id),
        project_id=str(project_id),
        user_id=str(user_id),
        scope="snippet_transmission",
        provider_ids=["anthropic"],
        data_categories=["code_snippets"],
        granted_for="project",
        policy_version="1.0",
        preview_hash="sha256:abc",
        granted_at=now_iso,
        expires_at=None,
        revoked_at=None,
        is_active=True,
    )

    # Mock ConsentService class methods
    async def mock_list(ctx, project_id, active_only=False, scope=None):
        return [mock_item]

    async def mock_create(ctx, project_id, req):
        return mock_item

    async def mock_revoke(ctx, project_id, consent_id):
        revoked = mock_item.model_copy()
        revoked.revoked_at = now_iso
        revoked.is_active = False
        return revoked

    async def mock_verify(ctx, project_id, scope, provider_id=None):
        if scope != "snippet_transmission":
            raise ConsentRequiredError(detail=f"Operation requires '{scope}' consent")

    monkeypatch.setattr(ConsentService, "list_consents", mock_list)
    monkeypatch.setattr(ConsentService, "create_consent", mock_create)
    monkeypatch.setattr(ConsentService, "revoke_consent", mock_revoke)
    monkeypatch.setattr(ConsentService, "verify_consent", mock_verify)

    client = TestClient(app)

    # 1. GET /api/v1/projects/{pid}/consents
    res = client.get(f"/api/v1/projects/{project_id}/consents")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["scope"] == "snippet_transmission"

    # 2. POST /api/v1/projects/{pid}/consents
    res = client.post(
        f"/api/v1/projects/{project_id}/consents",
        headers={"Idempotency-Key": "test-key-consent-1"},
        json={
            "scope": "snippet_transmission",
            "provider_ids": ["anthropic"],
            "data_categories": ["code_snippets"],
            "granted_for": "project",
        },
    )
    assert res.status_code == 201
    created_data = res.json()
    assert created_data["id"] == str(consent_id)

    # 3. DELETE /api/v1/projects/{pid}/consents/{cid}
    res = client.delete(f"/api/v1/projects/{project_id}/consents/{consent_id}")
    assert res.status_code == 200
    revoked_data = res.json()
    assert revoked_data["is_active"] is False
    assert revoked_data["revoked_at"] is not None

    # 4. GET /api/v1/projects/{pid}/consents/check
    res = client.get(f"/api/v1/projects/{project_id}/consents/check?scope=snippet_transmission")
    assert res.status_code == 200
    assert res.json()["has_consent"] is True

    res = client.get(f"/api/v1/projects/{project_id}/consents/check?scope=cloud_index")
    assert res.status_code == 200
    assert res.json()["has_consent"] is False


@pytest.mark.asyncio
async def test_consent_service_revoke_cloud_index_triggers_purge_and_audit(monkeypatch) -> None:
    """Verify revoking cloud_index consent purges chunks and writes audit event."""
    from contextlib import asynccontextmanager

    project_id = generate_uuid7()
    workspace_id = generate_uuid7()
    consent_id = generate_uuid7()
    user_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=workspace_id, user_id=user_id)

    mock_record = ConsentRecord(
        id=consent_id,
        workspace_id=workspace_id,
        project_id=project_id,
        user_id=user_id,
        scope="cloud_index",
        provider_ids=["google-gemini"],
        data_categories=["code_snippets", "ast_metadata"],
        granted_for="project",
        policy_version="1.0",
        granted_at=datetime.now(UTC),
        revoked_at=datetime.now(UTC),
    )

    mock_project = MagicMock(spec=Project)
    mock_project.id = project_id
    mock_project.sync_mode = "indexed"

    mock_session = AsyncMock()

    @asynccontextmanager
    async def mock_session_scope():
        yield mock_session

    monkeypatch.setattr("app.domain.consent.consent_service.session_scope", mock_session_scope)

    mock_consent_repo = MagicMock()
    mock_consent_repo.revoke_consent = AsyncMock(return_value=mock_record)
    mock_consent_repo.has_active_consent = AsyncMock(return_value=False)
    monkeypatch.setattr(
        "app.domain.consent.consent_service.ConsentRepository", lambda s: mock_consent_repo
    )

    mock_brain_repo = MagicMock()
    mock_brain_repo.purge_project_chunks = AsyncMock(
        return_value={"code_chunks": 42, "embeddings": 42}
    )
    monkeypatch.setattr(
        "app.domain.consent.consent_service.BrainRepository", lambda s: mock_brain_repo
    )

    mock_project_repo = MagicMock()
    mock_project_repo.get_by_id = AsyncMock(return_value=mock_project)
    mock_project_repo.update = AsyncMock(return_value=mock_project)
    monkeypatch.setattr(
        "app.domain.consent.consent_service.ProjectRepository", lambda s: mock_project_repo
    )

    mock_audit_repo = MagicMock()
    mock_audit_repo.record = AsyncMock()
    monkeypatch.setattr(
        "app.domain.consent.consent_service.AuditEventRepository", lambda s: mock_audit_repo
    )

    # Execute revoke
    result = await ConsentService.revoke_consent(ctx, project_id, consent_id)

    assert result.id == str(consent_id)
    assert result.purged_counts == {"code_chunks": 42, "embeddings": 42}
    assert result.sync_mode_updated is True
    assert result.new_sync_mode == "metadata_only"

    # Verify purges and updates were executed
    mock_brain_repo.purge_project_chunks.assert_awaited_once_with(ctx, project_id)
    mock_project_repo.update.assert_awaited_once_with(ctx, project_id, sync_mode="metadata_only")
    mock_audit_repo.record.assert_awaited_once()

    audit_kwargs = mock_audit_repo.record.await_args.kwargs
    assert audit_kwargs["action"] == "consent.revoked"
    assert audit_kwargs["target_id"] == str(consent_id)
    assert audit_kwargs["metadata"]["purged_counts"] == {"code_chunks": 42, "embeddings": 42}
    assert audit_kwargs["metadata"]["sync_mode_updated"] is True
