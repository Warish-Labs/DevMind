"""Unit tests for DocsAlive specialist agent and gated patch proposals (docs/01 CAP-04, docs/05 §6.7)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.auth_context import AuthContext
from app.core.errors import ConflictError
from app.core.ids import generate_uuid7
from app.llm.models import LLMGenerationResponse, TokenUsage
from app.llm.router import LLMGatewayRouter
from app.orchestration.docsalive import DocsAliveAgent, run_docsalive_specialist
from app.orchestration.manager import classify_intent_deterministically
from app.orchestration.state import RequestState, RunState, SpecialistTask
from app.persistence.models.living_documentation import DocDriftItem, DocumentationRecord
from app.persistence.models.project import Project


@pytest.fixture
def auth_ctx() -> AuthContext:
    return AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_test_docsalive",
        email="docsalive@devmind.test",
        workspace_id=generate_uuid7(),
        workspace_role="admin",
        permissions=frozenset({"project:read", "project:update", "analysis:create"}),
    )


@pytest.mark.asyncio
async def test_docsalive_detects_drift_and_creates_proposals(auth_ctx: AuthContext) -> None:
    """Verify DocsAlive identifies missing routes and builds unified diff patch proposals."""
    session = AsyncMock()
    project_id = generate_uuid7()
    doc_id = generate_uuid7()

    mock_project = Project(
        id=project_id,
        workspace_id=auth_ctx.workspace_id,
        name="Test Docs Project",
        slug="test-docs",
    )

    now = datetime.now(UTC)
    doc_content = (
        "# API Reference\n\n## Endpoints\n\n### `GET /api/v1/health`\nHealth check endpoint.\n"
    )

    mock_doc = DocumentationRecord(
        id=doc_id,
        workspace_id=auth_ctx.workspace_id,
        project_id=project_id,
        path="docs/api.md",
        title="API Reference",
        kind="api",
        current_version_hash="dummy_hash",
        content_snapshot=doc_content,
        extracted_symbols=[{"kind": "route", "method": "GET", "path": "/api/v1/health", "line": 5}],
        created_at=now,
        updated_at=now,
    )

    agent = DocsAliveAgent(session=session)
    agent.project_repo.get_by_id = AsyncMock(return_value=mock_project)
    agent.repo.list_documents_by_project = AsyncMock(return_value=[mock_doc])

    recorded_items: list[DocDriftItem] = []

    async def fake_record_drift_item(**kwargs):
        item = DocDriftItem(
            id=generate_uuid7(),
            workspace_id=kwargs["workspace_id"],
            project_id=kwargs["project_id"],
            documentation_record_id=kwargs["documentation_record_id"],
            kind=kwargs["kind"],
            explanation=kwargs["explanation"],
            target_symbol_key=kwargs.get("target_symbol_key"),
            target_route_path=kwargs.get("target_route_path"),
            status="detected",
            proposal=kwargs.get("proposal"),
            created_at=now,
            updated_at=now,
        )
        item.documentation_record = mock_doc
        recorded_items.append(item)
        return item

    agent.repo.record_drift_item = AsyncMock(side_effect=fake_record_drift_item)

    # Detect drift with a new undocumented route and a removed route
    known_routes = {"GET /api/v1/health", "POST /api/v1/bugs/new"}
    drift_items = await agent.detect_and_propose(
        ctx=auth_ctx,
        project_id=project_id,
        known_routes=known_routes,
    )

    assert len(drift_items) >= 1
    undoc = next(i for i in drift_items if i.kind == "undocumented_route")
    assert undoc.target_route_path == "POST /api/v1/bugs/new"
    assert undoc.proposal is not None
    assert undoc.proposal["gated"] is True
    assert "diff_content" in undoc.proposal
    assert "+++ b/docs/api.md" in undoc.proposal["diff_content"]


@pytest.mark.asyncio
async def test_docsalive_llm_patch_proposal(auth_ctx: AuthContext) -> None:
    """Verify that DocsAlive leverages LLM router for rich patch drafting when available."""
    session = AsyncMock()
    project_id = generate_uuid7()
    doc_id = generate_uuid7()

    mock_project = Project(
        id=project_id,
        workspace_id=auth_ctx.workspace_id,
        name="LLM Test Project",
        slug="llm-proj",
    )

    mock_doc = DocumentationRecord(
        id=doc_id,
        workspace_id=auth_ctx.workspace_id,
        project_id=project_id,
        path="README.md",
        title="Project Readme",
        kind="readme",
        current_version_hash="abc123hash",
        content_snapshot="# Overview\n\nWelcome to DevMind.",
        extracted_symbols=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    llm_payload = {
        "summary": "Document new Bug Memory service endpoint",
        "drift_kind": "undocumented_route",
        "target_section": "Endpoints",
        "proposed_content": "### `POST /api/v1/bugs`\n\nCreate a new bug record.",
        "diff_content": "--- a/README.md\n+++ b/README.md\n@@ -1,2 +1,6 @@\n",
        "confidence": 0.95,
        "notes": ["Verified against OpenAPI specification"],
    }

    mock_router = MagicMock(spec=LLMGatewayRouter)
    mock_router.generate = AsyncMock(
        return_value=LLMGenerationResponse(
            content=json.dumps(llm_payload),
            raw_response={},
            provider_id="fake_provider",
            model_id="fake_model",
            usage=TokenUsage(input_tokens=100, output_tokens=50),
        )
    )

    agent = DocsAliveAgent(session=session, router=mock_router)
    agent.project_repo.get_by_id = AsyncMock(return_value=mock_project)
    agent.repo.list_documents_by_project = AsyncMock(return_value=[mock_doc])

    async def fake_record(**kwargs):
        item = DocDriftItem(
            id=generate_uuid7(),
            workspace_id=kwargs["workspace_id"],
            project_id=kwargs["project_id"],
            documentation_record_id=kwargs["documentation_record_id"],
            kind=kwargs["kind"],
            explanation=kwargs["explanation"],
            status="detected",
            proposal=kwargs.get("proposal"),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        item.documentation_record = mock_doc
        return item

    agent.repo.record_drift_item = AsyncMock(side_effect=fake_record)

    drift_items = await agent.detect_and_propose(
        ctx=auth_ctx,
        project_id=project_id,
        known_routes={"POST /api/v1/bugs"},
    )

    assert len(drift_items) == 1
    assert drift_items[0].proposal["summary"] == "Document new Bug Memory service endpoint"
    assert drift_items[0].proposal["confidence"] == 0.95


@pytest.mark.asyncio
async def test_docsalive_approval_and_apply_gate(auth_ctx: AuthContext) -> None:
    """Verify human approval gate: applying a patch fails if not approved, succeeds when approved."""
    session = AsyncMock()
    drift_id = generate_uuid7()
    doc_id = generate_uuid7()

    initial_content = "# System Overview\n\nOld content."
    mock_doc = DocumentationRecord(
        id=doc_id,
        workspace_id=auth_ctx.workspace_id,
        project_id=generate_uuid7(),
        path="docs/overview.md",
        title="System Overview",
        kind="architecture",
        current_version_hash="initial_hash",
        content_snapshot=initial_content,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_drift = DocDriftItem(
        id=drift_id,
        workspace_id=auth_ctx.workspace_id,
        project_id=mock_doc.project_id,
        documentation_record_id=doc_id,
        kind="undocumented_route",
        explanation="Missing doc for route",
        status="detected",
        proposal={
            "proposed_content": "### `GET /metrics`\n\nPrometheus metrics.",
            "diff_content": "--- a/docs/overview.md\n+++ b/docs/overview.md\n",
            "gated": True,
        },
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    mock_drift.documentation_record = mock_doc

    agent = DocsAliveAgent(session=session)
    agent.repo.get_drift_item_by_id = AsyncMock(return_value=mock_drift)
    agent.repo.get_document_by_id = AsyncMock(return_value=mock_doc)

    # 1. Applying while status is 'detected' must fail with ConflictError
    with pytest.raises(ConflictError) as exc_info:
        await agent.apply_patch(ctx=auth_ctx, drift_id=drift_id)
    assert exc_info.value.code == "doc_drift.not_approved"

    # 2. Approve proposal
    async def fake_update_status(**kwargs):
        mock_drift.status = kwargs["status"]
        if "proposal" in kwargs:
            mock_drift.proposal = kwargs["proposal"]
        return mock_drift

    agent.repo.update_drift_status = AsyncMock(side_effect=fake_update_status)
    approved = await agent.approve_drift(
        ctx=auth_ctx, drift_id=drift_id, decided_by="maintainer@devmind.test"
    )
    assert approved.status == "approved"
    assert approved.proposal["decided_by"] == "maintainer@devmind.test"

    # 3. Applying while status is 'approved' succeeds and updates doc
    applied_drift, updated_doc = await agent.apply_patch(ctx=auth_ctx, drift_id=drift_id)
    assert applied_drift.status == "applied"
    assert "GET /metrics" in updated_doc.content_snapshot
    assert updated_doc.current_version_hash != "initial_hash"


@pytest.mark.asyncio
async def test_docsalive_specialist_runner_in_workflow() -> None:
    """Verify run_docsalive_specialist emits draft findings and gated proposals."""
    session = AsyncMock()
    project_id = generate_uuid7()
    doc_id = generate_uuid7()

    mock_doc = DocumentationRecord(
        id=doc_id,
        workspace_id=generate_uuid7(),
        project_id=project_id,
        path="docs/api.md",
        title="API",
        kind="api",
        current_version_hash="hash",
        content_snapshot="# API\n",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    mock_drift = DocDriftItem(
        id=generate_uuid7(),
        workspace_id=mock_doc.workspace_id,
        project_id=project_id,
        documentation_record_id=doc_id,
        kind="undocumented_route",
        explanation="Route POST /api/v1/auth is undocumented",
        status="detected",
        proposal={
            "diff_content": "--- a/docs/api.md\n+++ b/docs/api.md\n",
            "proposed_content": "### POST /api/v1/auth",
        },
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    mock_drift.documentation_record = mock_doc

    state: RunState = {
        "run_id": str(generate_uuid7()),
        "project_id": str(project_id),
        "request": RequestState(job_type="doc_check", user_message="Check living documentation"),
        "plan": [],
        "proposals": [],
        "draft_findings": [],
    }

    task = SpecialistTask(
        specialist="docsalive",
        task_id="docsalive_task_1",
        status="running",
        input_refs=[],
        params={"known_routes": ["POST /api/v1/auth"]},
    )

    with pytest.MonkeyMock() if hasattr(pytest, "MonkeyMock") else MagicMock():
        from unittest.mock import patch

        with patch.object(
            DocsAliveAgent, "detect_and_propose", AsyncMock(return_value=[mock_drift])
        ):
            result = await run_docsalive_specialist(
                state=state,
                task=task,
                session=session,
            )

    assert task.status == "completed"
    assert len(result["draft_findings"]) == 1
    assert result["draft_findings"][0].finding_type == "documentation_drift"
    assert len(result["proposals"]) == 1
    assert result["proposals"][0].gated is True


def test_agent_manager_routes_docsalive() -> None:
    """Verify deterministic intent classifier routes doc_check requests to docsalive."""
    req = RequestState(job_type="doc_check", user_message="Find documentation drift")
    intent = classify_intent_deterministically(req)
    assert intent is not None
    assert intent.category == "documentation"
    assert "docsalive" in intent.requires_specialists
