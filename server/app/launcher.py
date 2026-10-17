"""Unified application launcher for DevMind backend services.

Supports:
  - DEVMIND_RUN_MODE=api (FastAPI HTTP web server via Uvicorn)
  - DEVMIND_RUN_MODE=worker (Celery worker daemon)
  - DEVMIND_RUN_MODE=scheduler (Celery beat periodic scheduler)
  - DEVMIND_RUN_MODE=all (Render free profile: Uvicorn + embedded Celery worker with beat, ADR-046)
"""

import logging
import signal
import subprocess
import sys
from collections.abc import Callable
from typing import Any

import uvicorn

from app.core.lifecycle import run_migrations_with_advisory_lock, run_startup_sweep
from app.core.logging import setup_logging
from app.core.settings import Settings, get_settings

logger = logging.getLogger("devmind.launcher")


def start_api(
    settings: Settings,
    host: str = "0.0.0.0",
    port: int = 8000,
    server_runner: Callable[..., Any] | None = None,
) -> None:
    """Run FastAPI HTTP server using Uvicorn."""
    logger.info("Starting DevMind API server on %s:%d (env=%s)", host, port, settings.env)
    if server_runner is not None:
        server_runner(settings, host, port)
        return

    config = uvicorn.Config(
        "app.main:app",
        host=host,
        port=port,
        log_config=None,
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.run()


def start_worker(
    settings: Settings,
    proc_runner: Callable[..., Any] | None = None,
) -> None:
    """Run standalone Celery worker."""
    logger.info("Starting standalone DevMind Celery worker (env=%s)", settings.env)
    cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "app.workers.celery_app",
        "worker",
        "-l",
        settings.log_level.lower(),
    ]
    if proc_runner is not None:
        proc_runner(cmd)
        return

    subprocess.run(cmd, check=False)


def start_scheduler(
    settings: Settings,
    proc_runner: Callable[..., Any] | None = None,
) -> None:
    """Run standalone Celery beat scheduler."""
    logger.info("Starting standalone DevMind Celery scheduler (env=%s)", settings.env)
    cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "app.workers.celery_app",
        "beat",
        "-l",
        settings.log_level.lower(),
    ]
    if proc_runner is not None:
        proc_runner(cmd)
        return

    subprocess.run(cmd, check=False)


def start_all(
    settings: Settings,
    host: str = "0.0.0.0",
    port: int = 8000,
    server_runner: Callable[..., Any] | None = None,
    celery_launcher: Callable[..., Any] | None = None,
) -> None:
    """Run combined API and embedded Celery worker with beat (ADR-046 free profile)."""
    logger.info(
        "Starting DevMind Free Profile (API + embedded Celery --pool=solo --beat) on %s:%d",
        host,
        port,
    )

    celery_cmd = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "app.workers.celery_app",
        "worker",
        "--beat",
        "--pool=solo",
        "--concurrency=1",
        "-l",
        settings.log_level.lower(),
    ]

    celery_proc: subprocess.Popen[Any] | Any = None
    if celery_launcher is not None:
        celery_proc = celery_launcher(celery_cmd)
    else:
        celery_proc = subprocess.Popen(celery_cmd)

    def _cleanup_celery() -> None:
        if celery_proc is not None:
            logger.info("Terminating embedded Celery worker...")
            try:
                if hasattr(celery_proc, "terminate"):
                    celery_proc.terminate()
                if hasattr(celery_proc, "wait"):
                    celery_proc.wait(timeout=5)
            except Exception as e:
                logger.warning("Error stopping Celery process: %s", e)
                if hasattr(celery_proc, "kill"):
                    celery_proc.kill()
            logger.info("Embedded Celery worker shutdown completed")

    # Hook cleanup to termination signals
    def _sig_handler(sig: int, _: Any) -> None:
        logger.info("Received termination signal %d in free profile launcher", sig)
        _cleanup_celery()
        sys.exit(0)

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _sig_handler)
        except (ValueError, OSError):
            pass

    try:
        if server_runner is not None:
            server_runner(settings, host, port)
        else:
            config = uvicorn.Config(
                "app.main:app",
                host=host,
                port=port,
                log_config=None,
                access_log=False,
            )
            server = uvicorn.Server(config)
            server.run()
    finally:
        _cleanup_celery()


def launch(
    settings: Settings | None = None,
    host: str = "0.0.0.0",
    port: int = 8000,
    server_runner: Callable[..., Any] | None = None,
    proc_runner: Callable[..., Any] | None = None,
    celery_launcher: Callable[..., Any] | None = None,
) -> int:
    """Initialize lifecycle (advisory lock migrations + startup sweep) and launch run mode."""
    if settings is None:
        settings = get_settings()

    # Honor PORT environment variable from hosting platform (e.g. Render assigns PORT)
    import os

    if os.getenv("PORT"):
        try:
            port = int(os.environ["PORT"])
        except ValueError:
            pass

    setup_logging(log_level=settings.log_level)
    logger.info(
        "DevMind launcher starting (run_mode=%s, env=%s, port=%d, redis_prefix=%s)",
        settings.run_mode,
        settings.env,
        port,
        settings.redis_key_prefix,
    )

    # 1. Run migrations under advisory lock
    run_migrations_with_advisory_lock(settings)

    # 2. Run startup sweep on Redis
    run_startup_sweep(settings)

    # 3. Dispatch to requested run mode
    mode = settings.run_mode
    if mode == "api":
        start_api(settings, host=host, port=port, server_runner=server_runner)
    elif mode == "worker":
        start_worker(settings, proc_runner=proc_runner)
    elif mode == "scheduler":
        start_scheduler(settings, proc_runner=proc_runner)
    elif mode == "all":
        start_all(
            settings,
            host=host,
            port=port,
            server_runner=server_runner,
            celery_launcher=celery_launcher,
        )
    else:
        logger.error("Unknown run_mode '%s'; valid modes are api, worker, scheduler, all", mode)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(launch())
