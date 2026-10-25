"""Structured JSON logging with sensitive secret and token redaction filter."""

import contextvars
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

# Context variables for correlation IDs
request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
job_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("job_id", default=None)
workspace_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "workspace_id", default=None
)
project_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "project_id", default=None
)
actor_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("actor_id", default=None)

# Patterns for sensitive information redaction
REDACTION_PATTERNS = [
    # Bearer tokens
    (re.compile(r"Bearer\s+[A-Za-z0-9\-_.~+/]+=*", re.IGNORECASE), "Bearer [REDACTED]"),
    # Clerk and provider keys
    (re.compile(r"sk_live_[0-9a-zA-Z]{16,}"), "[REDACTED:secret_key]"),
    (re.compile(r"sk_test_[0-9a-zA-Z]{16,}"), "[REDACTED:secret_key]"),
    (re.compile(r"pk_live_[0-9a-zA-Z]{16,}"), "[REDACTED:pub_key]"),
    (re.compile(r"pk_test_[0-9a-zA-Z]{16,}"), "[REDACTED:pub_key]"),
    (re.compile(r"whsec_[0-9a-zA-Z]{16,}"), "[REDACTED:webhook_secret]"),
    # DB connection password in URIs: scheme://user:password@host
    (re.compile(r"(://[^:]+:)([^@]+)(@)"), r"\1[REDACTED]\3"),
    # Generic secret assignment in query params / configs
    (
        re.compile(
            r"(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[^\s'\",]+['\"]?", re.IGNORECASE
        ),
        r"\1=[REDACTED]",
    ),
]


def redact_sensitive_text(text: str) -> str:
    """Apply all redaction rules to sensitive strings."""
    if not isinstance(text, str):
        return text
    result = text
    for pattern, replacement in REDACTION_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


class RedactionFilter(logging.Filter):
    """Filter that sanitizes log record messages and arguments to prevent leaking secrets."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact_sensitive_text(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_sensitive_text(v) if isinstance(v, str) else v for v in record.args
                )
        return True


class JSONFormatter(logging.Formatter):
    """JSON log formatter outputting structured records per ADR-002 and AGENTS.md."""

    def format(self, record: logging.LogRecord) -> str:
        super().format(record)
        log_payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Correlated context variables
        req_id = request_id_ctx.get() or getattr(record, "request_id", None)
        if req_id:
            log_payload["request_id"] = req_id

        job_id = job_id_ctx.get() or getattr(record, "job_id", None)
        if job_id:
            log_payload["job_id"] = job_id

        ws_id = workspace_id_ctx.get() or getattr(record, "workspace_id", None)
        if ws_id:
            log_payload["workspace_id"] = ws_id

        proj_id = project_id_ctx.get() or getattr(record, "project_id", None)
        if proj_id:
            log_payload["project_id"] = proj_id

        act_id = actor_id_ctx.get() or getattr(record, "actor_id", None)
        if act_id:
            log_payload["actor_id"] = act_id

        # Correlated OpenTelemetry trace and span IDs (W3C standard 32-hex / 16-hex)
        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            if span:
                span_ctx = span.get_span_context()
                if span_ctx and span_ctx.is_valid:
                    log_payload["trace_id"] = f"{span_ctx.trace_id:032x}"
                    log_payload["span_id"] = f"{span_ctx.span_id:016x}"
        except Exception:
            pass

        if record.exc_info and record.exc_text:
            log_payload["exception"] = redact_sensitive_text(record.exc_text)

        return json.dumps(log_payload)


def setup_logging(log_level: str = "INFO") -> None:
    """Configure root logging handler with redaction filter and JSON formatter."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers to avoid duplicates (preserve test log capture)
    for handler in list(root.handlers):
        if handler.__class__.__name__ == "LogCaptureHandler":
            continue
        root.removeHandler(handler)

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.addFilter(RedactionFilter())
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)

    # Intercept uvicorn logging
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        uv_logger = logging.getLogger(logger_name)
        uv_logger.handlers = []
        uv_logger.propagate = True
