"""Base abstract LLM provider adapter interface (docs/05 §11-§12, docs/11 M6-01)."""

from __future__ import annotations

import abc
from collections.abc import AsyncIterator

from app.llm.exceptions import LLMError, LLMInvalidOutputError, LLMPermissionError
from app.llm.models import (
    LLMGenerationRequest,
    LLMGenerationResponse,
    LLMStreamChunk,
    ModelCapabilities,
    ProviderDataPolicy,
)


class LLMAdapter(abc.ABC):
    """Abstract interface implemented by all LLM provider adapters."""

    @property
    @abc.abstractmethod
    def provider_id(self) -> str:
        """Provider identifier (e.g. 'google', 'openai', 'anthropic', 'fake')."""

    @property
    @abc.abstractmethod
    def model_id(self) -> str:
        """Specific model identifier (e.g. 'gemini-1.5-flash', 'fake-deterministic')."""

    @property
    @abc.abstractmethod
    def capabilities(self) -> ModelCapabilities:
        """Declared and verified model capabilities (docs/05 §11.2)."""

    @property
    def data_policy(self) -> ProviderDataPolicy:
        """Provider data privacy and terms review policy (docs/05 §11.1)."""
        return ProviderDataPolicy()

    @abc.abstractmethod
    async def generate(self, request: LLMGenerationRequest) -> LLMGenerationResponse:
        """Execute a non-streaming completion for the given unified request."""

    @abc.abstractmethod
    async def stream_generate(self, request: LLMGenerationRequest) -> AsyncIterator[LLMStreamChunk]:
        """Execute a streaming completion, yielding incremental stream chunks."""

    def validate_request_capabilities(self, request: LLMGenerationRequest) -> None:
        """Validate that the adapter's model capabilities satisfy the request requirements."""
        # 1. Tool calling validation
        if request.options.tools and not self.capabilities.tool_calling:
            raise LLMError(
                f"Model '{self.model_id}' on provider '{self.provider_id}' does not support tool calling",
                code="llm.unsupported_capability",
            )

        # 2. Structured output validation
        if request.options.structured_output:
            spec = request.options.structured_output
            if self.capabilities.structured_output == "none":
                raise LLMInvalidOutputError(
                    f"Model '{self.model_id}' on provider '{self.provider_id}' does not support structured output",
                )
            if spec.mode == "native" and self.capabilities.structured_output not in (
                "native",
                "json_mode",
            ):
                raise LLMInvalidOutputError(
                    f"Model '{self.model_id}' does not support native schema mode (supported: {self.capabilities.structured_output})",
                )

    def validate_data_policy(self, may_contain_source: bool = False) -> None:
        """Validate that customer source code is permitted to be transmitted to this provider."""
        if may_contain_source and not self.data_policy.source_code_allowed:
            raise LLMPermissionError(
                f"Provider '{self.provider_id}' does not permit source code transmission (terms_reviewed={self.data_policy.terms_reviewed})",
            )
