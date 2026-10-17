"""LLM Gateway quotas, concurrency semaphores, and sliding-window rate limiters (docs/05 §13, docs/11 M6-07).

Provides:
1. LLMConcurrencyManager: In-flight request caps per provider (providers.yaml max_in_flight)
   and per workspace to prevent tenant starvation.
2. LLMRateLimiter: Sliding-window rate limiter per provider (e.g. Gemini 15 RPM, Groq 30 RPM)
   with Redis and in-memory fallback, dynamic backoff recording on HTTP 429 Retry-After.
3. LLMQuotaEnforcer: Pre-call token budget checks, model context limit verification,
   and monthly workspace token quota tracking (quotas.free.yaml).
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.core.redis import get_async_redis_client
from app.core.settings import get_settings
from app.llm.config import GatewayConfig, ModelEntry, TaskEntry, load_gateway_config
from app.llm.exceptions import LLMContextLengthExceededError, LLMQuotaExceededError
from app.llm.models import LLMGenerationRequest

logger = logging.getLogger(__name__)

# Default requests-per-minute ceilings per provider adapter type (free tier limits)
DEFAULT_PROVIDER_RPM: dict[str, int] = {
    "google": 15,  # Gemini free tier RPM
    "gemini": 15,
    "groq": 30,  # Groq free tier RPM
    "openai_compatible": 30,
    "anthropic": 10,
    "fake": 10000,  # High ceiling for tests
}

DEFAULT_WORKSPACE_CONCURRENCY = 4
DEFAULT_MONTHLY_WORKSPACE_TOKEN_ALLOWANCE = 500000


class LLMConcurrencyManager:
    """Manages active in-flight request semaphores per provider and per workspace (docs/05 §13)."""

    def __init__(
        self,
        config: GatewayConfig | None = None,
        max_workspace_concurrency: int = DEFAULT_WORKSPACE_CONCURRENCY,
    ) -> None:
        self.config = config or load_gateway_config()
        self.max_workspace_concurrency = max_workspace_concurrency
        self._provider_semaphores: dict[str, asyncio.Semaphore] = {}
        self._provider_locks: dict[str, int] = {}  # Tracks current count
        self._workspace_in_flight: dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()

        # Initialize provider semaphores from config
        for p_key, p_entry in self.config.providers.providers.items():
            max_in_flight = p_entry.concurrency.max_in_flight if p_entry.concurrency else 8
            self._provider_semaphores[p_key] = asyncio.Semaphore(max_in_flight)
            self._provider_locks[p_key] = 0

    def _get_semaphore(self, provider_id: str) -> asyncio.Semaphore:
        """Get or lazily create a semaphore for a provider ID."""
        if provider_id not in self._provider_semaphores:
            self._provider_semaphores[provider_id] = asyncio.Semaphore(8)
            self._provider_locks[provider_id] = 0
        return self._provider_semaphores[provider_id]

    def get_in_flight_count(self, provider_id: str) -> int:
        """Return the number of currently active in-flight requests for a provider."""
        return self._provider_locks.get(provider_id, 0)

    def get_workspace_in_flight(self, workspace_id: str) -> int:
        """Return the number of currently active in-flight requests for a workspace."""
        return self._workspace_in_flight.get(workspace_id, 0)

    @asynccontextmanager
    async def acquire(
        self, provider_id: str, workspace_id: str | None = None
    ) -> AsyncIterator[None]:
        """Acquire in-flight slot for the given provider and tenant workspace."""
        if workspace_id:
            async with self._lock:
                current_ws_count = self._workspace_in_flight[workspace_id]
                if current_ws_count >= self.max_workspace_concurrency:
                    raise LLMQuotaExceededError(
                        message=f"Workspace '{workspace_id}' exceeded concurrent LLM request limit ({self.max_workspace_concurrency})",
                        quota_type="workspace_concurrency",
                        used=current_ws_count,
                        limit=self.max_workspace_concurrency,
                    )
                self._workspace_in_flight[workspace_id] += 1

        sem = self._get_semaphore(provider_id)
        await sem.acquire()
        async with self._lock:
            self._provider_locks[provider_id] = self._provider_locks.get(provider_id, 0) + 1

        try:
            yield
        finally:
            async with self._lock:
                self._provider_locks[provider_id] = max(
                    0, self._provider_locks.get(provider_id, 1) - 1
                )
                if workspace_id:
                    self._workspace_in_flight[workspace_id] = max(
                        0, self._workspace_in_flight[workspace_id] - 1
                    )
            sem.release()


class LLMRateLimiter:
    """Sliding-window request rate limiter per provider with backoff penalty support (docs/05 §13)."""

    def __init__(
        self,
        config: GatewayConfig | None = None,
        custom_provider_rpm: dict[str, int] | None = None,
        key_prefix: str | None = None,
    ) -> None:
        self.config = config or load_gateway_config()
        self.provider_rpm = dict(DEFAULT_PROVIDER_RPM)
        if custom_provider_rpm:
            self.provider_rpm.update(custom_provider_rpm)

        self._in_memory_windows: dict[str, deque[float]] = defaultdict(deque)
        self._provider_backoffs: dict[str, float] = {}  # provider_id -> until timestamp
        self._settings = get_settings()
        self._key_prefix = key_prefix if key_prefix is not None else self._settings.redis_key_prefix

    async def reset(self, provider_id: str | None = None) -> None:
        """Reset sliding window counters and backoffs for a provider or all providers."""
        if provider_id:
            self._in_memory_windows.pop(provider_id, None)
            self._provider_backoffs.pop(provider_id, None)
            key = f"{self._key_prefix}llm_ratelimit:{provider_id}"
            try:
                client = get_async_redis_client(self._settings)
                await client.delete(key)
            except Exception:
                pass
        else:
            self._in_memory_windows.clear()
            self._provider_backoffs.clear()

    def get_limit(self, provider_id: str) -> int:
        """Get the RPM limit for a given provider key."""
        if provider_id in self.provider_rpm:
            return self.provider_rpm[provider_id]

        # Look up provider adapter type in config
        if provider_id in self.config.providers.providers:
            adapter = self.config.providers.providers[provider_id].adapter.lower().strip()
            return self.provider_rpm.get(adapter, 60)
        return 60

    def record_backoff(self, provider_id: str, retry_after_s: float | None = None) -> None:
        """Record upstream HTTP 429 Retry-After deadline for a provider."""
        delay = float(retry_after_s) if retry_after_s and retry_after_s > 0 else 2.0
        until = time.time() + delay
        self._provider_backoffs[provider_id] = max(
            self._provider_backoffs.get(provider_id, 0.0), until
        )
        logger.warning(
            "Provider '%s' backed off for %.1fs (until %f)",
            provider_id,
            delay,
            self._provider_backoffs[provider_id],
        )

    def is_in_backoff(self, provider_id: str) -> bool:
        """Check whether a provider is currently in a retry-after penalty window."""
        until = self._provider_backoffs.get(provider_id, 0.0)
        return time.time() < until

    def get_remaining_backoff(self, provider_id: str) -> float:
        """Return remaining seconds in backoff penalty, or 0.0 if not in backoff."""
        until = self._provider_backoffs.get(provider_id, 0.0)
        remaining = until - time.time()
        return max(0.0, remaining)

    async def check_and_acquire(
        self, provider_id: str, window_seconds: int = 60
    ) -> tuple[bool, int, float]:
        """Check and consume a sliding-window rate limit token for a provider.

        Returns: (allowed, remaining_in_window, retry_after_seconds)
        """
        # If provider is under active backoff penalty
        if self.is_in_backoff(provider_id):
            retry_after = self.get_remaining_backoff(provider_id)
            return False, 0, retry_after

        limit = self.get_limit(provider_id)
        now = time.time()
        window_start = now - window_seconds
        member = f"{now}:{uuid.uuid4().hex[:6]}"
        key = f"{self._settings.redis_key_prefix}llm_ratelimit:{provider_id}"

        # Attempt Redis sliding window first
        try:
            client = get_async_redis_client(self._settings)
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
                return True, remaining, 0.0
            else:
                if oldest_items:
                    oldest_ts = float(oldest_items[0][1])
                    retry_after = max(1.0, oldest_ts + window_seconds - now)
                else:
                    retry_after = float(window_seconds)
                return False, 0, retry_after

        except Exception as exc:
            logger.debug(
                "Redis sliding window error for provider '%s' (%s); falling back to in-memory",
                provider_id,
                exc,
            )
            return self._in_memory_check(provider_id, limit, window_seconds, now)

    def _in_memory_check(
        self, provider_id: str, limit: int, window_seconds: int, now: float
    ) -> tuple[bool, int, float]:
        """In-memory fallback for sliding-window rate limiting."""
        window_start = now - window_seconds
        queue = self._in_memory_windows[provider_id]

        while queue and queue[0] <= window_start:
            queue.popleft()

        current_count = len(queue)
        if current_count < limit:
            queue.append(now)
            remaining = max(0, limit - (current_count + 1))
            return True, remaining, 0.0
        else:
            oldest_ts = queue[0] if queue else now
            retry_after = max(1.0, oldest_ts + window_seconds - now)
            return False, 0, retry_after


class LLMQuotaEnforcer:
    """Enforces pre-call token budgets, model context ceilings, and workspace monthly quotas (docs/05 §13)."""

    def __init__(
        self,
        config: GatewayConfig | None = None,
        monthly_allowance: int = DEFAULT_MONTHLY_WORKSPACE_TOKEN_ALLOWANCE,
    ) -> None:
        self.config = config or load_gateway_config()
        self.monthly_allowance = monthly_allowance
        self._workspace_usage: dict[str, int] = defaultdict(int)

    def estimate_input_tokens(self, request: LLMGenerationRequest) -> int:
        """Estimate token count for a generation request (4 chars ~= 1 token)."""
        char_count = sum(len(m.content or "") for m in request.messages)
        if request.options.tools:
            for tool in request.options.tools:
                char_count += len(tool.function.name) + len(tool.function.description or "")
                char_count += len(str(tool.function.parameters))
        return max(1, char_count // 4)

    def get_workspace_usage(self, workspace_id: str) -> int:
        """Return recorded cumulative token usage for a workspace."""
        return self._workspace_usage.get(workspace_id, 0)

    def set_workspace_usage(self, workspace_id: str, tokens: int) -> None:
        """Set or override recorded cumulative token usage for testing."""
        self._workspace_usage[workspace_id] = tokens

    def record_usage(self, workspace_id: str, tokens: int) -> None:
        """Record consumed tokens towards workspace monthly allowance."""
        if workspace_id and tokens > 0:
            self._workspace_usage[workspace_id] += tokens

    def check_pre_call(
        self,
        request: LLMGenerationRequest,
        task_entry: TaskEntry,
        model_entry: ModelEntry,
    ) -> None:
        """Verify request meets context size, task budget, and workspace quota constraints."""
        estimated_input = self.estimate_input_tokens(request)

        # 1. Check model context size limit (docs/05 §11.6 rule 5)
        max_model_input = model_entry.limits.max_input_tokens
        if max_model_input is not None and estimated_input > max_model_input:
            raise LLMContextLengthExceededError(
                message=(
                    f"Prompt estimated at {estimated_input} tokens exceeds model '{model_entry.model_id}' "
                    f"input context ceiling of {max_model_input} tokens"
                ),
                input_tokens=estimated_input,
                max_tokens=max_model_input,
            )

        # 2. Check task input token budget (tasks.yaml budget.max_input_tokens)
        max_task_budget = task_entry.budget.max_input_tokens
        if max_task_budget is not None and estimated_input > max_task_budget:
            raise LLMQuotaExceededError(
                message=(
                    f"Estimated prompt of {estimated_input} tokens exceeds configured budget "
                    f"of {max_task_budget} tokens for task '{request.task}'"
                ),
                quota_type="task_input_budget",
                used=estimated_input,
                limit=max_task_budget,
            )

        # 3. Check workspace monthly token quota (ADR-046 / quotas.free.yaml)
        workspace_id = request.metadata.get("workspace_id")
        if workspace_id:
            current_usage = self.get_workspace_usage(workspace_id)
            if current_usage + estimated_input > self.monthly_allowance:
                raise LLMQuotaExceededError(
                    message=(
                        f"Workspace '{workspace_id}' exceeded monthly token quota "
                        f"({current_usage + estimated_input} > {self.monthly_allowance})"
                    ),
                    quota_type="workspace_monthly_tokens",
                    used=current_usage,
                    limit=self.monthly_allowance,
                )
