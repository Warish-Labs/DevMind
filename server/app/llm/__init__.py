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
from app.llm.prompt_loader import (
    PromptFrontMatter,
    PromptLoader,
    PromptTemplate,
    RenderedPrompt,
    default_prompt_loader,
    detect_injection_signals,
    escape_untrusted_content,
)
from app.llm.quotas import LLMConcurrencyManager, LLMQuotaEnforcer, LLMRateLimiter
from app.llm.registry import (
    create_adapter,
    get_adapter_class,
    list_supported_adapters,
    register_adapter,
)
from app.llm.repair import (
    StructuredOutputRepairer,
    ValidationResult,
    clean_json_string,
    extract_json_candidate,
)
from app.llm.router import LLMGatewayRouter
from app.llm.schemas import (
    AgentPlan,
    BugSimilarityExplanation,
    FindingExplanation,
    RewrittenQuery,
    SchemaRegistry,
    SynthesizedAnswer,
    default_schema_registry,
)
from app.llm.usage import LLMUsageRecorder, RecordedUsage, UsageSink, calculate_cost_units

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
    "LLMUsageRecorder",
    "RecordedUsage",
    "UsageSink",
    "calculate_cost_units",
    "StructuredOutputRepairer",
    "ValidationResult",
    "extract_json_candidate",
    "clean_json_string",
    "SchemaRegistry",
    "default_schema_registry",
    "AgentPlan",
    "BugSimilarityExplanation",
    "FindingExplanation",
    "SynthesizedAnswer",
    "RewrittenQuery",
    # Prompt Template Loader & Injection Defenses
    "PromptLoader",
    "default_prompt_loader",
    "PromptTemplate",
    "PromptFrontMatter",
    "RenderedPrompt",
    "escape_untrusted_content",
    "detect_injection_signals",
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
