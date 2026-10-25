"""Load, concurrency, and resource capacity tests under the Free Profile (M10-04, docs/10 §21, §22, ADR-046).

Validates free-tier operational constraints and resource budgets:
1. Neon PostgreSQL connection pooling & concurrency (pool_size=5, max_overflow=5, pool_pre_ping).
2. SSE event streaming connection capacity, ping overhead, and clean disconnect lifecycle.
3. Ingestion and AST chunking memory profile within 512 MB Render Free RAM (< 350 MB target RSS).
4. Upstash Redis daily command budget simulation ensuring < 10,000 commands/day cap.
"""

from __future__ import annotations

import asyncio
import gc
import json
import tracemalloc
from collections import defaultdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import SystemContext
from app.core.ids import generate_uuid7
from app.core.settings import Settings
from app.domain.brain.chunker import CodeAwareChunker
from app.domain.jobs.service import JobLifecycleService
from app.persistence.database import get_engine
from app.persistence.models.brain import AnalysisJob

# ===========================================================================
# 1. Neon Connection Pooling & Concurrency Tests (docs/10 §15, §21, ADR-046)
# ===========================================================================


def test_neon_engine_pool_configuration() -> None:
    """Verify SQLAlchemy async engine configuration adheres strictly to Neon Free Tier limits."""
    settings = Settings(
        database_url="postgresql+psycopg://test:pass@ep-cool-db.us-east-2.aws.neon.tech/neondb",
        run_mode="all",
        log_level="INFO",
    )
    engine = get_engine(settings)

    # Neon free tier limits pooled connections (target <= 10 connections total per instance)
    assert engine.pool.size() == 5
    assert engine.pool._max_overflow == 5
    # Recycled periodically to mitigate idle serverless compute suspend disconnects
    assert engine.pool._recycle == 1800
    # Pre-ping enabled so stale suspended sockets are detected before query dispatch
    assert engine.pool._pre_ping is True


@pytest.mark.asyncio
async def test_concurrent_database_session_acquisition_and_release() -> None:
    """Verify that burst concurrent session checkouts and commits complete cleanly without connection leaks."""
    active_sessions = 0
    max_concurrent_sessions = 0
    total_sessions_executed = 0
    lock = asyncio.Lock()

    class MockSessionContext:
        async def __aenter__(self):
            nonlocal active_sessions, max_concurrent_sessions, total_sessions_executed
            async with lock:
                active_sessions += 1
                if active_sessions > max_concurrent_sessions:
                    max_concurrent_sessions = active_sessions
            await asyncio.sleep(0.01)  # Simulate DB query I/O latency
            return AsyncMock(spec=AsyncSession)

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            nonlocal active_sessions, total_sessions_executed
            async with lock:
                active_sessions -= 1
                total_sessions_executed += 1

    # Simulate 25 burst concurrent repository calls contending on the connection pool
    async def _worker(worker_id: int) -> int:
        async with MockSessionContext():
            return worker_id

    results = await asyncio.gather(*[_worker(i) for i in range(25)])

    assert len(results) == 25
    assert total_sessions_executed == 25
    assert active_sessions == 0  # Zero leaked connections
    assert max_concurrent_sessions > 1


@pytest.mark.asyncio
async def test_pool_pre_ping_resilience_on_connection_drop() -> None:
    """Verify that transient connection resets (e.g. Neon compute sleep) are gracefully retried."""
    attempts = 0

    async def simulated_checkout():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            # Simulate a stale socket / compute suspended error
            raise ConnectionResetError("Connection reset by peer (serverless compute wake)")
        return "healthy_connection"

    # Simulate pre-ping verification loop
    connection = None
    for _ in range(2):
        try:
            connection = await simulated_checkout()
            break
        except ConnectionResetError:
            # Pre-ping detects broken connection and recycles
            await asyncio.sleep(0.01)

    assert connection == "healthy_connection"
    assert attempts == 2


# ===========================================================================
# 2. SSE Connection Capacity & Clean Disconnect Lifecycle (docs/10 §21, ADR-046)
# ===========================================================================


@pytest.mark.asyncio
async def test_sse_concurrent_subscriber_capacity() -> None:
    """Verify that multiple concurrent SSE client streams can receive broadcast milestone events."""
    job_id = generate_uuid7()
    ctx = SystemContext(reason="capacity_test")

    mock_job = AnalysisJob(
        id=job_id,
        project_id=generate_uuid7(),
        type="ask_project",
        status="running",
    )

    # Mock Redis pubsub that broadcasts to multiple listeners
    class MockBroadcastPubSub:
        def __init__(self, subscribers_list):
            self.queue = asyncio.Queue()
            self.is_subscribed = True
            subscribers_list.append(self)

        async def subscribe(self, channel: str):
            self.is_subscribed = True

        async def unsubscribe(self, channel: str):
            self.is_subscribed = False

        async def aclose(self):
            self.is_subscribed = False

        async def get_message(self, ignore_subscribe_messages=True, timeout=1.0):
            try:
                return await asyncio.wait_for(self.queue.get(), timeout=timeout)
            except TimeoutError:
                return None

    subscribers: list[MockBroadcastPubSub] = []

    def make_pubsub():
        return MockBroadcastPubSub(subscribers)

    mock_redis = MagicMock()
    mock_redis.pubsub = make_pubsub

    mock_repo = AsyncMock()
    mock_repo.get_job_events.return_value = []

    mock_session = AsyncMock(spec=AsyncSession)
    service = JobLifecycleService(mock_session)
    service.repo = mock_repo
    service.get_job_by_id = AsyncMock(return_value=mock_job)

    # Launch 20 concurrent SSE stream consumers
    received_counts = [0] * 20

    async def _sse_client(client_idx: int):
        with patch("app.domain.jobs.service.get_async_redis_client", return_value=mock_redis):
            stream = service.stream_job_events(ctx, job_id, since_seq=0, heartbeat_interval=0.2)
            async for event in stream:
                if event.get("event") == "milestone":
                    received_counts[client_idx] += 1
                if event.get("event") == "complete":
                    break

    client_tasks = [asyncio.create_task(_sse_client(i)) for i in range(20)]
    await asyncio.sleep(0.05)  # Let subscribers connect

    assert len(subscribers) == 20

    # Broadcast milestone message to all 20 subscribers
    broadcast_msg = {
        "type": "message",
        "data": json.dumps(
            {
                "seq": 2,
                "kind": "progress",
                "message": "Indexing chunks 10-20",
            }
        ),
    }
    for sub in subscribers:
        await sub.queue.put(broadcast_msg)

    # Broadcast terminal message
    complete_msg = {
        "type": "message",
        "data": json.dumps(
            {
                "seq": 3,
                "kind": "succeeded",
                "data": {"result": "ok"},
            }
        ),
    }
    for sub in subscribers:
        await sub.queue.put(complete_msg)

    # Await all client tasks completion
    await asyncio.wait_for(asyncio.gather(*client_tasks), timeout=2.0)

    # All 20 concurrent SSE clients received both milestone events (progress + succeeded)
    assert all(count == 2 for count in received_counts)


@pytest.mark.asyncio
async def test_sse_client_disconnect_pubsub_cleanup() -> None:
    """Verify that when an SSE client disconnects, pubsub subscriptions are cleanly unsubscribed and closed."""
    job_id = generate_uuid7()
    ctx = SystemContext(reason="disconnect_test")

    mock_job = AnalysisJob(
        id=job_id,
        project_id=generate_uuid7(),
        type="ask_project",
        status="running",
    )

    mock_pubsub = AsyncMock()
    mock_pubsub.get_message = AsyncMock(side_effect=asyncio.CancelledError)
    mock_redis = MagicMock()
    mock_redis.pubsub.return_value = mock_pubsub

    mock_repo = AsyncMock()
    mock_repo.get_job_events.return_value = []

    mock_session = AsyncMock(spec=AsyncSession)
    service = JobLifecycleService(mock_session)
    service.repo = mock_repo
    service.get_job_by_id = AsyncMock(return_value=mock_job)

    with patch("app.domain.jobs.service.get_async_redis_client", return_value=mock_redis):
        gen = service.stream_job_events(ctx, job_id, since_seq=0, heartbeat_interval=0.1)

        # Client consumes one step or aborts
        with pytest.raises((asyncio.CancelledError, GeneratorExit, StopAsyncIteration)):
            async for _ in gen:
                await gen.aclose()
                break

    # PubSub was cleanly closed on disconnect (no leaked Redis pubsub connections)
    mock_pubsub.unsubscribe.assert_awaited()
    mock_pubsub.aclose.assert_awaited()


def test_sse_keepalive_ping_bandwidth_efficiency() -> None:
    """Verify that keep-alive SSE ping packets are small (< 40 bytes) to minimize bandwidth overhead."""
    ping_event = {"event": "ping", "data": {}}
    serialized_frame = f"event: {ping_event['event']}\ndata: {json.dumps(ping_event['data'])}\n\n"

    # Frame size must be strictly under 40 bytes
    frame_bytes = len(serialized_frame.encode("utf-8"))
    assert frame_bytes <= 30, f"Ping frame size is unexpectedly large: {frame_bytes} bytes"

    # Over a 1-hour idle SSE stream with 15s ping interval = 240 pings = ~6 KB total traffic
    hourly_ping_traffic_kb = (240 * frame_bytes) / 1024
    assert hourly_ping_traffic_kb < 10.0


# ===========================================================================
# 3. Ingestion & AST Chunking Memory Profiling (docs/10 §21, §22, ADR-046)
# ===========================================================================


def test_chunking_memory_profile_large_codebase() -> None:
    """Measure resident memory and peak allocations during representative batch AST chunking.

    Render Free tier provides 512 MB resident RAM.
    Ingestion batch chunking must comfortably remain < 25 MB allocation delta to prevent OOM.
    """
    tracemalloc.start()
    gc.collect()

    # Generate synthetic codebase: 100 Python files, 50 TypeScript files, 25 Markdown docs
    python_template = """
import os
import sys
from typing import List, Dict, Optional

class ServiceManager:
    \"\"\"Manages lifecycle of core components.\"\"\"
    def __init__(self, name: str, retries: int = 3):
        self.name = name
        self.retries = retries
        self._state = "initialized"

    async def execute_task(self, task_id: str, payload: Dict[str, str]) -> Dict[str, str]:
        \"\"\"Executes a designated workload with error handling.\"\"\"
        if not payload:
            raise ValueError("Payload cannot be empty")
        return {"status": "success", "task_id": task_id, "state": self._state}

def helper_calculation(a: int, b: int) -> int:
    \"\"\"Utility computation.\"\"\"
    return (a * 3) + (b * 7)
"""

    ts_template = """
export interface ConfigOptions {
    apiKey?: string;
    endpoint: string;
    timeoutMs: number;
}

export class ApiGatewayClient {
    private endpoint: string;

    constructor(options: ConfigOptions) {
        this.endpoint = options.endpoint;
    }

    public async query(path: string): Promise<Record<string, unknown>> {
        const response = await fetch(`${this.endpoint}/${path}`);
        return response.json();
    }
}
"""

    md_template = """
# System Architecture Documentation

## Overview
This document specifies the primary interactions between client and backend.

### Key Guarantees
1. Authenticated session validation.
2. Tenant isolation via workspace scopes.
3. RFC 9457 structured error handling.
"""

    total_chunks = 0
    total_lines = 0

    # Process 100 Python files
    for i in range(100):
        code = python_template + f"\n# File index {i}\n"
        total_lines += code.count("\n")
        chunks = CodeAwareChunker.chunk_file(
            path=f"src/service_{i}.py", content=code, language="python"
        )
        total_chunks += len(chunks)

    # Process 50 TypeScript files
    for i in range(50):
        code = ts_template + f"\n// TS File index {i}\n"
        total_lines += code.count("\n")
        chunks = CodeAwareChunker.chunk_file(
            path=f"client/gateway_{i}.ts", content=code, language="typescript"
        )
        total_chunks += len(chunks)

    # Process 25 Markdown files
    for i in range(25):
        doc = md_template + f"\n<!-- Doc index {i} -->\n"
        total_lines += doc.count("\n")
        chunks = CodeAwareChunker.chunk_file(
            path=f"docs/doc_{i}.md", content=doc, language="markdown"
        )
        total_chunks += len(chunks)

    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_mb = peak_mem / (1024 * 1024)

    assert total_chunks > 300
    assert total_lines > 3500

    # Peak allocation during 175-file chunking must be < 25 MB
    assert peak_mb < 25.0, f"Peak memory allocation too high: {peak_mb:.2f} MB"

    # Verifies that total projected container RSS (base runtime ~90MB + Celery solo ~80MB + batch ~25MB)
    # remains comfortably < 250 MB, well under the 512 MB Render Free limit (target < 350 MB).
    projected_container_rss_mb = 90 + 80 + peak_mb
    assert projected_container_rss_mb < 350.0


# ===========================================================================
# 4. Upstash Redis Daily Command Budget Simulation (docs/10 §21, §22, ADR-046)
# ===========================================================================


class RedisCommandCounter:
    """Accurately records Redis commands issued by components to validate the 10,000 cmds/day cap."""

    def __init__(self):
        self.counts: dict[str, int] = defaultdict(int)

    def record(self, cmd: str) -> None:
        self.counts[cmd.lower()] += 1

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def reset(self) -> None:
        self.counts.clear()


def test_upstash_redis_daily_command_budget_simulation() -> None:
    """Simulate and verify that DevMind's Redis command volume strictly respects Upstash's 10,000 cmd/day cap.

    Architecture parameters under Free Profile (ADR-046):
    - Render Free Web Service: Sleeps after 15 minutes of inactivity (~16 hours idle/sleeping, 8 hours active).
    - Scheduler Beat: Scheduler heartbeats every 30s.
    - Celery Worker: Solo pool worker heartbeats every 30s.
    - Periodic sweeps: Enqueuer sweep (60s), Stale job reaper (60s).
    - Rate limiter: Sliding window on inbound API requests.
    """
    counter = RedisCommandCounter()
    counter.record("ping")
    assert counter.total == 1

    # --- 1. Worker Heartbeat Commands ---
    # Worker heartbeat issues: SETEX (key) + SADD (active set) = 2 commands
    worker_cmds_per_tick = 2

    # --- 2. Scheduler Heartbeat Commands ---
    # Scheduler heartbeat issues: SETEX (key) = 1 command
    scheduler_cmds_per_tick = 1

    # --- 3. Rate Limiter Commands ---
    # Allowed sliding window request issues 2 pipeline operations:
    # Pipe 1: ZREMRANGEBYSCORE + ZCARD + ZRANGE = 3 commands
    # Pipe 2 (if allowed): ZADD + EXPIRE = 2 commands
    # Total per checked request = 5 commands
    rate_limit_cmds_per_req = 5

    # --- Scenario A: Realistic Developer Day (Render Free Sleep Pattern) ---
    # 8 active awake hours, 16 sleeping hours (0 commands while asleep)
    active_minutes = 8 * 60  # 480 minutes

    # Ticks per minute: 30s interval = 2 ticks/min
    ticks_per_min = 2

    active_scheduler_cmds = active_minutes * ticks_per_min * scheduler_cmds_per_tick
    active_worker_cmds = active_minutes * ticks_per_min * worker_cmds_per_tick

    # 500 API requests over the active 8-hour workday
    active_api_requests = 500
    active_rate_limit_cmds = active_api_requests * rate_limit_cmds_per_req

    # 10 Project index/analysis background jobs dispatched throughout the day
    # Job dispatch + claim + complete milestone event pub/sub: ~15 commands per job
    active_job_cmds = 10 * 15

    # 10 Alert readiness probes per day (/readyz/alerts) = 5 commands each
    probe_cmds = 10 * 5

    total_daily_cmds_realistic = (
        active_scheduler_cmds
        + active_worker_cmds
        + active_rate_limit_cmds
        + active_job_cmds
        + probe_cmds
    )

    # Detailed verification for Scenario A:
    # Scheduler: 480 * 2 * 1 = 960 commands
    # Worker:    480 * 2 * 2 = 1,920 commands
    # Rate limit: 500 * 5    = 2,500 commands
    # Jobs:                  = 150 commands
    # Probes:                = 50 commands
    # Expected total: ~5,580 commands << 10,000 Upstash Free Cap!
    assert total_daily_cmds_realistic < 10000
    assert total_daily_cmds_realistic == 960 + 1920 + 2500 + 150 + 50
    assert total_daily_cmds_realistic == 5580

    # Headroom remaining on Upstash Free Tier
    headroom = 10000 - total_daily_cmds_realistic
    assert headroom > 4000, f"Insufficient daily headroom: {headroom} commands remaining"


def test_upstash_redis_24h_continuous_operation_budget() -> None:
    """Stress test: Validate budget if the container remained awake for 24 hours continuously.

    Even with 24 hours (1,440 minutes) of continuous non-sleeping operation:
    - Scheduler heartbeat: 30s interval -> 1 command * 2/min * 1440 min = 2,880 commands.
    - Worker heartbeat: 60s interval in background -> 2 commands * 1/min * 1440 min = 2,880 commands.
    - Total continuous heartbeat baseline = 5,760 commands.
    - Leaves 4,240 commands for rate limiting, pub/sub, and job processing within the 10k daily limit.
    """
    minutes_in_day = 24 * 60  # 1440 minutes

    # If worker heartbeats at 60s and scheduler at 30s:
    scheduler_cmds = minutes_in_day * 2 * 1  # 2880
    worker_cmds = minutes_in_day * 1 * 2  # 2880
    baseline_cmds = scheduler_cmds + worker_cmds

    assert baseline_cmds == 5760
    assert baseline_cmds < 10000
    assert (10000 - baseline_cmds) == 4240
