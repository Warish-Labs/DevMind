import asyncio
import logging

import redis.asyncio as aioredis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError

from app.core.settings import Settings, get_settings

logger = logging.getLogger(__name__)

_redis_clients_by_loop: dict[int, aioredis.Redis] = {}


def get_async_redis_client(settings: Settings | None = None) -> aioredis.Redis:
    """Get or create an async Redis client bound to the current running event loop."""
    try:
        loop = asyncio.get_running_loop()
        loop_id = id(loop)
    except RuntimeError:
        loop_id = 0

    client = _redis_clients_by_loop.get(loop_id)
    if client is None:
        if settings is None:
            settings = get_settings()
        client = aioredis.from_url(
            settings.redis_url,
            max_connections=20,
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
        )
        _redis_clients_by_loop[loop_id] = client
    return client


async def close_redis_client() -> None:
    """Close all cached async Redis clients."""
    global _redis_clients_by_loop
    for client in list(_redis_clients_by_loop.values()):
        try:
            await client.aclose()
        except Exception:
            pass
    _redis_clients_by_loop.clear()


async def check_redis_connectivity(settings: Settings | None = None) -> bool:
    """Check Redis connectivity without raising exceptions."""
    try:
        client = get_async_redis_client(settings)
        pong = await client.ping()
        return bool(pong)
    except (RedisConnectionError, RedisError, OSError, Exception) as exc:
        logger.debug("Redis ping failed: %s", exc)
        return False
