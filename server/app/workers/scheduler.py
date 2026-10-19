"""Scheduler entry point for DevMind periodic tasks and retention sweeps (docs/10 §9, docs/07 §9)."""

import asyncio
import logging
import signal
from typing import Any

from app.core.auth_context import SystemContext
from app.core.logging import setup_logging
from app.core.settings import get_settings
from app.domain.retention.retention_service import RetentionService

logger = logging.getLogger("devmind.scheduler")


async def run_retention_sweep_job() -> None:
    """Run automated retention sweep across all workspaces and projects."""
    logger.info("DevMind scheduler: starting scheduled retention sweep")
    try:
        ctx = SystemContext(reason="scheduled_retention_sweep")
        service = RetentionService()
        reports = await service.execute_retention_sweep(ctx)
        total_projects = len(reports)
        total_purged = sum(sum(r.purged_counts.values()) for r in reports)
        logger.info(
            "DevMind scheduler: retention sweep completed for %d projects (total_purged=%d)",
            total_projects,
            total_purged,
        )
    except Exception as exc:
        logger.error("DevMind scheduler: retention sweep failed: %s", exc, exc_info=True)


async def periodic_sweep_worker(stop_event: asyncio.Event, interval_seconds: int = 86400) -> None:
    """Periodic worker executing retention sweeps at the configured interval."""
    # Run an initial sweep shortly after startup, then periodic
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=10.0)
        return
    except TimeoutError:
        pass

    while not stop_event.is_set():
        await run_retention_sweep_job()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=float(interval_seconds))
        except TimeoutError:
            continue


async def main() -> None:
    settings = get_settings()
    setup_logging(log_level=settings.log_level)
    logger.info(
        "DevMind scheduler service started (mode=%s, env=%s)", settings.run_mode, settings.env
    )

    stop_event = asyncio.Event()

    def _signal_handler(*_: Any) -> None:
        logger.info("DevMind scheduler shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    # Spawn periodic worker
    sweep_task = asyncio.create_task(periodic_sweep_worker(stop_event))

    await stop_event.wait()
    await sweep_task
    logger.info("DevMind scheduler stopped cleanly")


if __name__ == "__main__":
    asyncio.run(main())
