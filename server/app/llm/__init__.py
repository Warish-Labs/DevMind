"""DevMind LLM gateway: provider adapters, model router, prompts (docs/05 §11-§12, docs/11 M6)."""

from app.llm.adapter import LLMAdapter
from app.llm.adapters.fake import FakeFaultInjection, FakeLLMAdapter
from app.llm.embedding_adapter import (
    EmbeddingAdapter,
    EmbeddingInputType,
    EmbeddingResult,
    FakeEmbeddingAdapter,
    get_embedding_adapter,
)
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
    FinishReason,
    FunctionCall,
    FunctionDefinition,
    LLMGenerationOptions,
    LLMGenerationRequest,
    LLMGenerationResponse,
    LLMStreamChunk,
    MessageRole,
    ModelCapabilities,
    ProviderDataPolicy,
    StructuredOutputMode,
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

__all__ = [
    # Embedding gateway exports
    "EmbeddingAdapter",
    "EmbeddingInputType",
    "EmbeddingResult",
    "FakeEmbeddingAdapter",
    "get_embedding_adapter",
    # LLM adapter & registry
    "LLMAdapter",
    "FakeLLMAdapter",
    "FakeFaultInjection",
    "register_adapter",
    "get_adapter_class",
    "list_supported_adapters",
    "create_adapter",
    # Models & types
    "ChatMessage",
    "MessageRole",
    "StructuredOutputMode",
    "FinishReason",
    "FunctionCall",
    "ToolCall",
    "FunctionDefinition",
    "ToolDefinition",
    "StructuredOutputSpec",
    "LLMGenerationOptions",
    "TokenUsage",
    "LLMGenerationRequest",
    "LLMGenerationResponse",
    "LLMStreamChunk",
    "ModelCapabilities",
    "ProviderDataPolicy",
    # Exceptions
    "LLMError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "LLMProviderError",
    "LLMInvalidOutputError",
    "LLMUnavailableError",
    "LLMRefusalError",
    "LLMQuotaExceededError",
    "LLMPermissionError",
    "LLMContextLengthExceededError",
]
