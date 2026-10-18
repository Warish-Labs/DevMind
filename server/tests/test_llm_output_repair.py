"""Tests for structured output schema validation, JSON sanitization, and schema repair (docs/05 §10, ADR-027, M6-09).

Verifies:
1. Markdown fence extraction and JSON syntax cleanup (extract_json_candidate, clean_json_string).
2. Canonical task schemas (AgentPlan, FindingExplanation, SynthesizedAnswer, RewrittenQuery) and SchemaRegistry.
3. StructuredOutputRepairer validation logic (valid, syntax errors, schema violations).
4. Router integration:
   - Direct success validation and markdown fence cleanup.
   - One-shot schema repair execution when initial output is invalid.
   - Failed repair raises LLMInvalidOutputError without attempting fallback candidates (ADR-027).
   - Automatic output_schema resolution from tasks.yaml declarations.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.llm import (
    AgentPlan,
    ChatMessage,
    FakeLLMAdapter,
    FindingExplanation,
    GatewayConfig,
    LLMGatewayRouter,
    LLMGenerationRequest,
    LLMInvalidOutputError,
    LLMUsageRecorder,
    RewrittenQuery,
    SchemaRegistry,
    StructuredOutputRepairer,
    SynthesizedAnswer,
    clean_json_string,
    default_schema_registry,
    extract_json_candidate,
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


def _build_repair_test_config() -> GatewayConfig:
    """Build a deterministic in-memory GatewayConfig for testing structured output validation and repair."""
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
        "m_primary": ModelEntry(
            provider="p_primary",
            model_id="fake-primary-v1",
            capabilities=ModelCapabilitiesConfig(
                structured_output="native",
                streaming=True,
            ),
            limits=ModelLimitsConfig(max_input_tokens=10000, max_output_tokens=2000),
            price_units=ModelPriceUnitsConfig(input_per_1k=10, output_per_1k=30),
        ),
        "m_fallback": ModelEntry(
            provider="p_fallback",
            model_id="fake-fallback-v1",
            capabilities=ModelCapabilitiesConfig(
                structured_output="native",
                streaming=True,
            ),
            limits=ModelLimitsConfig(max_input_tokens=10000, max_output_tokens=2000),
            price_units=ModelPriceUnitsConfig(input_per_1k=10, output_per_1k=30),
        ),
    }

    tasks = {
        "plan_task": TaskEntry(
            model="m_primary",
            fallbacks=["m_fallback"],
            output_schema="AgentPlan",
            budget=TaskBudgetConfig(max_input_tokens=5000),
        ),
        "freeform_task": TaskEntry(
            model="m_primary",
            fallbacks=["m_fallback"],
            budget=TaskBudgetConfig(max_input_tokens=5000),
        ),
    }

    return GatewayConfig(
        config_hash="test-config-repair",
        providers=ProvidersConfig(version=1, providers=providers),
        models=ModelsConfig(version=1, models=models),
        tasks=TasksConfig(version=1, defaults=DefaultsConfig(), tasks=tasks),
    )


# ============================================================================
# 1. Extraction and JSON Cleaning Tests
# ============================================================================


def test_extract_json_candidate_markdown_blocks() -> None:
    """Verify JSON extraction from markdown code fences."""
    # ```json ... ```
    raw1 = 'Here is the response:\n```json\n{"summary": "Plan A", "steps": ["step1"]}\n```\nHope it helps!'
    assert extract_json_candidate(raw1) == '{"summary": "Plan A", "steps": ["step1"]}'

    # ``` ... ``` without json tag
    raw2 = '```\n{"key": "value"}\n```'
    assert extract_json_candidate(raw2) == '{"key": "value"}'


def test_extract_json_candidate_surrounding_text() -> None:
    """Verify JSON extraction when model includes preamble without fences."""
    raw = 'Sure! Here is your requested JSON object: {"name": "DevMind", "status": "active"}. Let me know if you need anything else.'
    assert extract_json_candidate(raw) == '{"name": "DevMind", "status": "active"}'


def test_clean_json_string_trailing_commas() -> None:
    """Verify removal of trailing commas before closing braces and brackets."""
    flawed_object = '{"summary": "Test", "steps": ["s1", "s2",], "confidence": 0.9,}'
    cleaned = clean_json_string(flawed_object)
    parsed = json.loads(cleaned)
    assert parsed["summary"] == "Test"
    assert parsed["steps"] == ["s1", "s2"]
    assert parsed["confidence"] == 0.9


# ============================================================================
# 2. Canonical Task Schemas and Registry Tests
# ============================================================================


def test_canonical_schemas_validation() -> None:
    """Verify canonical Pydantic schemas enforce required fields and bounds."""
    # AgentPlan
    plan = AgentPlan(summary="Plan", steps=["s1"], confidence=0.85)
    assert plan.is_safe is True

    with pytest.raises(ValidationError):
        # Confidence out of bounds > 1.0
        AgentPlan(summary="Plan", steps=[], confidence=1.5)

    with pytest.raises(ValidationError):
        # Extra fields forbidden
        AgentPlan(summary="Plan", steps=[], unexpected_key="bad")  # type: ignore[call-arg]

    # FindingExplanation
    explanation = FindingExplanation(
        summary="Missing guard",
        impact="Unauthorized route access",
        likely_cause="Route missing @require_auth decorator",
        remediation_proposal="Add @require_auth decorator to router",
    )
    assert explanation.confidence == 0.8

    # SynthesizedAnswer
    answer = SynthesizedAnswer(
        answer="DevMind uses Next.js and FastAPI.",
        citations=["docs/01-overview.md"],
    )
    assert answer.confidence == 0.9

    # RewrittenQuery
    query = RewrittenQuery(
        rewritten_query="JWT verification token expiration Clerk",
        keywords=["jwt", "clerk", "auth"],
        intent="authentication_lookup",
    )
    assert query.intent == "authentication_lookup"


def test_schema_registry() -> None:
    """Verify SchemaRegistry stores canonical schemas and builds StructuredOutputSpec."""
    registry = SchemaRegistry()
    assert registry.contains("AgentPlan")
    assert registry.contains("FindingExplanation")
    assert registry.contains("SynthesizedAnswer")
    assert registry.contains("RewrittenQuery")

    spec = registry.build_spec("AgentPlan", mode="native")
    assert spec.schema_name == "AgentPlan"
    assert spec.mode == "native"
    assert "properties" in spec.schema_def
    assert "summary" in spec.schema_def["properties"]


# ============================================================================
# 3. StructuredOutputRepairer Unit Tests
# ============================================================================


def test_repairer_validate_success() -> None:
    """Verify validation succeeds when JSON matches registered schema."""
    repairer = StructuredOutputRepairer()
    spec = default_schema_registry.build_spec("AgentPlan")

    valid_json = json.dumps(
        {
            "summary": "Valid plan",
            "steps": ["step 1", "step 2"],
            "confidence": 0.95,
            "selected_agents": ["CodeMate"],
            "is_safe": True,
        }
    )

    result = repairer.validate(valid_json, spec)
    assert result.is_valid is True
    assert result.validated_model is not None
    assert result.validated_model.summary == "Valid plan"


def test_repairer_validate_syntax_error() -> None:
    """Verify validation reports syntax error on malformed JSON."""
    repairer = StructuredOutputRepairer()
    spec = default_schema_registry.build_spec("AgentPlan")

    broken_json = '{"summary": "Incomplete string'
    result = repairer.validate(broken_json, spec)
    assert result.is_valid is False
    assert any("syntax error" in err.lower() for err in result.errors)


def test_repairer_validate_schema_violation() -> None:
    """Verify validation reports clear field errors on schema violations."""
    repairer = StructuredOutputRepairer()
    spec = default_schema_registry.build_spec("AgentPlan")

    # Missing 'steps', confidence > 1.0
    bad_data = json.dumps({"summary": "Bad plan", "confidence": 2.5})
    result = repairer.validate(bad_data, spec)
    assert result.is_valid is False
    errors_str = " ".join(result.errors)
    assert "steps" in errors_str
    assert "confidence" in errors_str


# ============================================================================
# 4. Router Integration: Validation and Repair Flow Tests
# ============================================================================


@pytest.mark.asyncio
async def test_router_structured_output_direct_success() -> None:
    """Verify router cleanly processes valid structured output without repair."""
    config = _build_repair_test_config()
    recorder = LLMUsageRecorder()
    router = LLMGatewayRouter(config=config, usage_recorder=recorder)

    valid_payload = json.dumps(
        {
            "summary": "Deploy plan",
            "steps": ["build", "test"],
            "confidence": 1.0,
            "selected_agents": [],
            "is_safe": True,
        }
    )

    adapter = FakeLLMAdapter(
        model_id="fake-primary-v1",
        scripted_responses=[valid_payload],
    )
    router.register_adapter_override("m_primary", adapter)

    req = LLMGenerationRequest(
        task="plan_task",
        messages=[ChatMessage.user("Generate plan")],
    )

    resp = await router.generate(req)
    assert resp.content == valid_payload
    # Exactly 1 call was made to the adapter (no repair needed)
    assert adapter.call_count == 1
    assert len(recorder.history) == 1
    assert recorder.history[0].outcome == "success"


@pytest.mark.asyncio
async def test_router_cleans_markdown_fences() -> None:
    """Verify router automatically strips markdown fences from LLM responses."""
    config = _build_repair_test_config()
    router = LLMGatewayRouter(config=config)

    fenced_payload = (
        "```json\n"
        + json.dumps(
            {
                "summary": "Fenced plan",
                "steps": ["inspect"],
                "confidence": 0.8,
                "selected_agents": [],
                "is_safe": True,
            }
        )
        + "\n```"
    )

    adapter = FakeLLMAdapter(
        model_id="fake-primary-v1",
        scripted_responses=[fenced_payload],
    )
    router.register_adapter_override("m_primary", adapter)

    req = LLMGenerationRequest(
        task="plan_task",
        messages=[ChatMessage.user("Generate plan")],
    )

    resp = await router.generate(req)
    # The returned content must be valid raw JSON without the ```json fences
    assert not resp.content.startswith("```")
    parsed = json.loads(resp.content)
    assert parsed["summary"] == "Fenced plan"
    assert adapter.call_count == 1


@pytest.mark.asyncio
async def test_router_one_shot_repair_success() -> None:
    """Verify that when initial output is invalid, router executes 1 repair attempt and recovers."""
    config = _build_repair_test_config()
    recorder = LLMUsageRecorder()
    router = LLMGatewayRouter(config=config, usage_recorder=recorder)

    # Initial response is invalid (missing 'steps' field)
    initial_flawed_payload = json.dumps({"summary": "Flawed initial plan", "confidence": 0.9})
    # Repaired response is strictly valid
    repaired_valid_payload = json.dumps(
        {
            "summary": "Repaired valid plan",
            "steps": ["step_fixed"],
            "confidence": 0.95,
            "selected_agents": [],
            "is_safe": True,
        }
    )

    adapter = FakeLLMAdapter(
        model_id="fake-primary-v1",
        scripted_responses=[initial_flawed_payload, repaired_valid_payload],
    )
    router.register_adapter_override("m_primary", adapter)

    req = LLMGenerationRequest(
        task="plan_task",
        messages=[ChatMessage.user("Generate plan")],
    )

    resp = await router.generate(req)
    assert adapter.call_count == 2
    parsed = json.loads(resp.content)
    assert parsed["summary"] == "Repaired valid plan"
    assert parsed["steps"] == ["step_fixed"]

    # Verify repair request included repair instructions in messages
    repair_req = adapter.history[1]
    assert len(repair_req.messages) > 1
    last_msg = repair_req.messages[-1]
    assert "Validation errors encountered" in last_msg.content
    assert "steps" in last_msg.content


@pytest.mark.asyncio
async def test_router_failed_repair_raises_invalid_output_without_fallback() -> None:
    """Verify that if repair attempt also fails, LLMInvalidOutputError is raised without trying fallback (ADR-027)."""
    config = _build_repair_test_config()
    recorder = LLMUsageRecorder()
    router = LLMGatewayRouter(config=config, usage_recorder=recorder)

    # Both initial and repair attempt are invalid
    bad_payload_1 = '{"summary": "Bad 1"}'
    bad_payload_2 = '{"summary": "Bad 2 after repair"}'

    primary_adapter = FakeLLMAdapter(
        model_id="fake-primary-v1",
        scripted_responses=[bad_payload_1, bad_payload_2],
    )
    fallback_adapter = FakeLLMAdapter(
        model_id="fake-fallback-v1",
        scripted_responses=['{"summary": "Fallback should not be called"}'],
    )
    router.register_adapter_override("m_primary", primary_adapter)
    router.register_adapter_override("m_fallback", fallback_adapter)

    req = LLMGenerationRequest(
        task="plan_task",
        messages=[ChatMessage.user("Generate plan")],
    )

    with pytest.raises(LLMInvalidOutputError) as exc_info:
        await router.generate(req)

    assert exc_info.value.code == "llm.invalid_output"
    assert "repair attempt" in str(exc_info.value).lower()

    # Primary adapter was called twice (1 initial + 1 repair attempt)
    assert primary_adapter.call_count == 2
    # ADR-027 constraint: fallback model must NEVER be called on invalid output
    assert fallback_adapter.call_count == 0

    # Failure usage recorded
    assert len(recorder.history) >= 1
    assert recorder.history[-1].outcome == "failure"


@pytest.mark.asyncio
async def test_router_automatic_task_output_schema_resolution() -> None:
    """Verify that tasks.yaml output_schema is automatically attached and validated."""
    config = _build_repair_test_config()
    router = LLMGatewayRouter(config=config)

    # plan_task has output_schema: AgentPlan in tasks.yaml
    valid_payload = json.dumps(
        {
            "summary": "Resolved plan",
            "steps": ["analyze", "execute"],
            "confidence": 0.9,
            "selected_agents": [],
            "is_safe": True,
        }
    )

    adapter = FakeLLMAdapter(
        model_id="fake-primary-v1",
        scripted_responses=[valid_payload],
    )
    router.register_adapter_override("m_primary", adapter)

    # Do not set options.structured_output explicitly
    req = LLMGenerationRequest(
        task="plan_task",
        messages=[ChatMessage.user("Please plan")],
    )

    resp = await router.generate(req)
    assert resp.content == valid_payload
    # Verify adapter received structured_output spec in options
    sent_req = adapter.history[0]
    assert sent_req.options.structured_output is not None
    assert sent_req.options.structured_output.schema_name == "AgentPlan"
