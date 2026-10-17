"""Recorded-shape tests verifying OpenAICompatibleAdapter (docs/05 §11.1, §12, docs/11 M6-05)."""

import json
from typing import Any

import httpx
import pytest

from app.llm import (
    ChatMessage,
    LLMError,
    LLMGenerationOptions,
    LLMGenerationRequest,
    LLMPermissionError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMTimeoutError,
    OpenAICompatibleAdapter,
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
async def test_openai_compatible_adapter_metadata_and_capabilities() -> None:
    """Verify adapter metadata, verified capabilities, and data policy."""
    adapter = OpenAICompatibleAdapter(
        model_id="llama-3.3-70b-versatile",
        provider_id="groq",
        api_key="test-key",
    )
    assert adapter.provider_id == "groq"
    assert adapter.model_id == "llama-3.3-70b-versatile"
    assert adapter.capabilities.tool_calling is True
    assert adapter.capabilities.structured_output == "native"
    assert adapter.capabilities.streaming is True
    assert adapter.capabilities.supports_system_prompt is True

    # Data policy guard
    assert adapter.data_policy.source_code_allowed is False
    assert adapter.data_policy.terms_reviewed is False

    with pytest.raises(LLMPermissionError):
        adapter.validate_data_policy(may_contain_source=True)


@pytest.mark.asyncio
async def test_openai_compatible_adapter_missing_api_key_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify invocation without API key raises LLMError with code llm.authentication_error."""
    monkeypatch.delenv("DEVMIND_LLM_ALT_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    adapter = OpenAICompatibleAdapter(api_key="")
    req = LLMGenerationRequest(task="test", messages=[ChatMessage.user("hello")])

    with pytest.raises(LLMError) as exc_info:
        await adapter.generate(req)
    assert exc_info.value.code == "llm.authentication_error"


@pytest.mark.asyncio
async def test_openai_compatible_adapter_generate_text_success() -> None:
    """Verify standard chat completion and token usage extraction."""
    mock_response = {
        "id": "chatcmpl-12345",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "This is an OpenAI/Groq compatible response.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 18,
            "completion_tokens": 9,
            "total_tokens": 27,
        },
    }

    client, requests = _make_mock_client(json_data=mock_response)
    adapter = OpenAICompatibleAdapter(
        api_key="sk-test-key",
        base_url="https://api.groq.com/openai/v1",
        client=client,
    )

    req = LLMGenerationRequest(
        task="code_answer",
        messages=[
            ChatMessage.system("System prompt."),
            ChatMessage.user("User question."),
        ],
        options=LLMGenerationOptions(temperature=0.2, max_output_tokens=500),
    )

    resp = await adapter.generate(req)

    assert resp.content == "This is an OpenAI/Groq compatible response."
    assert resp.role == "assistant"
    assert resp.finish_reason == "stop"
    assert resp.usage.input_tokens == 18
    assert resp.usage.output_tokens == 9
    assert resp.usage.total_tokens == 27
    assert resp.latency_ms > 0

    # Verify HTTP request
    assert len(requests) == 1
    sent_req = requests[0]
    assert sent_req.headers["Authorization"] == "Bearer sk-test-key"
    payload = json.loads(sent_req.content.decode("utf-8"))
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1]["role"] == "user"
    assert payload["temperature"] == 0.2
    assert payload["max_tokens"] == 500


@pytest.mark.asyncio
async def test_openai_compatible_adapter_structured_output_json_schema() -> None:
    """Verify native json_schema response_format and JSON validation."""
    expected_data = {"verdict": "pass", "score": 98}
    mock_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps(expected_data),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 30, "completion_tokens": 15},
    }

    client, requests = _make_mock_client(json_data=mock_response)
    adapter = OpenAICompatibleAdapter(api_key="test-key", client=client)

    schema = {
        "type": "object",
        "properties": {
            "verdict": {"type": "string"},
            "score": {"type": "integer"},
        },
        "required": ["verdict", "score"],
    }

    req = LLMGenerationRequest(
        task="evaluation",
        messages=[ChatMessage.user("Evaluate test run")],
        options=LLMGenerationOptions(
            structured_output=StructuredOutputSpec(
                schema_name="EvalVerdict",
                schema_def=schema,
                mode="native",
                strict=True,
            )
        ),
    )

    resp = await adapter.generate(req)
    assert resp.content is not None
    data = json.loads(resp.content)
    assert data["verdict"] == "pass"
    assert data["score"] == 98

    # Verify response_format in request payload
    payload = json.loads(requests[0].content.decode("utf-8"))
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["name"] == "EvalVerdict"
    assert payload["response_format"]["json_schema"]["strict"] is True


@pytest.mark.asyncio
async def test_openai_compatible_adapter_tool_calling() -> None:
    """Verify tool definition translation and ToolCall extraction."""
    mock_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_abc123",
                            "type": "function",
                            "function": {
                                "name": "get_file_tree",
                                "arguments": '{"path": "server/app"}',
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ]
    }

    client, requests = _make_mock_client(json_data=mock_response)
    adapter = OpenAICompatibleAdapter(api_key="test-key", client=client)

    tool = ToolDefinition.from_params(
        name="get_file_tree",
        description="List files in directory",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    )

    req = LLMGenerationRequest(
        task="file_tree",
        messages=[ChatMessage.user("Show files")],
        options=LLMGenerationOptions(tools=[tool], tool_choice="auto"),
    )

    resp = await adapter.generate(req)

    assert resp.finish_reason == "tool_calls"
    assert len(resp.tool_calls) == 1
    tc = resp.tool_calls[0]
    assert tc.id == "call_abc123"
    assert tc.function.name == "get_file_tree"
    assert json.loads(tc.function.arguments)["path"] == "server/app"

    # Verify tools in request payload
    payload = json.loads(requests[0].content.decode("utf-8"))
    assert payload["tools"][0]["function"]["name"] == "get_file_tree"
    assert payload["tool_choice"] == "auto"


@pytest.mark.asyncio
async def test_openai_compatible_adapter_streaming_sse() -> None:
    """Verify SSE streaming delta chunks and final usage."""
    sse_body = (
        'data: {"choices": [{"delta": {"content": "Chunk 1 "}}]}\n\n'
        'data: {"choices": [{"delta": {"content": "Chunk 2"}}]}\n\n'
        'data: {"choices": [{"finish_reason": "stop"}], "usage": {"prompt_tokens": 12, "completion_tokens": 6}}\n\n'
        "data: [DONE]\n\n"
    )

    client, _ = _make_mock_client(
        text_content=sse_body,
        headers={"Content-Type": "text/event-stream"},
    )
    adapter = OpenAICompatibleAdapter(api_key="test-key", client=client)

    req = LLMGenerationRequest(
        task="stream_test",
        messages=[ChatMessage.user("Stream hello")],
    )

    chunks = []
    async for chunk in adapter.stream_generate(req):
        chunks.append(chunk)

    assert len(chunks) == 3
    assert chunks[0].delta_content == "Chunk 1 "
    assert chunks[1].delta_content == "Chunk 2"
    assert chunks[2].finish_reason == "stop"
    assert chunks[2].usage is not None
    assert chunks[2].usage.input_tokens == 12
    assert chunks[2].usage.output_tokens == 6


@pytest.mark.asyncio
async def test_openai_compatible_adapter_content_filter_raises_refusal() -> None:
    """Verify finish_reason content_filter maps to LLMRefusalError."""
    mock_response = {
        "choices": [
            {
                "message": {"role": "assistant", "content": None},
                "finish_reason": "content_filter",
            }
        ]
    }

    client, _ = _make_mock_client(json_data=mock_response)
    adapter = OpenAICompatibleAdapter(api_key="test-key", client=client)

    req = LLMGenerationRequest(task="unsafe", messages=[ChatMessage.user("unsafe prompt")])

    with pytest.raises(LLMRefusalError) as exc_info:
        await adapter.generate(req)
    assert exc_info.value.code == "llm.refusal"


@pytest.mark.asyncio
async def test_openai_compatible_adapter_rate_limit_mapping() -> None:
    """Verify HTTP 429 maps to LLMRateLimitError with retry-after."""
    mock_err = {"error": {"message": "Rate limit exceeded (30 RPM)", "type": "rate_limit_error"}}

    client, _ = _make_mock_client(
        status_code=429,
        json_data=mock_err,
        headers={"retry-after": "6"},
    )
    adapter = OpenAICompatibleAdapter(api_key="test-key", client=client)

    req = LLMGenerationRequest(task="test", messages=[ChatMessage.user("prompt")])

    with pytest.raises(LLMRateLimitError) as exc_info:
        await adapter.generate(req)
    assert exc_info.value.code == "llm.rate_limit"
    assert exc_info.value.retry_after_s == 6.0


@pytest.mark.asyncio
async def test_openai_compatible_adapter_timeout_mapping() -> None:
    """Verify httpx.TimeoutException maps to LLMTimeoutError."""
    client, _ = _make_mock_client(exception=httpx.ReadTimeout("Timeout"))
    adapter = OpenAICompatibleAdapter(api_key="test-key", client=client, timeout_seconds=8.0)

    req = LLMGenerationRequest(task="test", messages=[ChatMessage.user("prompt")])

    with pytest.raises(LLMTimeoutError) as exc_info:
        await adapter.generate(req)
    assert exc_info.value.code == "llm.timeout"
    assert exc_info.value.timeout_s == 8.0


def test_openai_compatible_adapter_registry_lookup() -> None:
    """Verify adapter discovery in registry for openai_compatible, openai, and groq."""
    adapters = list_supported_adapters()
    assert "openai_compatible" in adapters
    assert "openai" in adapters
    assert "groq" in adapters

    cls = get_adapter_class("openai_compatible")
    assert cls is OpenAICompatibleAdapter

    instance = create_adapter("groq", api_key="groq-key", model_id="llama-3.3-70b-versatile")
    assert isinstance(instance, OpenAICompatibleAdapter)
    assert instance.model_id == "llama-3.3-70b-versatile"
