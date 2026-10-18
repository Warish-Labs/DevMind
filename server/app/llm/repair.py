"""Structured output schema validation, JSON sanitization, and repair engine (docs/05 §10, ADR-027, M6-09).

Enforces schema contracts on LLM responses:
1. Strips markdown fences, extracts JSON substrings, and cleans minor syntax anomalies (e.g. trailing commas).
2. Validates JSON against registered Pydantic models (or JSON schema dictionary).
3. On validation failure: constructs an actionable repair prompt and executes exactly ONE repair attempt.
4. If the repair attempt fails: raises LLMInvalidOutputError (which fails without falling back to another provider).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.llm.adapter import LLMAdapter
from app.llm.models import (
    ChatMessage,
    LLMGenerationRequest,
    LLMGenerationResponse,
    StructuredOutputSpec,
)
from app.llm.schemas import SchemaRegistry, default_schema_registry

logger = logging.getLogger(__name__)

# Regex for markdown code blocks containing json or plain code
_CODE_BLOCK_PATTERN = re.compile(
    r"```(?:json)?\s*\n?(.*?)\n?```",
    re.DOTALL | re.IGNORECASE,
)

# Regex for trailing commas before closing braces or brackets
_TRAILING_COMMA_PATTERN = re.compile(r",\s*([\]}])")


def extract_json_candidate(text: str) -> str:
    """Extract candidate JSON string from raw text, removing markdown fences if present."""
    if not text:
        return ""

    stripped = text.strip()

    # 1. Check for fenced code block: ```json ... ``` or ``` ... ```
    match = _CODE_BLOCK_PATTERN.search(stripped)
    if match:
        return match.group(1).strip()

    # 2. Check for outer curly braces or square brackets
    first_brace = stripped.find("{")
    last_brace = stripped.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return stripped[first_brace : last_brace + 1].strip()

    first_bracket = stripped.find("[")
    last_bracket = stripped.rfind("]")
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        return stripped[first_bracket : last_bracket + 1].strip()

    return stripped


def clean_json_string(text: str) -> str:
    """Clean minor syntax flaws from candidate JSON string (e.g. trailing commas)."""
    if not text:
        return ""
    # Strip trailing commas before closing braces/brackets
    cleaned = _TRAILING_COMMA_PATTERN.sub(r"\1", text)
    return cleaned


class ValidationResult(BaseModel):
    """Result of validating an LLM output against a structured output specification."""

    model_config = ConfigDict(extra="forbid")

    is_valid: bool
    parsed_data: dict[str, Any] | list[Any] | None = None
    validated_model: Any = None
    errors: list[str] = Field(default_factory=list)
    cleaned_json: str | None = None

    @property
    def error_message(self) -> str | None:
        """Formatted summary of all validation errors."""
        return "; ".join(self.errors) if self.errors else None


class StructuredOutputRepairer:
    """Validates structured outputs and executes exactly one repair attempt on failure (docs/05 §10)."""

    def __init__(self, registry: SchemaRegistry | None = None) -> None:
        self.registry = registry or default_schema_registry

    def validate(
        self,
        raw_output: str | None,
        spec: StructuredOutputSpec,
    ) -> ValidationResult:
        """Validate raw output against the requested StructuredOutputSpec."""
        if not raw_output or not raw_output.strip():
            return ValidationResult(
                is_valid=False,
                errors=["Empty or null response content received from LLM"],
            )

        candidate = extract_json_candidate(raw_output)
        cleaned = clean_json_string(candidate)

        # 1. Parse JSON
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            return ValidationResult(
                is_valid=False,
                cleaned_json=cleaned,
                errors=[f"JSON syntax error at line {exc.lineno}, col {exc.colno}: {exc.msg}"],
            )

        # 2. Validate against registered Pydantic schema model if available
        schema_cls = self.registry.get(spec.schema_name)
        if schema_cls is not None:
            if not isinstance(parsed, dict):
                return ValidationResult(
                    is_valid=False,
                    parsed_data=parsed,
                    cleaned_json=cleaned,
                    errors=[
                        f"Expected JSON object for schema '{spec.schema_name}', got {type(parsed).__name__}"
                    ],
                )
            try:
                model_instance = schema_cls.model_validate(parsed)
                return ValidationResult(
                    is_valid=True,
                    parsed_data=parsed,
                    validated_model=model_instance,
                    cleaned_json=cleaned,
                )
            except ValidationError as val_err:
                errors: list[str] = []
                for err in val_err.errors():
                    loc = " -> ".join(str(p) for p in err.get("loc", []))
                    msg = err.get("msg", "Validation error")
                    errors.append(f"Field '{loc}': {msg}")
                return ValidationResult(
                    is_valid=False,
                    parsed_data=parsed,
                    cleaned_json=cleaned,
                    errors=errors,
                )

        # 3. Fallback: Validate against spec.schema_def required fields if not registered Pydantic model
        schema_def = spec.schema_def
        if isinstance(parsed, dict) and isinstance(schema_def, dict):
            required = schema_def.get("required", [])
            missing = [f for f in required if f not in parsed]
            if missing:
                return ValidationResult(
                    is_valid=False,
                    parsed_data=parsed,
                    cleaned_json=cleaned,
                    errors=[f"Missing required schema fields: {missing}"],
                )

        # Basic JSON object valid
        return ValidationResult(
            is_valid=True,
            parsed_data=parsed,
            cleaned_json=cleaned,
        )

    def build_repair_messages(
        self,
        original_messages: list[ChatMessage],
        raw_output: str,
        errors: list[str],
        spec: StructuredOutputSpec,
    ) -> list[ChatMessage]:
        """Construct conversation history and repair instructions for the repair attempt (docs/05 §10)."""
        formatted_errors = "\n".join(f"- {err}" for err in errors)
        repair_instruction = (
            f"Your previous response did not satisfy the required schema for '{spec.schema_name}'.\n"
            f"Validation errors encountered:\n{formatted_errors}\n\n"
            f"Please correct the errors and output ONLY valid, well-formed JSON conforming strictly to the "
            f"'{spec.schema_name}' schema. Do NOT include markdown formatting or commentary outside the JSON."
        )

        repair_messages = list(original_messages)
        repair_messages.append(ChatMessage.assistant(raw_output))
        repair_messages.append(ChatMessage.user(repair_instruction))
        return repair_messages

    async def attempt_repair(
        self,
        *,
        adapter: LLMAdapter,
        request: LLMGenerationRequest,
        raw_output: str,
        errors: list[str],
        spec: StructuredOutputSpec,
    ) -> tuple[LLMGenerationResponse, ValidationResult]:
        """Execute exactly one repair attempt with the same adapter/model (docs/05 §10)."""
        logger.warning(
            "Structured output validation failed for task '%s' (schema: %s). Initiating 1 repair attempt.",
            request.task,
            spec.schema_name,
        )

        repair_messages = self.build_repair_messages(request.messages, raw_output, errors, spec)
        repair_options = request.options.model_copy(deep=True)
        # Use temperature 0.0 for deterministic schema repair
        repair_options.temperature = 0.0
        repair_options.structured_output = spec

        repair_request = LLMGenerationRequest(
            task=request.task,
            messages=repair_messages,
            options=repair_options,
            model_alias=request.model_alias,
            metadata={**request.metadata, "is_repair_attempt": True},
        )

        repair_response = await adapter.generate(repair_request)
        repair_validation = self.validate(repair_response.content, spec)
        return repair_response, repair_validation
