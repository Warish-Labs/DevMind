"""Tests validating Job Lifecycle service, atomic claim, heartbeat lease, dead-worker reaper, and Celery configuration (M4-02, docs/10 §9, docs/02 §10)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import SystemContext
from app.core.ids import generate_uuid7
from app.core.settings import Settings
from app.domain.jobs.service import JobLifecycleService
from app.persistence.models.brain import AnalysisJob
from app.workers.celery_app import create_celery_app


def test_celery_queue_and_route_configuration() -> None:
    """Verify Celery queue topology, JSON-only serialization, and multi-queue routing."""
    settings = Settings(
        redis_key_prefix="test_prefix:",
        redis_url="redis://localhost:6379/2",
    )
    app = create_celery_app(settings)

    # 1. Queues
    queue_names = [q.name for q in app.conf.task_queues]
    assert "test_prefix:default" in queue_names
    assert "test_prefix:ingest" in queue_names
    assert "test_prefix:embed" in queue_names
    assert "test_prefix:analysis" in queue_names
    assert app.conf.task_default_queue == "test_prefix:default"

    # 2. Reliability & Serialization (docs/10 §9)
    assert app.conf.task_acks_late is True
    assert app.conf.task_reject_on_worker_lost is True
    assert app.conf.worker_prefetch_multiplier == 1
    assert app.conf.task_serializer == "json"
    assert app.conf.result_serializer == "json"
    assert app.conf.accept_content == ["json"]
    assert app.conf.broker_transport_options["visibility_timeout"] >= 3600

    # 3. Routes
    routes = app.conf.task_routes
    assert routes["devmind.ingest_*"]["queue"] == "test_prefix:ingest"
    assert routes["devmind.embed_*"]["queue"] == "test_prefix:embed"
    assert routes["devmind.analysis_*"]["queue"] == "test_prefix:analysis"

    # 4. Beat schedule
    beat = app.conf.beat_schedule
    assert "devmind.enqueuer_sweep" in beat
    assert "devmind.stale_job_reaper" in beat


@pytest.mark.asyncio
async def test_job_claim_compare_and_set_succeeds_on_queued_job() -> None:
    """Verify that an atomic compare-and-set claim transitions queued -> running."""
    mock_session = AsyncMock(spec=AsyncSession)
    service = JobLifecycleService(mock_session)
    sys_ctx = SystemContext(reason="worker_claim_test")

    job_id = generate_uuid7()
    claimed_job = AnalysisJob(
        id=job_id,
        project_id=generate_uuid7(),
        type="ingest_project",
        status="running",
        attempt=1,
        max_attempts=3,
        queue="ingest",
    )

    mock_result_claim = MagicMock()
    mock_result_claim.scalars.return_value.first.return_value = claimed_job

    mock_result_seq = MagicMock()
    mock_result_seq.scalar_one.return_value = 0

    mock_session.execute.side_effect = [mock_result_claim, mock_result_seq]

    result = await service.claim_job(sys_ctx, job_id)
    assert result is not None
    assert result.status == "running"
    assert result.attempt == 1
    assert mock_session.add.called
    assert mock_session.flush.called


@pytest.mark.asyncio
async def test_job_claim_fails_if_already_claimed_or_not_queued() -> None:
    """Verify that a second concurrent claim on an already running job returns None (prevents double execution)."""
    mock_session = AsyncMock(spec=AsyncSession)
    service = JobLifecycleService(mock_session)
    sys_ctx = SystemContext(reason="worker_claim_test")

    job_id = generate_uuid7()

    # Zero rows returned (job was not in 'queued' state)
    mock_result_none = MagicMock()
    mock_result_none.scalars.return_value.first.return_value = None
    mock_session.execute.return_value = mock_result_none

    result = await service.claim_job(sys_ctx, job_id)
    assert result is None


@pytest.mark.asyncio
async def test_job_heartbeat_updates_running_job() -> None:
    """Verify heartbeat update succeeds on running job."""
    mock_session = AsyncMock(spec=AsyncSession)
    service = JobLifecycleService(mock_session)
    sys_ctx = SystemContext(reason="heartbeat_test")

    job_id = generate_uuid7()

    mock_result = MagicMock()
    mock_result.rowcount = 1
    mock_session.execute.return_value = mock_result

    updated = await service.record_heartbeat(sys_ctx, job_id)
    assert updated is True
    assert mock_session.flush.called


@pytest.mark.asyncio
async def test_job_cooperative_cancellation_detection() -> None:
    """Verify cooperative cancellation detection transitions job to cancelled."""
    mock_session = AsyncMock(spec=AsyncSession)
    service = JobLifecycleService(mock_session)
    sys_ctx = SystemContext(reason="cancel_check")

    job_id = generate_uuid7()
    job = AnalysisJob(
        id=job_id,
        project_id=generate_uuid7(),
        type="ingest_project",
        status="cancel_requested",
        cancel_requested_at=datetime.now(UTC),
    )

    mock_result_job = MagicMock()
    mock_result_job.scalars.return_value.first.return_value = job

    mock_result_seq = MagicMock()
    mock_result_seq.scalar_one.return_value = 1

    mock_session.execute.side_effect = [mock_result_job, mock_result_seq]

    is_cancelled = await service.is_cancelled_or_requested(sys_ctx, job_id)
    assert is_cancelled is True
    assert job.status == "cancelled"
    assert job.finished_at is not None
    assert mock_session.flush.called


@pytest.mark.asyncio
async def test_complete_job_marks_succeeded_with_result_ref() -> None:
    """Verify completing a job sets status succeeded and stores result_ref."""
    mock_session = AsyncMock(spec=AsyncSession)
    service = JobLifecycleService(mock_session)
    sys_ctx = SystemContext(reason="complete_test")

    job_id = generate_uuid7()
    completed_job = AnalysisJob(
        id=job_id,
        project_id=generate_uuid7(),
        type="ingest_project",
        status="succeeded",
        result_ref={"files_ingested": 10},
    )

    mock_result_update = MagicMock()
    mock_result_update.scalars.return_value.first.return_value = completed_job

    mock_result_seq = MagicMock()
    mock_result_seq.scalar_one.return_value = 2

    mock_session.execute.side_effect = [mock_result_update, mock_result_seq]

    result = await service.complete_job(sys_ctx, job_id, result_ref={"files_ingested": 10})
    assert result is not None
    assert result.status == "succeeded"
    assert result.result_ref == {"files_ingested": 10}


@pytest.mark.asyncio
async def test_fail_job_requeues_when_retryable_and_attempts_remain() -> None:
    """Verify that a retryable failure requeues when attempt < max_attempts."""
    mock_session = AsyncMock(spec=AsyncSession)
    service = JobLifecycleService(mock_session)
    sys_ctx = SystemContext(reason="fail_retry_test")

    job_id = generate_uuid7()
    job = AnalysisJob(
        id=job_id,
        project_id=generate_uuid7(),
        type="ingest_project",
        status="running",
        attempt=1,
        max_attempts=3,
    )

    mock_result_job = MagicMock()
    mock_result_job.scalars.return_value.first.return_value = job

    mock_result_seq = MagicMock()
    mock_result_seq.scalar_one.return_value = 2

    mock_session.execute.side_effect = [mock_result_job, mock_result_seq]

    res = await service.fail_job(
        sys_ctx,
        job_id,
        error_code="RATE_LIMITED",
        error_detail="Temporary upstream rate limit",
        retryable=True,
    )
    assert res is not None
    assert res.status == "queued"
    assert res.error_code == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_fail_job_permanently_when_attempts_exhausted() -> None:
    """Verify that job permanently fails when max_attempts is reached."""
    mock_session = AsyncMock(spec=AsyncSession)
    service = JobLifecycleService(mock_session)
    sys_ctx = SystemContext(reason="fail_permanent_test")

    job_id = generate_uuid7()
    job = AnalysisJob(
        id=job_id,
        project_id=generate_uuid7(),
        type="ingest_project",
        status="running",
        attempt=3,
        max_attempts=3,
    )

    mock_result_job = MagicMock()
    mock_result_job.scalars.return_value.first.return_value = job

    mock_result_seq = MagicMock()
    mock_result_seq.scalar_one.return_value = 3

    mock_session.execute.side_effect = [mock_result_job, mock_result_seq]

    res = await service.fail_job(
        sys_ctx,
        job_id,
        error_code="PERSISTENT_ERROR",
        error_detail="Unrecoverable error",
        retryable=True,
    )
    assert res is not None
    assert res.status == "failed"
    assert res.finished_at is not None


@pytest.mark.asyncio
async def test_stale_job_reaper_requeues_dead_worker_jobs() -> None:
    """Verify that stale_job_reaper identifies dead worker jobs and requeues them if attempts remain."""
    mock_session = AsyncMock(spec=AsyncSession)
    service = JobLifecycleService(mock_session)
    sys_ctx = SystemContext(reason="reaper_test")

    job_id_1 = generate_uuid7()
    job_id_2 = generate_uuid7()

    # Job 1 has attempt 1/3 (requeued)
    stale_job_1 = AnalysisJob(
        id=job_id_1,
        project_id=generate_uuid7(),
        type="ingest_project",
        status="running",
        attempt=1,
        max_attempts=3,
        heartbeat_at=datetime.now(UTC) - timedelta(seconds=200),
    )
    # Job 2 has attempt 3/3 (exhausted -> failed)
    stale_job_2 = AnalysisJob(
        id=job_id_2,
        project_id=generate_uuid7(),
        type="ingest_project",
        status="running",
        attempt=3,
        max_attempts=3,
        heartbeat_at=datetime.now(UTC) - timedelta(seconds=250),
    )

    mock_result_stale = MagicMock()
    mock_result_stale.scalars.return_value.all.return_value = [stale_job_1, stale_job_2]

    mock_result_seq_1 = MagicMock()
    mock_result_seq_1.scalar_one.return_value = 1

    mock_result_seq_2 = MagicMock()
    mock_result_seq_2.scalar_one.return_value = 2

    mock_session.execute.side_effect = [mock_result_stale, mock_result_seq_1, mock_result_seq_2]

    reaped_count = await service.reap_stale_jobs(sys_ctx, heartbeat_timeout_seconds=120)
    assert reaped_count == 2
    assert stale_job_1.status == "queued"
    assert stale_job_1.error_code == "DEAD_WORKER_HEARTBEAT_TIMEOUT"
    assert stale_job_2.status == "failed"
    assert stale_job_2.finished_at is not None
    assert mock_session.flush.called


@pytest.mark.asyncio
async def test_sweep_stranded_jobs_finds_old_queued_jobs() -> None:
    """Verify that sweep_stranded_jobs returns queued job IDs older than threshold."""
    mock_session = AsyncMock(spec=AsyncSession)
    service = JobLifecycleService(mock_session)
    sys_ctx = SystemContext(reason="sweep_test")

    job_id = generate_uuid7()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [job_id]
    mock_session.execute.return_value = mock_result

    stranded = await service.sweep_stranded_jobs(sys_ctx, stranded_threshold_seconds=60)
    assert stranded == [job_id]
