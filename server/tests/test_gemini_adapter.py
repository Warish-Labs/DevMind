"""Recorded-shape tests verifying GoogleGeminiAdapter with official Gemini REST contracts (docs/05 §11.1, §12, docs/11 M6-04)."""

import json
from typing import Any

import httpx
import pytest

from app.llm import (
    ChatMessage,
    GoogleGeminiAdapter,
    LLMError,
    LLMGenerationOptions,
    LLMGenerationRequest,
    LLMInvalidOutputError,
    LLMPermissionError,
    LLMProviderError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMTimeoutError,
    StructuredOutputSpec,
    ToolDefinition,
    create_adapter,
    get_adapter_class,
    list_supported_adapters,
)


def _make_mock_client(
    status_code: int = 200,
    json_data: dict[str, Any] | None = None,
    text_content: str | None = None,
    headers: dict[str, str] | None = None,
    exception: Exception | None = None,
) -> tuple[httpx.AsyncClient, list[httpx.Request]]:
    """Create an AsyncClient with MockTransport recording requests."""
    recorded_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        if exception:
            raise exception
        resp_headers = headers or {}
        if json_data is not None:
            return httpx.Response(
                status_code=status_code,
                json=json_data,
                headers={"Content-Type": "application/json", **resp_headers},
            )
        return httpx.Response(
            status_code=status_code,
            text=text_content or "",
            headers=resp_headers,
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return client, recorded_requests


@pytest.mark.asyncio
async def test_gemini_adapter_metadata_and_capabilities() -> None:
    """Verify GoogleGeminiAdapter metadata, capabilities, and data policy."""
    adapter = GoogleGeminiAdapter(model_id="gemini-1.5-flash", api_key="dummy-key")
    assert adapter.provider_id == "google"
    assert adapter.model_id == "gemini-1.5-flash"
    assert adapter.capabilities.tool_calling is True
    assert adapter.capabilities.structured_output == "native"
    assert adapter.capabilities.streaming is True
    assert adapter.capabilities.supports_system_prompt is True

    # Free tier data policy
    assert adapter.data_policy.source_code_allowed is False
    assert adapter.data_policy.terms_reviewed is False

    # Validation: source code blocked
    with pytest.raises(LLMPermissionError):
        adapter.validate_data_policy(may_contain_source=True)


@pytest.mark.asyncio
async def test_gemini_adapter_missing_api_key_raises_auth_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify invocation without API key raises LLMError authentication error."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("DEVMIND_LLM_PRIMARY_API_KEY", raising=False)

    adapter = GoogleGeminiAdapter(api_key="")
    req = LLMGenerationRequest(task="test", messages=[ChatMessage.user("hello")])

    with pytest.raises(LLMError) as exc_info:
        await adapter.generate(req)
    assert exc_info.value.code == "llm.authentication_error"


@pytest.mark.asyncio
async def test_gemini_adapter_generate_text_success() -> None:
    """Verify standard text generation and token usage extraction."""
    mock_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "Hello developer! This is DevMind reasoning."}],
                    "role": "model",
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 24,
            "candidatesTokenCount": 12,
            "totalTokenCount": 36,
        },
    }

    client, requests = _make_mock_client(json_data=mock_response)
    adapter = GoogleGeminiAdapter(api_key="test-api-key", client=client)

    req = LLMGenerationRequest(
        task="code_answer",
        messages=[
            ChatMessage.system("You are DevMind code intelligence assistant."),
            ChatMessage.user("Explain repository architecture."),
        ],
        options=LLMGenerationOptions(temperature=0.3, max_output_tokens=1000),
    )

    resp = await adapter.generate(req)

    assert resp.content == "Hello developer! This is DevMind reasoning."
    assert resp.role == "assistant"
    assert resp.finish_reason == "stop"
    assert resp.usage.input_tokens == 24
    assert resp.usage.output_tokens == 12
    assert resp.usage.total_tokens == 36
    assert resp.latency_ms > 0
    assert resp.provider_id == "google"
    assert resp.model_id == "gemini-1.5-flash"

    # Verify request payload
    assert len(requests) == 1
    sent_req = requests[0]
    assert sent_req.headers["x-goog-api-key"] == "test-api-key"
    payload = json.loads(sent_req.content.decode("utf-8"))
    assert (
        payload["systemInstruction"]["parts"][0]["text"]
        == "You are DevMind code intelligence assistant."
    )
    assert payload["contents"][0]["role"] == "user"
    assert payload["contents"][0]["parts"][0]["text"] == "Explain repository architecture."
    assert payload["generationConfig"]["temperature"] == 0.3
    assert payload["generationConfig"]["maxOutputTokens"] == 1000


@pytest.mark.asyncio
async def test_gemini_adapter_structured_json_native_success() -> None:
    """Verify structured output with native responseSchema and JSON validation."""
    expected_plan = {"steps": ["inspect", "diagnose", "fix"], "confidence": 0.95}
    mock_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": json.dumps(expected_plan)}],
                    "role": "model",
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {"promptTokenCount": 40, "candidatesTokenCount": 25},
    }

    client, requests = _make_mock_client(json_data=mock_response)
    adapter = GoogleGeminiAdapter(api_key="test-key", client=client)

    schema = {
        "type": "object",
        "properties": {
            "steps": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number"},
        },
        "required": ["steps", "confidence"],
    }

    req = LLMGenerationRequest(
        task="agent_manager_routing",
        messages=[ChatMessage.user("Generate action plan")],
        options=LLMGenerationOptions(
            structured_output=StructuredOutputSpec(
                schema_name="AgentPlan",
                schema_def=schema,
                mode="native",
            )
        ),
    )

    resp = await adapter.generate(req)
    assert resp.content is not None
    parsed = json.loads(resp.content)
    assert parsed["steps"] == ["inspect", "diagnose", "fix"]
    assert parsed["confidence"] == 0.95

    # Check request payload configured JSON mime type and schema
    payload = json.loads(requests[0].content.decode("utf-8"))
    assert payload["generationConfig"]["responseMimeType"] == "application/json"
    assert payload["generationConfig"]["responseSchema"] == schema


@pytest.mark.asyncio
async def test_gemini_adapter_structured_json_malformed_raises_invalid_output() -> None:
    """Verify that structured output response with non-JSON text raises LLMInvalidOutputError."""
    mock_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "I am not valid JSON output"}],
                    "role": "model",
                },
                "finishReason": "STOP",
            }
        ]
    }

    client, _ = _make_mock_client(json_data=mock_response)
    adapter = GoogleGeminiAdapter(api_key="test-key", client=client)

    req = LLMGenerationRequest(
        task="agent_manager_routing",
        messages=[ChatMessage.user("Generate plan")],
        options=LLMGenerationOptions(
            structured_output=StructuredOutputSpec(
                schema_name="AgentPlan",
                schema_def={"type": "object"},
                mode="native",
            )
        ),
    )

    with pytest.raises(LLMInvalidOutputError) as exc_info:
        await adapter.generate(req)
    assert exc_info.value.code == "llm.invalid_output"


@pytest.mark.asyncio
async def test_gemini_adapter_tool_calling_request_and_response() -> None:
    """Verify tool definition translation, functionCallingConfig, and ToolCall extraction."""
    mock_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "functionCall": {
                                "name": "search_code_symbols",
                                "args": {"query": "AuthContext", "limit": 5},
                            }
                        }
                    ],
                    "role": "model",
                },
                "finishReason": "STOP",
            }
        ]
    }

    client, requests = _make_mock_client(json_data=mock_response)
    adapter = GoogleGeminiAdapter(api_key="test-key", client=client)

    tool = ToolDefinition.from_params(
        name="search_code_symbols",
        description="Search symbols in repository",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
            "required": ["query"],
        },
    )

    req = LLMGenerationRequest(
        task="symbol_lookup",
        messages=[ChatMessage.user("Where is AuthContext defined?")],
        options=LLMGenerationOptions(tools=[tool], tool_choice="auto"),
    )

    resp = await adapter.generate(req)

    assert resp.finish_reason == "tool_calls"
    assert len(resp.tool_calls) == 1
    tc = resp.tool_calls[0]
    assert tc.function.name == "search_code_symbols"
    args = json.loads(tc.function.arguments)
    assert args["query"] == "AuthContext"
    assert args["limit"] == 5

    # Verify tool declarations sent to Gemini
    payload = json.loads(requests[0].content.decode("utf-8"))
    assert len(payload["tools"]) == 1
    fn_decl = payload["tools"][0]["functionDeclarations"][0]
    assert fn_decl["name"] == "search_code_symbols"
    assert payload["toolConfig"]["functionCallingConfig"]["mode"] == "AUTO"


@pytest.mark.asyncio
async def test_gemini_adapter_streaming_sse_chunks() -> None:
    """Verify streaming token deltas and usage extraction from Server-Sent Events."""
    sse_body = (
        'data: {"candidates": [{"content": {"parts": [{"text": "Hello "}]}}]}\n\n'
        'data: {"candidates": [{"content": {"parts": [{"text": "world!"}]}}]}\n\n'
        'data: {"candidates": [{"finishReason": "STOP"}], "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5}}\n\n'
        "data: [DONE]\n\n"
    )

    client, requests = _make_mock_client(
        text_content=sse_body,
        headers={"Content-Type": "text/event-stream"},
    )
    adapter = GoogleGeminiAdapter(api_key="test-key", client=client)

    req = LLMGenerationRequest(
        task="code_answer",
        messages=[ChatMessage.user("Hello")],
    )

    chunks = []
    async for chunk in adapter.stream_generate(req):
        chunks.append(chunk)

    assert len(chunks) == 3
    assert chunks[0].delta_content == "Hello "
    assert chunks[1].delta_content == "world!"
    assert chunks[2].finish_reason == "stop"
    assert chunks[2].usage is not None
    assert chunks[2].usage.input_tokens == 10
    assert chunks[2].usage.output_tokens == 5

    assert "streamGenerateContent?alt=sse" in str(requests[0].url)


@pytest.mark.asyncio
async def test_gemini_adapter_safety_refusal_raises() -> None:
    """Verify that SAFETY finishReason triggers an explicit LLMRefusalError."""
    mock_response = {
        "candidates": [
            {
                "finishReason": "SAFETY",
                "content": {"parts": []},
            }
        ]
    }

    client, _ = _make_mock_client(json_data=mock_response)
    adapter = GoogleGeminiAdapter(api_key="test-key", client=client)

    req = LLMGenerationRequest(task="unsafe_test", messages=[ChatMessage.user("prompt")])

    with pytest.raises(LLMRefusalError) as exc_info:
        await adapter.generate(req)
    assert exc_info.value.code == "llm.refusal"
    assert exc_info.value.reason == "SAFETY"


@pytest.mark.asyncio
async def test_gemini_adapter_rate_limit_error_handling() -> None:
    """Verify HTTP 429 / RESOURCE_EXHAUSTED maps to LLMRateLimitError with retry hint."""
    mock_err = {
        "error": {
            "code": 429,
            "message": "Quota exceeded for quota metric 'Queries' and limit 'Queries per minute'",
            "status": "RESOURCE_EXHAUSTED",
        }
    }

    client, _ = _make_mock_client(
        status_code=429,
        json_data=mock_err,
        headers={"retry-after": "4"},
    )
    adapter = GoogleGeminiAdapter(api_key="test-key", client=client)

    req = LLMGenerationRequest(task="rate_limited", messages=[ChatMessage.user("prompt")])

    with pytest.raises(LLMRateLimitError) as exc_info:
        await adapter.generate(req)
    assert exc_info.value.code == "llm.rate_limit"
    assert exc_info.value.retry_after_s == 4.0


@pytest.mark.asyncio
async def test_gemini_adapter_5xx_provider_error() -> None:
    """Verify HTTP 503 maps to LLMProviderError."""
    mock_err = {
        "error": {
            "code": 503,
            "message": "The model is overloaded. Please try again later.",
            "status": "UNAVAILABLE",
        }
    }

    client, _ = _make_mock_client(status_code=503, json_data=mock_err)
    adapter = GoogleGeminiAdapter(api_key="test-key", client=client)

    req = LLMGenerationRequest(task="overloaded", messages=[ChatMessage.user("prompt")])

    with pytest.raises(LLMProviderError) as exc_info:
        await adapter.generate(req)
    assert exc_info.value.code == "llm.provider_error"
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_gemini_adapter_timeout_handling() -> None:
    """Verify httpx.TimeoutException maps to LLMTimeoutError."""
    client, _ = _make_mock_client(exception=httpx.ReadTimeout("Read timed out"))
    adapter = GoogleGeminiAdapter(api_key="test-key", client=client, timeout_seconds=10.0)

    req = LLMGenerationRequest(task="timeout_test", messages=[ChatMessage.user("prompt")])

    with pytest.raises(LLMTimeoutError) as exc_info:
        await adapter.generate(req)
    assert exc_info.value.code == "llm.timeout"
    assert exc_info.value.timeout_s == 10.0


def test_gemini_adapter_registry_discovery() -> None:
    """Verify 'google' and 'gemini' keys are registered in the adapter factory registry."""
    adapters = list_supported_adapters()
    assert "google" in adapters
    assert "gemini" in adapters

    cls = get_adapter_class("google")
    assert cls is GoogleGeminiAdapter

    instance = create_adapter("google", api_key="registered-key", model_id="gemini-1.5-flash")
    assert isinstance(instance, GoogleGeminiAdapter)
    assert instance.model_id == "gemini-1.5-flash"
