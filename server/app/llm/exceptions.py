"""LLM Gateway exception hierarchy (docs/05 §10-§12, docs/03 §10.1)."""

from __future__ import annotations

from typing import Any


class LLMError(Exception):
    """Base exception for all LLM gateway operations."""

    def __init__(
        self, message: str, code: str = "llm.error", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class LLMTimeoutError(LLMError):
    """Raised when an LLM provider request times out."""

    def __init__(
        self, message: str = "LLM provider request timed out", timeout_s: float | None = None
    ) -> None:
        super().__init__(
            message=message,
            code="llm.timeout",
            details={"timeout_s": timeout_s} if timeout_s is not None else None,
        )
        self.timeout_s = timeout_s


class LLMRateLimitError(LLMError):
    """Raised when an LLM provider rejects requests due to rate limits (HTTP 429)."""

    def __init__(
        self, message: str = "LLM provider rate limit exceeded", retry_after_s: float | None = None
    ) -> None:
        super().__init__(
            message=message,
            code="llm.rate_limit",
            details={"retry_after_s": retry_after_s} if retry_after_s is not None else None,
        )
        self.retry_after_s = retry_after_s


class LLMProviderError(LLMError):
    """Raised when an LLM provider encounters an upstream error (e.g. 5xx)."""

    def __init__(
        self,
        message: str = "Upstream LLM provider error",
        status_code: int | None = None,
        raw_error: Any = None,
    ) -> None:
        super().__init__(
            message=message,
            code="llm.provider_error",
            details={"status_code": status_code, "raw_error": str(raw_error)}
            if status_code
            else None,
        )
        self.status_code = status_code
        self.raw_error = raw_error


class LLMInvalidOutputError(LLMError):
    """Raised when structured output schema validation or JSON decoding fails (docs/05 §10)."""

    def __init__(
        self,
        message: str = "LLM output failed schema validation",
        raw_output: str | None = None,
        validation_errors: list[str] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="llm.invalid_output",
            details={
                "raw_output_snippet": raw_output[:200] if raw_output else None,
                "errors": validation_errors,
            },
        )
        self.raw_output = raw_output
        self.validation_errors = validation_errors or []


class LLMUnavailableError(LLMError):
    """Raised when no configured LLM provider or fallback is available (docs/05 §12)."""

    def __init__(
        self, message: str = "No LLM provider or eligible fallback is currently available"
    ) -> None:
        super().__init__(message=message, code="llm.unavailable")


class LLMRefusalError(LLMError):
    """Raised when an LLM provider explicitly refuses to complete a prompt (safety or policy refusal)."""

    def __init__(
        self, message: str = "LLM provider refused to process request", reason: str | None = None
    ) -> None:
        super().__init__(
            message=message, code="llm.refusal", details={"reason": reason} if reason else None
        )
        self.reason = reason


class LLMQuotaExceededError(LLMError):
    """Raised when workspace or project token quota / budget is exhausted (docs/05 §13)."""

    def __init__(
        self,
        message: str = "LLM token quota or budget exceeded",
        quota_type: str | None = None,
        used: int | None = None,
        limit: int | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="quota.exceeded",
            details={"quota_type": quota_type, "used": used, "limit": limit},
        )
        self.quota_type = quota_type
        self.used = used
        self.limit = limit


class LLMPermissionError(LLMError):
    """Raised when a task violates privacy/data policy (e.g. source_code_allowed guard per docs/05 §11.4)."""

    def __init__(
        self, message: str = "LLM data policy does not permit source code transmission"
    ) -> None:
        super().__init__(message=message, code="llm.permission_denied")


class LLMContextLengthExceededError(LLMError):
    """Raised when input tokens exceed model context limit (docs/05 §11.6)."""

    def __init__(
        self,
        message: str = "Context length exceeded maximum allowed input tokens",
        input_tokens: int | None = None,
        max_tokens: int | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="llm.context_length_exceeded",
            details={"input_tokens": input_tokens, "max_tokens": max_tokens},
        )
        self.input_tokens = input_tokens
        self.max_tokens = max_tokens
