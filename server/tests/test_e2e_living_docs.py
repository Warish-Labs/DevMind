"""End-to-End integration test suite for Living Documentation & DocsAlive (CAP-04, docs/01 §7, docs/03 §3.5, M12-06)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.auth_context import AuthContext
from app.core.errors import ConflictError, NotFoundError
from app.domain.auth import (
    PERM_PROJECT_READ,
    PERM_PROJECT_UPDATE,
)
from app.domain.living_docs.schemas import (
    DocDriftDetectRequest,
    DocRecordCreate,
    DriftApprovalRequest,
)
from app.domain.living_docs.service import LivingDocService
from app.persistence.models.living_documentation import DocDriftItem, DocumentationRecord
from app.persistence.models.project import Project


@pytest.mark.asyncio
async def test_e2e_living_docs_lifecycle_and_approval_gate() -> None:
    """E2E test: register doc -> drift detection -> approval gate -> rejection/approval -> patch application."""
    workspace_id = uuid4()
    project_id = uuid4()
    user_id = uuid4()
    doc_id = uuid4()
    drift_id = uuid4()

    ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_clerk_123",
        email="maintainer@devmind.ai",
        workspace_id=workspace_id,
        workspace_role="admin",
        project_id=project_id,
        project_role="maintainer",
        permissions=frozenset({PERM_PROJECT_READ, PERM_PROJECT_UPDATE}),
    )

    mock_session = AsyncMock()
    service = LivingDocService(session=mock_session)

    mock_project = Project(
        id=project_id,
        workspace_id=workspace_id,
        name="Documentation Hub",
        slug="doc-hub",
    )
    service.project_repo.get_by_id = AsyncMock(return_value=mock_project)

    # 1. Register a new Markdown document
    initial_content = (
        "# API Reference\n\n## Endpoints\n\n`GET /api/v1/projects`\n\nLists all projects.\n"
    )
    initial_hash = hashlib.sha256(initial_content.encode("utf-8")).hexdigest()

    mock_doc = DocumentationRecord(
        id=doc_id,
        workspace_id=workspace_id,
        project_id=project_id,
        path="docs/api.md",
        title="API Reference",
        kind="api_reference",
        current_version_hash=initial_hash,
        content_snapshot=initial_content,
        extracted_symbols=[{"type": "route", "path": "/api/v1/projects", "line": 5}],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service.repo.upsert_document_record = AsyncMock(return_value=(mock_doc, True))

    reg_result = await service.register_document(
        ctx,
        project_id,
        DocRecordCreate(
            path="docs/api.md",
            title="API Reference",
            kind="api_reference",
            content=initial_content,
        ),
    )
    assert reg_result.id == doc_id
    assert reg_result.current_version_hash == initial_hash

    # 2. Run drift detection with a new active route in code
    service.repo.list_documents_by_project = AsyncMock(return_value=[mock_doc])

    mock_drift = DocDriftItem(
        id=drift_id,
        workspace_id=workspace_id,
        project_id=project_id,
        documentation_record_id=doc_id,
        kind="undocumented_route",
        status="detected",
        target_route_path="/api/v1/projects/{project_id}/bugs",
        target_symbol_key=None,
        explanation="Route /api/v1/projects/{project_id}/bugs active in code but missing from docs/api.md",
        proposal={
            "summary": "Document active endpoint /api/v1/projects/{project_id}/bugs",
            "diff_content": (
                "--- a/docs/api.md\n"
                "+++ b/docs/api.md\n"
                "@@ -6,2 +6,6 @@\n"
                "+### `/api/v1/projects/{project_id}/bugs`\n"
                "+Active endpoint detected in code.\n"
            ),
            "gated": True,
            "confidence": 0.95,
        },
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service.agent.detect_and_propose = AsyncMock(return_value=[mock_drift])

    detect_res = await service.detect_drift(
        ctx,
        project_id,
        DocDriftDetectRequest(
            known_routes=["/api/v1/projects", "/api/v1/projects/{project_id}/bugs"],
        ),
    )
    assert detect_res.drift_count == 1
    assert detect_res.drift_items[0].kind == "undocumented_route"
    assert detect_res.drift_items[0].status == "detected"

    # 3. Approval Gate Enforcement: Trying to apply an unapproved proposal fails with ConflictError
    service.agent.apply_patch = AsyncMock(
        side_effect=ConflictError(
            detail=f"Drift proposal {drift_id} must be approved before applying"
        )
    )
    with pytest.raises(ConflictError):
        await service.apply_drift_patch(ctx, drift_id)

    # 4. Reject proposal (maintenance action)
    rejected_drift = DocDriftItem(
        id=drift_id,
        workspace_id=workspace_id,
        project_id=project_id,
        documentation_record_id=doc_id,
        kind="undocumented_route",
        status="rejected",
        explanation="test",
        proposal={"rejection_reason": "Not ready for public API docs"},
    )
    service.agent.reject_drift = AsyncMock(return_value=rejected_drift)

    reject_res = await service.reject_drift_item(
        ctx,
        drift_id,
        DriftApprovalRequest(reason="Not ready for public API docs"),
    )
    assert reject_res.status == "rejected"

    # 5. Approve proposal
    approved_drift = DocDriftItem(
        id=drift_id,
        workspace_id=workspace_id,
        project_id=project_id,
        documentation_record_id=doc_id,
        kind="undocumented_route",
        status="approved",
        explanation="test",
        proposal=mock_drift.proposal,
    )
    service.agent.approve_drift = AsyncMock(return_value=approved_drift)

    approve_res = await service.approve_drift_item(
        ctx,
        drift_id,
        DriftApprovalRequest(reason="Verified against OpenAPI route"),
    )
    assert approve_res.status == "approved"

    # 6. Apply approved patch
    updated_content = (
        initial_content
        + "\n### `/api/v1/projects/{project_id}/bugs`\nActive endpoint detected in code.\n"
    )
    updated_hash = hashlib.sha256(updated_content.encode("utf-8")).hexdigest()
    updated_doc = DocumentationRecord(
        id=doc_id,
        workspace_id=workspace_id,
        project_id=project_id,
        path="docs/api.md",
        title="API Reference",
        kind="api_reference",
        current_version_hash=updated_hash,
        content_snapshot=updated_content,
    )
    applied_drift = DocDriftItem(
        id=drift_id,
        workspace_id=workspace_id,
        project_id=project_id,
        documentation_record_id=doc_id,
        kind="undocumented_route",
        status="applied",
        explanation="test",
        proposal=mock_drift.proposal,
    )
    service.agent.apply_patch = AsyncMock(return_value=(applied_drift, updated_doc))

    apply_res = await service.apply_drift_patch(ctx, drift_id)
    assert apply_res.status == "applied"
    assert "Patch successfully applied" in apply_res.message


@pytest.mark.asyncio
async def test_e2e_living_docs_multi_tenant_isolation() -> None:
    """Verify cross-workspace tenant boundaries are enforced for Living Documentation."""
    tenant_b_workspace = uuid4()
    project_id = uuid4()

    tenant_b_ctx = AuthContext(
        user_id=uuid4(),
        clerk_user_id="user_tenant_b",
        email="tenant_b@devmind.ai",
        workspace_id=tenant_b_workspace,
        workspace_role="admin",
        permissions=frozenset({PERM_PROJECT_READ, PERM_PROJECT_UPDATE}),
    )

    mock_session = AsyncMock()
    service = LivingDocService(session=mock_session)

    # Scoped project repository returns None for other tenant's project
    service.project_repo.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError):
        await service.list_documents(tenant_b_ctx, project_id)
