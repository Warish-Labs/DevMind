"""OpenTelemetry tracing, metrics instrumentation, and payload redaction guards (docs/02 §12, docs/10 §13, docs/11 M10-02).

Provides:
1. OpenTelemetry TracerProvider & MeterProvider with configurable exporters (memory, console).
2. Span creation with strict payload-scrubbing policy (ADR-047: zero secrets, source code, prompts or completions in spans).
3. Standardized metrics for HTTP requests, background worker tasks, LLM generation, and queue depth.
4. TelemetryMiddleware for automated FastAPI request tracing and metric collection.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import Request, Response
from opentelemetry import metrics, trace
from opentelemetry.metrics import Counter, Histogram, UpDownCounter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Status, StatusCode
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.logging import (
    job_id_ctx,
    project_id_ctx,
    redact_sensitive_text,
    request_id_ctx,
    workspace_id_ctx,
)
from app.core.settings import Settings, get_settings

logger = logging.getLogger("devmind.telemetry")

# Forbidden attribute keys and substrings that must NEVER be placed in telemetry payloads (Rule 5, ADR-047)
FORBIDDEN_EXACT_KEYS = frozenset(
    {
        "prompt",
        "completion",
        "code",
        "source",
        "body",
        "payload",
        "password",
        "secret",
        "token",
        "key",
        "cookie",
        "authorization",
    }
)
FORBIDDEN_SUBSTRING_KEYS = frozenset(
    {
        "prompt",
        "completion",
        "source_code",
        "raw_payload",
        "password",
        "secret",
        "token",
        "pepper",
        "jwt",
        "cookie",
        "authorization",
        "api_key",
    }
)

# Global in-memory storage for test validation and diagnostics
_tracer_provider: TracerProvider | None = None
_meter_provider: MeterProvider | None = None
_in_memory_span_exporter: InMemorySpanExporter | None = None
_in_memory_metric_reader: InMemoryMetricReader | None = None

# Telemetry instruments
_http_requests_total: Counter | None = None
_http_request_duration_seconds: Histogram | None = None
_worker_jobs_total: Counter | None = None
_worker_job_duration_seconds: Histogram | None = None
_llm_requests_total: Counter | None = None
_llm_tokens_total: Counter | None = None
_llm_latency_seconds: Histogram | None = None
_queue_depth: UpDownCounter | None = None


def sanitize_span_attributes(attributes: dict[str, Any] | None) -> dict[str, Any]:
    """Sanitize attributes to ensure zero secrets, tokens, source code, or prompts are emitted."""
    if not attributes:
        return {}

    sanitized: dict[str, Any] = {}
    for key, val in attributes.items():
        k_lower = key.lower()
        # Drop forbidden payload keys
        if k_lower in FORBIDDEN_EXACT_KEYS or any(
            sub in k_lower for sub in FORBIDDEN_SUBSTRING_KEYS
        ):
            continue

        if isinstance(val, (int, float, bool)):
            sanitized[key] = val
        elif isinstance(val, str):
            sanitized[key] = redact_sensitive_text(val)
        else:
            sanitized[key] = redact_sensitive_text(str(val))

    return sanitized


def init_telemetry(settings: Settings | None = None) -> None:
    """Initialize OpenTelemetry tracing and metrics providers with resource tags and exporters."""
    global _tracer_provider, _meter_provider
    global _in_memory_span_exporter, _in_memory_metric_reader
    global _http_requests_total, _http_request_duration_seconds
    global _worker_jobs_total, _worker_job_duration_seconds
    global _llm_requests_total, _llm_tokens_total, _llm_latency_seconds, _queue_depth

    if settings is None:
        settings = get_settings()

    if _tracer_provider is not None:
        # Already initialized; avoid re-registering global TracerProvider
        return

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.namespace": "devmind",
            "deployment.environment": settings.env,
        }
    )

    # 1. TracerProvider setup
    _tracer_provider = TracerProvider(resource=resource)
    _in_memory_span_exporter = InMemorySpanExporter()
    _tracer_provider.add_span_processor(SimpleSpanProcessor(_in_memory_span_exporter))

    if settings.otel_exporter == "console":
        _tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    try:
        trace.set_tracer_provider(_tracer_provider)
    except Exception:
        pass

    # 2. MeterProvider setup
    _in_memory_metric_reader = InMemoryMetricReader()
    _meter_provider = MeterProvider(resource=resource, metric_readers=[_in_memory_metric_reader])
    try:
        metrics.set_meter_provider(_meter_provider)
    except Exception:
        pass

    meter = _meter_provider.get_meter("devmind")

    _http_requests_total = meter.create_counter(
        name="devmind_http_requests_total",
        description="Total count of incoming HTTP requests handled by the API",
        unit="1",
    )
    _http_request_duration_seconds = meter.create_histogram(
        name="devmind_http_request_duration_seconds",
        description="Duration of incoming HTTP requests in seconds",
        unit="s",
    )
    _worker_jobs_total = meter.create_counter(
        name="devmind_worker_jobs_total",
        description="Total count of background analysis and ingestion jobs processed",
        unit="1",
    )
    _worker_job_duration_seconds = meter.create_histogram(
        name="devmind_worker_job_duration_seconds",
        description="Duration of background worker jobs in seconds",
        unit="s",
    )
    _llm_requests_total = meter.create_counter(
        name="devmind_llm_requests_total",
        description="Total count of LLM generation and embedding calls",
        unit="1",
    )
    _llm_tokens_total = meter.create_counter(
        name="devmind_llm_tokens_total",
        description="Total tokens consumed by LLM calls (input and output)",
        unit="1",
    )
    _llm_latency_seconds = meter.create_histogram(
        name="devmind_llm_latency_seconds",
        description="Latency of LLM calls in seconds",
        unit="s",
    )
    _queue_depth = meter.create_up_down_counter(
        name="devmind_queue_depth",
        description="Estimated depth of active Celery background queues",
        unit="1",
    )

    logger.debug("OpenTelemetry initialized with resource %s", resource.attributes)


def get_tracer(name: str = "devmind") -> trace.Tracer:
    """Return an OpenTelemetry Tracer instance."""
    if _tracer_provider is not None:
        return _tracer_provider.get_tracer(name)
    return trace.get_tracer(name)


def get_meter(name: str = "devmind") -> metrics.Meter:
    """Return an OpenTelemetry Meter instance."""
    if _meter_provider is not None:
        return _meter_provider.get_meter(name)
    return metrics.get_meter(name)


@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    tracer_name: str = "devmind",
    record_exception: bool = True,
    set_status_on_exception: bool = True,
) -> Iterator[trace.Span]:
    """Context manager for tracing operations with automatic attribute scrubbing and error tracking."""
    tracer = get_tracer(tracer_name)
    clean_attrs = sanitize_span_attributes(attributes)

    # Correlate tenant and request context if not explicitly provided
    if "request_id" not in clean_attrs:
        req_id = request_id_ctx.get()
        if req_id:
            clean_attrs["request_id"] = req_id

    if "job_id" not in clean_attrs:
        job_id = job_id_ctx.get()
        if job_id:
            clean_attrs["job_id"] = job_id

    if "workspace_id" not in clean_attrs:
        ws_id = workspace_id_ctx.get()
        if ws_id:
            clean_attrs["workspace_id"] = ws_id

    if "project_id" not in clean_attrs:
        proj_id = project_id_ctx.get()
        if proj_id:
            clean_attrs["project_id"] = proj_id

    with tracer.start_as_current_span(name, attributes=clean_attrs) as span:
        try:
            yield span
        except Exception as exc:
            if record_exception:
                span.record_exception(exc)
            if set_status_on_exception:
                span.set_status(Status(StatusCode.ERROR, description=str(exc)))
            raise


# --- Metric Recording Functions ---


def record_http_request(
    method: str,
    route: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    """Record HTTP request metric counts and latency histogram."""
    attrs = {
        "http.method": method.upper(),
        "http.route": route,
        "http.status_code": status_code,
    }
    if _http_requests_total is not None:
        _http_requests_total.add(1, attrs)
    if _http_request_duration_seconds is not None:
        _http_request_duration_seconds.record(duration_seconds, attrs)


def record_worker_job(
    job_type: str,
    status: str,
    duration_seconds: float,
) -> None:
    """Record background worker task execution count and duration."""
    attrs = {
        "job.type": job_type,
        "job.status": status,
    }
    if _worker_jobs_total is not None:
        _worker_jobs_total.add(1, attrs)
    if _worker_job_duration_seconds is not None:
        _worker_job_duration_seconds.record(duration_seconds, attrs)


def record_llm_call(
    provider: str,
    model: str,
    task_name: str,
    status: str,
    input_tokens: int,
    output_tokens: int,
    duration_seconds: float,
) -> None:
    """Record LLM request metrics, token consumption, and latency."""
    base_attrs = {
        "llm.provider": provider,
        "llm.model": model,
        "llm.task": task_name,
        "llm.status": status,
    }
    if _llm_requests_total is not None:
        _llm_requests_total.add(1, base_attrs)
    if _llm_latency_seconds is not None:
        _llm_latency_seconds.record(duration_seconds, base_attrs)

    if _llm_tokens_total is not None:
        if input_tokens > 0:
            _llm_tokens_total.add(
                input_tokens,
                {"llm.provider": provider, "llm.model": model, "token_type": "input"},
            )
        if output_tokens > 0:
            _llm_tokens_total.add(
                output_tokens,
                {"llm.provider": provider, "llm.model": model, "token_type": "output"},
            )


def record_queue_depth(queue: str, delta: int) -> None:
    """Update queue depth up-down counter."""
    if _queue_depth is not None:
        _queue_depth.add(delta, {"queue": queue})


# --- Testing and Verification Helpers ---


def get_in_memory_spans() -> list[Any]:
    """Retrieve all spans captured by the in-memory exporter."""
    if _in_memory_span_exporter is not None:
        return list(_in_memory_span_exporter.get_finished_spans())
    return []


def reset_telemetry_for_testing() -> None:
    """Clear captured in-memory spans and re-initialize reader for test isolation."""
    global _in_memory_span_exporter
    if _in_memory_span_exporter is not None:
        _in_memory_span_exporter.clear()


def get_metrics_snapshot() -> dict[str, Any]:
    """Collect metric data points from the in-memory metric reader for inspection."""
    if _in_memory_metric_reader is None:
        return {}

    metric_data = _in_memory_metric_reader.get_metrics_data()
    if not metric_data:
        return {}

    snapshot: dict[str, Any] = {}
    for resource_metric in metric_data.resource_metrics:
        for scope_metric in resource_metric.scope_metrics:
            for metric in scope_metric.metrics:
                data_points = []
                for dp in metric.data.data_points:
                    dp_dict: dict[str, Any] = {
                        "attributes": dict(dp.attributes) if dp.attributes else {}
                    }
                    if hasattr(dp, "value"):
                        dp_dict["value"] = dp.value
                    elif hasattr(dp, "count"):
                        dp_dict["count"] = dp.count
                        dp_dict["sum"] = getattr(dp, "sum", None)
                    data_points.append(dp_dict)
                snapshot[metric.name] = data_points

    return snapshot


# --- FastAPI Telemetry Middleware ---


class TelemetryMiddleware(BaseHTTPMiddleware):
    """Middleware capturing OpenTelemetry server spans, correlation IDs, and HTTP metrics."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        method = request.method
        path = request.url.path
        req_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")

        span_attrs: dict[str, Any] = {
            "http.method": method,
            "http.url": path,
        }
        if req_id:
            span_attrs["request_id"] = req_id

        # Route matching if available
        route_path = path
        for r in request.app.routes:
            match, _ = r.matches(request.scope)
            if match.name == "FULL" and hasattr(r, "path"):
                route_path = str(r.path)
                break
        span_attrs["http.route"] = route_path

        start_time = time.perf_counter()
        tracer = get_tracer("devmind.http")

        with tracer.start_as_current_span(
            f"{method} {route_path}",
            attributes=sanitize_span_attributes(span_attrs),
        ) as span:
            span_ctx = span.get_span_context()
            if span_ctx.is_valid:
                trace_id_hex = f"{span_ctx.trace_id:032x}"
                span_id_hex = f"{span_ctx.span_id:016x}"
                request.state.trace_id = trace_id_hex
                request.state.span_id = span_id_hex

            try:
                response = await call_next(request)
                duration = time.perf_counter() - start_time
                status_code = response.status_code

                span.set_attribute("http.status_code", status_code)
                if status_code >= 500:
                    span.set_status(Status(StatusCode.ERROR, description=f"HTTP {status_code}"))
                else:
                    span.set_status(Status(StatusCode.OK))

                if span_ctx.is_valid:
                    response.headers["X-Trace-ID"] = f"{span_ctx.trace_id:032x}"

                record_http_request(
                    method=method,
                    route=route_path,
                    status_code=status_code,
                    duration_seconds=duration,
                )
                return response

            except Exception as exc:
                duration = time.perf_counter() - start_time
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, description=str(exc)))
                span.set_attribute("http.status_code", 500)

                record_http_request(
                    method=method,
                    route=route_path,
                    status_code=500,
                    duration_seconds=duration,
                )
                raise
