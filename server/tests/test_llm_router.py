"""Tests for LLM Gateway Router (docs/05 §11.6, §12, docs/11 M6-06).

Verifies:
1. Candidate resolution with capability matching, deprecation checks, and environment filtering.
2. Source code privacy guard enforcement (ADR-047).
3. Fallback execution on transient errors (timeout, rate limit, provider error).
4. Strict non-bypass on safety refusal (LLMRefusalError) and schema invalid output (LLMInvalidOutputError).
5. Streaming fallback on initial failure vs mid-stream error propagation.
6. Adapter overrides and registry resolution.
"""

from __future__ import annotations

import pytest

from app.llm import (
    ChatMessage,
    FakeFaultInjection,
    FakeLLMAdapter,
    GatewayConfig,
    LLMError,
    LLMGatewayRouter,
    LLMGenerationRequest,
    LLMGenerationResponse,
    LLMInvalidOutputError,
    LLMProviderError,
    LLMRefusalError,
    LLMUnavailableError,
    load_gateway_config,
)
from app.llm.config import (
    DefaultsConfig,
    ModelCapabilitiesConfig,
    ModelEntry,
    ModelsConfig,
    ProviderDataPolicyConfig,
    ProviderEntry,
    ProvidersConfig,
    TaskDataConfig,
    TaskEntry,
    TasksConfig,
)


def _build_test_gateway_config() -> GatewayConfig:
    """Build a deterministic in-memory GatewayConfig for unit testing router behavior."""
    providers = {
        "p_primary": ProviderEntry(
            adapter="fake",
            enabled=True,
            environments=["development", "test", "production"],
            terms_reviewed=True,
            data_policy=ProviderDataPolicyConfig(source_code_allowed=True),
        ),
        "p_fallback": ProviderEntry(
            adapter="fake",
            enabled=True,
            environments=["development", "test", "production"],
            terms_reviewed=True,
            data_policy=ProviderDataPolicyConfig(source_code_allowed=True),
        ),
        "p_no_source": ProviderEntry(
            adapter="fake",
            enabled=True,
            environments=["development", "test", "production"],
            terms_reviewed=True,
            data_policy=ProviderDataPolicyConfig(source_code_allowed=False),
        ),
        "p_unreviewed_prod": ProviderEntry(
            adapter="fake",
            enabled=True,
            environments=["development", "test", "production"],
            terms_reviewed=False,
            data_policy=ProviderDataPolicyConfig(source_code_allowed=True),
        ),
        "p_disabled": ProviderEntry(
            adapter="fake",
            enabled=False,
            environments=["development", "test", "production"],
            terms_reviewed=True,
        ),
    }

    models = {
        "m_primary": ModelEntry(
            provider="p_primary",
            model_id="primary-model-v1",
            kind="generation",
            status="evaluated",
            capabilities=ModelCapabilitiesConfig(
                tool_calling=True, structured_output="native", streaming=True
            ),
        ),
        "m_fallback": ModelEntry(
            provider="p_fallback",
            model_id="fallback-model-v1",
            kind="generation",
            status="evaluated",
            capabilities=ModelCapabilitiesConfig(
                tool_calling=True, structured_output="native", streaming=True
            ),
        ),
        "m_no_tools": ModelEntry(
            provider="p_primary",
            model_id="no-tools-model",
            kind="generation",
            status="evaluated",
            capabilities=ModelCapabilitiesConfig(
                tool_calling=False, structured_output="native", streaming=True
            ),
        ),
        "m_deprecated": ModelEntry(
            provider="p_primary",
            model_id="deprecated-model",
            kind="generation",
            status="deprecated",
            capabilities=ModelCapabilitiesConfig(
                tool_calling=True, structured_output="native", streaming=True
            ),
        ),
        "m_no_source": ModelEntry(
            provider="p_no_source",
            model_id="no-source-model",
            kind="generation",
            status="evaluated",
            capabilities=ModelCapabilitiesConfig(
                tool_calling=True, structured_output="native", streaming=True
            ),
        ),
        "m_unreviewed": ModelEntry(
            provider="p_unreviewed_prod",
            model_id="unreviewed-model",
            kind="generation",
            status="evaluated",
            capabilities=ModelCapabilitiesConfig(
                tool_calling=True, structured_output="native", streaming=True
            ),
        ),
        "m_disabled": ModelEntry(
            provider="p_disabled",
            model_id="disabled-model",
            kind="generation",
            status="evaluated",
            capabilities=ModelCapabilitiesConfig(
                tool_calling=True, structured_output="native", streaming=True
            ),
        ),
    }

    tasks = {
        "general_code": TaskEntry(
            model="m_primary",
            fallbacks=["m_fallback"],
            required_capabilities=["tool_calling", "streaming"],
            data=TaskDataConfig(may_contain_source=True),
        ),
        "needs_tools": TaskEntry(
            model="m_no_tools",
            fallbacks=["m_fallback"],
            required_capabilities=["tool_calling"],
        ),
        "with_deprecated_fallback": TaskEntry(
            model="m_primary",
            fallbacks=["m_deprecated", "m_fallback"],
            required_capabilities=[],
        ),
        "with_disabled_primary": TaskEntry(
            model="m_disabled",
            fallbacks=["m_fallback"],
            required_capabilities=[],
        ),
        "source_restricted": TaskEntry(
            model="m_no_source",
            fallbacks=["m_fallback"],
            required_capabilities=[],
            data=TaskDataConfig(may_contain_source=True),
        ),
        "prod_unreviewed": TaskEntry(
            model="m_unreviewed",
            fallbacks=["m_fallback"],
            required_capabilities=[],
            data=TaskDataConfig(may_contain_source=True),
        ),
    }

    return GatewayConfig(
        config_hash="test-config-hash-sha256",
        providers=ProvidersConfig(version=1, providers=providers),
        models=ModelsConfig(version=1, models=models),
        tasks=TasksConfig(version=1, defaults=DefaultsConfig(), tasks=tasks),
    )


# ============================================================================
# Candidate Resolution & Filtering Tests
# ============================================================================


def test_candidate_resolution_basic() -> None:
    """Verify normal task candidate resolution returns primary and eligible fallbacks."""
    config = _build_test_gateway_config()
    router = LLMGatewayRouter(config=config, environment="test")

    candidates = router.resolve_candidates("general_code")
    assert candidates == ["m_primary", "m_fallback"]


def test_candidate_resolution_capability_filtering() -> None:
    """Verify models missing required capabilities are filtered out."""
    config = _build_test_gateway_config()
    router = LLMGatewayRouter(config=config, environment="test")

    # m_no_tools lacks tool_calling, so primary is skipped, leaving m_fallback
    candidates = router.resolve_candidates("needs_tools")
    assert candidates == ["m_fallback"]


def test_candidate_resolution_deprecated_filtering() -> None:
    """Verify deprecated models are excluded from candidate list (docs/05 §11.6 rule 4)."""
    config = _build_test_gateway_config()
    router = LLMGatewayRouter(config=config, environment="test")

    candidates = router.resolve_candidates("with_deprecated_fallback")
    assert "m_deprecated" not in candidates
    assert candidates == ["m_primary", "m_fallback"]


def test_candidate_resolution_disabled_provider_filtering() -> None:
    """Verify models associated with disabled providers are skipped."""
    config = _build_test_gateway_config()
    router = LLMGatewayRouter(config=config, environment="test")

    candidates = router.resolve_candidates("with_disabled_primary")
    assert candidates == ["m_fallback"]


def test_candidate_resolution_source_code_privacy_guard() -> None:
    """Verify source code transmission is blocked when provider policy disallows it (ADR-047)."""
    config = _build_test_gateway_config()
    router = LLMGatewayRouter(config=config, environment="test")

    # m_no_source uses p_no_source which has source_code_allowed=False
    candidates = router.resolve_candidates("source_restricted")
    assert "m_no_source" not in candidates
    assert candidates == ["m_fallback"]


def test_candidate_resolution_production_unreviewed_terms_guard() -> None:
    """Verify in production/staging that unreviewed terms block source transmission."""
    config = _build_test_gateway_config()

    # In development: unreviewed terms allowed
    router_dev = LLMGatewayRouter(config=config, environment="development")
    candidates_dev = router_dev.resolve_candidates("prod_unreviewed")
    assert "m_unreviewed" in candidates_dev

    # In production: unreviewed terms excluded
    router_prod = LLMGatewayRouter(config=config, environment="production")
    candidates_prod = router_prod.resolve_candidates("prod_unreviewed")
    assert "m_unreviewed" not in candidates_prod
    assert candidates_prod == ["m_fallback"]


def test_candidate_resolution_unknown_task_error() -> None:
    """Verify resolving unknown task raises LLMError with proper code."""
    config = _build_test_gateway_config()
    router = LLMGatewayRouter(config=config, environment="test")

    with pytest.raises(LLMError) as exc_info:
        router.resolve_candidates("non_existent_task")
    assert exc_info.value.code == "llm.unknown_task"


def test_candidate_resolution_no_eligible_models_error() -> None:
    """Verify LLMUnavailableError is raised when all candidates are disqualified."""
    config = _build_test_gateway_config()
    router = LLMGatewayRouter(config=config, environment="test")

    # m_no_tools has fallbacks: [m_fallback]. If we request streaming and neither has streaming:
    config.models.models["m_fallback"].capabilities.streaming = False
    with pytest.raises(LLMUnavailableError) as exc_info:
        router.resolve_candidates("needs_tools", streaming=True)
    assert "No eligible provider or fallback model available" in str(exc_info.value)


# ============================================================================
# Generation & Fallback Execution Tests
# ============================================================================


@pytest.mark.asyncio
async def test_router_generate_primary_success() -> None:
    """Verify normal primary model generation when no errors occur."""
    config = _build_test_gateway_config()
    primary_adapter = FakeLLMAdapter(
        model_id="primary-model-v1", scripted_responses=["Primary Success"]
    )
    fallback_adapter = FakeLLMAdapter(model_id="fallback-model-v1", scripted_responses=["Fallback"])

    router = LLMGatewayRouter(
        config=config,
        environment="test",
        adapter_overrides={
            "m_primary": primary_adapter,
            "m_fallback": fallback_adapter,
        },
    )

    req = LLMGenerationRequest(task="general_code", messages=[ChatMessage.user("Hello")])
    resp = await router.generate(req)

    assert resp.content == "Primary Success"
    assert primary_adapter.call_count == 1
    assert fallback_adapter.call_count == 0


@pytest.mark.asyncio
async def test_router_generate_fallback_on_timeout() -> None:
    """Verify router automatically falls back when primary model times out (docs/05 §12)."""
    config = _build_test_gateway_config()
    primary_adapter = FakeLLMAdapter(
        model_id="primary-model-v1",
        faults=FakeFaultInjection(timeout=True),
    )
    fallback_adapter = FakeLLMAdapter(
        model_id="fallback-model-v1",
        scripted_responses=["Fallback recovered after timeout"],
    )

    router = LLMGatewayRouter(
        config=config,
        environment="test",
        adapter_overrides={
            "m_primary": primary_adapter,
            "m_fallback": fallback_adapter,
        },
    )

    req = LLMGenerationRequest(task="general_code", messages=[ChatMessage.user("Hello")])
    resp = await router.generate(req)

    assert resp.content == "Fallback recovered after timeout"
    assert primary_adapter.call_count == 1
    assert fallback_adapter.call_count == 1


@pytest.mark.asyncio
async def test_router_generate_fallback_on_rate_limit_and_5xx() -> None:
    """Verify fallback on rate limits and upstream 5xx errors."""
    config = _build_test_gateway_config()
    primary_adapter = FakeLLMAdapter(
        model_id="primary-model-v1",
        faults=FakeFaultInjection(rate_limit=True),
    )
    fallback_adapter = FakeLLMAdapter(
        model_id="fallback-model-v1",
        scripted_responses=["Fallback recovered after rate limit"],
    )

    router = LLMGatewayRouter(
        config=config,
        environment="test",
        adapter_overrides={
            "m_primary": primary_adapter,
            "m_fallback": fallback_adapter,
        },
    )

    req = LLMGenerationRequest(task="general_code", messages=[ChatMessage.user("Hello")])
    resp = await router.generate(req)

    assert resp.content == "Fallback recovered after rate limit"
    assert primary_adapter.call_count == 1
    assert fallback_adapter.call_count == 1


@pytest.mark.asyncio
async def test_router_generate_all_candidates_fail() -> None:
    """Verify LLMUnavailableError when all eligible candidates fail."""
    config = _build_test_gateway_config()
    primary_adapter = FakeLLMAdapter(
        model_id="primary-model-v1",
        faults=FakeFaultInjection(provider_5xx=True, provider_status_code=500),
    )
    fallback_adapter = FakeLLMAdapter(
        model_id="fallback-model-v1",
        faults=FakeFaultInjection(timeout=True),
    )

    router = LLMGatewayRouter(
        config=config,
        environment="test",
        adapter_overrides={
            "m_primary": primary_adapter,
            "m_fallback": fallback_adapter,
        },
    )

    req = LLMGenerationRequest(task="general_code", messages=[ChatMessage.user("Hello")])
    with pytest.raises(LLMUnavailableError) as exc_info:
        await router.generate(req)

    assert "All eligible models exhausted for task 'general_code'" in str(exc_info.value)
    assert primary_adapter.call_count == 1
    assert fallback_adapter.call_count == 1


# ============================================================================
# Non-Bypass Safety & Schema Error Tests (ADR-027 & docs/05 §12)
# ============================================================================


@pytest.mark.asyncio
async def test_router_refusal_error_never_falls_back() -> None:
    """Verify safety content refusals immediately re-raise and NEVER fall back (ADR-027)."""
    config = _build_test_gateway_config()
    primary_adapter = FakeLLMAdapter(
        model_id="primary-model-v1",
        faults=FakeFaultInjection(refusal=True, refusal_reason="Content policy refusal"),
    )
    fallback_adapter = FakeLLMAdapter(
        model_id="fallback-model-v1",
        scripted_responses=["Unreached fallback"],
    )

    router = LLMGatewayRouter(
        config=config,
        environment="test",
        adapter_overrides={
            "m_primary": primary_adapter,
            "m_fallback": fallback_adapter,
        },
    )

    req = LLMGenerationRequest(task="general_code", messages=[ChatMessage.user("Risky prompt")])
    with pytest.raises(LLMRefusalError) as exc_info:
        await router.generate(req)

    assert "Content policy refusal" in str(exc_info.value)
    assert primary_adapter.call_count == 1
    # Fallback must NEVER have been called to bypass refusal
    assert fallback_adapter.call_count == 0


@pytest.mark.asyncio
async def test_router_invalid_output_error_never_falls_back() -> None:
    """Verify structured output validation failures re-raise without attempting fallbacks."""
    config = _build_test_gateway_config()

    class _InvalidOutputAdapter(FakeLLMAdapter):
        async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
            self.call_count += 1
            raise LLMInvalidOutputError("Schema validation failed on output")

    primary_adapter = _InvalidOutputAdapter(model_id="primary-model-v1")
    fallback_adapter = FakeLLMAdapter(
        model_id="fallback-model-v1",
        scripted_responses=["Unreached fallback"],
    )

    router = LLMGatewayRouter(
        config=config,
        environment="test",
        adapter_overrides={
            "m_primary": primary_adapter,
            "m_fallback": fallback_adapter,
        },
    )

    req = LLMGenerationRequest(task="general_code", messages=[ChatMessage.user("Generate JSON")])
    with pytest.raises(LLMInvalidOutputError):
        await router.generate(req)

    assert primary_adapter.call_count == 1
    assert fallback_adapter.call_count == 0


# ============================================================================
# Streaming & Fallback Tests
# ============================================================================


@pytest.mark.asyncio
async def test_router_stream_generate_success() -> None:
    """Verify normal streaming generation yields all chunks from primary adapter."""
    config = _build_test_gateway_config()
    primary_adapter = FakeLLMAdapter(
        model_id="primary-model-v1",
        scripted_responses=["Hello world streaming tokens"],
    )

    router = LLMGatewayRouter(
        config=config,
        environment="test",
        adapter_overrides={"m_primary": primary_adapter},
    )

    req = LLMGenerationRequest(task="general_code", messages=[ChatMessage.user("Stream test")])
    chunks = [chunk async for chunk in router.stream_generate(req)]

    assert len(chunks) > 1
    assembled = "".join(c.delta_content or "" for c in chunks)
    assert "Hello world streaming tokens" in assembled


@pytest.mark.asyncio
async def test_router_stream_generate_initial_failure_falls_back() -> None:
    """Verify streaming fallback occurs if primary fails before producing chunks."""
    config = _build_test_gateway_config()
    primary_adapter = FakeLLMAdapter(
        model_id="primary-model-v1",
        faults=FakeFaultInjection(timeout=True),
    )
    fallback_adapter = FakeLLMAdapter(
        model_id="fallback-model-v1",
        scripted_responses=["Fallback stream content"],
    )

    router = LLMGatewayRouter(
        config=config,
        environment="test",
        adapter_overrides={
            "m_primary": primary_adapter,
            "m_fallback": fallback_adapter,
        },
    )

    req = LLMGenerationRequest(task="general_code", messages=[ChatMessage.user("Stream test")])
    chunks = [chunk async for chunk in router.stream_generate(req)]

    assert len(chunks) > 0
    assembled = "".join(c.delta_content or "" for c in chunks)
    assert "Fallback stream content" in assembled
    assert primary_adapter.call_count == 1
    assert fallback_adapter.call_count == 1


@pytest.mark.asyncio
async def test_router_stream_generate_midstream_failure_does_not_fallback() -> None:
    """Verify mid-stream failure aborts and does NOT attempt fallback once tokens were emitted."""
    config = _build_test_gateway_config()
    primary_adapter = FakeLLMAdapter(
        model_id="primary-model-v1",
        scripted_responses=["Token1 Token2 Token3 Token4 Token5"],
        faults=FakeFaultInjection(partial_stream=True),
    )
    fallback_adapter = FakeLLMAdapter(
        model_id="fallback-model-v1",
        scripted_responses=["Fallback unreached"],
    )

    router = LLMGatewayRouter(
        config=config,
        environment="test",
        adapter_overrides={
            "m_primary": primary_adapter,
            "m_fallback": fallback_adapter,
        },
    )

    req = LLMGenerationRequest(task="general_code", messages=[ChatMessage.user("Stream test")])
    with pytest.raises(LLMProviderError):
        async for _ in router.stream_generate(req):
            pass

    assert primary_adapter.call_count == 1
    # Fallback must NOT have been called mid-stream
    assert fallback_adapter.call_count == 0


# ============================================================================
# Model Alias Override and Real Config Integration
# ============================================================================


def test_router_model_alias_priority() -> None:
    """Verify request model_alias prioritizes the requested model if eligible."""
    config = _build_test_gateway_config()
    router = LLMGatewayRouter(config=config, environment="test")

    candidates = router.resolve_candidates("general_code", model_override="m_fallback")
    assert candidates[0] == "m_fallback"
    assert "m_primary" in candidates


def test_router_with_real_gateway_configs() -> None:
    """Verify router initializes cleanly with repo's real YAML configs and resolves test_task."""
    real_config = load_gateway_config()
    router = LLMGatewayRouter(config=real_config, environment="test")

    # test_task maps to test_model on fake_provider
    candidates = router.resolve_candidates("test_task")
    assert candidates == ["test_model"]

    adapter = router.get_adapter("test_model")
    assert adapter is not None
    assert adapter.provider_id == "fake"
