"""Idempotency middleware with SHA-256 payload binding (docs/03 §10)."""

import hashlib
import json
import logging
import time
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.errors import PROBLEM_MEDIA_TYPE, ProblemDetails
from app.core.redis import get_async_redis_client
from app.core.settings import Settings, get_settings

logger = logging.getLogger(__name__)

# In-memory cache fallback for idempotency keys when Redis is offline or during testing
# Dict mapping key -> (record_dict, expires_at_timestamp)
_in_memory_idempotency_records: dict[str, tuple[dict[str, Any], float]] = {}
_in_memory_locks: dict[str, float] = {}


def require_idempotency_key(fn: Any) -> Any:
    """Decorator to explicitly require Idempotency-Key header on a route."""
    fn.__require_idempotency_key__ = True
    return fn


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Middleware enforcing idempotency and caching 2xx responses for 24 hours.

    Rules from docs/03 §10:
    - Idempotency-Key required on POST operations creating scans, jobs, uploads or consents.
    - Stored 24 hours.
    - Same key and body returns original response with Idempotent-Replay: true.
    - Same key with different body returns 422 idempotency.mismatch.
    """

    IDEMPOTENCY_HEADER = "idempotency-key"

    def __init__(self, app: Any, settings: Settings | None = None) -> None:
        super().__init__(app)
        self.settings = settings or get_settings()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        method = request.method.upper()
        if method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key") or request.headers.get(
            "idempotency-key"
        )

        is_required = self._is_idempotency_required(request)

        if not idempotency_key:
            if is_required:
                req_id = getattr(request.state, "request_id", None)
                problem = ProblemDetails(
                    type="about:blank",
                    title="Validation Failed",
                    status=422,
                    detail="Missing required 'Idempotency-Key' header for this operation",
                    code="validation.failed",
                    request_id=req_id,
                )
                return JSONResponse(
                    status_code=422,
                    content=problem.model_dump(exclude_none=True),
                    media_type=PROBLEM_MEDIA_TYPE,
                )
            # Not required and not provided -> proceed normally
            return await call_next(request)

        # Read and preserve request body
        body = await request.body()

        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": body, "more_body": False}

        request._receive = receive  # type: ignore[assignment]

        payload_hash = hashlib.sha256(body).hexdigest()
        principal = self._get_principal(request)
        route_id = f"{method}:{request.url.path}"
        storage_key = (
            f"{self.settings.redis_key_prefix}idempotency:{principal}:{route_id}:{idempotency_key}"
        )
        lock_key = f"{self.settings.redis_key_prefix}idempotency:lock:{principal}:{idempotency_key}"

        # Check existing cached response
        cached_record = await self._get_cached_record(storage_key)
        if cached_record is not None:
            if cached_record["request_hash"] != payload_hash:
                req_id = getattr(request.state, "request_id", None)
                problem = ProblemDetails(
                    type="about:blank",
                    title="Idempotency Key Mismatch",
                    status=422,
                    detail="Idempotency key has already been used with a different request payload",
                    code="idempotency.mismatch",
                    request_id=req_id,
                )
                return JSONResponse(
                    status_code=422,
                    content=problem.model_dump(exclude_none=True),
                    media_type=PROBLEM_MEDIA_TYPE,
                )

            # Idempotent replay: return cached response
            headers = dict(cached_record.get("headers", {}))
            headers["Idempotent-Replay"] = "true"
            req_id = getattr(request.state, "request_id", None)
            if req_id and "x-request-id" not in {k.lower() for k in headers}:
                headers["X-Request-ID"] = req_id

            return Response(
                content=cached_record["body"].encode("utf-8"),
                status_code=cached_record["status_code"],
                headers=headers,
                media_type=headers.get("content-type", "application/json"),
            )

        # Acquire lock to prevent duplicate concurrent execution
        locked = await self._acquire_lock(lock_key, ttl_seconds=60)
        if not locked:
            req_id = getattr(request.state, "request_id", None)
            problem = ProblemDetails(
                type="about:blank",
                title="Conflict",
                status=409,
                detail="A request with this idempotency key is currently being processed. Please retry shortly.",
                code="conflict.state",
                request_id=req_id,
            )
            return JSONResponse(
                status_code=409,
                content=problem.model_dump(exclude_none=True),
                media_type=PROBLEM_MEDIA_TYPE,
            )

        try:
            response = await call_next(request)

            # Collect body chunks to re-emit and potentially cache
            chunks = [chunk async for chunk in response.body_iterator]
            resp_content = b"".join(chunks)

            headers = dict(response.headers)
            headers["Idempotent-Replay"] = "false"

            new_response = Response(
                content=resp_content,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type,
            )

            # Only cache successful 2xx responses (docs/03 §10)
            if 200 <= response.status_code < 300:
                record = {
                    "request_hash": payload_hash,
                    "status_code": response.status_code,
                    "headers": {
                        k: v
                        for k, v in response.headers.items()
                        if k.lower() in ("content-type", "x-request-id")
                    },
                    "body": resp_content.decode("utf-8", errors="replace"),
                }
                await self._save_record(
                    storage_key, record, ttl_seconds=self.settings.idempotency_ttl_seconds
                )

            return new_response

        finally:
            await self._release_lock(lock_key)

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

    def _is_idempotency_required(self, request: Request) -> bool:
        """Check if request targets a resource requiring an idempotency key."""
        endpoint = self._get_endpoint(request)
        if endpoint and getattr(endpoint, "__require_idempotency_key__", False):
            return True

        path = request.url.path
        method = request.method.upper()

        if method == "POST":
            # Scans, jobs, uploads/snippets, consents per docs/03 §10
            if (
                "/scans" in path
                or "/analyses" in path
                or "/jobs" in path
                or "/snippets" in path
                or "/consents" in path
            ):
                return True

        return False

    def _get_principal(self, request: Request) -> str:
        """Derive a stable principal identifier for the caller."""
        auth_ctx = getattr(request.state, "auth_context", None)
        if auth_ctx is not None:
            user_id = getattr(auth_ctx, "user_id", None)
            if user_id:
                return f"usr:{user_id}"
            subject = getattr(auth_ctx, "subject", None)
            if subject:
                return f"sub:{subject}"

        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
            return f"tok:{token_hash}"

        client_ip = request.client.host if request.client else "127.0.0.1"
        ip_hash = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()[:16]
        return f"ip:{ip_hash}"

    async def _get_cached_record(self, key: str) -> dict[str, Any] | None:
        """Retrieve cached record from Redis or in-memory fallback."""
        try:
            client = get_async_redis_client(self.settings)
            raw = await client.get(key)
            if raw:
                return json.loads(raw)
            return None
        except Exception as exc:
            logger.debug("Redis idempotency get error (%s); checking in-memory", exc)
            item = _in_memory_idempotency_records.get(key)
            if item:
                rec, expires_at = item
                if time.time() < expires_at:
                    return rec
                del _in_memory_idempotency_records[key]
            return None

    async def _save_record(self, key: str, record: dict[str, Any], ttl_seconds: int) -> None:
        """Save cached record into Redis or in-memory fallback."""
        try:
            client = get_async_redis_client(self.settings)
            await client.set(key, json.dumps(record), ex=ttl_seconds)
        except Exception as exc:
            logger.debug("Redis idempotency set error (%s); saving in-memory", exc)
            _in_memory_idempotency_records[key] = (record, time.time() + ttl_seconds)

    async def _acquire_lock(self, lock_key: str, ttl_seconds: int = 60) -> bool:
        """Acquire in-flight processing lock."""
        try:
            client = get_async_redis_client(self.settings)
            acquired = await client.set(lock_key, "1", nx=True, ex=ttl_seconds)
            return bool(acquired)
        except Exception as exc:
            logger.debug("Redis lock error (%s); checking in-memory lock", exc)
            now = time.time()
            if lock_key in _in_memory_locks:
                if now < _in_memory_locks[lock_key]:
                    return False
            _in_memory_locks[lock_key] = now + ttl_seconds
            return True

    async def _release_lock(self, lock_key: str) -> None:
        """Release in-flight processing lock."""
        try:
            client = get_async_redis_client(self.settings)
            await client.delete(lock_key)
        except Exception:
            _in_memory_locks.pop(lock_key, None)
