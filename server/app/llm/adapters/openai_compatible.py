"""OpenAI-compatible LLM provider adapter (Groq, OpenAI, Together, Mistral, Ollama) (docs/05 §11.1, §12, docs/11 M6-05).

Implements the standard /chat/completions REST protocol using async httpx.
Disabled by default until API keys are configured (ADR-027, ADR-046).
Supports structured JSON outputs, function/tool calling, SSE token streaming,
and RFC 9457 typed error responses.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.llm.adapter import LLMAdapter
from app.llm.exceptions import (
    LLMError,
    LLMInvalidOutputError,
    LLMProviderError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMTimeoutError,
)
from app.llm.models import (
    FinishReason,
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

logger = logging.getLogger(__name__)

DEFAULT_OPENAI_COMPATIBLE_MODEL = "llama-3.3-70b-versatile"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


class OpenAICompatibleAdapter(LLMAdapter):
    """Adapter for OpenAI-compatible Chat Completions endpoints (docs/05 §11.1, §12).

    Compatible with Groq (free tier: 30 RPM), OpenAI, Together, Mistral, or local Ollama.
    Disabled by default until an API key or custom endpoint is configured.
    """

    def __init__(
        self,
        model_id: str = DEFAULT_OPENAI_COMPATIBLE_MODEL,
        api_key: str | None = None,
        base_url: str = DEFAULT_OPENAI_BASE_URL,
        provider_id: str = "openai_compatible",
        timeout_seconds: float = 60.0,
        client: httpx.AsyncClient | None = None,
        data_policy: ProviderDataPolicy | None = None,
    ) -> None:
        self._model_id = model_id
        self._provider_id = provider_id
        self._api_key = (
            api_key
            or os.getenv("DEVMIND_LLM_ALT_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("GROQ_API_KEY")
            or ""
        )
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._custom_client = client

        self._data_policy = data_policy or ProviderDataPolicy(
            source_code_allowed=False,
            terms_reviewed=False,
            note="Alternative provider: terms unreviewed; disabled by default until configured",
        )

        self._capabilities = ModelCapabilities(
            tool_calling=True,
            structured_output="native",
            streaming=True,
            supports_system_prompt=True,
        )

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

    def _get_api_key(self) -> str:
        """Resolve API key or raise authentication error."""
        key = self._api_key.strip()
        if not key:
            raise LLMError(
                f"Provider '{self.provider_id}' API key is not configured. Set DEVMIND_LLM_ALT_API_KEY or provider-specific key.",
                code="llm.authentication_error",
            )
        return key

    def _build_request_payload(
        self, request: LLMGenerationRequest, stream: bool = False
    ) -> dict[str, Any]:
        """Convert standard LLMGenerationRequest into OpenAI chat completion payload."""
        payload: dict[str, Any] = {
            "model": self._model_id,
            "stream": stream,
        }

        # 1. Messages translation
        messages: list[dict[str, Any]] = []
        for msg in request.messages:
            msg_dict: dict[str, Any] = {"role": msg.role}
            if msg.content is not None:
                msg_dict["content"] = msg.content
            if msg.name:
                msg_dict["name"] = msg.name

            if msg.role == "assistant" and msg.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]

            if msg.role == "tool" and msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id

            messages.append(msg_dict)

        payload["messages"] = messages

        # 2. Options
        opts = request.options
        if opts.temperature is not None:
            payload["temperature"] = opts.temperature
        if opts.max_output_tokens is not None:
            payload["max_tokens"] = opts.max_output_tokens
        if opts.top_p is not None:
            payload["top_p"] = opts.top_p
        if opts.stop_sequences:
            payload["stop"] = opts.stop_sequences

        # 3. Structured outputs
        if opts.structured_output:
            spec = opts.structured_output
            if spec.mode == "native":
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": spec.schema_name,
                        "strict": spec.strict,
                        "schema": spec.schema_def,
                    },
                }
            else:
                payload["response_format"] = {"type": "json_object"}

        # 4. Tools (Function Calling)
        if opts.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.function.name,
                        "description": t.function.description or "",
                        "parameters": t.function.parameters,
                    },
                }
                for t in opts.tools
            ]

            if opts.tool_choice:
                payload["tool_choice"] = opts.tool_choice

        if stream:
            payload["stream_options"] = {"include_usage": True}

        return payload

    def _parse_message(
        self, choice: dict[str, Any]
    ) -> tuple[str | None, list[ToolCall], FinishReason]:
        """Parse message, tool calls, and finish reason from completion choice."""
        msg = choice.get("message", {})
        content = msg.get("content")
        raw_tool_calls = msg.get("tool_calls", [])

        tool_calls: list[ToolCall] = []
        for tc in raw_tool_calls:
            fn = tc.get("function", {})
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    type=tc.get("type", "function"),
                    function=FunctionCall(
                        name=fn.get("name", ""),
                        arguments=fn.get("arguments", ""),
                    ),
                )
            )

        raw_finish = choice.get("finish_reason") or "stop"
        if raw_finish == "tool_calls" or (tool_calls and raw_finish == "stop"):
            finish_reason: FinishReason = "tool_calls"
        elif raw_finish == "length":
            finish_reason = "length"
        elif raw_finish == "content_filter":
            raise LLMRefusalError(
                message="OpenAI compatible provider filtered content due to safety policy",
                reason="content_filter",
            )
        else:
            finish_reason = "stop"

        return content, tool_calls, finish_reason

    def _parse_usage(self, data: dict[str, Any]) -> TokenUsage:
        """Parse token usage statistics."""
        usage_data = data.get("usage", {})
        prompt_tokens = usage_data.get("prompt_tokens", 0)
        completion_tokens = usage_data.get("completion_tokens", 0)
        total_tokens = usage_data.get("total_tokens", prompt_tokens + completion_tokens)

        return TokenUsage(
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    def _handle_error_response(self, response: httpx.Response) -> None:
        """Map HTTP error responses to RFC 9457 exception hierarchy."""
        status_code = response.status_code
        try:
            err_data = response.json()
            err_info = err_data.get("error", {})
            err_message = err_info.get("message", response.text)
            err_type = err_info.get("type", "")
        except Exception:
            err_message = response.text
            err_type = ""

        # Rate limits (HTTP 429)
        if status_code == 429:
            retry_header = response.headers.get("retry-after")
            retry_after_s: float | None = float(retry_header) if retry_header and retry_header.isdigit() else 2.0
            raise LLMRateLimitError(
                message=f"LLM provider rate limit exceeded: {err_message}",
                retry_after_s=retry_after_s,
            )

        # Authentication / permissions
        if status_code in (401, 403):
            raise LLMError(
                message=f"LLM provider authentication failed ({status_code}): {err_message}",
                code="llm.authentication_error",
                details={"status_code": status_code, "error_type": err_type},
            )

        # Invalid requests
        if status_code == 400:
            raise LLMInvalidOutputError(
                message=f"LLM provider rejected request ({status_code}): {err_message}",
                raw_output=err_message,
            )

        # Provider 5xx
        if status_code >= 500:
            raise LLMProviderError(
                message=f"LLM provider upstream error ({status_code}): {err_message}",
                status_code=status_code,
                raw_error=err_message,
            )

        raise LLMError(
            message=f"LLM provider returned error ({status_code}): {err_message}",
            code="llm.provider_error",
            details={"status_code": status_code, "error_type": err_type},
        )

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        """Execute non-streaming completion."""
        self.validate_request_capabilities(request)
        api_key = self._get_api_key()
        payload = self._build_request_payload(request, stream=False)

        endpoint = f"{self._base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        start_time = time.perf_counter()

        try:
            if self._custom_client:
                response = await self._custom_client.post(
                    endpoint, json=payload, headers=headers, timeout=self._timeout_seconds
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.post(endpoint, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                f"Provider request timed out after {self._timeout_seconds}s",
                timeout_s=self._timeout_seconds,
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(
                f"Provider network connection error: {exc}",
                raw_error=str(exc),
            ) from exc

        if not response.is_success:
            self._handle_error_response(response)

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        data = response.json()

        choices = data.get("choices", [])
        if not choices:
            return LLMGenerationResponse(
                content=None,
                tool_calls=[],
                finish_reason="other",
                usage=self._parse_usage(data),
                provider_id=self.provider_id,
                model_id=self.model_id,
                raw_response=data,
                latency_ms=latency_ms,
            )

        content, tool_calls, finish_reason = self._parse_message(choices[0])
        usage = self._parse_usage(data)

        # Validate structured output if requested
        if request.options.structured_output and content:
            try:
                json.loads(content)
            except json.JSONDecodeError as exc:
                raise LLMInvalidOutputError(
                    message="Structured output response is not valid JSON",
                    raw_output=content,
                    validation_errors=[str(exc)],
                ) from exc

        return LLMGenerationResponse(
            content=content,
            role="assistant",
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
            provider_id=self.provider_id,
            model_id=self.model_id,
            raw_response=data,
            latency_ms=latency_ms,
        )

    async def stream_generate(
        self, request: LLMGenerationRequest
    ) -> AsyncIterator[LLMStreamChunk]:
        """Execute streaming completion yielding incremental stream chunks."""
        self.validate_request_capabilities(request)
        api_key = self._get_api_key()
        payload = self._build_request_payload(request, stream=True)

        endpoint = f"{self._base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        try:
            if self._custom_client:
                async with self._custom_client.stream(
                    "POST", endpoint, json=payload, headers=headers, timeout=self._timeout_seconds
                ) as stream_resp:
                    if not stream_resp.is_success:
                        await stream_resp.aread()
                        self._handle_error_response(stream_resp)

                    async for chunk in self._process_sse_stream(stream_resp):
                        yield chunk
            else:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    async with client.stream(
                        "POST", endpoint, json=payload, headers=headers
                    ) as stream_resp:
                        if not stream_resp.is_success:
                            await stream_resp.aread()
                            self._handle_error_response(stream_resp)

                        async for chunk in self._process_sse_stream(stream_resp):
                            yield chunk
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                f"Provider streaming timed out after {self._timeout_seconds}s",
                timeout_s=self._timeout_seconds,
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(
                f"Provider stream network connection error: {exc}",
                raw_error=str(exc),
            ) from exc

    async def _process_sse_stream(
        self, response: httpx.Response
    ) -> AsyncIterator[LLMStreamChunk]:
        """Process SSE event stream from /chat/completions."""
        async for line in response.aiter_lines():
            line = line.strip()
            if not line or not line.startswith("data:"):
                continue

            raw_json = line[len("data:") :].strip()
            if not raw_json or raw_json == "[DONE]":
                break

            try:
                data = json.loads(raw_json)
            except json.JSONDecodeError:
                continue

            usage = self._parse_usage(data) if "usage" in data and data["usage"] else None
            choices = data.get("choices", [])
            if not choices:
                if usage:
                    yield LLMStreamChunk(delta_content="", finish_reason="stop", usage=usage)
                continue

            choice = choices[0]
            delta = choice.get("delta", {})
            delta_text = delta.get("content", "")
            raw_tool_calls = delta.get("tool_calls", [])

            tool_calls: list[ToolCall] = []
            for tc in raw_tool_calls:
                fn = tc.get("function", {})
                tool_calls.append(
                    ToolCall(
                        id=tc.get("id", ""),
                        type=tc.get("type", "function"),
                        function=FunctionCall(
                            name=fn.get("name", ""),
                            arguments=fn.get("arguments", ""),
                        ),
                    )
                )

            finish_reason = choice.get("finish_reason")

            yield LLMStreamChunk(
                delta_content=delta_text or "",
                delta_tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage=usage,
            )


# Self-register adapter in registry
register_adapter("openai_compatible", OpenAICompatibleAdapter)
register_adapter("openai", OpenAICompatibleAdapter)
register_adapter("groq", OpenAICompatibleAdapter)
