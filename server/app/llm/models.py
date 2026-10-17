"""Common request, response, message, capability, and policy types for LLM gateway (docs/05 §10-§12)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

MessageRole = Literal["system", "user", "assistant", "tool"]
StructuredOutputMode = Literal["native", "json_mode", "prompt_only", "none"]
FinishReason = Literal["stop", "length", "tool_calls", "content_filter", "error", "other"]


class FunctionCall(BaseModel):
    """Function call representation conforming to tool calling interfaces."""

    name: str = Field(description="Name of the function called by the model")
    arguments: str = Field(
        default="", description="JSON-encoded argument string for the function call"
    )


class ToolCall(BaseModel):
    """Tool call emitted by the model during multi-step reasoning."""

    id: str = Field(description="Unique tool call invocation ID")
    type: Literal["function"] = Field(default="function", description="Tool call type")
    function: FunctionCall = Field(description="Invoked function specification")


class ChatMessage(BaseModel):
    """Standard normalized chat message across all provider adapters."""

    role: MessageRole = Field(description="Role of the message sender")
    content: str | None = Field(default=None, description="Text content of the message")
    name: str | None = Field(
        default=None, description="Optional name identifier for tool or participant"
    )
    tool_call_id: str | None = Field(
        default=None, description="Referenced tool call ID when role is 'tool'"
    )
    tool_calls: list[ToolCall] | None = Field(
        default=None,
        description="Tool calls requested by assistant when role is 'assistant'",
    )

    @classmethod
    def system(cls, content: str) -> ChatMessage:
        """Create a system message."""
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> ChatMessage:
        """Create a user message."""
        return cls(role="user", content=content)

    @classmethod
    def assistant(
        cls, content: str | None = None, tool_calls: list[ToolCall] | None = None
    ) -> ChatMessage:
        """Create an assistant message."""
        return cls(role="assistant", content=content, tool_calls=tool_calls)

    @classmethod
    def tool(cls, tool_call_id: str, content: str, name: str | None = None) -> ChatMessage:
        """Create a tool result message."""
        return cls(role="tool", tool_call_id=tool_call_id, content=content, name=name)


class FunctionDefinition(BaseModel):
    """Function definition for tool calling interfaces."""

    name: str = Field(description="Name of the function")
    description: str | None = Field(
        default=None, description="Purpose and description of the function"
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON schema describing expected parameters",
    )


class ToolDefinition(BaseModel):
    """Tool definition presented to LLM adapters."""

    type: Literal["function"] = Field(default="function", description="Tool category")
    function: FunctionDefinition = Field(description="Function schema definition")

    @classmethod
    def from_params(
        cls,
        name: str,
        description: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> ToolDefinition:
        """Helper to create tool definition directly from components."""
        return cls(
            type="function",
            function=FunctionDefinition(
                name=name,
                description=description,
                parameters=parameters or {"type": "object", "properties": {}},
            ),
        )


class StructuredOutputSpec(BaseModel):
    """Schema specification for structured outputs (docs/05 §10)."""

    schema_name: str = Field(
        description="Identifier for the expected output schema (e.g. 'AgentPlan')"
    )
    schema_def: dict[str, Any] = Field(description="JSON schema dict describing the structure")
    mode: StructuredOutputMode = Field(
        default="native",
        description="Structured output enforcement mode",
    )
    strict: bool = Field(default=True, description="Whether schema matching must be strict")


class LLMGenerationOptions(BaseModel):
    """Generation options passed into adapter invocations."""

    temperature: float = Field(default=0.2, ge=0.0, le=2.0, description="Sampling temperature")
    max_output_tokens: int | None = Field(
        default=None, gt=0, description="Maximum output token cap"
    )
    top_p: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Nucleus sampling threshold"
    )
    stop_sequences: list[str] | None = Field(
        default=None, description="Sequences that halt generation"
    )
    structured_output: StructuredOutputSpec | None = Field(
        default=None,
        description="Structured output schema specification",
    )
    tools: list[ToolDefinition] | None = Field(
        default=None, description="Available tools for the LLM"
    )
    tool_choice: Literal["auto", "none", "required"] | dict[str, Any] | None = Field(
        default=None,
        description="Tool choice constraint for generation",
    )


class TokenUsage(BaseModel):
    """Token accounting structure per gateway call (docs/05 §13)."""

    input_tokens: int = Field(default=0, ge=0, description="Tokens in prompt/context")
    output_tokens: int = Field(default=0, ge=0, description="Tokens in generated response")
    total_tokens: int = Field(default=0, ge=0, description="Sum of input and output tokens")

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.total_tokens == 0 and (self.input_tokens > 0 or self.output_tokens > 0):
            self.total_tokens = self.input_tokens + self.output_tokens


class LLMGenerationRequest(BaseModel):
    """Unified request model passed into the LLM gateway and adapters."""

    task: str = Field(
        description="Task key mapped in tasks.yaml (e.g. 'code_answer', 'query_rewrite')"
    )
    messages: list[ChatMessage] = Field(description="Ordered conversation messages")
    model_alias: str | None = Field(
        default=None,
        description="Optional explicit logical model key (e.g. 'primary_reasoning')",
    )
    options: LLMGenerationOptions = Field(
        default_factory=LLMGenerationOptions,
        description="Inference parameters",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Audit metadata (request_id, workspace_id, project_id, job_id)",
    )


class LLMGenerationResponse(BaseModel):
    """Unified generation response from LLM adapters."""

    content: str | None = Field(default=None, description="Text response content")
    role: Literal["assistant"] = Field(default="assistant", description="Message role")
    tool_calls: list[ToolCall] = Field(
        default_factory=list, description="Tool calls generated by the model"
    )
    finish_reason: FinishReason = Field(default="stop", description="Reason inference terminated")
    usage: TokenUsage = Field(default_factory=TokenUsage, description="Recorded token usage")
    provider_id: str = Field(description="Provider identifier (e.g. 'google', 'fake')")
    model_id: str = Field(description="Model identifier invoked")
    raw_response: dict[str, Any] | None = Field(
        default=None, description="Raw provider metadata for debugging"
    )
    latency_ms: float = Field(
        default=0.0, ge=0.0, description="Total generation duration in milliseconds"
    )


class LLMStreamChunk(BaseModel):
    """Incremental streaming chunk returned by adapters."""

    delta_content: str = Field(default="", description="Incremental text token(s)")
    delta_tool_calls: list[ToolCall] = Field(
        default_factory=list, description="Incremental tool call fragments"
    )
    finish_reason: str | None = Field(default=None, description="Termination reason on final chunk")
    usage: TokenUsage | None = Field(
        default=None, description="Final token usage statistics if available"
    )


class ModelCapabilities(BaseModel):
    """Capabilities verified and declared for a model (docs/05 §11.2)."""

    tool_calling: bool = Field(
        default=False, description="Whether model supports function/tool calling"
    )
    structured_output: StructuredOutputMode = Field(
        default="none",
        description="Mode of structured output support (native, json_mode, prompt_only, none)",
    )
    streaming: bool = Field(default=True, description="Whether model supports streaming output")
    supports_system_prompt: bool = Field(
        default=True, description="Whether system role messages are natively handled"
    )


class ProviderDataPolicy(BaseModel):
    """Data privacy and terms review status for a provider (docs/05 §11.1, §11.4)."""

    source_code_allowed: bool = Field(
        default=False,
        description="Whether terms review allows customer source code transmission",
    )
    terms_reviewed: bool = Field(
        default=False,
        description="Whether official legal terms review has been signed off",
    )
    note: str | None = Field(default=None, description="Reference link or date of terms review")
