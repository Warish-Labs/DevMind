from app.llm.adapter import LLMAdapter
from app.llm.adapters.fake import FakeFaultInjection, FakeLLMAdapter
from app.llm.adapters.google_genai import GoogleGeminiAdapter
from app.llm.adapters.openai_compatible import OpenAICompatibleAdapter
from app.llm.config import (
    ConfigValidationError,
    GatewayConfig,
    load_gateway_config,
    validate_gateway_config,
)
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
from app.llm.quotas import LLMConcurrencyManager, LLMQuotaEnforcer, LLMRateLimiter
from app.llm.registry import (
    create_adapter,
    get_adapter_class,
    list_supported_adapters,
    register_adapter,
)
from app.llm.router import LLMGatewayRouter

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
    "GoogleGeminiAdapter",
    "OpenAICompatibleAdapter",
    "register_adapter",
    "get_adapter_class",
    "list_supported_adapters",
    "create_adapter",
    # Gateway Router, Quotas & Configuration
    "LLMGatewayRouter",
    "LLMConcurrencyManager",
    "LLMRateLimiter",
    "LLMQuotaEnforcer",
    "GatewayConfig",
    "load_gateway_config",
    "validate_gateway_config",
    "ConfigValidationError",
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
