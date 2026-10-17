"""Google Gemini LLM provider adapter using official Gemini REST/SDK protocol (docs/05 §11.1, §12, docs/11 M6-04).

Supports Google AI Studio free-tier and standard keys (GEMINI_API_KEY / DEVMIND_LLM_PRIMARY_API_KEY)
with native structured outputs, function calling, Server-Sent Events (SSE) streaming,
and comprehensive RFC 9457 error mapping.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
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

DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"


class GoogleGeminiAdapter(LLMAdapter):
    """Production LLM adapter for Google Gemini models (docs/05 §11.1, §12).

    Connects to Google's Generative Language API using official v1beta contracts.
    Free tier compatible (15 RPM / 1M TPM / 1500 RPD) with rate limit recovery hints.
    """

    def __init__(
        self,
        model_id: str = DEFAULT_GEMINI_MODEL,
        api_key: str | None = None,
        base_url: str = DEFAULT_GEMINI_BASE_URL,
        timeout_seconds: float = 60.0,
        client: httpx.AsyncClient | None = None,
        data_policy: ProviderDataPolicy | None = None,
    ) -> None:
        self._model_id = model_id
        self._api_key = (
            api_key or os.getenv("GEMINI_API_KEY") or os.getenv("DEVMIND_LLM_PRIMARY_API_KEY") or ""
        )
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._custom_client = client

        # Data policy: Free tier content may be used for Google product improvement (docs/SETUP-GUIDE.md §294)
        self._data_policy = data_policy or ProviderDataPolicy(
            source_code_allowed=False,
            terms_reviewed=False,
            note="Google AI Studio free tier: prompt/response content may be used for product improvement per terms; public/synthetic only",
        )

        self._capabilities = ModelCapabilities(
            tool_calling=True,
            structured_output="native",
            streaming=True,
            supports_system_prompt=True,
        )

    @property
    def provider_id(self) -> str:
        return "google"

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
                "Gemini API key is not configured. Set GEMINI_API_KEY or DEVMIND_LLM_PRIMARY_API_KEY.",
                code="llm.authentication_error",
            )
        return key

    def _build_request_payload(self, request: LLMGenerationRequest) -> dict[str, Any]:
        """Convert standard LLMGenerationRequest into Google Gemini API payload."""
        payload: dict[str, Any] = {}

        # 1. System instructions
        system_contents: list[str] = [
            m.content for m in request.messages if m.role == "system" and m.content
        ]
        if system_contents:
            payload["systemInstruction"] = {
                "parts": [{"text": "\n\n".join(system_contents)}],
            }

        # 2. Conversation messages (user and assistant/model)
        contents: list[dict[str, Any]] = []
        for msg in request.messages:
            if msg.role == "system":
                continue

            parts: list[dict[str, Any]] = []
            if msg.content:
                parts.append({"text": msg.content})

            # Assistant tool calls
            if msg.role == "assistant" and msg.tool_calls:
                for tc in msg.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    except json.JSONDecodeError:
                        args = {"raw_arguments": tc.function.arguments}
                    parts.append(
                        {
                            "functionCall": {
                                "name": tc.function.name,
                                "args": args,
                            }
                        }
                    )

            # Tool response
            if msg.role == "tool":
                tool_name = msg.name or "function"
                try:
                    tool_resp = json.loads(msg.content or "{}")
                except json.JSONDecodeError:
                    tool_resp = {"output": msg.content}
                parts.append(
                    {
                        "functionResponse": {
                            "name": tool_name,
                            "response": tool_resp,
                        }
                    }
                )

            gemini_role = "model" if msg.role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": parts})

        payload["contents"] = contents

        # 3. Generation configuration
        generation_config: dict[str, Any] = {}
        opts = request.options

        if opts.temperature is not None:
            generation_config["temperature"] = opts.temperature
        if opts.max_output_tokens is not None:
            generation_config["maxOutputTokens"] = opts.max_output_tokens
        if opts.top_p is not None:
            generation_config["topP"] = opts.top_p
        if opts.stop_sequences:
            generation_config["stopSequences"] = opts.stop_sequences

        # Structured output schema configuration
        if opts.structured_output:
            generation_config["responseMimeType"] = "application/json"
            if opts.structured_output.mode == "native":
                generation_config["responseSchema"] = opts.structured_output.schema_def

        if generation_config:
            payload["generationConfig"] = generation_config

        # 4. Tools (Function Calling)
        if opts.tools:
            function_declarations: list[dict[str, Any]] = []
            for tool in opts.tools:
                fn_decl: dict[str, Any] = {"name": tool.function.name}
                if tool.function.description:
                    fn_decl["description"] = tool.function.description
                if tool.function.parameters:
                    fn_decl["parameters"] = tool.function.parameters
                function_declarations.append(fn_decl)

            payload["tools"] = [{"functionDeclarations": function_declarations}]

            # Tool choice constraint
            if opts.tool_choice:
                if opts.tool_choice == "auto":
                    payload["toolConfig"] = {"functionCallingConfig": {"mode": "AUTO"}}
                elif opts.tool_choice == "required":
                    payload["toolConfig"] = {"functionCallingConfig": {"mode": "ANY"}}
                elif opts.tool_choice == "none":
                    payload["toolConfig"] = {"functionCallingConfig": {"mode": "NONE"}}

        return payload

    def _parse_candidate(
        self, candidate: dict[str, Any]
    ) -> tuple[str | None, list[ToolCall], FinishReason]:
        """Parse Gemini candidate parts into unified content, tool calls, and finish reason."""
        content_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        content_dict = candidate.get("content", {})
        parts = content_dict.get("parts", [])

        for part in parts:
            if "text" in part:
                content_parts.append(part["text"])
            elif "functionCall" in part:
                fc = part["functionCall"]
                call_id = f"call_{uuid.uuid4().hex[:12]}"
                tool_calls.append(
                    ToolCall(
                        id=call_id,
                        type="function",
                        function=FunctionCall(
                            name=fc.get("name", ""),
                            arguments=json.dumps(fc.get("args", {})),
                        ),
                    )
                )

        combined_content = "".join(content_parts) if content_parts else None

        # Map finish reason
        raw_reason = candidate.get("finishReason", "STOP").upper()
        if raw_reason == "SAFETY":
            raise LLMRefusalError(
                message="Google Gemini refused request due to content safety filters",
                reason="SAFETY",
            )
        elif raw_reason == "MAX_TOKENS":
            finish_reason: FinishReason = "length"
        elif tool_calls:
            finish_reason = "tool_calls"
        else:
            finish_reason = "stop"

        return combined_content, tool_calls, finish_reason

    def _parse_usage(self, data: dict[str, Any]) -> TokenUsage:
        """Parse token usage metadata from Gemini response."""
        usage_meta = data.get("usageMetadata", {})
        prompt_tokens = usage_meta.get("promptTokenCount", 0)
        candidates_tokens = usage_meta.get("candidatesTokenCount", 0)
        total_tokens = usage_meta.get("totalTokenCount", prompt_tokens + candidates_tokens)

        return TokenUsage(
            input_tokens=prompt_tokens,
            output_tokens=candidates_tokens,
            total_tokens=total_tokens,
        )

    def _handle_error_response(self, response: httpx.Response) -> None:
        """Map Gemini HTTP error statuses and payloads to typed LLM exceptions (RFC 9457)."""
        status_code = response.status_code
        try:
            err_data = response.json()
            err_info = err_data.get("error", {})
            err_message = err_info.get("message", response.text)
            err_status = err_info.get("status", "")
        except Exception:
            err_message = response.text
            err_status = ""

        # Rate limit (HTTP 429 / RESOURCE_EXHAUSTED)
        if status_code == 429 or err_status == "RESOURCE_EXHAUSTED":
            retry_header = response.headers.get("retry-after")
            retry_after_s: float | None = (
                float(retry_header) if retry_header and retry_header.isdigit() else 2.0
            )
            raise LLMRateLimitError(
                message=f"Gemini API rate limit exceeded: {err_message}",
                retry_after_s=retry_after_s,
            )

        # Authentication / Permission (HTTP 401 / 403)
        if status_code in (401, 403) or err_status in ("UNAUTHENTICATED", "PERMISSION_DENIED"):
            raise LLMError(
                message=f"Gemini API authentication failed ({status_code}): {err_message}",
                code="llm.authentication_error",
                details={"status_code": status_code, "gemini_status": err_status},
            )

        # Invalid Argument (HTTP 400 / INVALID_ARGUMENT)
        if status_code == 400 or err_status == "INVALID_ARGUMENT":
            raise LLMInvalidOutputError(
                message=f"Gemini API rejected request payload: {err_message}",
                raw_output=err_message,
            )

        # Upstream 5xx errors
        if status_code >= 500:
            raise LLMProviderError(
                message=f"Gemini API upstream error ({status_code}): {err_message}",
                status_code=status_code,
                raw_error=err_message,
            )

        raise LLMError(
            message=f"Gemini API returned error ({status_code}): {err_message}",
            code="llm.provider_error",
            details={"status_code": status_code, "gemini_status": err_status},
        )

    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        """Execute a non-streaming completion using Google Gemini generateContent."""
        self.validate_request_capabilities(request)
        api_key = self._get_api_key()
        payload = self._build_request_payload(request)

        url = f"{self._base_url}/models/{self._model_id}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }

        start_time = time.perf_counter()

        try:
            if self._custom_client:
                response = await self._custom_client.post(
                    url, json=payload, headers=headers, timeout=self._timeout_seconds
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                f"Gemini API request timed out after {self._timeout_seconds}s",
                timeout_s=self._timeout_seconds,
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(
                f"Gemini API network connection error: {exc}",
                raw_error=str(exc),
            ) from exc

        if not response.is_success:
            self._handle_error_response(response)

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        data = response.json()

        candidates = data.get("candidates", [])
        if not candidates:
            # Check for prompt-level safety block
            prompt_feedback = data.get("promptFeedback", {})
            block_reason = prompt_feedback.get("blockReason")
            if block_reason:
                raise LLMRefusalError(
                    message=f"Gemini API blocked prompt: {block_reason}",
                    reason=block_reason,
                )
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

        content, tool_calls, finish_reason = self._parse_candidate(candidates[0])
        usage = self._parse_usage(data)

        # Validate structured output if requested
        if request.options.structured_output and content:
            try:
                json.loads(content)
            except json.JSONDecodeError as exc:
                raise LLMInvalidOutputError(
                    message="Gemini structured output response is not valid JSON",
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

    async def stream_generate(self, request: LLMGenerationRequest) -> AsyncIterator[LLMStreamChunk]:
        """Execute a streaming completion using Google Gemini streamGenerateContent (SSE)."""
        self.validate_request_capabilities(request)
        api_key = self._get_api_key()
        payload = self._build_request_payload(request)

        url = f"{self._base_url}/models/{self._model_id}:streamGenerateContent?alt=sse"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }

        try:
            if self._custom_client:
                async with self._custom_client.stream(
                    "POST", url, json=payload, headers=headers, timeout=self._timeout_seconds
                ) as stream_resp:
                    if not stream_resp.is_success:
                        # Read body to extract error
                        await stream_resp.aread()
                        self._handle_error_response(stream_resp)

                    async for chunk in self._process_sse_stream(stream_resp):
                        yield chunk
            else:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    async with client.stream(
                        "POST", url, json=payload, headers=headers
                    ) as stream_resp:
                        if not stream_resp.is_success:
                            await stream_resp.aread()
                            self._handle_error_response(stream_resp)

                        async for chunk in self._process_sse_stream(stream_resp):
                            yield chunk
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                f"Gemini API streaming timed out after {self._timeout_seconds}s",
                timeout_s=self._timeout_seconds,
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(
                f"Gemini API stream network error: {exc}",
                raw_error=str(exc),
            ) from exc

    async def _process_sse_stream(self, response: httpx.Response) -> AsyncIterator[LLMStreamChunk]:
        """Process SSE event stream lines from Gemini streamGenerateContent."""
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

            candidates = data.get("candidates", [])
            usage = self._parse_usage(data) if "usageMetadata" in data else None

            if not candidates:
                if usage:
                    yield LLMStreamChunk(delta_content="", finish_reason="stop", usage=usage)
                continue

            cand = candidates[0]
            raw_reason = cand.get("finishReason")
            if raw_reason == "SAFETY":
                raise LLMRefusalError(
                    message="Gemini stream blocked by safety filter",
                    reason="SAFETY",
                )

            delta_text, delta_tool_calls, finish_reason = self._parse_candidate(cand)
            finish_str = finish_reason if raw_reason else None

            yield LLMStreamChunk(
                delta_content=delta_text or "",
                delta_tool_calls=delta_tool_calls,
                finish_reason=finish_str,
                usage=usage,
            )


# Self-register adapter in registry
register_adapter("google", GoogleGeminiAdapter)
register_adapter("gemini", GoogleGeminiAdapter)
