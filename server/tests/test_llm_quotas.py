"""Tests for LLM Gateway Quotas, Concurrency Semaphores, and Rate Limiters (docs/05 §13, docs/11 M6-07).

Verifies:
1. Provider concurrency semaphores and per-workspace concurrency caps.
2. Sliding-window rate limiters per provider with dynamic backoff penalties on HTTP 429.
3. Pre-call token budget checks, context ceiling verification, and monthly workspace quota enforcement.
4. Router integration: rate-limited primary models falling back, context-length overflow fallbacks,
   and token usage recording towards tenant allowances.
"""

from __future__ import annotations

import pytest

from app.llm import (
    ChatMessage,
    FakeLLMAdapter,
    GatewayConfig,
    LLMConcurrencyManager,
    LLMContextLengthExceededError,
    LLMGatewayRouter,
    LLMGenerationRequest,
    LLMQuotaEnforcer,
    LLMQuotaExceededError,
    LLMRateLimiter,
)
from app.llm.config import (
    DefaultsConfig,
    ModelCapabilitiesConfig,
    ModelEntry,
    ModelLimitsConfig,
    ModelsConfig,
    ProviderDataPolicyConfig,
    ProviderEntry,
    ProvidersConfig,
    TaskBudgetConfig,
    TaskEntry,
    TasksConfig,
)


def _build_quota_test_config() -> GatewayConfig:
    """Build a deterministic in-memory GatewayConfig for testing quotas and rate limits."""
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
        "m_small_context": ModelEntry(
            provider="p_primary",
            model_id="small-context-model",
            kind="generation",
            status="evaluated",
            capabilities=ModelCapabilitiesConfig(
                tool_calling=True, structured_output="native", streaming=True
            ),
            limits=ModelLimitsConfig(max_input_tokens=100),
        ),
        "m_large_context": ModelEntry(
            provider="p_fallback",
            model_id="large-context-model",
            kind="generation",
            status="evaluated",
            capabilities=ModelCapabilitiesConfig(
                tool_calling=True, structured_output="native", streaming=True
            ),
            limits=ModelLimitsConfig(max_input_tokens=100000),
        ),
    }

    tasks = {
        "budgeted_task": TaskEntry(
            model="m_small_context",
            fallbacks=["m_large_context"],
            required_capabilities=[],
            budget=TaskBudgetConfig(max_input_tokens=500),
        ),
    }

    return GatewayConfig(
        config_hash="test-quota-config-hash",
        providers=ProvidersConfig(version=1, providers=providers),
        models=ModelsConfig(version=1, models=models),
        tasks=TasksConfig(version=1, defaults=DefaultsConfig(), tasks=tasks),
    )


# ============================================================================
# Concurrency Semaphore Tests
# ============================================================================


@pytest.mark.asyncio
async def test_concurrency_manager_acquire_and_release() -> None:
    """Verify provider concurrency semaphore tracks in-flight requests and releases properly."""
    config = _build_quota_test_config()
    cm = LLMConcurrencyManager(config=config, max_workspace_concurrency=4)

    assert cm.get_in_flight_count("p_primary") == 0
    assert cm.get_workspace_in_flight("ws_1") == 0

    async with cm.acquire("p_primary", workspace_id="ws_1"):
        assert cm.get_in_flight_count("p_primary") == 1
        assert cm.get_workspace_in_flight("ws_1") == 1

    assert cm.get_in_flight_count("p_primary") == 0
    assert cm.get_workspace_in_flight("ws_1") == 0


@pytest.mark.asyncio
async def test_concurrency_manager_workspace_cap() -> None:
    """Verify exceeding per-workspace concurrency cap raises LLMQuotaExceededError."""
    config = _build_quota_test_config()
    cm = LLMConcurrencyManager(config=config, max_workspace_concurrency=2)

    async with cm.acquire("p_primary", workspace_id="ws_tenant_a"):
        async with cm.acquire("p_primary", workspace_id="ws_tenant_a"):
            with pytest.raises(LLMQuotaExceededError) as exc_info:
                async with cm.acquire("p_primary", workspace_id="ws_tenant_a"):
                    pass
            assert exc_info.value.quota_type == "workspace_concurrency"
            assert exc_info.value.limit == 2


# ============================================================================
# Sliding-Window Rate Limiter Tests
# ============================================================================


@pytest.mark.asyncio
async def test_rate_limiter_sliding_window_enforcement() -> None:
    """Verify sliding-window rate limiter permits requests up to RPM and throttles overflow."""
    config = _build_quota_test_config()
    limiter = LLMRateLimiter(config=config, custom_provider_rpm={"p_primary": 3})
    await limiter.reset("p_primary")

    # First 3 requests allowed
    ok1, rem1, retry1 = await limiter.check_and_acquire("p_primary", window_seconds=60)
    assert ok1 is True
    assert rem1 == 2
    assert retry1 == 0.0

    ok2, rem2, retry2 = await limiter.check_and_acquire("p_primary", window_seconds=60)
    assert ok2 is True
    assert rem2 == 1

    ok3, rem3, retry3 = await limiter.check_and_acquire("p_primary", window_seconds=60)
    assert ok3 is True
    assert rem3 == 0

    # 4th request exceeds limit
    ok4, rem4, retry4 = await limiter.check_and_acquire("p_primary", window_seconds=60)
    assert ok4 is False
    assert rem4 == 0
    assert retry4 > 0.0


@pytest.mark.asyncio
async def test_rate_limiter_backoff_recording() -> None:
    """Verify HTTP 429 Retry-After penalty marks provider in backoff and denies calls."""
    config = _build_quota_test_config()
    limiter = LLMRateLimiter(config=config)

    assert limiter.is_in_backoff("p_primary") is False

    limiter.record_backoff("p_primary", retry_after_s=5.0)
    assert limiter.is_in_backoff("p_primary") is True
    assert limiter.get_remaining_backoff("p_primary") > 3.0

    allowed, _, retry_after = await limiter.check_and_acquire("p_primary")
    assert allowed is False
    assert retry_after > 3.0


# ============================================================================
# Quota Enforcer Tests
# ============================================================================


def test_quota_enforcer_context_ceiling_check() -> None:
    """Verify request exceeding model max_input_tokens raises LLMContextLengthExceededError."""
    config = _build_quota_test_config()
    enforcer = LLMQuotaEnforcer(config=config)

    # Prompt with ~250 tokens (1000 characters) exceeds m_small_context limit of 100
    long_content = "x" * 1000
    req = LLMGenerationRequest(
        task="budgeted_task",
        messages=[ChatMessage.user(long_content)],
    )

    with pytest.raises(LLMContextLengthExceededError) as exc_info:
        enforcer.check_pre_call(
            request=req,
            task_entry=config.tasks.tasks["budgeted_task"],
            model_entry=config.models.models["m_small_context"],
        )
    assert exc_info.value.max_tokens == 100


def test_quota_enforcer_task_budget_check() -> None:
    """Verify request exceeding task budget raises LLMQuotaExceededError."""
    config = _build_quota_test_config()
    enforcer = LLMQuotaEnforcer(config=config)

    # Prompt with ~600 tokens (2400 characters) exceeds task budget of 500
    very_long_content = "y" * 2400
    req = LLMGenerationRequest(
        task="budgeted_task",
        messages=[ChatMessage.user(very_long_content)],
    )

    with pytest.raises(LLMQuotaExceededError) as exc_info:
        enforcer.check_pre_call(
            request=req,
            task_entry=config.tasks.tasks["budgeted_task"],
            model_entry=config.models.models["m_large_context"],
        )
    assert exc_info.value.quota_type == "task_input_budget"
    assert exc_info.value.limit == 500


def test_quota_enforcer_workspace_monthly_allowance() -> None:
    """Verify exceeding monthly workspace token allowance raises LLMQuotaExceededError."""
    config = _build_quota_test_config()
    enforcer = LLMQuotaEnforcer(config=config, monthly_allowance=1000)

    # Set workspace usage to 950 tokens
    enforcer.set_workspace_usage("ws_free_tier", 950)

    # Request with ~100 tokens (400 characters) pushes total past 1000
    req = LLMGenerationRequest(
        task="budgeted_task",
        messages=[ChatMessage.user("a" * 400)],
        metadata={"workspace_id": "ws_free_tier"},
    )

    with pytest.raises(LLMQuotaExceededError) as exc_info:
        enforcer.check_pre_call(
            request=req,
            task_entry=config.tasks.tasks["budgeted_task"],
            model_entry=config.models.models["m_large_context"],
        )
    assert exc_info.value.quota_type == "workspace_monthly_tokens"


# ============================================================================
# Router Integration Tests with Quotas & Rate Limits
# ============================================================================


@pytest.mark.asyncio
async def test_router_rate_limit_fallback_execution() -> None:
    """Verify router automatically falls back when primary provider hits rate limit."""
    config = _build_quota_test_config()
    rate_limiter = LLMRateLimiter(config=config)

    # Intentionally trigger backoff penalty on p_primary
    rate_limiter.record_backoff("p_primary", retry_after_s=10.0)

    primary_adapter = FakeLLMAdapter(model_id="small-context-model", scripted_responses=["Primary"])
    fallback_adapter = FakeLLMAdapter(
        model_id="large-context-model", scripted_responses=["Fallback Recovered"]
    )

    router = LLMGatewayRouter(
        config=config,
        environment="test",
        adapter_overrides={
            "m_small_context": primary_adapter,
            "m_large_context": fallback_adapter,
        },
        rate_limiter=rate_limiter,
    )

    req = LLMGenerationRequest(
        task="budgeted_task",
        messages=[ChatMessage.user("Hello")],
    )

    resp = await router.generate(req)
    assert resp.content == "Fallback Recovered"
    # Primary was bypassed due to active rate limit backoff
    assert primary_adapter.call_count == 0
    assert fallback_adapter.call_count == 1


@pytest.mark.asyncio
async def test_router_context_length_overflow_fallback() -> None:
    """Verify router falls back when prompt exceeds primary model context ceiling (docs/05 §11.6 rule 5)."""
    config = _build_quota_test_config()
    primary_adapter = FakeLLMAdapter(model_id="small-context-model", scripted_responses=["Primary"])
    fallback_adapter = FakeLLMAdapter(
        model_id="large-context-model", scripted_responses=["Large Context Response"]
    )

    router = LLMGatewayRouter(
        config=config,
        environment="test",
        adapter_overrides={
            "m_small_context": primary_adapter,
            "m_large_context": fallback_adapter,
        },
    )

    # Prompt with ~150 tokens exceeds m_small_context (100) but fits m_large_context (100000)
    req = LLMGenerationRequest(
        task="budgeted_task",
        messages=[ChatMessage.user("z" * 600)],
    )

    resp = await router.generate(req)
    assert resp.content == "Large Context Response"
    assert primary_adapter.call_count == 0
    assert fallback_adapter.call_count == 1


@pytest.mark.asyncio
async def test_router_records_workspace_usage_on_success() -> None:
    """Verify token usage from successful generation is recorded towards workspace allowance."""
    config = _build_quota_test_config()
    quota_enforcer = LLMQuotaEnforcer(config=config, monthly_allowance=50000)
    adapter = FakeLLMAdapter(model_id="small-context-model", scripted_responses=["Done"])

    router = LLMGatewayRouter(
        config=config,
        environment="test",
        adapter_overrides={"m_small_context": adapter},
        quota_enforcer=quota_enforcer,
    )

    req = LLMGenerationRequest(
        task="budgeted_task",
        messages=[ChatMessage.user("Count my tokens")],
        metadata={"workspace_id": "ws_accounting_1"},
    )

    assert quota_enforcer.get_workspace_usage("ws_accounting_1") == 0

    resp = await router.generate(req)
    assert resp.content == "Done"
    assert quota_enforcer.get_workspace_usage("ws_accounting_1") > 0
