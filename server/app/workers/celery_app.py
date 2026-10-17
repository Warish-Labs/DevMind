"""Celery application configuration for DevMind background workers (docs/10 §9, docs/02 §10)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any
from uuid import UUID

from celery import Celery
from kombu import Queue
from sqlalchemy import select

from app.core.auth_context import SystemContext
from app.core.settings import Settings, get_settings
from app.domain.brain.embedding_service import EmbeddingService
from app.domain.jobs.service import JobLifecycleService
from app.persistence.database import session_scope
from app.persistence.models.brain import AnalysisJob

logger = logging.getLogger("devmind.workers")


def _run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    """Helper to run async database coroutines synchronously within Celery tasks."""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def create_celery_app(settings: Settings | None = None) -> Celery:
    """Create and configure the Celery application with multi-workload queues and reliability guarantees."""
    if settings is None:
        settings = get_settings()

    app = Celery("devmind")

    # Prefix isolation for shared Redis (Render Key Value, ADR-046)
    prefix = settings.redis_key_prefix

    default_queue = f"{prefix}default"
    ingest_queue = f"{prefix}ingest"
    embed_queue = f"{prefix}embed"
    analysis_queue = f"{prefix}analysis"

    app.conf.update(
        broker_url=settings.redis_url,
        result_backend=settings.redis_url,
        broker_transport_options={
            "global_keyprefix": prefix,
            "visibility_timeout": 3600,  # Greater than max task duration to prevent duplicate delivery (docs/10 §9)
        },
        result_backend_transport_options={"global_keyprefix": prefix},
        task_default_queue=default_queue,
        task_queues=(
            Queue(default_queue, routing_key="default"),
            Queue(ingest_queue, routing_key="ingest"),
            Queue(embed_queue, routing_key="embed"),
            Queue(analysis_queue, routing_key="analysis"),
        ),
        task_routes={
            "devmind.ingest_*": {"queue": ingest_queue},
            "devmind.embed_*": {"queue": embed_queue},
            "devmind.analysis_*": {"queue": analysis_queue},
            "devmind.*": {"queue": default_queue},
        },
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_acks_late=True,  # Return message to queue on worker loss (docs/10 §9)
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,  # Low prefetch to prevent head-of-line blocking on long tasks
        timezone="UTC",
        enable_utc=True,
        beat_schedule={
            "devmind.enqueuer_sweep": {
                "task": "devmind.enqueuer_sweep",
                "schedule": 60.0,
            },
            "devmind.stale_job_reaper": {
                "task": "devmind.stale_job_reaper",
                "schedule": 60.0,
            },
        },
    )

    @app.task(name="devmind.ping")
    def ping() -> str:
        """Health check probe task."""
        return "pong"

    @app.task(name="devmind.enqueuer_sweep")
    def enqueuer_sweep() -> dict[str, Any]:
        """Periodic scheduler task finding queued jobs stranded by container restarts/sleeps (docs/02 §10.2)."""
        logger.info("Executing periodic enqueuer sweep")

        async def _sweep() -> list[UUID]:
            async with session_scope() as session:
                service = JobLifecycleService(session)
                sys_ctx = SystemContext(reason="periodic_enqueuer_sweep")
                return await service.sweep_stranded_jobs(sys_ctx, stranded_threshold_seconds=60)

        stranded_ids = _run_async(_sweep())
        for job_id in stranded_ids:
            logger.info("Re-dispatching stranded queued job: %s", job_id)
            process_job.apply_async(args=[str(job_id)])

        return {
            "status": "ok",
            "swept": len(stranded_ids),
            "job_ids": [str(j) for j in stranded_ids],
        }

    @app.task(name="devmind.stale_job_reaper")
    def stale_job_reaper() -> dict[str, Any]:
        """Periodic scheduler task reaping jobs whose worker heartbeat expired (docs/02 §10.2)."""
        logger.info("Executing periodic stale job reaper")

        async def _reap() -> int:
            async with session_scope() as session:
                service = JobLifecycleService(session)
                sys_ctx = SystemContext(reason="periodic_stale_job_reaper")
                return await service.reap_stale_jobs(sys_ctx, heartbeat_timeout_seconds=120)

        reaped_count = _run_async(_reap())
        return {"status": "ok", "reaped": reaped_count}

    @app.task(name="devmind.process_job", bind=True)
    def process_job(self: Any, job_id_str: str) -> dict[str, Any]:
        """Worker task processing an analysis job by ID with compare-and-set claim and heartbeat lease."""
        job_id = UUID(job_id_str)
        sys_ctx = SystemContext(reason=f"worker_process_job_{job_id}")

        async def _claim() -> tuple[bool, str, dict[str, Any]]:
            async with session_scope() as session:
                service = JobLifecycleService(session)
                job = await service.claim_job(sys_ctx, job_id)
                if not job:
                    return False, "", {}
                return True, job.type, job.params

        claimed, job_type, params = _run_async(_claim())
        if not claimed:
            logger.info("Job %s was not in queued state or already claimed; skipping", job_id)
            return {"status": "skipped", "job_id": job_id_str}

        logger.info("Worker claimed job %s (type=%s)", job_id, job_type)

        try:
            # Check for cancellation before executing heavy work
            async def _check_cancelled() -> bool:
                async with session_scope() as session:
                    service = JobLifecycleService(session)
                    return await service.is_cancelled_or_requested(sys_ctx, job_id)

            if _run_async(_check_cancelled()):
                logger.info("Job %s was cancelled before execution completed", job_id)
                return {"status": "cancelled", "job_id": job_id_str}

            # Dispatch based on job type (ingest_project, embed_chunks, security_review, etc.)
            result_data = {
                "processed_at": asyncio.get_event_loop().time()
                if asyncio.get_event_loop().is_running()
                else 0
            }

            if job_type == "embed_chunks":

                async def _run_embed() -> dict[str, Any]:
                    async with session_scope() as session:
                        service = EmbeddingService(session)
                        project_id_raw = params.get("project_id")
                        if not project_id_raw:
                            stmt = select(AnalysisJob).where(AnalysisJob.id == job_id)
                            job_rec = (await session.execute(stmt)).scalars().first()
                            project_id = job_rec.project_id if job_rec else None
                        else:
                            project_id = UUID(project_id_raw)
                        if not project_id:
                            raise ValueError(f"No project_id associated with job {job_id}")

                        space_id_raw = params.get("space_id")
                        space_id = UUID(space_id_raw) if space_id_raw else None
                        batch_size = int(params.get("batch_size", 50))
                        return await service.process_embed_chunks(
                            ctx=sys_ctx,
                            project_id=project_id,
                            space_id=space_id,
                            batch_size=batch_size,
                        )

                embed_stats = _run_async(_run_embed())
                result_data.update(embed_stats)

            async def _complete() -> None:
                async with session_scope() as session:
                    service = JobLifecycleService(session)
                    await service.complete_job(sys_ctx, job_id, result_ref=result_data)

            _run_async(_complete())
            logger.info("Job %s completed successfully", job_id)
            return {"status": "succeeded", "job_id": job_id_str, "result": result_data}

        except Exception as exc:
            error_msg = str(exc)
            logger.error("Job %s failed with exception: %s", job_id, error_msg, exc_info=True)

            async def _fail() -> None:
                async with session_scope() as session:
                    service = JobLifecycleService(session)
                    await service.fail_job(
                        sys_ctx,
                        job_id,
                        error_code="WORKER_EXECUTION_ERROR",
                        error_detail=error_msg,
                        retryable=True,
                    )

            _run_async(_fail())
            raise

    return app


celery_app = create_celery_app()
