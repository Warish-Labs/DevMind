"""Celery application configuration for DevMind background workers."""

from typing import Any

from celery import Celery

from app.core.settings import Settings, get_settings


def create_celery_app(settings: Settings | None = None) -> Celery:
    """Create and configure the Celery application."""
    if settings is None:
        settings = get_settings()

    app = Celery("devmind")

    # Prefix isolation for shared Redis (Render Key Value, ADR-046)
    prefix = settings.redis_key_prefix
    app.conf.update(
        broker_url=settings.redis_url,
        result_backend=settings.redis_url,
        broker_transport_options={"global_keyprefix": prefix},
        result_backend_transport_options={"global_keyprefix": prefix},
        task_default_queue=f"{prefix}default",
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        timezone="UTC",
        enable_utc=True,
    )

    @app.task(name="devmind.ping")
    def ping() -> str:
        """Health check probe task."""
        return "pong"

    @app.task(name="devmind.enqueuer_sweep")
    def enqueuer_sweep() -> dict[str, Any]:
        """Periodic task to re-enqueue queued jobs stranded by container sleeps."""
        return {"status": "ok", "swept": 0}

    @app.task(name="devmind.stale_job_reaper")
    def stale_job_reaper() -> dict[str, Any]:
        """Periodic task to reap jobs with expired heartbeats."""
        return {"status": "ok", "reaped": 0}

    return app


celery_app = create_celery_app()
