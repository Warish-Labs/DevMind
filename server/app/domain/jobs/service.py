"""Job lifecycle domain service managing async work states, claims, heartbeats, and reaping (docs/02 §10, docs/03 §3.3, docs/10 §9)."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import NotFoundError
from app.core.redis import get_async_redis_client
from app.core.settings import get_settings
from app.persistence.models.brain import AnalysisJob, JobEvent
from app.persistence.repositories.brain_repo import BrainRepository

logger = logging.getLogger("devmind.jobs")

_default_job_enqueuer: Callable[[UUID], Any] | None = None


def register_job_enqueuer(fn: Callable[[UUID], Any]) -> None:
    """Register the global Celery task enqueuer without breaking domain layer boundaries."""
    global _default_job_enqueuer
    _default_job_enqueuer = fn


def get_job_enqueuer() -> Callable[[UUID], Any] | None:
    return _default_job_enqueuer


class JobLifecycleService:
    """Domain service managing the lifecycle state machine for AnalysisJobs.

    Guarantees:
    - Atomic compare-and-set claiming (prevents double execution).
    - Periodic heartbeats tracking live worker leases.
    - Safe cooperative cancellation checks at safe points.
    - Dead worker reaping for expired heartbeats with retry budgeting.
    - Enqueuer sweep finding stranded queued jobs.
    - Milestone event persistence to `job_events`.
    - Real-time Redis pub/sub broadcasting and SSE streaming.
    """

    def __init__(
        self,
        session: AsyncSession,
        enqueuer: Callable[[UUID], Any] | None = None,
    ) -> None:
        self.session = session
        self.repo = BrainRepository(session)
        self.enqueuer = enqueuer or _default_job_enqueuer

    async def _append_event(
        self,
        ctx: SystemContext,
        job_id: UUID,
        kind: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> JobEvent:
        """Helper to append an event to the job log."""
        stmt = select(func.coalesce(func.max(JobEvent.seq), 0)).where(JobEvent.job_id == job_id)
        res = await self.session.execute(stmt)
        next_seq = res.scalar_one() + 1

        event = JobEvent(
            job_id=job_id,
            seq=next_seq,
            kind=kind,
            message=message,
            data=data or {},
        )
        self.session.add(event)
        return event

    async def claim_job(self, ctx: SystemContext, job_id: UUID) -> AnalysisJob | None:
        """Atomically claim a queued job for worker execution.

        Returns:
            The claimed AnalysisJob in 'running' state, or None if already claimed or not queued.
        """
        now = datetime.now(UTC)
        stmt = (
            update(AnalysisJob)
            .where(
                AnalysisJob.id == job_id,
                AnalysisJob.status == "queued",
            )
            .values(
                status="running",
                attempt=AnalysisJob.attempt + 1,
                heartbeat_at=now,
                started_at=func.coalesce(AnalysisJob.started_at, now),
            )
            .returning(AnalysisJob)
        )
        result = await self.session.execute(stmt)
        job = result.scalars().first()

        if job:
            await self._append_event(
                ctx,
                job_id,
                kind="claimed",
                message=f"Job claimed by worker on attempt {job.attempt}",
                data={"attempt": job.attempt, "queue": job.queue},
            )
            await self.session.flush()

        return job

    async def record_heartbeat(self, ctx: SystemContext, job_id: UUID) -> bool:
        """Record activity heartbeat for a running job.

        Returns:
            True if heartbeat was updated, False if job is no longer running.
        """
        now = datetime.now(UTC)
        stmt = (
            update(AnalysisJob)
            .where(
                AnalysisJob.id == job_id,
                AnalysisJob.status == "running",
            )
            .values(heartbeat_at=now)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def is_cancelled_or_requested(self, ctx: SystemContext, job_id: UUID) -> bool:
        """Check if user requested job cancellation and transition to cancelled state if so."""
        stmt = select(AnalysisJob).where(AnalysisJob.id == job_id)
        result = await self.session.execute(stmt)
        job = result.scalars().first()

        if not job:
            return False

        if job.status == "cancelled":
            return True

        if job.status == "cancel_requested" or job.cancel_requested_at is not None:
            now = datetime.now(UTC)
            job.status = "cancelled"
            job.finished_at = now
            await self._append_event(
                ctx,
                job_id,
                kind="cancelled",
                message="Job cancelled at cooperative checkpoint",
            )
            await self.session.flush()
            return True

        return False

    async def complete_job(
        self,
        ctx: SystemContext,
        job_id: UUID,
        result_ref: dict[str, Any] | None = None,
    ) -> AnalysisJob | None:
        """Mark a job as successfully completed."""
        now = datetime.now(UTC)
        stmt = (
            update(AnalysisJob)
            .where(
                AnalysisJob.id == job_id,
                AnalysisJob.status == "running",
            )
            .values(
                status="succeeded",
                finished_at=now,
                result_ref=result_ref,
            )
            .returning(AnalysisJob)
        )
        result = await self.session.execute(stmt)
        job = result.scalars().first()

        if job:
            await self.publish_job_event(
                ctx,
                job_id,
                kind="succeeded",
                message="Job finished with status 'succeeded'",
                data={"result_ref": result_ref},
            )
            await self.session.flush()

        return job

    async def fail_job(
        self,
        ctx: SystemContext,
        job_id: UUID,
        error_code: str,
        error_detail: str | None = None,
        retryable: bool = False,
    ) -> AnalysisJob | None:
        """Record job failure, requeuing if retryable and attempts remain."""
        stmt = select(AnalysisJob).where(AnalysisJob.id == job_id)
        result = await self.session.execute(stmt)
        job = result.scalars().first()

        if not job:
            return None

        now = datetime.now(UTC)
        attempt = job.attempt or 0
        max_attempts = job.max_attempts or 3
        if retryable and attempt < max_attempts:
            job.status = "queued"
            job.error_code = error_code
            job.error_detail = error_detail
            await self.publish_job_event(
                ctx,
                job_id,
                kind="retry_queued",
                message=f"Transient failure ({error_code}); requeued for attempt {attempt + 1}/{max_attempts}",
                data={"error_code": error_code, "attempt": attempt},
            )
        else:
            job.status = "failed"
            job.finished_at = now
            job.error_code = error_code
            job.error_detail = error_detail
            await self.publish_job_event(
                ctx,
                job_id,
                kind="failed",
                message=f"Job permanently failed with code '{error_code}': {error_detail or ''}",
                data={"error_code": error_code, "error_detail": error_detail},
            )

        await self.session.flush()
        return job

    async def reap_stale_jobs(
        self, ctx: SystemContext, heartbeat_timeout_seconds: int = 120
    ) -> int:
        """Find running jobs with expired heartbeats and either requeue or fail them."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=heartbeat_timeout_seconds)

        stmt = select(AnalysisJob).where(
            AnalysisJob.status == "running",
            (AnalysisJob.heartbeat_at < cutoff)
            | (AnalysisJob.heartbeat_at.is_(None) & (AnalysisJob.started_at < cutoff)),
        )
        result = await self.session.execute(stmt)
        stale_jobs = list(result.scalars().all())

        reaped_count = 0
        for job in stale_jobs:
            attempt = job.attempt or 0
            max_attempts = job.max_attempts or 3
            if attempt < max_attempts:
                job.status = "queued"
                job.error_code = "DEAD_WORKER_HEARTBEAT_TIMEOUT"
                job.error_detail = f"Worker heartbeat lease expired (>{heartbeat_timeout_seconds}s); requeued for recovery"
                await self._append_event(
                    ctx,
                    job.id,
                    kind="reaped_requeued",
                    message=f"Dead worker detected. Requeued for attempt {attempt + 1}/{max_attempts}",
                    data={"reaped_at": now.isoformat()},
                )
            else:
                job.status = "failed"
                job.finished_at = now
                job.error_code = "DEAD_WORKER_HEARTBEAT_TIMEOUT"
                job.error_detail = f"Worker heartbeat lease expired (>{heartbeat_timeout_seconds}s); maximum attempts ({max_attempts}) reached"
                await self._append_event(
                    ctx,
                    job.id,
                    kind="reaped_failed",
                    message="Dead worker detected. Maximum attempts exhausted; marked failed.",
                    data={"reaped_at": now.isoformat()},
                )
            reaped_count += 1

        if reaped_count > 0:
            await self.session.flush()

        return reaped_count

    async def sweep_stranded_jobs(
        self, ctx: SystemContext, stranded_threshold_seconds: int = 60
    ) -> list[UUID]:
        """Find jobs stuck in 'queued' state for longer than threshold (e.g. after container restart)."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=stranded_threshold_seconds)

        stmt = select(AnalysisJob.id).where(
            AnalysisJob.status == "queued",
            AnalysisJob.created_at < cutoff,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # --- Agent Workflows and Analysis Job Operations (docs/03 §5.2, §12.2) ---

    async def create_analysis_job(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        job_type: str,
        params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        consent_id: UUID | None = None,
    ) -> AnalysisJob:
        """Create and enqueue an asynchronous analysis job (docs/03 §3.3, §12.2)."""
        requested_by = getattr(ctx, "user_id", None) if isinstance(ctx, AuthContext) else None
        job = await self.repo.create_job(
            ctx=ctx,
            project_id=project_id,
            job_type=job_type,
            params=params or {},
            idempotency_key=idempotency_key,
            consent_id=consent_id,
            requested_by=requested_by,
        )

        # Append initial created event and broadcast
        await self.publish_job_event(
            ctx=ctx,
            job_id=job.id,
            kind="created",
            message=f"Analysis job created (type={job_type})",
            data={"job_type": job_type, "params": params or {}},
        )

        # Dispatch execution via registered enqueuer
        if self.enqueuer:
            try:
                self.enqueuer(job.id)
            except Exception as exc:
                logger.warning("Failed to enqueue job %s: %s", job.id, exc)

        return job

    async def get_job_by_id(
        self,
        ctx: AuthContext | SystemContext,
        job_id: UUID,
    ) -> AnalysisJob | None:
        """Retrieve an analysis job by ID with authorization verification."""
        return await self.repo.get_job_by_id(ctx, job_id)

    async def list_project_jobs(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AnalysisJob]:
        """List background jobs for a project."""
        return await self.repo.list_jobs(ctx, project_id, status=status, limit=limit, offset=offset)

    async def request_job_cancellation(
        self,
        ctx: AuthContext | SystemContext,
        job_id: UUID,
    ) -> AnalysisJob:
        """Request cooperative cancellation of a background job."""
        job = await self.get_job_by_id(ctx, job_id)
        if not job:
            raise NotFoundError(f"Job {job_id} not found", code="job.not_found")

        now = datetime.now(UTC)
        if job.status in ("succeeded", "failed", "cancelled"):
            return job

        if job.status == "queued":
            job.status = "cancelled"
            job.finished_at = now
            await self.publish_job_event(
                ctx=ctx,
                job_id=job_id,
                kind="cancelled",
                message="Job cancelled while queued",
            )
        else:
            job.status = "cancel_requested"
            job.cancel_requested_at = now
            await self.publish_job_event(
                ctx=ctx,
                job_id=job_id,
                kind="cancel_requested",
                message="Cancellation requested by user",
            )

        await self.session.flush()
        return job

    async def publish_job_event(
        self,
        ctx: AuthContext | SystemContext,
        job_id: UUID,
        kind: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> JobEvent:
        """Persist milestone event to database and broadcast on Redis pub/sub channel."""
        event = await self.repo.record_job_event(
            ctx=ctx,
            job_id=job_id,
            kind=kind,
            message=message,
            data=data or {},
        )

        try:
            settings = get_settings()
            redis_client = get_async_redis_client(settings)
            channel = f"{settings.redis_key_prefix}job_events:{job_id}"
            payload = json.dumps(
                {
                    "id": str(event.id),
                    "job_id": str(job_id),
                    "seq": event.seq,
                    "kind": event.kind,
                    "message": event.message,
                    "data": event.data,
                    "created_at": event.created_at.isoformat()
                    if event.created_at
                    else datetime.now(UTC).isoformat(),
                }
            )
            await redis_client.publish(channel, payload)
        except Exception as exc:
            logger.debug("Failed to publish job event to Redis channel: %s", exc)

        return event

    async def stream_job_events(
        self,
        ctx: AuthContext | SystemContext,
        job_id: UUID,
        since_seq: int = 0,
        heartbeat_interval: float = 15.0,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream past events from DB and real-time events from Redis pub/sub via SSE."""
        job = await self.get_job_by_id(ctx, job_id)
        if not job:
            raise NotFoundError(f"Job {job_id} not found", code="job.not_found")

        # 1. Yield all historic events with seq > since_seq
        past_events = await self.repo.get_job_events(ctx, job_id, since_seq=since_seq)
        last_seq = since_seq
        for ev in past_events:
            last_seq = max(last_seq, ev.seq)
            yield {
                "event": "milestone",
                "data": {
                    "id": str(ev.id),
                    "job_id": str(ev.job_id),
                    "seq": ev.seq,
                    "kind": ev.kind,
                    "message": ev.message,
                    "data": ev.data,
                    "created_at": ev.created_at.isoformat() if ev.created_at else "",
                },
            }

        # If job is already in terminal state, emit complete and finish
        if job.status in ("succeeded", "failed", "cancelled"):
            yield {
                "event": "complete",
                "data": {
                    "status": job.status,
                    "result_ref": job.result_ref,
                    "error_code": job.error_code,
                    "error_detail": job.error_detail,
                },
            }
            return

        # 2. Subscribe to Redis pub/sub for real-time streaming
        settings = get_settings()
        pubsub = None
        channel = f"{settings.redis_key_prefix}job_events:{job_id}"
        try:
            redis_client = get_async_redis_client(settings)
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(channel)
        except Exception as exc:
            logger.warning("Redis pubsub subscription failed (%s); polling DB fallback", exc)
            pubsub = None

        try:
            while True:
                msg = None
                if pubsub:
                    try:
                        msg = await asyncio.wait_for(
                            pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                            timeout=heartbeat_interval,
                        )
                    except TimeoutError:
                        msg = None
                else:
                    await asyncio.sleep(min(heartbeat_interval, 2.0))

                if msg and msg.get("type") == "message":
                    raw_data = msg.get("data")
                    if raw_data:
                        try:
                            payload = (
                                json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                            )
                            seq = payload.get("seq", 0)
                            if seq > last_seq:
                                last_seq = seq
                                yield {"event": "milestone", "data": payload}
                                if payload.get("kind") in ("succeeded", "failed", "cancelled"):
                                    yield {"event": "complete", "data": payload.get("data", {})}
                                    break
                        except Exception:
                            pass
                elif msg is None:
                    # Heartbeat ping
                    yield {"event": "ping", "data": {}}

                # Check fresh DB state for terminal status
                fresh_job = await self.get_job_by_id(ctx, job_id)
                if fresh_job and fresh_job.status in ("succeeded", "failed", "cancelled"):
                    yield {
                        "event": "complete",
                        "data": {
                            "status": fresh_job.status,
                            "result_ref": fresh_job.result_ref,
                            "error_code": fresh_job.error_code,
                            "error_detail": fresh_job.error_detail,
                        },
                    }
                    break

        finally:
            if pubsub:
                try:
                    await pubsub.unsubscribe(channel)
                    await pubsub.aclose()
                except Exception:
                    pass
