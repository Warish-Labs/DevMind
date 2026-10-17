"""Tests for LLM Gateway Usage Recording, Cost Accounting, and Persistence (docs/05 §13, docs/03 §3.5, M6-08).

Verifies:
1. calculate_cost_units logic (zero pricing, weighted token costs, rounding).
2. LLMUsageRecorder in-memory recording, totals aggregation, workspace scoping, and clear.
3. Database persistence integration with mock session factory and error resilience.
4. LLMGatewayRouter integration:
   - Success path recording with workspace, project, job metadata and calculated cost.
   - Fallback execution recording (failure/timeout on primary, success on fallback).
   - Refusal (LLMRefusalError) and timeout (LLMTimeoutError) recording with correct outcomes.
   - Streaming generation usage recording upon stream completion.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.llm import (
    ChatMessage,
    FakeFaultInjection,
    FakeLLMAdapter,
    GatewayConfig,
    LLMGatewayRouter,
    LLMGenerationRequest,
    LLMRefusalError,
    LLMUsageRecorder,
    RecordedUsage,
    calculate_cost_units,
)
from app.llm.config import (
    DefaultsConfig,
    ModelCapabilitiesConfig,
    ModelEntry,
    ModelLimitsConfig,
    ModelPriceUnitsConfig,
    ModelsConfig,
    ProviderDataPolicyConfig,
    ProviderEntry,
    ProvidersConfig,
    TaskBudgetConfig,
    TaskEntry,
    TasksConfig,
)
from app.persistence import create_database_usage_sink


def _build_usage_test_config() -> GatewayConfig:
    """Build a deterministic in-memory GatewayConfig for testing usage recording and cost units."""
    providers = {
        "p_primary": ProviderEntry(
            adapter="fake",
            enabled=True,
            environments=["development", "test"],
            terms_reviewed=True,
            data_policy=ProviderDataPolicyConfig(source_code_allowed=True),
        ),
        "p_fallback": ProviderEntry(
            adapter="fake",
            enabled=True,
            environments=["development", "test"],
            terms_reviewed=True,
            data_policy=ProviderDataPolicyConfig(source_code_allowed=True),
        ),
    }

    models = {
        "model_primary": ModelEntry(
            provider="p_primary",
            model_id="fake-primary-v1",
            capabilities=ModelCapabilitiesConfig(
                structured_output="native",
                streaming=True,
            ),
            limits=ModelLimitsConfig(max_input_tokens=10000, max_output_tokens=2000),
            price_units=ModelPriceUnitsConfig(input_per_1k=50, output_per_1k=150),
        ),
        "model_fallback": ModelEntry(
            provider="p_fallback",
            model_id="fake-fallback-v1",
            capabilities=ModelCapabilitiesConfig(
                structured_output="native",
                streaming=True,
            ),
            limits=ModelLimitsConfig(max_input_tokens=10000, max_output_tokens=2000),
            price_units=ModelPriceUnitsConfig(input_per_1k=20, output_per_1k=60),
        ),
    }

    tasks = {
        "test_task": TaskEntry(
            model="model_primary",
            fallbacks=["model_fallback"],
            budget=TaskBudgetConfig(max_input_tokens=8000),
        ),
    }

    return GatewayConfig(
        config_hash="test-config-hash",
        providers=ProvidersConfig(version=1, providers=providers),
        models=ModelsConfig(version=1, models=models),
        tasks=TasksConfig(version=1, defaults=DefaultsConfig(), tasks=tasks),
    )


# ---------------------------------------------------------------------------
# Unit tests: Cost units calculation
# ---------------------------------------------------------------------------


def test_calculate_cost_units_none_or_zero() -> None:
    """When pricing config is missing or 0, cost is 0."""
    assert calculate_cost_units(1000, 500, None) == 0
    zero_pricing = ModelPriceUnitsConfig(input_per_1k=0, output_per_1k=0)
    assert calculate_cost_units(5000, 2000, zero_pricing) == 0


def test_calculate_cost_units_weighted() -> None:
    """Computes correct cost units: (input * in_rate + output * out_rate) / 1000."""
    pricing = ModelPriceUnitsConfig(input_per_1k=50, output_per_1k=150)
    # (2000 * 50 + 1000 * 150) / 1000 = (100,000 + 150,000) / 1000 = 250
    assert calculate_cost_units(2000, 1000, pricing) == 250


def test_calculate_cost_units_rounding() -> None:
    """Properly rounds non-integer values to integer cost units."""
    pricing = ModelPriceUnitsConfig(input_per_1k=15, output_per_1k=45)
    # (100 * 15 + 10 * 45) / 1000 = (1500 + 450) / 1000 = 1.95 -> 2
    assert calculate_cost_units(100, 10, pricing) == 2


# ---------------------------------------------------------------------------
# Unit tests: LLMUsageRecorder in-memory recording & aggregation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_usage_recorder_in_memory() -> None:
    """Verifies in-memory call recording and history tracking."""
    recorder = LLMUsageRecorder()
    ws_1 = uuid4()
    ws_2 = uuid4()
    proj_1 = uuid4()
    job_1 = uuid4()

    pricing = ModelPriceUnitsConfig(input_per_1k=10, output_per_1k=30)

    entry1 = await recorder.record_call(
        task="code_review",
        provider_id="gemini",
        model_id="gemini-1.5-flash",
        input_tokens=1000,
        output_tokens=200,
        latency_ms=120,
        outcome="success",
        workspace_id=ws_1,
        project_id=proj_1,
        job_id=job_1,
        price_units=pricing,
    )

    assert isinstance(entry1, RecordedUsage)
    assert entry1.input_tokens == 1000
    assert entry1.output_tokens == 200
    assert entry1.total_tokens == 1200
    assert entry1.cost_units == 16  # (1000*10 + 200*30)/1000 = 16
    assert entry1.outcome == "success"
    assert entry1.workspace_id == ws_1
    assert entry1.project_id == proj_1
    assert entry1.job_id == job_1

    # Second entry on different workspace
    await recorder.record_call(
        task="code_review",
        provider_id="groq",
        model_id="llama-3.3-70b",
        input_tokens=500,
        output_tokens=100,
        latency_ms=80,
        outcome="failure",
        workspace_id=ws_2,
        price_units=pricing,
    )

    assert len(recorder.history) == 2
    ws1_records = recorder.get_records_for_workspace(ws_1)
    assert len(ws1_records) == 1
    assert ws1_records[0].workspace_id == ws_1

    # Token aggregation
    totals_ws1 = recorder.get_token_totals(ws_1)
    assert totals_ws1.input_tokens == 1000
    assert totals_ws1.output_tokens == 200
    assert totals_ws1.total_tokens == 1200

    totals_all = recorder.get_token_totals()
    assert totals_all.input_tokens == 1500
    assert totals_all.output_tokens == 300
    assert totals_all.total_tokens == 1800

    # Clear history
    recorder.clear_history()
    assert len(recorder.history) == 0


# ---------------------------------------------------------------------------
# Unit tests: Database persistence integration & error resilience
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_usage_recorder_db_persistence() -> None:
    """Verifies that record_call invokes session factory and UsageRecordRepository."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    class MockContextManager:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    session_factory = MagicMock(return_value=MockContextManager())
    sink = create_database_usage_sink(session_factory)
    recorder = LLMUsageRecorder(sink=sink)

    ws_id = uuid4()
    proj_id = uuid4()

    # Note: UsageRecordRepository.record will be called on mock_session
    entry = await recorder.record_call(
        task="symbol_indexing",
        provider_id="p_primary",
        model_id="m_primary",
        input_tokens=400,
        output_tokens=100,
        latency_ms=250,
        outcome="success",
        workspace_id=ws_id,
        project_id=proj_id,
    )

    assert entry.outcome == "success"
    session_factory.assert_called_once()
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_usage_recorder_db_resilience_on_failure() -> None:
    """Verifies that DB failure does not crash the recorder or caller."""

    class FailingContextManager:
        async def __aenter__(self):
            raise RuntimeError("Database connection lost")

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    session_factory = MagicMock(return_value=FailingContextManager())
    sink = create_database_usage_sink(session_factory)
    recorder = LLMUsageRecorder(sink=sink)

    ws_id = uuid4()
    # Call should succeed and return RecordedUsage without raising exception
    entry = await recorder.record_call(
        task="symbol_indexing",
        provider_id="p_primary",
        model_id="m_primary",
        input_tokens=200,
        output_tokens=50,
        latency_ms=100,
        outcome="success",
        workspace_id=ws_id,
    )
    assert entry.input_tokens == 200
    assert len(recorder.history) == 1


# ---------------------------------------------------------------------------
# Integration tests: LLMGatewayRouter + LLMUsageRecorder
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_router_records_usage_on_successful_generation() -> None:
    """Verifies that router.generate records usage with calculated cost units and latency."""
    config = _build_usage_test_config()
    recorder = LLMUsageRecorder()
    router = LLMGatewayRouter(config=config, usage_recorder=recorder)

    adapter_primary = FakeLLMAdapter(
        model_id="fake-primary-v1",
        scripted_responses=["Hello DevMind"],
    )
    router.register_adapter_override("model_primary", adapter_primary)

    ws_id = uuid4()
    proj_id = uuid4()
    job_id = uuid4()

    req = LLMGenerationRequest(
        task="test_task",
        messages=[ChatMessage(role="user", content="Test")],
        metadata={
            "workspace_id": str(ws_id),
            "project_id": str(proj_id),
            "job_id": str(job_id),
        },
    )

    resp = await router.generate(req)
    assert resp.content == "Hello DevMind"

    assert len(recorder.history) == 1
    record = recorder.history[0]
    assert record.llm_task == "test_task"
    assert record.provider_id == "p_primary"
    assert record.model_id == "fake-primary-v1"
    assert record.input_tokens > 0
    assert record.output_tokens > 0
    assert record.total_tokens == record.input_tokens + record.output_tokens
    assert record.cost_units >= 0
    assert record.latency_ms > 0
    assert record.outcome == "success"
    assert record.workspace_id == ws_id
    assert record.project_id == proj_id
    assert record.job_id == job_id


@pytest.mark.asyncio
async def test_router_records_usage_on_fallback() -> None:
    """Verifies that both the failed primary and successful fallback calls are recorded."""
    config = _build_usage_test_config()
    recorder = LLMUsageRecorder()
    router = LLMGatewayRouter(config=config, usage_recorder=recorder)

    # Primary will timeout
    adapter_primary = FakeLLMAdapter(
        model_id="fake-primary-v1",
        faults=FakeFaultInjection(timeout=True),
    )
    # Fallback will succeed
    adapter_fallback = FakeLLMAdapter(
        model_id="fake-fallback-v1",
        scripted_responses=["Fallback succeeded"],
    )
    router.register_adapter_override("model_primary", adapter_primary)
    router.register_adapter_override("model_fallback", adapter_fallback)

    ws_id = uuid4()
    req = LLMGenerationRequest(
        task="test_task",
        messages=[ChatMessage(role="user", content="Ping")],
        metadata={"workspace_id": str(ws_id)},
    )

    resp = await router.generate(req)
    assert resp.content == "Fallback succeeded"

    assert len(recorder.history) == 2
    primary_record, fallback_record = recorder.history[0], recorder.history[1]

    # Primary timed out
    assert primary_record.provider_id == "p_primary"
    assert primary_record.outcome == "timeout"

    # Fallback succeeded
    assert fallback_record.provider_id == "p_fallback"
    assert fallback_record.outcome == "success"
    assert fallback_record.input_tokens > 0
    assert fallback_record.output_tokens > 0


@pytest.mark.asyncio
async def test_router_records_usage_on_refusal() -> None:
    """Verifies that refusal records a failure outcome and raises without retrying."""
    config = _build_usage_test_config()
    recorder = LLMUsageRecorder()
    router = LLMGatewayRouter(config=config, usage_recorder=recorder)

    adapter_primary = FakeLLMAdapter(
        model_id="fake-primary-v1",
        faults=FakeFaultInjection(refusal=True),
    )
    router.register_adapter_override("model_primary", adapter_primary)

    req = LLMGenerationRequest(
        task="test_task",
        messages=[ChatMessage(role="user", content="Refuse me")],
    )

    with pytest.raises(LLMRefusalError):
        await router.generate(req)

    assert len(recorder.history) == 1
    assert recorder.history[0].outcome == "failure"


@pytest.mark.asyncio
async def test_router_records_usage_on_streaming() -> None:
    """Verifies streaming generation accumulates tokens and records usage upon completion."""
    config = _build_usage_test_config()
    recorder = LLMUsageRecorder()
    router = LLMGatewayRouter(config=config, usage_recorder=recorder)

    adapter_primary = FakeLLMAdapter(
        model_id="fake-primary-v1",
        scripted_responses=["Hello world streaming tokens"],
    )
    router.register_adapter_override("model_primary", adapter_primary)

    ws_id = uuid4()
    req = LLMGenerationRequest(
        task="test_task",
        messages=[ChatMessage(role="user", content="Stream me")],
        metadata={"workspace_id": str(ws_id)},
    )

    chunks = []
    async for chunk in router.stream_generate(req):
        if chunk.delta_content:
            chunks.append(chunk.delta_content)

    assert "Hello world streaming tokens" in "".join(chunks)
    assert len(recorder.history) == 1
    record = recorder.history[0]
    assert record.outcome == "success"
    assert record.workspace_id == ws_id
