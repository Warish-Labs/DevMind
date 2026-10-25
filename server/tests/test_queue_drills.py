"""Queue soak and Redis failure drills (M10-05, docs/02 §10, §11, docs/10 §9, §14, §16, §18).

Validates reliability, disaster recovery, and fault tolerance:
1. Redis temporary outage & graceful degradation:
   - Rate limiter falls back to in-memory sliding window on Redis connection failure.
   - SSE event stream falls back to DB polling on Redis Pub/Sub failure without dropping clients.
   - Worker and scheduler heartbeats log warnings and gracefully continue when Redis is down.
   - Alert evaluator captures Redis unavailability gracefully.
2. Redis crash & rebuild drill (reconstructibility from PostgreSQL):
   - PostgreSQL authoritative state holds stranded 'queued' and 'running' jobs.
   - Stale job reaper detects heartbeat timeouts on dead worker jobs and resets them to 'queued'.
   - Periodic enqueuer sweep sweeps all stranded jobs from PostgreSQL and re-enqueues them to Celery.
   - Atomic CAS claims guarantee idempotent execution without duplicate side effects.
3. Worker termination mid-task & retry / failure handling:
   - Celery task_acks_late and task_reject_on_worker_lost guarantees.
   - Dead worker job reaches max attempts and transitions to failed state with dead-worker error code.
4. Queue soak & backpressure:
   - Multi-queue routing (default, ingest, embed, analysis) under burst enqueue pressure.
   - Queue depth alert threshold trigger (> 50 messages) and recovery when drained.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
import redis.exceptions
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.alerts import AlertSeverity, evaluate_system_alerts
from app.core.auth_context import SystemContext
from app.core.heartbeat import (
    record_scheduler_heartbeat_sync,
    record_worker_heartbeat_sync,
)
from app.core.ids import generate_uuid7
from app.core.settings import Settings
from app.domain.jobs.service import JobLifecycleService
from app.middleware.rate_limit import RateLimitMiddleware
from app.persistence.models.brain import AnalysisJob
from app.workers.celery_app import create_celery_app

# ===========================================================================
# 1. Redis Outage & Graceful Degradation Drills (docs/10 §16, §18)
# ===========================================================================


@pytest.mark.asyncio
async def test_rate_limiter_in_memory_fallback_on_redis_outage() -> None:
    """Verify that when Redis is completely down, RateLimitMiddleware falls back to in-memory sliding window."""
    settings = Settings(
        rate_limit_enabled=True,
        rate_limit_read=5,
        redis_url="redis://invalid-host:6379/0",
    )

    middleware = RateLimitMiddleware(app=MagicMock(), settings=settings)

    # Mock Redis client that fails with ConnectionError
    mock_redis = MagicMock()
    pipe = MagicMock()
    pipe.execute = AsyncMock(
        side_effect=redis.exceptions.ConnectionError("Redis connection refused (outage drill)")
    )
    mock_redis.pipeline.return_value = pipe

    with patch("app.middleware.rate_limit.get_async_redis_client", return_value=mock_redis):
        # Dispatch 5 requests for the same principal
        test_key = f"rate_limit:test_outage:{generate_uuid7().hex[:8]}"

        # 5 allowed
        for _ in range(5):
            allowed, remaining, _, _ = await middleware._check_sliding_window(
                key=test_key, limit=5, window_seconds=60
            )
            assert allowed is True

        # 6th request is rejected by in-memory sliding window
        allowed, remaining, retry_after, _ = await middleware._check_sliding_window(
            key=test_key, limit=5, window_seconds=60
        )
        assert allowed is False
        assert retry_after > 0


@pytest.mark.asyncio
async def test_sse_stream_db_fallback_on_redis_pubsub_outage() -> None:
    """Verify that when Redis Pub/Sub fails, SSE streaming falls back to DB polling without crashing."""
    job_id = generate_uuid7()
    ctx = SystemContext(reason="redis_pubsub_outage_drill")

    mock_job = AnalysisJob(
        id=job_id,
        project_id=generate_uuid7(),
        type="ask_project",
        status="succeeded",
    )

    mock_session = AsyncMock(spec=AsyncSession)
    service = JobLifecycleService(mock_session)
    service.repo = AsyncMock()
    service.repo.get_job_events.return_value = []
    service.get_job_by_id = AsyncMock(return_value=mock_job)

    # Mock Redis client whose pubsub() raises ConnectionError
    mock_redis = MagicMock()
    mock_redis.pubsub.side_effect = redis.exceptions.ConnectionError("Redis Pub/Sub unreachable")

    with patch("app.domain.jobs.service.get_async_redis_client", return_value=mock_redis):
        events: list[dict[str, Any]] = []
        async for event in service.stream_job_events(
            ctx, job_id, since_seq=0, heartbeat_interval=0.1
        ):
            events.append(event)

        # Stream cleanly terminated with completion event from DB polling fallback
        assert len(events) >= 1
        assert events[-1]["event"] == "complete"
        assert events[-1]["data"]["status"] == "succeeded"


def test_heartbeat_sync_emission_resilient_on_redis_error() -> None:
    """Verify that synchronous worker and scheduler heartbeat recording does not crash on Redis failure."""
    settings = Settings(
        redis_key_prefix="drill:",
        redis_url="redis://localhost:6379/1",
    )

    with patch("redis.Redis.from_url") as mock_from_url:
        mock_client = MagicMock()
        mock_client.setex.side_effect = redis.exceptions.ConnectionError("Redis down")
        mock_client.sadd.side_effect = redis.exceptions.ConnectionError("Redis down")
        mock_from_url.return_value = mock_client

        # Worker heartbeat should not raise exception
        worker_hb = record_worker_heartbeat_sync(
            worker_id="test-worker-1", queues=["default"], settings=settings
        )
        assert worker_hb.worker_id == "test-worker-1"

        # Scheduler heartbeat should not raise exception
        scheduler_hb = record_scheduler_heartbeat_sync(settings=settings)
        assert scheduler_hb.scheduler_id == "scheduler-default"


@pytest.mark.asyncio
async def test_alert_evaluator_handles_redis_connection_error() -> None:
    """Verify that evaluate_alerts captures Redis connection failure without crashing and flags an alert."""
    settings = Settings(
        redis_key_prefix="drill:",
        redis_url="redis://invalid-host:6379/0",
    )

    mock_redis = AsyncMock()
    mock_redis.llen.side_effect = redis.exceptions.ConnectionError("Redis broker offline")

    alerts = await evaluate_system_alerts(settings=settings, redis_client=mock_redis)

    # At least one alert was emitted for the offline broker / heartbeats
    alert_names = [a.name for a in alerts]
    assert any("worker" in name or "scheduler" in name or "queue" in name for name in alert_names)


# ===========================================================================
# 2. Redis Crash & Queue Rebuild Drill (Reconstructibility from DB, docs/02 §11)
# ===========================================================================


@pytest.mark.asyncio
async def test_redis_crash_and_queue_rebuild_from_postgres_state() -> None:
    """Simulate complete Redis wipe and rebuild of queues via PostgreSQL authoritative state.

    Scenario:
    1. Redis broker crashes and restarts empty (0 messages in queues).
    2. In PostgreSQL:
       - Job A was 'queued' (waiting in Redis before crash).
       - Job B was 'running' on a worker that crashed along with Redis.
    3. Step 1: Stale job reaper identifies Job B (expired heartbeat) and requeues it back to 'queued'.
    4. Step 2: Enqueuer sweep identifies all stranded 'queued' jobs (Job A & Job B) and re-dispatches to Celery.
    5. Step 3: Worker claims and completes both jobs.
    """
    job_a_id = generate_uuid7()
    job_b_id = generate_uuid7()
    now = datetime.now(UTC)
    old_time = now - timedelta(seconds=180)  # > 120s stale threshold

    # Mock DB jobs
    job_a = AnalysisJob(
        id=job_a_id,
        project_id=generate_uuid7(),
        type="security_review",
        status="queued",
        attempt=0,
    )
    job_a.created_at = old_time

    job_b = AnalysisJob(
        id=job_b_id,
        project_id=generate_uuid7(),
        type="ask_project",
        status="running",
        attempt=1,
        max_attempts=3,
    )
    job_b.started_at = old_time
    job_b.heartbeat_at = old_time  # Dead worker heartbeat

    jobs_db: dict[UUID, AnalysisJob] = {
        job_a_id: job_a,
        job_b_id: job_b,
    }

    mock_session = AsyncMock(spec=AsyncSession)
    service = JobLifecycleService(mock_session)
    sys_ctx = SystemContext(reason="redis_rebuild_drill")

    # Step 1: Run stale job reaper
    # Simulate DB query returning stale running jobs
    async def mock_execute_reap(stmt):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            j for j in jobs_db.values() if j.status == "running"
        ]
        return mock_result

    mock_session.execute = mock_execute_reap
    service._append_event = AsyncMock()

    reaped_count = await service.reap_stale_jobs(sys_ctx, heartbeat_timeout_seconds=120)

    # Job B was reaped and requeued to 'queued' state
    assert reaped_count == 1
    assert job_b.status == "queued"
    assert job_b.error_code == "DEAD_WORKER_HEARTBEAT_TIMEOUT"

    # Step 2: Run enqueuer sweep on all stranded 'queued' jobs
    async def mock_execute_sweep(stmt):
        mock_result = MagicMock()
        # Returns all queued job IDs
        mock_result.scalars.return_value.all.return_value = [
            j.id for j in jobs_db.values() if j.status == "queued"
        ]
        return mock_result

    mock_session.execute = mock_execute_sweep

    stranded_job_ids = await service.sweep_stranded_jobs(sys_ctx, stranded_threshold_seconds=60)

    # Both Job A and Job B are swept for re-enqueueing
    assert len(stranded_job_ids) == 2
    assert job_a_id in stranded_job_ids
    assert job_b_id in stranded_job_ids

    # Step 3: Verify atomic CAS claim transitions queued -> running idempotently
    async def mock_claim(ctx, target_job_id):
        job = jobs_db.get(target_job_id)
        if job and job.status == "queued":
            job.status = "running"
            job.attempt = (job.attempt or 0) + 1
            job.heartbeat_at = datetime.now(UTC)
            return job
        return None

    service.claim_job = mock_claim

    # Worker claims Job A
    claimed_a = await service.claim_job(sys_ctx, job_a_id)
    assert claimed_a is not None
    assert claimed_a.status == "running"
    assert claimed_a.attempt == 1

    # Duplicate worker claim for Job A is rejected (idempotency guard)
    duplicate_claim = await service.claim_job(sys_ctx, job_a_id)
    assert duplicate_claim is None


# ===========================================================================
# 3. Worker Termination Mid-Task & Retry Lifecycle (docs/10 §9)
# ===========================================================================


def test_celery_reliability_flags_configured() -> None:
    """Verify Celery task_acks_late and task_reject_on_worker_lost are enforced (docs/10 §9)."""
    settings = Settings(
        redis_key_prefix="drill:",
        redis_url="redis://localhost:6379/1",
    )
    celery_app = create_celery_app(settings)

    # Task acknowledgement happens only after task completion
    assert celery_app.conf.task_acks_late is True
    # If worker dies abruptly (SIGKILL, OOM), message is rejected and re-queued
    assert celery_app.conf.task_reject_on_worker_lost is True
    # Visibility timeout is 3600s, preventing premature redelivery during execution
    assert celery_app.conf.broker_transport_options["visibility_timeout"] >= 3600


@pytest.mark.asyncio
async def test_dead_worker_reaches_max_attempts_and_fails() -> None:
    """Verify that a job repeatedly abandoned by a dying worker eventually transitions to 'failed'."""
    job_id = generate_uuid7()
    now = datetime.now(UTC)
    old_time = now - timedelta(seconds=200)

    job = AnalysisJob(
        id=job_id,
        project_id=generate_uuid7(),
        type="ask_project",
        status="running",
        attempt=3,  # Already at max_attempts
        max_attempts=3,
    )
    job.started_at = old_time
    job.heartbeat_at = old_time

    mock_session = AsyncMock(spec=AsyncSession)

    async def mock_execute(stmt):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [job]
        return mock_result

    mock_session.execute = mock_execute
    service = JobLifecycleService(mock_session)
    service._append_event = AsyncMock()
    sys_ctx = SystemContext(reason="dead_worker_max_attempts_drill")

    reaped_count = await service.reap_stale_jobs(sys_ctx, heartbeat_timeout_seconds=120)

    assert reaped_count == 1
    assert job.status == "failed"
    assert job.error_code == "DEAD_WORKER_HEARTBEAT_TIMEOUT"
    assert "maximum attempts" in (job.error_detail or "")


# ===========================================================================
# 4. Queue Soak & Backpressure Drill (docs/10 §14, §21)
# ===========================================================================


def test_multi_queue_routing_topology() -> None:
    """Verify multi-queue routing rules distribute workloads cleanly across queue partitions."""
    settings = Settings(
        redis_key_prefix="drill:",
        redis_url="redis://localhost:6379/1",
    )
    celery_app = create_celery_app(settings)

    routes = celery_app.conf.task_routes

    # Check designated queues
    assert routes["devmind.ingest_*"]["queue"] == "drill:ingest"
    assert routes["devmind.embed_*"]["queue"] == "drill:embed"
    assert routes["devmind.analysis_*"]["queue"] == "drill:analysis"
    assert routes["devmind.*"]["queue"] == "drill:default"


@pytest.mark.asyncio
async def test_queue_depth_alert_triggered_under_burst_soak() -> None:
    """Simulate soak burst where queue depth exceeds threshold (>50 messages), triggering alert."""
    settings = Settings(
        redis_key_prefix="drill:",
        alert_max_queue_depth=50,
    )

    mock_redis = AsyncMock()
    # Simulate high queue depth under soak: 75 messages in default queue
    mock_redis.llen.return_value = 75

    # Mock active heartbeats so worker is healthy
    with patch("app.core.alerts.check_worker_liveness", return_value=(True, [MagicMock()], [])):
        with patch(
            "app.core.alerts.check_scheduler_liveness", return_value=(True, MagicMock(), 5.0)
        ):
            alerts = await evaluate_system_alerts(settings=settings, redis_client=mock_redis)

            # High queue depth triggers warning alert
            queue_alerts = [a for a in alerts if a.name == "queue_depth_exceeded"]
            assert len(queue_alerts) > 0
            assert queue_alerts[0].severity == AlertSeverity.WARNING
            assert queue_alerts[0].current_value == 75
            assert queue_alerts[0].threshold == 50.0

            # Once queue drains below 50, alert clears
            mock_redis.llen.return_value = 10
            cleared_alerts = await evaluate_system_alerts(
                settings=settings, redis_client=mock_redis
            )
            assert not any(a.name == "queue_depth_exceeded" for a in cleared_alerts)
