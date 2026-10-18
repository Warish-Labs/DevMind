"""Celery application configuration for DevMind background workers (docs/10 §9, docs/02 §10)."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Coroutine
from typing import Any
from uuid import UUID

from celery import Celery
from kombu import Queue
from sqlalchemy import select

from app.core.auth_context import SystemContext
from app.core.settings import Settings, get_settings
from app.domain.brain.embedding_service import EmbeddingService
from app.domain.jobs import register_job_enqueuer
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
            result_data = {"processed_at": time.time()}

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

            elif job_type in ("ask_project", "security_review", "comprehensive_review"):

                async def _run_agent_workflow() -> dict[str, Any]:
                    async with session_scope() as session:
                        service = JobLifecycleService(session)
                        stmt = select(AnalysisJob).where(AnalysisJob.id == job_id)
                        job_rec = (await session.execute(stmt)).scalars().first()
                        if not job_rec:
                            raise ValueError(f"Job {job_id} not found")
                        project_id = job_rec.project_id

                        # Emit intake milestone
                        await service.publish_job_event(
                            sys_ctx,
                            job_id,
                            kind="intake",
                            message=f"Starting {job_type} agent workflow",
                            data={"job_type": job_type, "params": params},
                        )

                        # Build AgentManager and execute
                        from app.orchestration.manager import AgentManager
                        from app.orchestration.state import create_initial_run_state
                        from app.persistence.repositories.brain_repo import BrainRepository

                        manager = AgentManager(session=session)

                        # Determine user query
                        user_message = params.get("query") or params.get("message")
                        if not user_message and job_type == "security_review":
                            user_message = "Review route security and authentication guards."

                        run_id = f"run_{job_id}"
                        workspace_id = params.get("workspace_id") or str(project_id)
                        actor_id = (
                            str(job_rec.requested_by)
                            if getattr(job_rec, "requested_by", None)
                            else "system"
                        )
                        init_state = create_initial_run_state(
                            run_id=run_id,
                            job_id=str(job_id),
                            project_id=str(project_id),
                            workspace_id=str(workspace_id),
                            actor_id=actor_id,
                            job_type=job_type,
                            params=params,
                            user_message=user_message,
                            consent_id=params.get("consent_id"),
                        )

                        # Execute workflow
                        final_state = await manager.run(init_state)

                        # Check for verified findings to persist
                        verified = final_state.get("verified", [])
                        persisted_findings_count = 0
                        if verified:
                            brain_repo = BrainRepository(session)
                            findings_payloads = []
                            for vf in verified:
                                s_line, e_line = vf.line_range if vf.line_range else (1, 1)
                                fp = f"{vf.rule_id}:{vf.file_path}:{s_line}-{e_line}"
                                findings_payloads.append(
                                    {
                                        "fingerprint": fp,
                                        "rule_id": vf.rule_id or "devmind.security.finding",
                                        "source": "llm_verified",
                                        "category": "security",
                                        "title": vf.title or "Security finding",
                                        "summary": vf.resolution_notes
                                        or "Detected security finding",
                                        "explanation": vf.resolution_notes,
                                        "severity": "high",
                                        "confidence": str(vf.confidence),
                                        "evidence_level": f"E{vf.evidence_level}",
                                        "status": "open",
                                        "primary_start_line": s_line,
                                        "primary_end_line": e_line,
                                    }
                                )
                            saved = await brain_repo.batch_upsert_findings(
                                sys_ctx, project_id, findings_payloads
                            )
                            persisted_findings_count = len(saved)

                            await service.publish_job_event(
                                sys_ctx,
                                job_id,
                                kind="findings_persisted",
                                message=f"Persisted {persisted_findings_count} findings to database",
                                data={"findings_count": persisted_findings_count},
                            )

                        # Emit progress & usage milestone
                        usage = final_state.get("usage")
                        if hasattr(usage, "total_input_tokens"):
                            in_tokens = usage.total_input_tokens
                            out_tokens = usage.total_output_tokens
                            tot_tokens = in_tokens + out_tokens
                        elif isinstance(usage, dict):
                            in_tokens = usage.get(
                                "total_input_tokens", usage.get("input_tokens", 0)
                            )
                            out_tokens = usage.get(
                                "total_output_tokens", usage.get("output_tokens", 0)
                            )
                            tot_tokens = usage.get("total_tokens", in_tokens + out_tokens)
                        else:
                            in_tokens, out_tokens, tot_tokens = 0, 0, 0

                        usage_dict = {
                            "input_tokens": in_tokens,
                            "output_tokens": out_tokens,
                            "total_tokens": tot_tokens,
                        }
                        await service.publish_job_event(
                            sys_ctx,
                            job_id,
                            kind="progress",
                            message=f"{job_type} analysis completed with {usage_dict.get('total_tokens', 0)} tokens",
                            data={"usage": usage_dict, "verified_count": len(verified)},
                        )

                        # Format result_data
                        summary_res = {
                            "final_response": final_state.get("final_response"),
                            "verified_findings_count": len(verified),
                            "persisted_findings_count": persisted_findings_count,
                            "usage": usage_dict,
                            "plan": [
                                {
                                    "specialist": t.specialist,
                                    "status": t.status,
                                    "task_id": t.task_id,
                                }
                                for t in final_state.get("plan", [])
                            ],
                            "hypotheses": [h.statement for h in final_state.get("hypotheses", [])],
                            "proposals": [p.title for p in final_state.get("proposals", [])],
                        }
                        return summary_res

                agent_stats = _run_async(_run_agent_workflow())
                result_data.update(agent_stats)

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

# Register default enqueuer with domain service
register_job_enqueuer(lambda jid: celery_app.send_task("devmind.process_job", args=[str(jid)]))
