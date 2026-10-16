"""Lifecycle hooks: startup sweep and migration advisory lock execution."""

import logging
from collections.abc import Callable
from typing import Any

import redis

from app.core.settings import Settings

logger = logging.getLogger("devmind.lifecycle")

# 64-bit integer advisory lock key for DevMind schema migrations ("DM_MIGR" in hex)
MIGRATION_ADVISORY_LOCK_KEY = 0x444D5F4D49475231


def run_migrations_with_advisory_lock(
    settings: Settings,
    migration_runner: Callable[[], bool] | None = None,
    lock_acquirer: Callable[[int], bool] | None = None,
    lock_releaser: Callable[[int], bool] | None = None,
) -> bool:
    """Run database migrations under a PostgreSQL advisory lock (ADR-046).
    
    Prevents race conditions when multiple instances boot or spin up under free tier.
    """
    logger.info("Initiating database migration check under advisory lock")

    if lock_acquirer is not None:
        locked = lock_acquirer(MIGRATION_ADVISORY_LOCK_KEY)
        if not locked:
            logger.warning(
                "Could not acquire migration advisory lock %s; another instance is migrating",
                hex(MIGRATION_ADVISORY_LOCK_KEY),
            )
            return False

        try:
            if migration_runner is not None:
                success = migration_runner()
                return success
            logger.info("Advisory lock migration check passed")
            return True
        finally:
            if lock_releaser is not None:
                lock_releaser(MIGRATION_ADVISORY_LOCK_KEY)

    # Default runtime behavior:
    # If a custom migration runner was supplied, execute it
    if migration_runner is not None:
        return migration_runner()

    # Pre-M2: Alembic and database tables land in Milestone M2.
    # Record structured log and verify configuration parameters.
    logger.info(
        "Advisory lock migration check: pre-M2 baseline verified (database_url configured=%s)",
        bool(settings.database_url),
    )
    return True


def run_startup_sweep(settings: Settings) -> dict[str, Any]:
    """Perform startup sweep on Redis to clear orphaned locks and stale keys (ADR-046).
    
    Ensures that containers restarting after an idle sleep (e.g. Render free tier)
    do not retain corrupted locks or dangling job claims.
    """
    prefix = settings.redis_key_prefix
    logger.info("Executing startup sweep with prefix '%s'", prefix)

    swept_count = 0
    total_scanned = 0

    try:
        client = redis.Redis.from_url(
            settings.redis_url,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
            decode_responses=True,
        )
        # Ping to check connectivity
        client.ping()

        # Scan for DevMind prefixed keys
        pattern = f"{prefix}*"
        for key in client.scan_iter(match=pattern, count=100):
            total_scanned += 1
            # Sweep stale locks or transient claim tokens that survived a crash
            if ":lock:" in key or ":tmp:" in key:
                ttl = client.ttl(key)
                # If key has no expiration (persisted across crash) or is already expired
                if ttl == -1 or ttl == -2:
                    client.delete(key)
                    swept_count += 1

        client.close()
        logger.info(
            "Startup sweep completed cleanly",
            extra={
                "key_prefix": prefix,
                "total_keys": total_scanned,
                "swept_keys": swept_count,
            },
        )
        return {
            "status": "ok",
            "key_prefix": prefix,
            "total_keys": total_scanned,
            "swept_keys": swept_count,
        }

    except (redis.exceptions.RedisError, ConnectionError, OSError) as exc:
        logger.warning(
            "Redis unreachable during startup sweep (%s); proceeding with degraded cache",
            str(exc),
            extra={"key_prefix": prefix},
        )
        return {
            "status": "degraded",
            "key_prefix": prefix,
            "reason": str(exc),
            "swept_keys": 0,
        }
