"""Deterministic fake LLM provider adapter with scripted responses and fault injection (docs/05 §11.1, §12, §15, M6-02)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field

from app.llm.adapter import LLMAdapter
from app.llm.exceptions import (
    LLMProviderError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMTimeoutError,
)
from app.llm.models import (
    FunctionCall,
    LLMGenerationRequest,
    LLMGenerationResponse,
    LLMStreamChunk,
    ModelCapabilities,
    ProviderDataPolicy,
    TokenUsage,
    ToolCall,
)
from app.llm.registry import register_adapter


class FakeFaultInjection(BaseModel):
    """Fault injection configuration for testing gateway resilience (docs/05 §15)."""

    timeout: bool = Field(default=False, description="Simulate an upstream timeout exception")
    rate_limit: bool = Field(default=False, description="Simulate HTTP 429 rate limit error")
    rate_limit_retry_after: float = Field(
        default=2.0, description="Retry-After header value in seconds"
    )
    provider_5xx: bool = Field(
        default=False, description="Simulate upstream provider 500/502/503 error"
    )
    provider_status_code: int = Field(
        default=500, description="Status code to include in provider error"
    )
    refusal: bool = Field(default=False, description="Simulate content/policy refusal")
    refusal_reason: str = Field(default="Safety policy refusal", description="Refusal explanation")
    malformed_output: bool = Field(
        default=False, description="Return malformed/unparseable JSON string"
    )
    partial_stream: bool = Field(
        default=False, description="Abort stream mid-generation with exception"
    )


class FakeLLMAdapter(LLMAdapter):
    """Deterministic, zero-cost LLM adapter for unit tests, CI, and local evaluation (docs/05 §11.1, §15)."""

    def __init__(
        self,
        model_id: str = "fake-deterministic",
        capabilities: ModelCapabilities | None = None,
        data_policy: ProviderDataPolicy | None = None,
        scripted_responses: list[str] | dict[str, str] | None = None,
        faults: FakeFaultInjection | None = None,
        latency_ms: float = 2.0,
    ) -> None:
        self._provider_id = "fake"
        self._model_id = model_id
        self._capabilities = capabilities or ModelCapabilities(
            tool_calling=True,
            structured_output="native",
            streaming=True,
            supports_system_prompt=True,
        )
        self._data_policy = data_policy or ProviderDataPolicy(
            source_code_allowed=True,
            terms_reviewed=True,
            note="Zero-cost in-memory test provider; no external network transmission",
        )
        self.scripted_queue: list[str] = (
            list(scripted_responses) if isinstance(scripted_responses, list) else []
        )
        self.scripted_tasks: dict[str, str] = (
            dict(scripted_responses) if isinstance(scripted_responses, dict) else {}
        )
        self.faults = faults or FakeFaultInjection()
        self.latency_ms = latency_ms
        self.call_count: int = 0
        self.history: list[LLMGenerationRequest] = []

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

    def _check_faults(self) -> None:
        """Evaluate active fault injection flags before processing inference."""
        if self.faults.timeout:
            raise LLMTimeoutError("Simulated upstream provider request timeout", timeout_s=30.0)
        if self.faults.rate_limit:
            raise LLMRateLimitError(
                "Simulated upstream rate limit exceeded (HTTP 429)",
                retry_after_s=self.faults.rate_limit_retry_after,
            )
        if self.faults.provider_5xx:
            raise LLMProviderError(
                f"Simulated upstream provider error (HTTP {self.faults.provider_status_code})",
                status_code=self.faults.provider_status_code,
            )
        if self.faults.refusal:
            raise LLMRefusalError(
                f"Simulated provider refusal: {self.faults.refusal_reason}",
                reason=self.faults.refusal_reason,
            )

    def _synthesize_structured_json(self, schema_name: str, schema_def: dict[str, Any]) -> str:
        """Synthesize a deterministic JSON payload conforming to the requested schema name or definition."""
        properties = schema_def.get("properties", {})
        result: dict[str, Any] = {}

        if properties:
            for prop_name, prop_spec in properties.items():
                prop_type = prop_spec.get("type", "string")
                if prop_type == "string":
                    result[prop_name] = f"fake_{prop_name}_value"
                elif prop_type == "integer":
                    result[prop_name] = 1
                elif prop_type == "number":
                    result[prop_name] = 1.0
                elif prop_type == "boolean":
                    result[prop_name] = True
                elif prop_type == "array":
                    result[prop_name] = ["item_1"]
                elif prop_type == "object":
                    result[prop_name] = {}
                else:
                    result[prop_name] = None
        else:
            result = {
                "schema": schema_name,
                "status": "completed",
                "summary": "Deterministic structured payload",
            }

        return json.dumps(result)

    def _resolve_response_content(
        self, request: LLMGenerationRequest
    ) -> tuple[str | None, list[ToolCall]]:
        """Determine content or tool calls to emit for the given request."""
        # Check malformed output fault
        if self.faults.malformed_output:
            return '{"status": "broken", "incomplete_json"', []

        # Check scripted response queue (FIFO)
        if self.scripted_queue:
            return self.scripted_queue.pop(0), []

        # Check scripted tasks map
        if request.task in self.scripted_tasks:
            return self.scripted_tasks[request.task], []

        # Tool calling simulation: if tools provided and not explicitly suppressed
        if request.options.tools and request.options.tool_choice != "none":
            first_tool = request.options.tools[0]
            call = ToolCall(
                id=f"call_fake_{self.call_count:04d}",
                function=FunctionCall(
                    name=first_tool.function.name,
                    arguments=json.dumps({"query": "fake_search_term"}),
                ),
            )
            return None, [call]

        # Structured output simulation
        if request.options.structured_output:
            spec = request.options.structured_output
            payload = self._synthesize_structured_json(spec.schema_name, spec.schema_def)
            return payload, []

        # Standard deterministic text completion based on prompt hash
        prompt_text = "".join(m.content or "" for m in request.messages)
        content_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:12]
        return f"Deterministic response for task '{request.task}' [hash:{content_hash}]", []

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        """Execute deterministic simulated generation."""
        self.call_count += 1
        self.history.append(request)

        # Validate request constraints and fault injection
        self.validate_request_capabilities(request)
        self._check_faults()

        content, tool_calls = self._resolve_response_content(request)

        # Approximate token usage
        prompt_len = sum(len(m.content or "") for m in request.messages)
        output_len = len(content or "") if content else 50
        input_tokens = max(1, prompt_len // 4)
        output_tokens = max(1, output_len // 4)
        usage = TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens)

        finish_reason = "tool_calls" if tool_calls else "stop"

        return LLMGenerationResponse(
            content=content,
            role="assistant",
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
            provider_id=self.provider_id,
            model_id=self.model_id,
            latency_ms=self.latency_ms,
        )

    async def stream_generate(self, request: LLMGenerationRequest) -> AsyncIterator[LLMStreamChunk]:
        """Execute deterministic simulated streaming."""
        self.call_count += 1
        self.history.append(request)

        self.validate_request_capabilities(request)
        self._check_faults()

        content, tool_calls = self._resolve_response_content(request)

        # If tool calls emitted, yield in single chunk
        if tool_calls:
            yield LLMStreamChunk(delta_tool_calls=tool_calls, finish_reason="tool_calls")
            return

        text = content or ""
        tokens = text.split(" ")
        for i, token in enumerate(tokens):
            if self.faults.partial_stream and i >= 2:
                raise LLMProviderError(
                    "Simulated stream connection abort mid-transfer", status_code=500
                )

            suffix = " " if i < len(tokens) - 1 else ""
            yield LLMStreamChunk(delta_content=token + suffix)

        # Final chunk with usage statistics
        output_tokens = max(1, len(text) // 4)
        yield LLMStreamChunk(
            finish_reason="stop",
            usage=TokenUsage(
                input_tokens=max(1, len(request.task) * 2), output_tokens=output_tokens
            ),
        )


# Register fake adapter in the provider registry
register_adapter("fake", FakeLLMAdapter)
