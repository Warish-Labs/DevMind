"""Job lifecycle domain service managing async work states, claims, heartbeats, and reaping (docs/02 §10, docs/03 §3.3, docs/10 §9)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import SystemContext
from app.persistence.models.brain import AnalysisJob, JobEvent
from app.persistence.repositories.brain_repo import BrainRepository


class JobLifecycleService:
    """Domain service managing the lifecycle state machine for AnalysisJobs.

    Guarantees:
    - Atomic compare-and-set claiming (prevents double execution).
    - Periodic heartbeats tracking live worker leases.
    - Safe cooperative cancellation checks at safe points.
    - Dead worker reaping for expired heartbeats with retry budgeting.
    - Enqueuer sweep finding stranded queued jobs.
    - Milestone event persistence to `job_events`.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = BrainRepository(session)

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
            await self._append_event(
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
        if retryable and job.attempt < job.max_attempts:
            job.status = "queued"
            job.error_code = error_code
            job.error_detail = error_detail
            await self._append_event(
                ctx,
                job_id,
                kind="retry_queued",
                message=f"Transient failure ({error_code}); requeued for attempt {job.attempt + 1}/{job.max_attempts}",
                data={"error_code": error_code, "attempt": job.attempt},
            )
        else:
            job.status = "failed"
            job.finished_at = now
            job.error_code = error_code
            job.error_detail = error_detail
            await self._append_event(
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
            if job.attempt < job.max_attempts:
                job.status = "queued"
                job.error_code = "DEAD_WORKER_HEARTBEAT_TIMEOUT"
                job.error_detail = f"Worker heartbeat lease expired (>{heartbeat_timeout_seconds}s); requeued for recovery"
                await self._append_event(
                    ctx,
                    job.id,
                    kind="reaped_requeued",
                    message=f"Dead worker detected. Requeued for attempt {job.attempt + 1}/{job.max_attempts}",
                    data={"reaped_at": now.isoformat()},
                )
            else:
                job.status = "failed"
                job.finished_at = now
                job.error_code = "DEAD_WORKER_HEARTBEAT_TIMEOUT"
                job.error_detail = f"Worker heartbeat lease expired (>{heartbeat_timeout_seconds}s); maximum attempts ({job.max_attempts}) reached"
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
