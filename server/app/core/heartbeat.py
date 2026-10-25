"""Celery background worker and scheduler heartbeat tracking (docs/10 §12, §14).

Tracks heartbeats in Redis with TTLs:
- Workers record periodic heartbeats with worker_id, hostname, pid, and serviced queues.
- Celery Beat records periodic scheduler ticks.
- Probes and alerting evaluate freshness against configurable stale thresholds.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import time
from datetime import UTC, datetime

import redis
import redis.asyncio as aioredis
from pydantic import BaseModel, Field

from app.core.redis import get_async_redis_client
from app.core.settings import Settings, get_settings

logger = logging.getLogger("devmind.heartbeat")


class WorkerHeartbeat(BaseModel):
    """Heartbeat record emitted by an active background Celery worker."""

    worker_id: str
    queues: list[str] = Field(default_factory=list)
    timestamp: str
    epoch: float
    hostname: str | None = None
    pid: int | None = None


class SchedulerHeartbeat(BaseModel):
    """Heartbeat record emitted by Celery Beat scheduler."""

    scheduler_id: str = "scheduler-default"
    timestamp: str
    epoch: float
    hostname: str | None = None
    pid: int | None = None


def _get_worker_key(prefix: str, worker_id: str) -> str:
    return f"{prefix}worker:heartbeat:{worker_id}"


def _get_scheduler_key(prefix: str) -> str:
    return f"{prefix}scheduler:heartbeat"


def _get_active_workers_set_key(prefix: str) -> str:
    return f"{prefix}workers:active"


# ---------------------------------------------------------------------------
# Async API (for FastAPI, operational endpoints, and tests)
# ---------------------------------------------------------------------------


async def record_worker_heartbeat(
    worker_id: str,
    queues: list[str] | None = None,
    settings: Settings | None = None,
    redis_client: aioredis.Redis | None = None,
    ttl_seconds: int | None = None,
) -> WorkerHeartbeat:
    """Record or update worker heartbeat in Redis with a TTL."""
    if settings is None:
        settings = get_settings()
    if redis_client is None:
        redis_client = get_async_redis_client(settings)

    if ttl_seconds is None:
        # Default TTL is 2x the stale heartbeat threshold (e.g. 240s)
        ttl_seconds = max(settings.alert_max_heartbeat_stale_seconds * 2, 60)

    now = datetime.now(UTC)
    epoch_now = time.time()
    queues_list = list(queues) if queues is not None else ["default"]

    hb = WorkerHeartbeat(
        worker_id=worker_id,
        queues=queues_list,
        timestamp=now.isoformat(),
        epoch=epoch_now,
        hostname=socket.gethostname(),
        pid=os.getpid(),
    )

    prefix = settings.redis_key_prefix
    key = _get_worker_key(prefix, worker_id)
    set_key = _get_active_workers_set_key(prefix)

    try:
        await redis_client.set(key, hb.model_dump_json(), ex=ttl_seconds)
        await redis_client.sadd(set_key, worker_id)
    except Exception as exc:
        logger.warning("Failed to record worker heartbeat in Redis: %s", exc)

    return hb


async def record_scheduler_heartbeat(
    scheduler_id: str = "scheduler-default",
    settings: Settings | None = None,
    redis_client: aioredis.Redis | None = None,
    ttl_seconds: int | None = None,
) -> SchedulerHeartbeat:
    """Record scheduler heartbeat tick in Redis with a TTL."""
    if settings is None:
        settings = get_settings()
    if redis_client is None:
        redis_client = get_async_redis_client(settings)

    if ttl_seconds is None:
        ttl_seconds = max(settings.alert_max_heartbeat_stale_seconds * 2, 60)

    now = datetime.now(UTC)
    epoch_now = time.time()

    hb = SchedulerHeartbeat(
        scheduler_id=scheduler_id,
        timestamp=now.isoformat(),
        epoch=epoch_now,
        hostname=socket.gethostname(),
        pid=os.getpid(),
    )

    prefix = settings.redis_key_prefix
    key = _get_scheduler_key(prefix)

    try:
        await redis_client.set(key, hb.model_dump_json(), ex=ttl_seconds)
    except Exception as exc:
        logger.warning("Failed to record scheduler heartbeat in Redis: %s", exc)

    return hb


async def get_worker_heartbeats(
    settings: Settings | None = None,
    redis_client: aioredis.Redis | None = None,
) -> list[WorkerHeartbeat]:
    """Retrieve all active worker heartbeat records, cleaning up expired worker keys."""
    if settings is None:
        settings = get_settings()
    if redis_client is None:
        redis_client = get_async_redis_client(settings)

    prefix = settings.redis_key_prefix
    set_key = _get_active_workers_set_key(prefix)

    try:
        worker_ids = await redis_client.smembers(set_key)
    except Exception as exc:
        logger.debug("Could not read worker set from Redis: %s", exc)
        return []

    heartbeats: list[WorkerHeartbeat] = []
    expired_ids: list[str] = []

    for wid in worker_ids:
        wid_str = wid.decode("utf-8") if isinstance(wid, bytes) else str(wid)
        key = _get_worker_key(prefix, wid_str)
        raw_val = await redis_client.get(key)
        if raw_val is None:
            expired_ids.append(wid_str)
        else:
            val_str = raw_val.decode("utf-8") if isinstance(raw_val, bytes) else raw_val
            try:
                data = json.loads(val_str)
                heartbeats.append(WorkerHeartbeat(**data))
            except Exception:
                expired_ids.append(wid_str)

    if expired_ids:
        try:
            await redis_client.srem(set_key, *expired_ids)
        except Exception:
            pass

    return heartbeats


async def get_scheduler_heartbeat(
    settings: Settings | None = None,
    redis_client: aioredis.Redis | None = None,
) -> SchedulerHeartbeat | None:
    """Retrieve the latest scheduler heartbeat record, if present and valid."""
    if settings is None:
        settings = get_settings()
    if redis_client is None:
        redis_client = get_async_redis_client(settings)

    prefix = settings.redis_key_prefix
    key = _get_scheduler_key(prefix)

    try:
        raw_val = await redis_client.get(key)
        if not raw_val:
            return None
        val_str = raw_val.decode("utf-8") if isinstance(raw_val, bytes) else raw_val
        data = json.loads(val_str)
        return SchedulerHeartbeat(**data)
    except Exception as exc:
        logger.debug("Could not read scheduler heartbeat from Redis: %s", exc)
        return None


async def check_worker_liveness(
    settings: Settings | None = None,
    redis_client: aioredis.Redis | None = None,
) -> tuple[bool, list[WorkerHeartbeat], list[str]]:
    """Check worker liveness against the stale heartbeat threshold.

    Returns:
        (is_healthy, heartbeats, warnings)
    """
    if settings is None:
        settings = get_settings()

    heartbeats = await get_worker_heartbeats(settings, redis_client)
    warnings: list[str] = []
    now = time.time()
    stale_limit = float(settings.alert_max_heartbeat_stale_seconds)

    if not heartbeats:
        return False, [], ["No active background workers found"]

    active_heartbeats: list[WorkerHeartbeat] = []
    for hb in heartbeats:
        age = now - hb.epoch
        if age > stale_limit:
            warnings.append(
                f"Worker '{hb.worker_id}' heartbeat is stale ({age:.1f}s > {stale_limit:.1f}s)"
            )
        else:
            active_heartbeats.append(hb)

    is_healthy = len(active_heartbeats) > 0 and len(warnings) == 0
    return is_healthy, active_heartbeats, warnings


async def check_scheduler_liveness(
    settings: Settings | None = None,
    redis_client: aioredis.Redis | None = None,
) -> tuple[bool, SchedulerHeartbeat | None, float | None]:
    """Check scheduler liveness against the stale heartbeat threshold.

    Returns:
        (is_healthy, heartbeat, lag_seconds)
    """
    if settings is None:
        settings = get_settings()

    hb = await get_scheduler_heartbeat(settings, redis_client)
    if hb is None:
        return False, None, None

    now = time.time()
    lag = now - hb.epoch
    stale_limit = float(settings.alert_max_heartbeat_stale_seconds)
    is_healthy = lag <= stale_limit
    return is_healthy, hb, lag


# ---------------------------------------------------------------------------
# Synchronous API (for Celery worker signals and beat scheduler tasks)
# ---------------------------------------------------------------------------


def record_worker_heartbeat_sync(
    worker_id: str,
    queues: list[str] | None = None,
    settings: Settings | None = None,
) -> WorkerHeartbeat:
    """Record worker heartbeat synchronously via standard redis connection."""
    if settings is None:
        settings = get_settings()

    ttl_seconds = max(settings.alert_max_heartbeat_stale_seconds * 2, 60)
    now = datetime.now(UTC)
    epoch_now = time.time()
    queues_list = list(queues) if queues is not None else ["default"]

    hb = WorkerHeartbeat(
        worker_id=worker_id,
        queues=queues_list,
        timestamp=now.isoformat(),
        epoch=epoch_now,
        hostname=socket.gethostname(),
        pid=os.getpid(),
    )

    prefix = settings.redis_key_prefix
    key = _get_worker_key(prefix, worker_id)
    set_key = _get_active_workers_set_key(prefix)

    try:
        sync_client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
        )
        sync_client.set(key, hb.model_dump_json(), ex=ttl_seconds)
        sync_client.sadd(set_key, worker_id)
        sync_client.close()
    except Exception as exc:
        logger.warning("Failed to record synchronous worker heartbeat: %s", exc)

    return hb


def record_scheduler_heartbeat_sync(
    scheduler_id: str = "scheduler-default",
    settings: Settings | None = None,
) -> SchedulerHeartbeat:
    """Record scheduler heartbeat synchronously via standard redis connection."""
    if settings is None:
        settings = get_settings()

    ttl_seconds = max(settings.alert_max_heartbeat_stale_seconds * 2, 60)
    now = datetime.now(UTC)
    epoch_now = time.time()

    hb = SchedulerHeartbeat(
        scheduler_id=scheduler_id,
        timestamp=now.isoformat(),
        epoch=epoch_now,
        hostname=socket.gethostname(),
        pid=os.getpid(),
    )

    prefix = settings.redis_key_prefix
    key = _get_scheduler_key(prefix)

    try:
        sync_client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
        )
        sync_client.set(key, hb.model_dump_json(), ex=ttl_seconds)
        sync_client.close()
    except Exception as exc:
        logger.warning("Failed to record synchronous scheduler heartbeat: %s", exc)

    return hb
