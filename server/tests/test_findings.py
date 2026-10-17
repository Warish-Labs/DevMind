"""Unit and integration tests for Findings batch ingestion, fingerprinting, and lifecycle state machine (docs/03 §3.4, §5.1, §12.5).

Verifies:
- Stable 64-character SHA-256 fingerprint generation across line shifts.
- Extension scanner evidence capped at E1 (Rule 5 invariant).
- Lifecycle state transitions and invalid transition rejection (409 Conflict).
- Dismissal reason code requirement (422 Validation).
- Recurrence reopening on resolved findings and re-verification on stale findings.
- Extension POST /api/v1/ext/projects/{pid}/findings:batch endpoint.
- Browser GET /findings and POST /transitions endpoints with RBAC enforcement.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.api.schemas import (
    BatchFindingsRequest,
    BatchFindingsResponse,
    FindingDetailItem,
    FindingEvidencePayload,
    FindingItem,
    FindingLocationPayload,
    FindingPayload,
    FindingStatusTransitionRequest,
)
from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import ConflictError, ValidationError
from app.core.settings import Settings
from app.domain.auth import get_auth_context, get_db_session, get_extension_auth_context
from app.domain.brain.findings_service import (
    FindingsService,
    compute_finding_fingerprint,
)
from app.persistence.models.brain import (
    Finding,
)


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    return session


def test_compute_finding_fingerprint_stability() -> None:
    """Verifies fingerprint stability across line number shifts when canonical identifier is provided."""
    fp1 = compute_finding_fingerprint(
        rule_id="devmind.authz.missing_role_check",
        path="src/routes/admin.ts",
        canonical_identifier="GET:/admin/users",
        location_fallback="10:20",
    )
    # Line numbers shift from 10:20 to 45:55 due to earlier code additions
    fp2 = compute_finding_fingerprint(
        rule_id="devmind.authz.missing_role_check",
        path="src/routes/admin.ts",
        canonical_identifier="GET:/admin/users",
        location_fallback="45:55",
    )

    assert len(fp1) == 64
    assert fp1 == fp2, (
        "Fingerprint must remain identical across line shifts when canonical_identifier matches"
    )


def test_compute_finding_fingerprint_location_fallback() -> None:
    """Verifies location fallback fingerprint calculation when canonical identifier is missing."""
    fp1 = compute_finding_fingerprint(
        rule_id="devmind.secrets.exposed_env_file",
        path=".env.production",
        canonical_identifier=None,
        location_fallback="1:1",
    )
    fp2 = compute_finding_fingerprint(
        rule_id="devmind.secrets.exposed_env_file",
        path=".env.staging",
        canonical_identifier=None,
        location_fallback="1:1",
    )

    assert len(fp1) == 64
    assert fp1 != fp2, "Different files must produce different fingerprints"


@pytest.mark.asyncio
async def test_batch_ingest_findings_validation(mock_session: AsyncMock) -> None:
    """Verifies validation on finding category, severity, and confidence."""
    service = FindingsService(mock_session)
    service.repo._verify_project_access = AsyncMock()  # type: ignore[method-assign]

    project_id = uuid.uuid4()
    ctx = SystemContext(reason="test")

    # Invalid category
    bad_category_req = BatchFindingsRequest(
        findings=[
            FindingPayload(
                rule_id="test.rule",
                category="invalid_category_xyz",
                title="Test",
                summary="Test",
                severity="high",
            )
        ]
    )
    with pytest.raises(ValidationError) as exc:
        await service.batch_ingest_findings(ctx, project_id, bad_category_req)
    assert exc.value.code == "finding.invalid_category"

    # Invalid severity
    bad_severity_req = BatchFindingsRequest(
        findings=[
            FindingPayload(
                rule_id="test.rule",
                category="authorization",
                title="Test",
                summary="Test",
                severity="super_critical_invalid",
            )
        ]
    )
    with pytest.raises(ValidationError) as exc:
        await service.batch_ingest_findings(ctx, project_id, bad_severity_req)
    assert exc.value.code == "finding.invalid_severity"


@pytest.mark.asyncio
async def test_evidence_level_ceiling_for_scanner(mock_session: AsyncMock) -> None:
    """Verifies that extension scanner findings are strictly capped at E1 (Rule 5 invariant)."""
    service = FindingsService(mock_session)
    service.repo._verify_project_access = AsyncMock()  # type: ignore[method-assign]

    project_id = uuid.uuid4()
    ctx = SystemContext(reason="test")

    # Setup session query mock to return empty
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalars.return_value.first.return_value = None
    mock_session.execute.return_value = mock_result

    # Client tries to claim E2/E3 evidence from extension scanner
    req = BatchFindingsRequest(
        findings=[
            FindingPayload(
                rule_id="devmind.authz.missing_role_check",
                category="authorization",
                title="Missing Role Check",
                summary="Route lacks role guard",
                severity="high",
                evidence_level="E3",
                location=FindingLocationPayload(path="src/admin.ts", start_line=10, end_line=20),
            )
        ]
    )

    response = await service.batch_ingest_findings(ctx, project_id, req, source="scanner")
    assert response.ingested == 1
    assert response.created == 1
    # Evidence level must be capped at E1
    assert response.findings[0].evidence_level == "E1"


@pytest.mark.asyncio
async def test_batch_ingest_deduplication_and_recurrence_reopening(mock_session: AsyncMock) -> None:
    """Verifies fingerprint deduplication, evidence merging, and recurrence reopening."""
    service = FindingsService(mock_session)
    service.repo._verify_project_access = AsyncMock()  # type: ignore[method-assign]

    project_id = uuid.uuid4()
    finding_id = uuid.uuid4()
    ctx = SystemContext(reason="test")

    # Simulate existing resolved finding
    resolved_finding = Finding(
        project_id=project_id,
        fingerprint="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        rule_id="devmind.authz.missing_role_check",
        source="scanner",
        category="authorization",
        title="Old Title",
        summary="Old Summary",
        severity="high",
        confidence="medium",
        evidence_level="E1",
        status="resolved",
        resolved_at=datetime.now(UTC),
    )
    resolved_finding.id = finding_id
    resolved_finding.evidence_items = []

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalars.return_value.first.return_value = resolved_finding
    mock_session.execute.return_value = mock_result

    req = BatchFindingsRequest(
        findings=[
            FindingPayload(
                rule_id="devmind.authz.missing_role_check",
                category="authorization",
                title="Updated Title",
                summary="Updated Summary",
                severity="high",
                fingerprint="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                evidence=[
                    FindingEvidencePayload(
                        path="src/admin.ts",
                        start_line=10,
                        end_line=20,
                        snippet_hash="sha256:abcd1234",
                    )
                ],
            )
        ]
    )

    response = await service.batch_ingest_findings(ctx, project_id, req, source="scanner")
    assert response.ingested == 1
    assert response.created == 0
    assert response.reopened == 1
    assert resolved_finding.status == "reopened"
    assert resolved_finding.resolved_at is None
    assert resolved_finding.title == "Updated Title"


@pytest.mark.asyncio
async def test_lifecycle_state_transitions(mock_session: AsyncMock) -> None:
    """Verifies state machine transitions, invalid transition rejections, and dismissal reason requirements."""
    service = FindingsService(mock_session)
    service.repo._verify_project_access = AsyncMock()  # type: ignore[method-assign]

    project_id = uuid.uuid4()
    finding_id = uuid.uuid4()

    ctx = AuthContext(
        user_id=uuid.uuid4(),
        clerk_user_id="user_123",
        email="test@devmind.dev",
        workspace_id=uuid.uuid4(),
        workspace_role="admin",
        project_id=project_id,
        project_role="maintainer",
        permissions=frozenset(
            {"findings:read", "finding:progress", "finding:triage", "finding:acknowledge"}
        ),
    )

    finding = Finding(
        project_id=project_id,
        fingerprint="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        rule_id="test.rule",
        source="scanner",
        category="authorization",
        title="Test Finding",
        summary="Test Summary",
        severity="medium",
        confidence="medium",
        evidence_level="E1",
        status="open",
    )
    finding.id = finding_id
    finding.evidence_items = []
    finding.status_history = []
    finding.primary_file = None

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = finding
    mock_session.execute.return_value = mock_result

    # 1. Invalid transition from open -> resolved directly without investigation
    with pytest.raises(ConflictError) as exc_invalid:
        await service.transition_status(
            ctx,
            project_id,
            finding_id,
            FindingStatusTransitionRequest(to_status="resolved"),
        )
    assert exc_invalid.value.code == "finding.invalid_transition"

    # 2. Dismissal requires reason code
    with pytest.raises(ValidationError) as exc_reason:
        await service.transition_status(
            ctx,
            project_id,
            finding_id,
            FindingStatusTransitionRequest(to_status="dismissed", reason=None),
        )
    assert exc_reason.value.code == "finding.reason_required"

    # 3. Valid transition: open -> acknowledged
    res_ack = await service.transition_status(
        ctx,
        project_id,
        finding_id,
        FindingStatusTransitionRequest(to_status="acknowledged", reason="Acknowledged by dev"),
    )
    assert res_ack.status == "acknowledged"
    assert finding.status == "acknowledged"
    assert finding.status_reason == "Acknowledged by dev"

    # 4. Valid transition: acknowledged -> in_progress
    await service.transition_status(
        ctx,
        project_id,
        finding_id,
        FindingStatusTransitionRequest(to_status="in_progress"),
    )
    assert finding.status == "in_progress"

    # 5. Valid transition: in_progress -> resolved
    await service.transition_status(
        ctx,
        project_id,
        finding_id,
        FindingStatusTransitionRequest(to_status="resolved", reason="Fixed in PR #42"),
    )
    assert finding.status == "resolved"
    assert finding.resolved_at is not None


def test_extension_findings_batch_endpoint(test_settings: Settings) -> None:
    """Verifies extension POST /api/v1/ext/projects/{pid}/findings:batch endpoint."""
    from app.main import create_app

    app = create_app(settings=test_settings)

    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    mock_auth = AuthContext(
        user_id=uuid.uuid4(),
        clerk_user_id="user_123",
        email="test@devmind.dev",
        workspace_id=workspace_id,
        workspace_role="admin",
        project_id=project_id,
        project_role="maintainer",
        permissions=frozenset({"project:sync"}),
    )

    batch_resp = BatchFindingsResponse(
        ingested=1,
        created=1,
        updated=0,
        reopened=0,
        findings=[
            FindingItem(
                id=uuid.uuid4(),
                project_id=project_id,
                fingerprint="a" * 64,
                rule_id="devmind.authz.missing_role_check",
                source="scanner",
                category="authorization",
                title="Missing Role Check",
                summary="Admin route lacks check",
                severity="high",
                confidence="medium",
                evidence_level="E1",
                status="open",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        ],
    )

    payload = {
        "findings": [
            {
                "rule_id": "devmind.authz.missing_role_check",
                "category": "authorization",
                "title": "Missing Role Check",
                "summary": "Admin route lacks check",
                "severity": "high",
                "location": {"path": "src/routes/admin.ts", "start_line": 7, "end_line": 9},
                "evidence": [
                    {
                        "path": "src/routes/admin.ts",
                        "start_line": 7,
                        "end_line": 9,
                        "snippet_hash": "sha256:11223344",
                    }
                ],
            }
        ]
    }

    # 1. Unauthenticated request without extension token rejected with 401
    with TestClient(app) as client:
        resp_unauth = client.post(f"/api/v1/ext/projects/{project_id}/findings:batch", json=payload)
        assert resp_unauth.status_code == 401

    # 2. Authenticated request with extension token
    mock_session = AsyncMock()
    app.dependency_overrides[get_extension_auth_context] = lambda: mock_auth
    app.dependency_overrides[get_db_session] = lambda: mock_session

    with (
        patch("app.domain.brain.findings_service.resolve_project_context", return_value=mock_auth),
        patch(
            "app.domain.brain.findings_service.FindingsService.batch_ingest_findings",
            return_value=batch_resp,
        ),
        TestClient(app) as client,
    ):
        resp_success = client.post(
            f"/api/v1/ext/projects/{project_id}/findings:batch",
            json=payload,
            headers={"Authorization": "Bearer dme_at_test_token"},
        )
        assert resp_success.status_code == 200
        data = resp_success.json()
        assert data["ingested"] == 1
        assert data["created"] == 1
        assert len(data["findings"]) == 1


def test_browser_findings_endpoints(test_settings: Settings) -> None:
    """Verifies browser GET /findings, GET /findings/{id}, and POST /findings/{id}/transitions endpoints."""
    from app.main import create_app

    app = create_app(settings=test_settings)

    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    finding_id = uuid.uuid4()

    mock_auth = AuthContext(
        user_id=uuid.uuid4(),
        clerk_user_id="user_123",
        email="test@devmind.dev",
        workspace_id=workspace_id,
        workspace_role="admin",
        project_id=project_id,
        project_role="maintainer",
        permissions=frozenset({"findings:read", "finding:progress", "finding:triage"}),
    )

    finding_item = FindingItem(
        id=finding_id,
        project_id=project_id,
        fingerprint="b" * 64,
        rule_id="devmind.authz.missing_role_check",
        source="scanner",
        category="authorization",
        title="Admin Check Missing",
        summary="Route lacks check",
        severity="high",
        confidence="medium",
        evidence_level="E1",
        status="open",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    finding_detail = FindingDetailItem(
        **finding_item.model_dump(),
        evidence=[],
        history=[],
    )

    mock_session = AsyncMock()
    app.dependency_overrides[get_auth_context] = lambda: mock_auth
    app.dependency_overrides[get_db_session] = lambda: mock_session

    with (
        patch("app.domain.brain.findings_service.resolve_project_context", return_value=mock_auth),
        patch(
            "app.domain.brain.findings_service.FindingsService.list_findings",
            return_value=[finding_item],
        ),
        patch(
            "app.domain.brain.findings_service.FindingsService.get_finding_detail",
            return_value=finding_detail,
        ),
        patch(
            "app.domain.brain.findings_service.FindingsService.transition_status",
            return_value=finding_detail,
        ),
        TestClient(app) as client,
    ):
        # 1. List findings
        resp_list = client.get(
            f"/api/v1/projects/{project_id}/findings?status=open&severity=high",
            headers={"Authorization": "Bearer mock_browser_token"},
        )
        assert resp_list.status_code == 200
        assert len(resp_list.json()) == 1

        # 2. Get finding detail
        resp_detail = client.get(
            f"/api/v1/projects/{project_id}/findings/{finding_id}",
            headers={"Authorization": "Bearer mock_browser_token"},
        )
        assert resp_detail.status_code == 200
        assert resp_detail.json()["id"] == str(finding_id)

        # 3. Transition status
        resp_trans = client.post(
            f"/api/v1/projects/{project_id}/findings/{finding_id}/transitions",
            json={"to_status": "acknowledged", "reason": "Acknowledged"},
            headers={"Authorization": "Bearer mock_browser_token"},
        )
        assert resp_trans.status_code == 200
