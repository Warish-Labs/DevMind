"""Operational alerting thresholds and health evaluators (docs/10 §14, §15, §18).

Monitors and alerts on:
- Queue depth per queue (exceeding alert_max_queue_depth)
- Oldest message age (exceeding alert_max_queue_age_seconds)
- Stale worker heartbeats and worker drop (exceeding alert_max_heartbeat_stale_seconds)
- Stale or missing Celery Beat scheduler heartbeats
- Active kill switches (indexing, llm, embed, webhooks, pause_queues)
- System and worker error rates (exceeding alert_max_error_rate_percent)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import StrEnum

import redis.asyncio as aioredis
from pydantic import BaseModel, Field

from app.core.heartbeat import check_scheduler_liveness, check_worker_liveness
from app.core.kill_switches import get_active_kill_switches
from app.core.redis import get_async_redis_client
from app.core.settings import Settings, get_settings
from app.core.telemetry import get_metrics_snapshot

logger = logging.getLogger("devmind.alerts")


class AlertSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class SystemAlert(BaseModel):
    """Normalized operational alert item for monitoring and probes."""

    name: str
    severity: AlertSeverity
    message: str
    metric: str
    current_value: float | str | int | bool
    threshold: float | str | int | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


def has_critical_alerts(alerts: list[SystemAlert]) -> bool:
    """Return True if any alert in the list has CRITICAL severity."""
    return any(a.severity == AlertSeverity.CRITICAL for a in alerts)


def compute_metrics_error_rate() -> float | None:
    """Compute recent error rate percentage from in-memory metrics snapshot if available."""
    try:
        snapshot = get_metrics_snapshot()
        http_requests = snapshot.get("devmind_http_requests_total", [])
        if not http_requests:
            return None

        total_requests = 0
        error_requests = 0
        for dp in http_requests:
            val = dp.get("value", 0)
            total_requests += val
            attrs = dp.get("attributes", {})
            status_code = str(attrs.get("http.status_code", "200"))
            if status_code.startswith("5"):
                error_requests += val

        if total_requests == 0:
            return 0.0
        return (error_requests / total_requests) * 100.0
    except Exception as exc:
        logger.debug("Could not compute error rate from telemetry snapshot: %s", exc)
        return None


async def evaluate_system_alerts(
    settings: Settings | None = None,
    redis_client: aioredis.Redis | None = None,
    *,
    queue_depth_override: dict[str, int] | None = None,
    queue_age_override: float | None = None,
    error_rate_override: float | None = None,
) -> list[SystemAlert]:
    """Evaluate operational health thresholds against Redis, heartbeats, and kill switches.

    Returns:
        List of triggered SystemAlert items.
    """
    if settings is None:
        settings = get_settings()

    alerts: list[SystemAlert] = []
    prefix = settings.redis_key_prefix
    monitored_queues = ["default", "ingest", "embed", "analysis"]

    # 1. Queue depth checks
    max_depth = settings.alert_max_queue_depth
    queue_depths: dict[str, int] = {}

    if queue_depth_override is not None:
        queue_depths = dict(queue_depth_override)
    else:
        try:
            if redis_client is None:
                redis_client = get_async_redis_client(settings)
            for q in monitored_queues:
                key = f"{prefix}{q}"
                length = await redis_client.llen(key)
                queue_depths[q] = int(length)
        except Exception as exc:
            logger.debug("Failed reading queue lengths from Redis: %s", exc)

    for qname, depth in queue_depths.items():
        if depth > max_depth:
            sev = AlertSeverity.CRITICAL if depth > (max_depth * 2) else AlertSeverity.WARNING
            alerts.append(
                SystemAlert(
                    name="queue_depth_exceeded",
                    severity=sev,
                    message=f"Queue '{qname}' depth {depth} exceeds threshold of {max_depth}",
                    metric=f"queue.depth.{qname}",
                    current_value=depth,
                    threshold=max_depth,
                )
            )

    # 2. Queue age / lag check
    max_age = float(settings.alert_max_queue_age_seconds)
    current_age = queue_age_override
    if current_age is not None and current_age > max_age:
        sev = AlertSeverity.CRITICAL if current_age > (max_age * 2) else AlertSeverity.WARNING
        alerts.append(
            SystemAlert(
                name="queue_age_exceeded",
                severity=sev,
                message=f"Oldest queued message age {current_age:.1f}s exceeds threshold of {max_age:.1f}s",
                metric="queue.oldest_message_age_seconds",
                current_value=round(current_age, 1),
                threshold=max_age,
            )
        )

    # 3. Worker heartbeat & drop checks
    try:
        workers_healthy, active_workers, worker_warnings = await check_worker_liveness(
            settings, redis_client
        )
        for warn in worker_warnings:
            alerts.append(
                SystemAlert(
                    name="worker_heartbeat_stale",
                    severity=AlertSeverity.WARNING,
                    message=warn,
                    metric="worker.heartbeat.stale",
                    current_value=True,
                    threshold=settings.alert_max_heartbeat_stale_seconds,
                )
            )
    except Exception as exc:
        logger.debug("Worker liveness check failed: %s", exc)

    # 4. Scheduler heartbeat check
    try:
        scheduler_healthy, sched_hb, sched_lag = await check_scheduler_liveness(
            settings, redis_client
        )
        if not scheduler_healthy and sched_lag is not None:
            alerts.append(
                SystemAlert(
                    name="scheduler_heartbeat_stale",
                    severity=AlertSeverity.WARNING,
                    message=(
                        f"Celery Beat scheduler tick is stale (lag: {sched_lag:.1f}s > "
                        f"{settings.alert_max_heartbeat_stale_seconds:.1f}s)"
                    ),
                    metric="scheduler.heartbeat.lag_seconds",
                    current_value=round(sched_lag, 1),
                    threshold=settings.alert_max_heartbeat_stale_seconds,
                )
            )
    except Exception as exc:
        logger.debug("Scheduler liveness check failed: %s", exc)

    # 5. Active kill switch checks
    active_switches = get_active_kill_switches(settings)
    for switch_name, is_active in active_switches.items():
        if is_active:
            # Queues pause or LLM disable are high-impact operational overrides (WARNING)
            sev = (
                AlertSeverity.WARNING
                if switch_name in ("pause_queues", "llm")
                else AlertSeverity.INFO
            )
            alerts.append(
                SystemAlert(
                    name="kill_switch_active",
                    severity=sev,
                    message=f"Administrative kill switch is active for '{switch_name}'",
                    metric=f"kill_switch.{switch_name}",
                    current_value=True,
                    threshold=False,
                )
            )

    # 6. Error rate checks
    err_rate = (
        error_rate_override if error_rate_override is not None else compute_metrics_error_rate()
    )
    max_err_rate = float(settings.alert_max_error_rate_percent)
    if err_rate is not None and err_rate > max_err_rate:
        sev = AlertSeverity.CRITICAL if err_rate > (max_err_rate * 2) else AlertSeverity.WARNING
        alerts.append(
            SystemAlert(
                name="error_rate_exceeded",
                severity=sev,
                message=f"System error rate {err_rate:.2f}% exceeds threshold of {max_err_rate:.2f}%",
                metric="system.error_rate_percent",
                current_value=round(err_rate, 2),
                threshold=max_err_rate,
            )
        )

    return alerts
