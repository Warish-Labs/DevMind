"""Tests verifying LLM provider adapter interfaces, capabilities, common models, and exceptions (docs/05 §11-§12, M6-01)."""

from collections.abc import AsyncIterator

import pytest
from pydantic import ValidationError

from app.llm.adapter import LLMAdapter
from app.llm.exceptions import (
    LLMContextLengthExceededError,
    LLMError,
    LLMInvalidOutputError,
    LLMPermissionError,
    LLMProviderError,
    LLMQuotaExceededError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.llm.models import (
    ChatMessage,
    FunctionCall,
    LLMGenerationOptions,
    LLMGenerationRequest,
    LLMGenerationResponse,
    LLMStreamChunk,
    ModelCapabilities,
    ProviderDataPolicy,
    StructuredOutputSpec,
    TokenUsage,
    ToolCall,
    ToolDefinition,
)
from app.llm.registry import (
    create_adapter,
    get_adapter_class,
    list_supported_adapters,
    register_adapter,
)


class DummyMockAdapter(LLMAdapter):
    """Concrete mock adapter for interface and capability testing."""

    def __init__(
        self,
        provider_id: str = "mock-provider",
        model_id: str = "mock-model-v1",
        capabilities: ModelCapabilities | None = None,
        data_policy: ProviderDataPolicy | None = None,
    ) -> None:
        self._provider_id = provider_id
        self._model_id = model_id
        self._capabilities = capabilities or ModelCapabilities()
        self._data_policy = data_policy or ProviderDataPolicy()

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def capabilities(self) -> ModelCapabilities:
        return self._capabilities

    @property
    def data_policy(self) -> ProviderDataPolicy:
        return self._data_policy

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        self.validate_request_capabilities(request)
        return LLMGenerationResponse(
            content="Mock response",
            provider_id=self.provider_id,
            model_id=self.model_id,
            usage=TokenUsage(input_tokens=10, output_tokens=5),
        )

    async def stream_generate(self, request: LLMGenerationRequest) -> AsyncIterator[LLMStreamChunk]:
        self.validate_request_capabilities(request)
        yield LLMStreamChunk(delta_content="Mock ")
        yield LLMStreamChunk(delta_content="response", finish_reason="stop")


def test_chat_message_factories_and_structure() -> None:
    """Verify ChatMessage factories and role mappings."""
    sys_msg = ChatMessage.system("You are a helpful assistant")
    assert sys_msg.role == "system"
    assert sys_msg.content == "You are a helpful assistant"

    user_msg = ChatMessage.user("Analyze this function")
    assert user_msg.role == "user"
    assert user_msg.content == "Analyze this function"

    tool_call = ToolCall(
        id="call_01",
        function=FunctionCall(name="search_symbols", arguments='{"query": "User"}'),
    )
    asst_msg = ChatMessage.assistant(content=None, tool_calls=[tool_call])
    assert asst_msg.role == "assistant"
    assert asst_msg.tool_calls is not None
    assert len(asst_msg.tool_calls) == 1
    assert asst_msg.tool_calls[0].function.name == "search_symbols"

    tool_res = ChatMessage.tool(
        tool_call_id="call_01", content='{"found": 1}', name="search_symbols"
    )
    assert tool_res.role == "tool"
    assert tool_res.tool_call_id == "call_01"
    assert tool_res.content == '{"found": 1}'
    assert tool_res.name == "search_symbols"


def test_token_usage_calculation() -> None:
    """Verify TokenUsage calculates total_tokens if omitted."""
    usage1 = TokenUsage(input_tokens=150, output_tokens=50)
    assert usage1.total_tokens == 200

    usage2 = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=175)
    assert usage2.total_tokens == 175


def test_tool_definition_factory() -> None:
    """Verify ToolDefinition factory helper."""
    tool = ToolDefinition.from_params(
        name="get_file_tree",
        description="List files in directory",
        parameters={"type": "object", "properties": {"dir": {"type": "string"}}},
    )
    assert tool.type == "function"
    assert tool.function.name == "get_file_tree"
    assert tool.function.description == "List files in directory"
    assert "dir" in tool.function.parameters.get("properties", {})


def test_generation_options_validation() -> None:
    """Verify temperature and token constraints in LLMGenerationOptions."""
    opts = LLMGenerationOptions(temperature=0.7, max_output_tokens=1000)
    assert opts.temperature == 0.7
    assert opts.max_output_tokens == 1000

    with pytest.raises(ValidationError):
        LLMGenerationOptions(temperature=2.5)  # > 2.0 invalid

    with pytest.raises(ValidationError):
        LLMGenerationOptions(temperature=-0.1)  # < 0.0 invalid

    with pytest.raises(ValidationError):
        LLMGenerationOptions(max_output_tokens=0)  # must be gt 0


def test_structured_output_spec() -> None:
    """Verify StructuredOutputSpec defaults and modes."""
    spec = StructuredOutputSpec(
        schema_name="FindingExplanation",
        schema_def={"type": "object", "properties": {"summary": {"type": "string"}}},
    )
    assert spec.schema_name == "FindingExplanation"
    assert spec.mode == "native"
    assert spec.strict is True


def test_adapter_capability_validation_tool_calling() -> None:
    """Verify adapter rejects tool calling when capability flag is false."""
    adapter = DummyMockAdapter(
        capabilities=ModelCapabilities(tool_calling=False),
    )
    tool = ToolDefinition.from_params(name="test_tool")
    req = LLMGenerationRequest(
        task="code_answer",
        messages=[ChatMessage.user("Hello")],
        options=LLMGenerationOptions(tools=[tool]),
    )

    with pytest.raises(LLMError) as exc_info:
        adapter.validate_request_capabilities(req)
    assert "does not support tool calling" in str(exc_info.value)
    assert exc_info.value.code == "llm.unsupported_capability"


def test_adapter_capability_validation_structured_output() -> None:
    """Verify adapter rejects structured output when unsupported."""
    adapter_none = DummyMockAdapter(
        capabilities=ModelCapabilities(structured_output="none"),
    )
    spec = StructuredOutputSpec(schema_name="TestSchema", schema_def={})
    req = LLMGenerationRequest(
        task="security_explanation",
        messages=[ChatMessage.user("Explain finding")],
        options=LLMGenerationOptions(structured_output=spec),
    )

    with pytest.raises(LLMInvalidOutputError) as exc_info:
        adapter_none.validate_request_capabilities(req)
    assert "does not support structured output" in str(exc_info.value)

    # Test native mode mismatch when adapter only supports prompt_only
    adapter_prompt_only = DummyMockAdapter(
        capabilities=ModelCapabilities(structured_output="prompt_only"),
    )
    with pytest.raises(LLMInvalidOutputError) as exc_info:
        adapter_prompt_only.validate_request_capabilities(req)
    assert "does not support native schema mode" in str(exc_info.value)


def test_adapter_data_policy_validation() -> None:
    """Verify data policy guard enforces source_code_allowed (docs/05 §11.4)."""
    # 1. Blocked by default
    adapter_unauthorized = DummyMockAdapter(
        data_policy=ProviderDataPolicy(source_code_allowed=False, terms_reviewed=False),
    )
    with pytest.raises(LLMPermissionError) as exc_info:
        adapter_unauthorized.validate_data_policy(may_contain_source=True)
    assert "does not permit source code transmission" in str(exc_info.value)

    # Allowed when source is false
    adapter_unauthorized.validate_data_policy(may_contain_source=False)

    # 2. Permitted when terms reviewed and source code allowed
    adapter_authorized = DummyMockAdapter(
        data_policy=ProviderDataPolicy(source_code_allowed=True, terms_reviewed=True),
    )
    adapter_authorized.validate_data_policy(may_contain_source=True)


@pytest.mark.asyncio
async def test_adapter_generate_and_stream() -> None:
    """Verify generate and stream_generate execution on concrete adapter."""
    adapter = DummyMockAdapter()
    req = LLMGenerationRequest(
        task="code_answer",
        messages=[ChatMessage.user("Test")],
    )

    # Test generate
    resp = await adapter.generate(req)
    assert resp.content == "Mock response"
    assert resp.provider_id == "mock-provider"
    assert resp.model_id == "mock-model-v1"
    assert resp.usage.total_tokens == 15

    # Test stream_generate
    chunks: list[LLMStreamChunk] = []
    async for chunk in adapter.stream_generate(req):
        chunks.append(chunk)

    assert len(chunks) == 2
    full_text = "".join(c.delta_content for c in chunks)
    assert full_text == "Mock response"
    assert chunks[1].finish_reason == "stop"


def test_llm_exception_hierarchy() -> None:
    """Verify all LLM exceptions inherit from LLMError and contain expected codes."""
    exceptions = [
        (LLMTimeoutError(timeout_s=30.0), "llm.timeout"),
        (LLMRateLimitError(retry_after_s=5.0), "llm.rate_limit"),
        (LLMProviderError("Upstream failure", status_code=502), "llm.provider_error"),
        (LLMInvalidOutputError("Invalid JSON", raw_output="{bad}"), "llm.invalid_output"),
        (LLMUnavailableError(), "llm.unavailable"),
        (LLMRefusalError(reason="safety"), "llm.refusal"),
        (LLMQuotaExceededError(quota_type="monthly_tokens"), "quota.exceeded"),
        (LLMPermissionError(), "llm.permission_denied"),
        (
            LLMContextLengthExceededError(input_tokens=12000, max_tokens=8000),
            "llm.context_length_exceeded",
        ),
    ]

    for exc, expected_code in exceptions:
        assert isinstance(exc, LLMError)
        assert exc.code == expected_code
        assert f"[{expected_code}]" in str(exc)


def test_adapter_registry() -> None:
    """Verify register_adapter, get_adapter_class, list_supported_adapters, create_adapter."""
    register_adapter("dummy_mock", DummyMockAdapter)

    assert "dummy_mock" in list_supported_adapters()
    retrieved_cls = get_adapter_class("dummy_mock")
    assert retrieved_cls is DummyMockAdapter

    instance = create_adapter("dummy_mock", provider_id="instantiated-mock")
    assert isinstance(instance, DummyMockAdapter)
    assert instance.provider_id == "instantiated-mock"

    with pytest.raises(LLMError) as exc_info:
        get_adapter_class("non_existent_provider_xyz")
    assert exc_info.value.code == "llm.unregistered_adapter"
