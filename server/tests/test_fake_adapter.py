"""Tests verifying the deterministic FakeLLMAdapter with scripted responses and fault injection (docs/05 §11.1, §12, §15, M6-02)."""

import json

import pytest

from app.llm import (
    ChatMessage,
    FakeFaultInjection,
    FakeLLMAdapter,
    LLMGenerationOptions,
    LLMGenerationRequest,
    LLMProviderError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMStreamChunk,
    LLMTimeoutError,
    StructuredOutputSpec,
    ToolDefinition,
    create_adapter,
    get_adapter_class,
    list_supported_adapters,
)


@pytest.mark.asyncio
async def test_fake_adapter_deterministic_generation() -> None:
    """Verify FakeLLMAdapter produces deterministic output and tracks history."""
    adapter = FakeLLMAdapter()
    assert adapter.provider_id == "fake"
    assert adapter.model_id == "fake-deterministic"
    assert adapter.capabilities.tool_calling is True
    assert adapter.data_policy.source_code_allowed is True

    req = LLMGenerationRequest(
        task="code_answer",
        messages=[ChatMessage.user("Explain function blast radius")],
    )

    resp1 = await adapter.generate(req)
    resp2 = await adapter.generate(req)

    assert resp1.content == resp2.content
    assert "Deterministic response for task 'code_answer'" in (resp1.content or "")
    assert resp1.usage.input_tokens > 0
    assert resp1.usage.output_tokens > 0
    assert resp1.finish_reason == "stop"
    assert adapter.call_count == 2
    assert len(adapter.history) == 2


@pytest.mark.asyncio
async def test_fake_adapter_scripted_responses_queue_and_map() -> None:
    """Verify scripted FIFO queue and task-specific response mappings."""
    # 1. FIFO list queue
    adapter_queue = FakeLLMAdapter(
        scripted_responses=["First answer", "Second answer"],
    )
    req1 = LLMGenerationRequest(task="task1", messages=[ChatMessage.user("Q1")])
    req2 = LLMGenerationRequest(task="task2", messages=[ChatMessage.user("Q2")])
    req3 = LLMGenerationRequest(task="task3", messages=[ChatMessage.user("Q3")])

    res1 = await adapter_queue.generate(req1)
    res2 = await adapter_queue.generate(req2)
    res3 = await adapter_queue.generate(req3)

    assert res1.content == "First answer"
    assert res2.content == "Second answer"
    assert "Deterministic response" in (res3.content or "")

    # 2. Dict keyed by task
    adapter_map = FakeLLMAdapter(
        scripted_responses={
            "query_rewrite": "search term expanded",
            "security_explanation": "Finding explanation text",
        }
    )
    req_rewrite = LLMGenerationRequest(
        task="query_rewrite", messages=[ChatMessage.user("raw query")]
    )
    req_sec = LLMGenerationRequest(
        task="security_explanation", messages=[ChatMessage.user("finding")]
    )

    res_rewrite = await adapter_map.generate(req_rewrite)
    res_sec = await adapter_map.generate(req_sec)

    assert res_rewrite.content == "search term expanded"
    assert res_sec.content == "Finding explanation text"


@pytest.mark.asyncio
async def test_fake_adapter_structured_output_synthesis() -> None:
    """Verify structured output generates valid JSON adhering to schema."""
    adapter = FakeLLMAdapter()
    spec = StructuredOutputSpec(
        schema_name="AgentPlan",
        schema_def={
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "confidence": {"type": "number"},
                "steps": {"type": "array"},
                "is_safe": {"type": "boolean"},
            },
        },
    )
    req = LLMGenerationRequest(
        task="agent_manager_routing",
        messages=[ChatMessage.user("Route plan")],
        options=LLMGenerationOptions(structured_output=spec),
    )

    resp = await adapter.generate(req)
    assert resp.content is not None
    parsed = json.loads(resp.content)

    assert parsed["summary"] == "fake_summary_value"
    assert parsed["confidence"] == 1.0
    assert parsed["steps"] == ["item_1"]
    assert parsed["is_safe"] is True


@pytest.mark.asyncio
async def test_fake_adapter_tool_calling_simulation() -> None:
    """Verify simulated tool calls when tools are provided in options."""
    adapter = FakeLLMAdapter()
    tool = ToolDefinition.from_params(
        name="find_references",
        description="Search references for a symbol",
    )
    req = LLMGenerationRequest(
        task="code_review_reasoning",
        messages=[ChatMessage.user("Find references")],
        options=LLMGenerationOptions(tools=[tool]),
    )

    resp = await adapter.generate(req)
    assert resp.content is None
    assert len(resp.tool_calls) == 1
    assert resp.finish_reason == "tool_calls"
    assert resp.tool_calls[0].function.name == "find_references"
    parsed_args = json.loads(resp.tool_calls[0].function.arguments)
    assert "query" in parsed_args


@pytest.mark.asyncio
async def test_fake_adapter_streaming_generation() -> None:
    """Verify streaming yields chunk deltas and final stop with usage."""
    adapter = FakeLLMAdapter(scripted_responses=["The continuous Project Brain is active"])
    req = LLMGenerationRequest(task="code_answer", messages=[ChatMessage.user("Stream test")])

    chunks: list[LLMStreamChunk] = []
    async for chunk in adapter.stream_generate(req):
        chunks.append(chunk)

    assert len(chunks) > 2
    full_text = "".join(c.delta_content for c in chunks)
    assert full_text == "The continuous Project Brain is active"

    final_chunk = chunks[-1]
    assert final_chunk.finish_reason == "stop"
    assert final_chunk.usage is not None
    assert final_chunk.usage.total_tokens > 0


@pytest.mark.asyncio
async def test_fake_adapter_fault_injection_timeout() -> None:
    """Verify timeout fault injection."""
    adapter = FakeLLMAdapter(faults=FakeFaultInjection(timeout=True))
    req = LLMGenerationRequest(task="code_answer", messages=[ChatMessage.user("Test")])

    with pytest.raises(LLMTimeoutError) as exc_info:
        await adapter.generate(req)
    assert exc_info.value.code == "llm.timeout"
    assert exc_info.value.timeout_s == 30.0


@pytest.mark.asyncio
async def test_fake_adapter_fault_injection_rate_limit() -> None:
    """Verify rate limit HTTP 429 fault injection."""
    adapter = FakeLLMAdapter(faults=FakeFaultInjection(rate_limit=True, rate_limit_retry_after=5.5))
    req = LLMGenerationRequest(task="code_answer", messages=[ChatMessage.user("Test")])

    with pytest.raises(LLMRateLimitError) as exc_info:
        await adapter.generate(req)
    assert exc_info.value.code == "llm.rate_limit"
    assert exc_info.value.retry_after_s == 5.5


@pytest.mark.asyncio
async def test_fake_adapter_fault_injection_provider_5xx() -> None:
    """Verify provider 5xx fault injection."""
    adapter = FakeLLMAdapter(faults=FakeFaultInjection(provider_5xx=True, provider_status_code=503))
    req = LLMGenerationRequest(task="code_answer", messages=[ChatMessage.user("Test")])

    with pytest.raises(LLMProviderError) as exc_info:
        await adapter.generate(req)
    assert exc_info.value.code == "llm.provider_error"
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_fake_adapter_fault_injection_refusal() -> None:
    """Verify content refusal fault injection."""
    adapter = FakeLLMAdapter(
        faults=FakeFaultInjection(refusal=True, refusal_reason="Prompt policy violation")
    )
    req = LLMGenerationRequest(task="code_answer", messages=[ChatMessage.user("Test")])

    with pytest.raises(LLMRefusalError) as exc_info:
        await adapter.generate(req)
    assert exc_info.value.code == "llm.refusal"
    assert exc_info.value.reason == "Prompt policy violation"


@pytest.mark.asyncio
async def test_fake_adapter_fault_injection_malformed_output() -> None:
    """Verify malformed unparseable JSON output fault."""
    adapter = FakeLLMAdapter(faults=FakeFaultInjection(malformed_output=True))
    req = LLMGenerationRequest(task="code_answer", messages=[ChatMessage.user("Test")])

    resp = await adapter.generate(req)
    assert resp.content is not None
    with pytest.raises(json.JSONDecodeError):
        json.loads(resp.content)


@pytest.mark.asyncio
async def test_fake_adapter_fault_injection_partial_stream() -> None:
    """Verify partial stream interruption fault."""
    adapter = FakeLLMAdapter(
        scripted_responses=["one two three four five six"],
        faults=FakeFaultInjection(partial_stream=True),
    )
    req = LLMGenerationRequest(task="code_answer", messages=[ChatMessage.user("Test")])

    received_text = ""
    with pytest.raises(LLMProviderError) as exc_info:
        async for chunk in adapter.stream_generate(req):
            received_text += chunk.delta_content

    assert "abort mid-transfer" in str(exc_info.value)
    assert len(received_text) > 0  # Received some chunks before abort


def test_fake_adapter_registered_in_registry() -> None:
    """Verify 'fake' adapter is registered and instantiable via factory."""
    assert "fake" in list_supported_adapters()
    cls = get_adapter_class("fake")
    assert cls is FakeLLMAdapter

    instance = create_adapter("fake", model_id="custom-fake-model")
    assert isinstance(instance, FakeLLMAdapter)
    assert instance.model_id == "custom-fake-model"
