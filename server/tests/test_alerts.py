"""Tests for M10-03 alerting thresholds, health checks, and kill switches (docs/10 §12, §14, §18, ADR-046, ADR-047)."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from app.core.alerts import (
    AlertSeverity,
    SystemAlert,
    evaluate_system_alerts,
    has_critical_alerts,
)
from app.core.errors import FeatureDisabledError
from app.core.heartbeat import (
    WorkerHeartbeat,
    check_scheduler_liveness,
    check_worker_liveness,
    get_scheduler_heartbeat,
    get_worker_heartbeats,
    record_scheduler_heartbeat,
    record_scheduler_heartbeat_sync,
    record_worker_heartbeat,
    record_worker_heartbeat_sync,
)
from app.core.kill_switches import (
    check_kill_switch,
    get_active_kill_switches,
    is_kill_switch_active,
    reset_dynamic_kill_switches,
    set_dynamic_kill_switch,
)
from app.core.settings import Settings

# ===========================================================================
# 1. Kill Switches Unit & Subsystem Tests
# ===========================================================================


def test_kill_switch_configuration_and_dynamic_overrides() -> None:
    """Verify default kill switch resolution and dynamic runtime overrides."""
    reset_dynamic_kill_switches()

    # Default settings: all kill switches inactive
    settings = Settings(
        kill_indexing=False,
        kill_llm=False,
        kill_embed=False,
        kill_webhooks=False,
        pause_queues=False,
    )
    assert not is_kill_switch_active("indexing", settings)
    assert not is_kill_switch_active("llm", settings)
    assert not is_kill_switch_active("embed", settings)
    assert not is_kill_switch_active("webhooks", settings)
    assert not is_kill_switch_active("pause_queues", settings)

    # Dynamic override
    set_dynamic_kill_switch("indexing", True)
    assert is_kill_switch_active("indexing", settings)
    assert not is_kill_switch_active("llm", settings)

    # Normalization of switch names
    set_dynamic_kill_switch("kill_llm", True)
    assert is_kill_switch_active("llm", settings)
    assert is_kill_switch_active("kill_llm", settings)

    set_dynamic_kill_switch("pause_queues", True)
    assert is_kill_switch_active("pause_queues", settings)
    assert is_kill_switch_active("queues", settings)

    # Reset overrides
    reset_dynamic_kill_switches()
    assert not is_kill_switch_active("indexing", settings)
    assert not is_kill_switch_active("llm", settings)
    assert not is_kill_switch_active("pause_queues", settings)


def test_check_kill_switch_raises_feature_disabled_error() -> None:
    """Assert check_kill_switch raises FeatureDisabledError with RFC 9457 attributes."""
    reset_dynamic_kill_switches()
    settings = Settings(kill_llm=True)

    with pytest.raises(FeatureDisabledError) as exc_info:
        check_kill_switch("llm", settings)

    err = exc_info.value
    assert err.status_code == 503
    assert err.code == "feature.disabled"
    assert "llm" in err.detail


def test_get_active_kill_switches_dictionary() -> None:
    """Verify dictionary of all active kill switches."""
    reset_dynamic_kill_switches()
    settings = Settings(kill_indexing=True, pause_queues=True)
    status_map = get_active_kill_switches(settings)

    assert status_map == {
        "indexing": True,
        "llm": False,
        "embed": False,
        "webhooks": False,
        "pause_queues": True,
    }


def test_webhook_blocked_by_kill_switch(client: TestClient) -> None:
    """Assert webhooks return RFC 9457 503 Problem Details when kill_webhooks is active."""
    reset_dynamic_kill_switches()
    set_dynamic_kill_switch("webhooks", True)

    try:
        response = client.post(
            "/api/v1/webhooks/clerk",
            headers={
                "svix-id": "msg_test123",
                "svix-timestamp": "12345678",
                "svix-signature": "v1,signature",
            },
            json={"type": "user.created", "data": {}},
        )
        assert response.status_code == 503
        data = response.json()
        assert data["code"] == "feature.disabled"
        assert "webhooks" in data["detail"]
    finally:
        reset_dynamic_kill_switches()


def test_llm_gateway_blocked_by_kill_switch() -> None:
    """Assert LLMGatewayRouter raises FeatureDisabledError when kill_llm is active."""
    from app.llm.models import ChatMessage, LLMGenerationRequest
    from app.llm.router import LLMGatewayRouter

    reset_dynamic_kill_switches()
    set_dynamic_kill_switch("llm", True)

    router = LLMGatewayRouter()
    request = LLMGenerationRequest(
        task="general_code",
        messages=[ChatMessage.user("Explain this architecture")],
    )

    import asyncio

    with pytest.raises(FeatureDisabledError) as exc_info:
        asyncio.run(router.generate(request))

    assert exc_info.value.code == "feature.disabled"
    reset_dynamic_kill_switches()


def test_embedding_service_blocked_by_kill_switch() -> None:
    """Assert EmbeddingService raises FeatureDisabledError when kill_embed is active."""
    from app.core.auth_context import SystemContext
    from app.domain.brain.embedding_service import EmbeddingService

    reset_dynamic_kill_switches()
    set_dynamic_kill_switch("embed", True)

    service = EmbeddingService(session=AsyncMock())
    sys_ctx = SystemContext(reason="test_embed")

    import asyncio

    with pytest.raises(FeatureDisabledError) as exc_info:
        asyncio.run(service.process_embed_chunks(ctx=sys_ctx, project_id=uuid4()))

    assert exc_info.value.code == "feature.disabled"
    reset_dynamic_kill_switches()


def test_celery_tasks_respect_pause_queues() -> None:
    """Assert background tasks defer execution when pause_queues is active."""
    from app.workers.celery_app import create_celery_app

    reset_dynamic_kill_switches()
    set_dynamic_kill_switch("pause_queues", True)

    try:
        app = create_celery_app()
        sweep_task = app.tasks["devmind.enqueuer_sweep"]
        res = sweep_task()
        assert res["status"] == "paused"
        assert res["swept"] == 0

        process_task = app.tasks["devmind.process_job"]
        job_res = process_task(str(uuid4()))
        assert job_res["status"] == "paused"
    finally:
        reset_dynamic_kill_switches()


# ===========================================================================
# 2. Heartbeats Unit Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_worker_heartbeat_recording_and_retrieval() -> None:
    """Verify async worker heartbeat recording and retrieval using mock Redis."""
    store: dict[str, str] = {}
    sets: dict[str, set[str]] = {}

    mock_redis = AsyncMock()

    async def mock_set(key: str, val: str, ex: int | None = None) -> bool:
        store[key] = val
        return True

    async def mock_get(key: str) -> str | None:
        return store.get(key)

    async def mock_sadd(key: str, member: str) -> int:
        sets.setdefault(key, set()).add(member)
        return 1

    async def mock_smembers(key: str) -> set[str]:
        return sets.get(key, set())

    async def mock_srem(key: str, *members: str) -> int:
        s = sets.get(key, set())
        for m in members:
            s.discard(m)
        return len(members)

    mock_redis.set.side_effect = mock_set
    mock_redis.get.side_effect = mock_get
    mock_redis.sadd.side_effect = mock_sadd
    mock_redis.smembers.side_effect = mock_smembers
    mock_redis.srem.side_effect = mock_srem

    settings = Settings(alert_max_heartbeat_stale_seconds=120)

    # 1. Record worker heartbeat
    hb = await record_worker_heartbeat(
        worker_id="worker-node-1",
        queues=["default", "ingest"],
        settings=settings,
        redis_client=mock_redis,
    )
    assert hb.worker_id == "worker-node-1"
    assert hb.queues == ["default", "ingest"]

    # 2. Retrieve worker heartbeats
    active_hbs = await get_worker_heartbeats(settings=settings, redis_client=mock_redis)
    assert len(active_hbs) == 1
    assert active_hbs[0].worker_id == "worker-node-1"

    # 3. Liveness check: healthy
    healthy, active_list, warnings = await check_worker_liveness(
        settings=settings, redis_client=mock_redis
    )
    assert healthy is True
    assert len(active_list) == 1
    assert len(warnings) == 0

    # 4. Simulate stale heartbeat
    store["dm:worker:heartbeat:worker-node-1"] = WorkerHeartbeat(
        worker_id="worker-node-1",
        queues=["default"],
        timestamp="2026-01-01T00:00:00Z",
        epoch=time.time() - 300,  # 300s old (> 120s threshold)
    ).model_dump_json()

    healthy, active_list, warnings = await check_worker_liveness(
        settings=settings, redis_client=mock_redis
    )
    assert healthy is False
    assert len(active_list) == 0
    assert len(warnings) == 1
    assert "stale" in warnings[0]


@pytest.mark.asyncio
async def test_scheduler_heartbeat_recording_and_liveness() -> None:
    """Verify async scheduler heartbeat recording and liveness checking."""
    store: dict[str, str] = {}
    mock_redis = AsyncMock()

    async def mock_set(key: str, val: str, ex: int | None = None) -> bool:
        store[key] = val
        return True

    async def mock_get(key: str) -> str | None:
        return store.get(key)

    mock_redis.set.side_effect = mock_set
    mock_redis.get.side_effect = mock_get

    settings = Settings(alert_max_heartbeat_stale_seconds=60)

    # 1. Record scheduler tick
    hb = await record_scheduler_heartbeat(
        scheduler_id="beat-node-1",
        settings=settings,
        redis_client=mock_redis,
    )
    assert hb.scheduler_id == "beat-node-1"

    # 2. Retrieve heartbeat
    fetched = await get_scheduler_heartbeat(settings=settings, redis_client=mock_redis)
    assert fetched is not None
    assert fetched.scheduler_id == "beat-node-1"

    # 3. Check liveness (healthy)
    healthy, sched_hb, lag = await check_scheduler_liveness(
        settings=settings, redis_client=mock_redis
    )
    assert healthy is True
    assert sched_hb is not None
    assert lag is not None and lag < 5.0


def test_sync_heartbeat_recording_functions() -> None:
    """Verify synchronous recording functions run without unhandled exceptions."""
    settings = Settings()
    with patch("redis.Redis.from_url") as mock_redis_cls:
        mock_client = MagicMock()
        mock_redis_cls.return_value = mock_client

        hb = record_worker_heartbeat_sync("worker-test", ["default"], settings=settings)
        assert hb.worker_id == "worker-test"
        mock_client.set.assert_called_once()
        mock_client.sadd.assert_called_once()

        mock_client.reset_mock()
        shb = record_scheduler_heartbeat_sync("scheduler-test", settings=settings)
        assert shb.scheduler_id == "scheduler-test"
        mock_client.set.assert_called_once()


# ===========================================================================
# 3. Operational Alert Evaluator Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_alerts_evaluator_queue_depth_threshold() -> None:
    """Assert queue depth exceeding alert_max_queue_depth triggers WARNING or CRITICAL alerts."""
    settings = Settings(alert_max_queue_depth=500)

    # 1. Below threshold: no queue alert
    alerts = await evaluate_system_alerts(
        settings=settings,
        queue_depth_override={"default": 50, "ingest": 10},
    )
    queue_alerts = [a for a in alerts if a.name == "queue_depth_exceeded"]
    assert len(queue_alerts) == 0

    # 2. Exceeding threshold (550 > 500) -> WARNING
    alerts = await evaluate_system_alerts(
        settings=settings,
        queue_depth_override={"default": 550, "ingest": 10},
    )
    queue_alerts = [a for a in alerts if a.name == "queue_depth_exceeded"]
    assert len(queue_alerts) == 1
    assert queue_alerts[0].severity == AlertSeverity.WARNING
    assert queue_alerts[0].current_value == 550

    # 3. Greatly exceeding threshold (1200 > 1000 = 2*threshold) -> CRITICAL
    alerts = await evaluate_system_alerts(
        settings=settings,
        queue_depth_override={"default": 1200},
    )
    queue_alerts = [a for a in alerts if a.name == "queue_depth_exceeded"]
    assert len(queue_alerts) == 1
    assert queue_alerts[0].severity == AlertSeverity.CRITICAL
    assert has_critical_alerts(alerts) is True


@pytest.mark.asyncio
async def test_alerts_evaluator_queue_age_threshold() -> None:
    """Assert queue oldest message age exceeding alert_max_queue_age_seconds triggers alert."""
    settings = Settings(alert_max_queue_age_seconds=300)

    # 1. Age within acceptable limit
    alerts = await evaluate_system_alerts(settings=settings, queue_age_override=120.0)
    age_alerts = [a for a in alerts if a.name == "queue_age_exceeded"]
    assert len(age_alerts) == 0

    # 2. Age exceeding limit (450s > 300s) -> WARNING
    alerts = await evaluate_system_alerts(settings=settings, queue_age_override=450.0)
    age_alerts = [a for a in alerts if a.name == "queue_age_exceeded"]
    assert len(age_alerts) == 1
    assert age_alerts[0].severity == AlertSeverity.WARNING
    assert age_alerts[0].current_value == 450.0

    # 3. Severe age lag (750s > 2*300s) -> CRITICAL
    alerts = await evaluate_system_alerts(settings=settings, queue_age_override=750.0)
    age_alerts = [a for a in alerts if a.name == "queue_age_exceeded"]
    assert len(age_alerts) == 1
    assert age_alerts[0].severity == AlertSeverity.CRITICAL


@pytest.mark.asyncio
async def test_alerts_evaluator_kill_switch_active() -> None:
    """Assert active kill switches produce operational notification alerts."""
    reset_dynamic_kill_switches()
    set_dynamic_kill_switch("pause_queues", True)
    set_dynamic_kill_switch("indexing", True)

    try:
        settings = Settings()
        alerts = await evaluate_system_alerts(settings=settings)
        ks_alerts = [a for a in alerts if a.name == "kill_switch_active"]
        switches_alerted = {a.metric for a in ks_alerts}

        assert "kill_switch.pause_queues" in switches_alerted
        assert "kill_switch.indexing" in switches_alerted

        # Check severity assignment
        pause_alert = next(a for a in ks_alerts if a.metric == "kill_switch.pause_queues")
        indexing_alert = next(a for a in ks_alerts if a.metric == "kill_switch.indexing")
        assert pause_alert.severity == AlertSeverity.WARNING
        assert indexing_alert.severity == AlertSeverity.INFO
    finally:
        reset_dynamic_kill_switches()


@pytest.mark.asyncio
async def test_alerts_evaluator_error_rate_threshold() -> None:
    """Assert high system error rates trigger error_rate_exceeded alerts."""
    settings = Settings(alert_max_error_rate_percent=5.0)

    # 1. Acceptable error rate (2.5% <= 5.0%)
    alerts = await evaluate_system_alerts(settings=settings, error_rate_override=2.5)
    err_alerts = [a for a in alerts if a.name == "error_rate_exceeded"]
    assert len(err_alerts) == 0

    # 2. Exceeding threshold (7.5% > 5.0%) -> WARNING
    alerts = await evaluate_system_alerts(settings=settings, error_rate_override=7.5)
    err_alerts = [a for a in alerts if a.name == "error_rate_exceeded"]
    assert len(err_alerts) == 1
    assert err_alerts[0].severity == AlertSeverity.WARNING
    assert err_alerts[0].current_value == 7.5

    # 3. Severe error rate (15.0% > 2*5.0%) -> CRITICAL
    alerts = await evaluate_system_alerts(settings=settings, error_rate_override=15.0)
    err_alerts = [a for a in alerts if a.name == "error_rate_exceeded"]
    assert len(err_alerts) == 1
    assert err_alerts[0].severity == AlertSeverity.CRITICAL


def test_alerts_do_not_contain_secrets_or_code() -> None:
    """Verify that alert messages and metrics never contain private keys, tokens, or source code."""
    alert = SystemAlert(
        name="queue_depth_exceeded",
        severity=AlertSeverity.WARNING,
        message="Queue 'default' depth 600 exceeds threshold of 500",
        metric="queue.depth.default",
        current_value=600,
        threshold=500,
    )
    raw_json = alert.model_dump_json()
    forbidden = ["secret", "token", "password", "Bearer", "jwt", "def ", "class "]
    for term in forbidden:
        assert term not in raw_json
