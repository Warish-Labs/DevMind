"""Tests for Agent Job integration (ask_project, security_review) and SSE event streaming (docs/03 §5.2, docs/05 §4, M7-08)."""

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from starlette.testclient import TestClient

from app.core.auth_context import AuthContext, SystemContext
from app.core.ids import generate_uuid7
from app.core.settings import Settings
from app.domain.auth import (
    PERM_ANALYSIS_CREATE,
    PERM_PROJECT_READ,
    PERMISSION_AUTHENTICATED,
    get_auth_context,
    get_db_session,
)
from app.domain.jobs.service import JobLifecycleService
from app.main import create_app
from app.persistence.models.brain import AnalysisJob, JobEvent
from app.workers.celery_app import create_celery_app


class MockAsyncSession:
    """In-memory mock AsyncSession for fast unit testing of domain services."""

    def __init__(self) -> None:
        self.jobs: dict[UUID, AnalysisJob] = {}
        self.events: list[JobEvent] = []
        self.findings: list[Any] = []

    def add(self, obj: Any) -> None:
        if isinstance(obj, AnalysisJob):
            if not obj.id:
                obj.id = generate_uuid7()
            if not obj.created_at:
                obj.created_at = datetime.now(UTC)
            self.jobs[obj.id] = obj
        elif isinstance(obj, JobEvent):
            if not obj.id:
                obj.id = generate_uuid7()
            if not obj.created_at:
                obj.created_at = datetime.now(UTC)
            self.events.append(obj)
        else:
            self.findings.append(obj)

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    async def close(self) -> None:
        pass


@pytest.fixture
def mock_session() -> MockAsyncSession:
    return MockAsyncSession()


# ---------------------------------------------------------------------------
# 1. API Endpoints: Analysis Job Creation & Idempotency
# ---------------------------------------------------------------------------


def test_create_analysis_job_api_success(test_settings: Settings) -> None:
    """Verify POST /projects/{pid}/analyses creates job and returns 202 with streaming links."""
    app = create_app(settings=test_settings)

    project_id = generate_uuid7()
    workspace_id = generate_uuid7()
    user_id = generate_uuid7()

    mock_ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_test123",
        email="test@devmind.test",
        workspace_id=workspace_id,
        workspace_role="maintainer",
        project_id=project_id,
        permissions=frozenset({PERMISSION_AUTHENTICATED, PERM_ANALYSIS_CREATE, PERM_PROJECT_READ}),
    )

    created_job = AnalysisJob(
        id=generate_uuid7(),
        project_id=project_id,
        type="security_review",
        status="queued",
        attempt=0,
        max_attempts=3,
        created_at=datetime.now(UTC),
    )

    mock_service = MagicMock(spec=JobLifecycleService)
    mock_service.create_analysis_job = AsyncMock(return_value=created_job)

    app.dependency_overrides[get_auth_context] = lambda: mock_ctx
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    with patch("app.api.jobs.JobLifecycleService", return_value=mock_service):
        with TestClient(app=app) as client:
            payload = {
                "type": "security_review",
                "params": {"scope": {"paths": ["server/app/routes/"]}},
            }
            res = client.post(
                f"/api/v1/projects/{project_id}/analyses",
                json=payload,
                headers={"Idempotency-Key": "test_idempotency_123"},
            )

            assert res.status_code == 202
            data = res.json()
            assert "job" in data
            assert data["job"]["type"] == "security_review"
            assert data["job"]["status"] == "queued"
            assert "links" in data
            assert data["links"]["self"] == f"/api/v1/jobs/{created_job.id}"
            assert data["links"]["events"] == f"/api/v1/jobs/{created_job.id}/events"


def test_create_analysis_job_api_forbidden(test_settings: Settings) -> None:
    """Caller without analysis:create receives 403 Forbidden."""
    app = create_app(settings=test_settings)
    project_id = generate_uuid7()

    # User has project:read only, lacks analysis:create
    mock_ctx = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_viewer123",
        email="viewer@devmind.test",
        project_id=project_id,
        permissions=frozenset({PERMISSION_AUTHENTICATED, PERM_PROJECT_READ}),
    )
    app.dependency_overrides[get_auth_context] = lambda: mock_ctx

    with TestClient(app=app) as client:
        res = client.post(
            f"/api/v1/projects/{project_id}/analyses",
            json={"type": "security_review"},
            headers={"Idempotency-Key": "test_forbidden_key"},
        )
        assert res.status_code == 403
        assert res.json()["code"] == "auth.forbidden"


# ---------------------------------------------------------------------------
# 2. API Endpoints: Job Details and Listing
# ---------------------------------------------------------------------------


def test_get_job_details_api(test_settings: Settings) -> None:
    """Verify GET /jobs/{id} returns job metadata or 404."""
    app = create_app(settings=test_settings)
    job_id = generate_uuid7()
    project_id = generate_uuid7()

    mock_ctx = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_viewer123",
        email="viewer@devmind.test",
        project_id=project_id,
        permissions=frozenset({PERMISSION_AUTHENTICATED, PERM_PROJECT_READ}),
    )
    app.dependency_overrides[get_auth_context] = lambda: mock_ctx
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    job_rec = AnalysisJob(
        id=job_id,
        project_id=project_id,
        type="ask_project",
        status="succeeded",
        attempt=1,
        max_attempts=3,
        result_ref={"answer": "Authentication is implemented using JWT."},
        created_at=datetime.now(UTC),
    )

    mock_service = MagicMock(spec=JobLifecycleService)
    mock_service.get_job_by_id = AsyncMock(
        side_effect=lambda ctx, jid: job_rec if jid == job_id else None
    )

    with patch("app.api.jobs.JobLifecycleService", return_value=mock_service):
        with TestClient(app=app) as client:
            # 1. Found job
            res = client.get(f"/api/v1/jobs/{job_id}")
            assert res.status_code == 200
            data = res.json()
            assert data["id"] == str(job_id)
            assert data["status"] == "succeeded"
            assert data["result_ref"]["answer"] == "Authentication is implemented using JWT."

            # 2. Missing job -> 404
            unknown_id = generate_uuid7()
            res_404 = client.get(f"/api/v1/jobs/{unknown_id}")
            assert res_404.status_code == 404
            assert res_404.json()["code"] == "job.not_found"


def test_list_project_jobs_api(test_settings: Settings) -> None:
    """Verify GET /projects/{pid}/jobs lists jobs for project."""
    app = create_app(settings=test_settings)
    project_id = generate_uuid7()

    mock_ctx = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_viewer123",
        email="viewer@devmind.test",
        project_id=project_id,
        permissions=frozenset({PERMISSION_AUTHENTICATED, PERM_PROJECT_READ}),
    )
    app.dependency_overrides[get_auth_context] = lambda: mock_ctx
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    job1 = AnalysisJob(
        id=generate_uuid7(),
        project_id=project_id,
        type="security_review",
        status="succeeded",
        created_at=datetime.now(UTC),
    )
    job2 = AnalysisJob(
        id=generate_uuid7(),
        project_id=project_id,
        type="ask_project",
        status="queued",
        created_at=datetime.now(UTC),
    )

    mock_service = MagicMock(spec=JobLifecycleService)
    mock_service.list_project_jobs = AsyncMock(return_value=[job1, job2])

    with patch("app.api.jobs.JobLifecycleService", return_value=mock_service):
        with TestClient(app=app) as client:
            res = client.get(f"/api/v1/projects/{project_id}/jobs")
            assert res.status_code == 200
            data = res.json()
            assert len(data) == 2
            assert data[0]["type"] == "security_review"
            assert data[1]["type"] == "ask_project"


# ---------------------------------------------------------------------------
# 3. Job Cancellation
# ---------------------------------------------------------------------------


def test_cancel_job_api(test_settings: Settings) -> None:
    """Verify POST /jobs/{id}/cancel requests cooperative cancellation."""
    app = create_app(settings=test_settings)
    job_id = generate_uuid7()
    project_id = generate_uuid7()

    mock_ctx = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_viewer123",
        email="viewer@devmind.test",
        project_id=project_id,
        permissions=frozenset({PERMISSION_AUTHENTICATED, PERM_PROJECT_READ}),
    )
    app.dependency_overrides[get_auth_context] = lambda: mock_ctx
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    cancelled_job = AnalysisJob(
        id=job_id,
        project_id=project_id,
        type="security_review",
        status="cancel_requested",
        created_at=datetime.now(UTC),
    )

    mock_service = MagicMock(spec=JobLifecycleService)
    mock_service.request_job_cancellation = AsyncMock(return_value=cancelled_job)

    with patch("app.api.jobs.JobLifecycleService", return_value=mock_service):
        with TestClient(app=app) as client:
            res = client.post(
                f"/api/v1/jobs/{job_id}/cancel",
                headers={"Idempotency-Key": f"cancel_{job_id}"},
            )
            assert res.status_code == 200
            assert res.json()["status"] == "cancel_requested"


# ---------------------------------------------------------------------------
# 4. SSE Job Event Streaming
# ---------------------------------------------------------------------------


def test_sse_event_streaming_endpoint(test_settings: Settings) -> None:
    """Verify GET /jobs/{id}/events streams RFC 8895 Server-Sent Events."""
    app = create_app(settings=test_settings)
    job_id = generate_uuid7()
    project_id = generate_uuid7()

    mock_ctx = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_viewer123",
        email="viewer@devmind.test",
        project_id=project_id,
        permissions=frozenset({PERMISSION_AUTHENTICATED, PERM_PROJECT_READ}),
    )
    app.dependency_overrides[get_auth_context] = lambda: mock_ctx
    app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    job_rec = AnalysisJob(
        id=job_id,
        project_id=project_id,
        type="ask_project",
        status="succeeded",
        created_at=datetime.now(UTC),
    )

    mock_service = MagicMock(spec=JobLifecycleService)
    mock_service.get_job_by_id = AsyncMock(return_value=job_rec)

    async def _mock_stream(ctx, jid, since_seq=0):
        yield {
            "event": "milestone",
            "data": {
                "id": str(generate_uuid7()),
                "job_id": str(jid),
                "seq": 1,
                "kind": "claimed",
                "message": "Worker claimed job",
            },
        }
        yield {
            "event": "milestone",
            "data": {
                "id": str(generate_uuid7()),
                "job_id": str(jid),
                "seq": 2,
                "kind": "progress",
                "message": "Retrieved 3 context packs",
            },
        }
        yield {
            "event": "complete",
            "data": {
                "status": "succeeded",
                "result_ref": {"answer": "Verified explanation."},
            },
        }

    mock_service.stream_job_events = _mock_stream

    with patch("app.api.jobs.JobLifecycleService", return_value=mock_service):
        with TestClient(app=app) as client:
            res = client.get(f"/api/v1/jobs/{job_id}/events")
            assert res.status_code == 200
            assert "text/event-stream" in res.headers["content-type"]

            lines = res.text.strip().split("\n")
            event_types = [
                event_line.replace("event: ", "")
                for event_line in lines
                if event_line.startswith("event: ")
            ]
            assert event_types == ["milestone", "milestone", "complete"]
            assert "Worker claimed job" in res.text
            assert "Retrieved 3 context packs" in res.text
            assert "Verified explanation" in res.text


# ---------------------------------------------------------------------------
# 5. Worker Agent Workflow Execution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_domain_job_lifecycle_service_events() -> None:
    """Test publish_job_event and cancellation state transitions in JobLifecycleService."""
    mock_session = AsyncMock()
    service = JobLifecycleService(session=mock_session)
    sys_ctx = SystemContext(reason="test")
    job_id = generate_uuid7()

    # Mock BrainRepository record_job_event
    mock_event = JobEvent(
        id=generate_uuid7(),
        job_id=job_id,
        seq=1,
        kind="test_kind",
        message="Test event message",
        data={"key": "val"},
        created_at=datetime.now(UTC),
    )
    service.repo.record_job_event = AsyncMock(return_value=mock_event)

    with patch("app.domain.jobs.service.get_async_redis_client") as mock_get_redis:
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        ev = await service.publish_job_event(
            sys_ctx,
            job_id=job_id,
            kind="test_kind",
            message="Test event message",
            data={"key": "val"},
        )

        assert ev.kind == "test_kind"
        assert ev.seq == 1
        # Verify redis publish was attempted
        mock_redis.publish.assert_called_once()
        published_channel, published_payload = mock_redis.publish.call_args[0]
        assert str(job_id) in published_channel
        payload_data = json.loads(published_payload)
        assert payload_data["message"] == "Test event message"


def test_worker_agent_workflow_integration() -> None:
    """Verify that celery worker task processes agent workflows and persists results."""
    from app.orchestration.state import UsageTotals, VerifiedFinding

    job_id = generate_uuid7()
    project_id = generate_uuid7()

    job_rec = AnalysisJob(
        id=job_id,
        project_id=project_id,
        type="security_review",
        status="running",
        attempt=1,
        max_attempts=3,
        params={"query": "Check route guards"},
        created_at=datetime.now(UTC),
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalars=lambda: MagicMock(first=lambda: job_rec))
    )

    # Mock AgentManager
    mock_manager = MagicMock()
    mock_manager.run = AsyncMock(
        return_value={
            "final_response": "Security review summary: all routes verified.",
            "verified": [
                VerifiedFinding(
                    draft_id="d1",
                    finding_id="vf_1",
                    is_verified=True,
                    evidence_score=1.0,
                    evidence_level=2,
                    confidence=0.9,
                    title="Missing authentication check",
                    file_path="server/app/api/users.py",
                    line_range=(10, 20),
                    rule_id="devmind.authn.unprotected_route",
                    resolution_notes="Route has no authentication guard.",
                )
            ],
            "usage": UsageTotals(total_input_tokens=150, total_output_tokens=50),
            "plan": [],
            "hypotheses": [],
            "proposals": [],
        }
    )

    with patch("app.workers.celery_app.session_scope") as mock_scope:
        mock_scope.return_value.__aenter__.return_value = mock_session
        with patch("app.orchestration.manager.AgentManager", return_value=mock_manager):
            with patch(
                "app.persistence.repositories.brain_repo.BrainRepository.batch_upsert_findings",
                new_callable=AsyncMock,
            ) as mock_upsert:
                mock_upsert.return_value = [MagicMock()]
                with patch(
                    "app.domain.jobs.service.JobLifecycleService.complete_job",
                    new_callable=AsyncMock,
                ) as mock_complete:
                    mock_complete.return_value = job_rec

                    celery = create_celery_app()
                    # Execute task
                    res = celery.tasks["devmind.process_job"].apply(args=[str(job_id)]).get()

                    assert res["status"] == "succeeded"
                    assert res["result"]["verified_findings_count"] == 1
                    assert res["result"]["persisted_findings_count"] == 1
                    assert res["result"]["usage"]["total_tokens"] == 200
                    assert "all routes verified" in res["result"]["final_response"]
