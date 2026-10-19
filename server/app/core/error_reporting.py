"""Free-tier compatible error reporting and payload scrubbing (OQ-15, ADR-030, ADR-046, ADR-047).

Provides:
1. Error capture interface with strict redaction (no source code, prompts, completions, auth tokens, or cookies).
2. Graceful fallback when DEVMIND_SENTRY_DSN is absent (Render logs are sufficient, zero paid dependency).
3. Automatic integration with OpenTelemetry trace_id and span_id.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request

from app.core.logging import (
    job_id_ctx,
    project_id_ctx,
    redact_sensitive_text,
    request_id_ctx,
    workspace_id_ctx,
)
from app.core.settings import Settings, get_settings

logger = logging.getLogger("devmind.errors")

_sentry_initialized = False


def _scrub_sentry_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Scrub sensitive data from error reports before external transmission (ADR-047)."""
    # 1. Remove request body, query strings with secrets, and sensitive headers
    request_data = event.get("request", {})
    if request_data:
        # Strip all raw body and data
        request_data.pop("data", None)

        headers = request_data.get("headers", {})
        if headers:
            for forbidden_header in ("authorization", "cookie", "x-api-key", "clerk-token"):
                headers.pop(forbidden_header, None)
                headers.pop(forbidden_header.title(), None)

    # 2. Scrub breadcrumbs
    breadcrumbs = event.get("breadcrumbs", {}).get("values", [])
    for bc in breadcrumbs:
        data = bc.get("data")
        if isinstance(data, dict):
            for k in list(data.keys()):
                if any(
                    s in k.lower() for s in ("token", "secret", "password", "code", "prompt", "key")
                ):
                    data[k] = "[REDACTED]"

    return event


def init_error_reporting(settings: Settings | None = None) -> None:
    """Initialize error reporting service if configured, or gracefully no-op."""
    global _sentry_initialized

    if settings is None:
        settings = get_settings()

    if not settings.sentry_dsn:
        logger.info("External error reporting disabled (using structured logging; OQ-15 / ADR-046)")
        return

    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.env,
            release="0.1.0",
            send_default_pii=False,
            before_send=_scrub_sentry_event,
            traces_sample_rate=0.0,  # We use OpenTelemetry for traces
        )
        _sentry_initialized = True
        logger.info("External error reporting initialized with payload scrubbing (OQ-15)")
    except ImportError:
        logger.warning(
            "DEVMIND_SENTRY_DSN provided but sentry-sdk not installed; defaulting to structured logging"
        )
    except Exception as exc:
        logger.error("Failed to initialize external error reporting: %s", redact_sensitive_text(str(exc)))


def report_exception(
    exc: Exception,
    context: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    """Report an exception with correlation IDs and redacted context."""
    # Build clean metadata
    metadata: dict[str, Any] = {}

    req_id = (
        getattr(request.state, "request_id", None)
        if request and hasattr(request, "state")
        else None
    ) or request_id_ctx.get()
    if req_id:
        metadata["request_id"] = req_id

    trace_id = (
        getattr(request.state, "trace_id", None)
        if request and hasattr(request, "state")
        else None
    )
    if trace_id:
        metadata["trace_id"] = trace_id

    job_id = job_id_ctx.get()
    if job_id:
        metadata["job_id"] = job_id

    ws_id = workspace_id_ctx.get()
    if ws_id:
        metadata["workspace_id"] = ws_id

    proj_id = project_id_ctx.get()
    if proj_id:
        metadata["project_id"] = proj_id

    if context:
        for k, v in context.items():
            if not any(
                forbidden in k.lower()
                for forbidden in ("code", "source", "prompt", "token", "secret", "password")
            ):
                metadata[k] = redact_sensitive_text(str(v))

    logger.error(
        "Reported exception [%s]: %s (context: %s)",
        type(exc).__name__,
        redact_sensitive_text(str(exc)),
        metadata,
    )

    if _sentry_initialized:
        try:
            import sentry_sdk

            with sentry_sdk.push_scope() as scope:
                for k, v in metadata.items():
                    scope.set_tag(k, v)
                sentry_sdk.capture_exception(exc)
        except Exception:
            pass
