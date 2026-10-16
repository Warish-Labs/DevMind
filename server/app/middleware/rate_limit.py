"""Redis-backed sliding-window rate limiting middleware (docs/03 §10, docs/07 §11)."""

import hashlib
import logging
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.errors import PROBLEM_MEDIA_TYPE, ProblemDetails
from app.core.redis import get_async_redis_client
from app.core.settings import Settings, get_settings

logger = logging.getLogger(__name__)

# In-memory fallback for sliding window when Redis is offline or in unit tests
_in_memory_windows: dict[str, deque[float]] = defaultdict(deque)


def rate_limit_class(class_name: str) -> Callable[[Any], Any]:
    """Decorator to explicitly tag an endpoint with a rate limit route class."""

    def decorator(fn: Any) -> Any:
        fn.__rate_limit_class__ = class_name
        return fn

    return decorator


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed sliding-window rate limiter per principal and route class."""

    EXEMPT_PATHS = {
        "/healthz",
        "/readyz",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    }

    def __init__(self, app: Any, settings: Settings | None = None) -> None:
        super().__init__(app)
        self.settings = settings or get_settings()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self.settings.rate_limit_enabled:
            return await call_next(request)

        path = request.url.path
        if path in self.EXEMPT_PATHS or path.startswith(("/docs", "/redoc")):
            return await call_next(request)

        route_class = self._determine_route_class(request)
        limit = self._get_limit_for_class(route_class)
        window_seconds = self.settings.rate_limit_window_seconds
        principal = self._get_principal(request)

        key = f"{self.settings.redis_key_prefix}ratelimit:{route_class}:{principal}"

        allowed, remaining, reset_seconds, retry_after = await self._check_sliding_window(
            key, limit, window_seconds
        )

        headers = {
            "RateLimit-Limit": str(limit),
            "RateLimit-Remaining": str(max(0, remaining)),
            "RateLimit-Reset": str(reset_seconds),
        }

        if not allowed:
            headers["Retry-After"] = str(retry_after)
            req_id = getattr(request.state, "request_id", None)
            problem = ProblemDetails(
                type="about:blank",
                title="Rate Limit Exceeded",
                status=429,
                detail=f"Rate limit exceeded for route class '{route_class}'. Please retry after {retry_after} seconds.",
                code="rate_limit.exceeded",
                request_id=req_id,
            )
            return JSONResponse(
                status_code=429,
                content=problem.model_dump(exclude_none=True),
                media_type=PROBLEM_MEDIA_TYPE,
                headers=headers,
            )

        response = await call_next(request)
        for h_key, h_val in headers.items():
            response.headers[h_key] = h_val
        return response

    def _get_endpoint(self, request: Request) -> Any:
        """Find the matching endpoint callable for the current request."""
        endpoint = request.scope.get("endpoint")
        if endpoint is not None:
            return endpoint

        from starlette.routing import Match

        app = getattr(request, "app", None)
        if app and hasattr(app, "routes"):
            for route in app.routes:
                match, _ = route.matches(request.scope)
                if match == Match.FULL:
                    return getattr(route, "endpoint", None)
        return None

    def _determine_route_class(self, request: Request) -> str:
        """Classify request into read, write, job_create, ext_sync, or auth."""
        # Check endpoint function attribute if available
        endpoint = self._get_endpoint(request)
        if endpoint and hasattr(endpoint, "__rate_limit_class__"):
            return endpoint.__rate_limit_class__

        path = request.url.path
        method = request.method.upper()

        if "/auth" in path or "clerk" in path:
            return "auth"

        if path.startswith("/api/v1/ext/") and not (
            ("/analyses" in path or "/jobs" in path) and method == "POST"
        ):
            return "ext_sync"

        if method == "POST" and ("/analyses" in path or "/jobs" in path or "/scans" in path):
            return "job_create"

        if method in ("GET", "HEAD", "OPTIONS"):
            return "read"

        return "write"

    def _get_limit_for_class(self, route_class: str) -> int:
        """Get the configured rate limit for a route class."""
        match route_class:
            case "auth":
                return self.settings.rate_limit_auth
            case "job_create":
                return self.settings.rate_limit_job_create
            case "ext_sync":
                return self.settings.rate_limit_ext_sync
            case "read":
                return self.settings.rate_limit_read
            case "write":
                return self.settings.rate_limit_write
            case _:
                return self.settings.rate_limit_write

    def _get_principal(self, request: Request) -> str:
        """Derive a stable principal identifier for the caller."""
        # 1. From request state auth_context if already populated
        auth_ctx = getattr(request.state, "auth_context", None)
        if auth_ctx is not None:
            user_id = getattr(auth_ctx, "user_id", None)
            if user_id:
                return f"usr:{user_id}"
            subject = getattr(auth_ctx, "subject", None)
            if subject:
                return f"sub:{subject}"

        # 2. From Authorization header token hash
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
            return f"tok:{token_hash}"

        # 3. Fallback to client IP hash
        client_ip = request.client.host if request.client else "127.0.0.1"
        ip_hash = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()[:16]
        return f"ip:{ip_hash}"

    async def _check_sliding_window(
        self, key: str, limit: int, window_seconds: int
    ) -> tuple[bool, int, int, int]:
        """Check and update sliding window counter using Redis or in-memory fallback.

        Returns: (allowed, remaining, reset_seconds, retry_after)
        """
        now = time.time()
        window_start = now - window_seconds
        member = f"{now}:{uuid.uuid4().hex[:6]}"

        try:
            client = get_async_redis_client(self.settings)
            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zrange(key, 0, 0, withscores=True)
            results = await pipe.execute()

            current_count = int(results[1])
            oldest_items = results[2]

            if current_count < limit:
                add_pipe = client.pipeline()
                add_pipe.zadd(key, {member: now})
                add_pipe.expire(key, window_seconds + 5)
                await add_pipe.execute()
                remaining = max(0, limit - (current_count + 1))
                return True, remaining, window_seconds, 0
            else:
                if oldest_items:
                    oldest_ts = float(oldest_items[0][1])
                    retry_after = max(1, int(oldest_ts + window_seconds - now + 1))
                else:
                    retry_after = window_seconds
                return False, 0, retry_after, retry_after

        except Exception as exc:
            logger.debug("Redis sliding window error (%s); falling back to in-memory", exc)
            return self._in_memory_sliding_window(key, limit, window_seconds, now)

    def _in_memory_sliding_window(
        self, key: str, limit: int, window_seconds: int, now: float
    ) -> tuple[bool, int, int, int]:
        """In-memory sliding window fallback."""
        window_start = now - window_seconds
        timestamps = _in_memory_windows[key]

        # Prune old entries
        while timestamps and timestamps[0] <= window_start:
            timestamps.popleft()

        current_count = len(timestamps)
        if current_count < limit:
            timestamps.append(now)
            remaining = max(0, limit - (current_count + 1))
            return True, remaining, window_seconds, 0
        else:
            oldest_ts = timestamps[0] if timestamps else now
            retry_after = max(1, int(oldest_ts + window_seconds - now + 1))
            return False, 0, retry_after, retry_after
