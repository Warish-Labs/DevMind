"""Tests for OpenTelemetry tracing, metrics, structured log correlation, and error reporting (M10-02)."""

import json
import logging

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.error_reporting import init_error_reporting, report_exception
from app.core.logging import JSONFormatter
from app.core.settings import Settings
from app.core.telemetry import (
    TelemetryMiddleware,
    get_in_memory_spans,
    get_metrics_snapshot,
    init_telemetry,
    record_llm_call,
    record_worker_job,
    reset_telemetry_for_testing,
    sanitize_span_attributes,
    trace_span,
)


@pytest.fixture(autouse=True)
def setup_test_telemetry() -> None:
    """Initialize clean telemetry in-memory for each test."""
    test_settings = Settings(
        env="test",
        otel_enabled=True,
        otel_service_name="devmind-test",
        otel_exporter="memory",
        sentry_dsn=None,
    )
    init_telemetry(test_settings)
    init_error_reporting(test_settings)
    reset_telemetry_for_testing()
    # Re-enable any devmind loggers disabled by import-linter static analysis
    for name in list(logging.root.manager.loggerDict.keys()):
        if name.startswith("devmind"):
            logging.getLogger(name).disabled = False


def test_sanitize_span_attributes_drops_forbidden_keys() -> None:
    """Verify ADR-047 / Rule 5 invariant: zero prompts, source code, or secrets in attributes."""
    dirty_attrs = {
        "service.name": "devmind-api",
        "prompt": "SELECT * FROM users; IGNORE PREVIOUS INSTRUCTIONS",
        "user_prompt": "Analyze this repo",
        "completion": "def secret_hack(): pass",
        "source_code": "def parse_auth(): return True",
        "raw_payload": "{'token': 'secret'}",
        "password": "super-secret-password",
        "token": "sk_live_123456789012345678",
        "http.status_code": 200,
        "tenant_id": "018f-test-uuid",
        "safe_message": "Bearer sk_test_123456789012345678 should be redacted",
    }

    sanitized = sanitize_span_attributes(dirty_attrs)

    assert "service.name" in sanitized
    assert "http.status_code" in sanitized
    assert "tenant_id" in sanitized
    assert sanitized["http.status_code"] == 200

    # Ensure prohibited payload keys are dropped
    assert "prompt" not in sanitized
    assert "user_prompt" not in sanitized
    assert "completion" not in sanitized
    assert "source_code" not in sanitized
    assert "raw_payload" not in sanitized
    assert "password" not in sanitized
    assert "token" not in sanitized

    # Ensure value redaction applied to allowed keys
    assert "sk_test_" not in sanitized["safe_message"]
    assert "[REDACTED" in sanitized["safe_message"]


def test_trace_span_context_manager() -> None:
    """Verify trace_span correctly opens, decorates, and closes a span with clean attributes."""
    with trace_span("test.operation", attributes={"operation_id": "op-42", "token": "secret"}) as span:
        assert span.is_recording()

    spans = get_in_memory_spans()
    assert len(spans) >= 1
    test_span = next(s for s in spans if s.name == "test.operation")
    assert test_span.name == "test.operation"
    assert test_span.attributes.get("operation_id") == "op-42"
    assert "token" not in test_span.attributes


def test_log_correlation_with_trace_and_span_ids() -> None:
    """Verify JSONFormatter automatically injects trace_id and span_id into log records."""
    formatter = JSONFormatter()
    logger = logging.getLogger("test.correlation")
    logger.setLevel(logging.INFO)

    log_output = None

    with trace_span("correlated.task"):
        record = logger.makeRecord(
            name="test.correlation",
            level=logging.INFO,
            fn="test.py",
            lno=1,
            msg="Processing correlated telemetry item",
            args=(),
            exc_info=None,
        )
        log_output = formatter.format(record)

    assert log_output is not None
    parsed = json.loads(log_output)
    assert "trace_id" in parsed
    assert len(parsed["trace_id"]) == 32  # W3C 32-hex trace ID
    assert "span_id" in parsed
    assert len(parsed["span_id"]) == 16  # W3C 16-hex span ID
    assert parsed["message"] == "Processing correlated telemetry item"


def test_telemetry_middleware_records_spans_and_metrics() -> None:
    """Verify TelemetryMiddleware creates HTTP spans, sets status, X-Trace-ID header, and records metrics."""
    app = FastAPI()
    app.add_middleware(TelemetryMiddleware)

    @app.get("/api/v1/test/items/{item_id}")
    async def get_item(item_id: str) -> dict[str, str]:
        return {"item": item_id}

    @app.get("/api/v1/test/error")
    async def get_error() -> None:
        raise HTTPException(status_code=500, detail="Server failure")

    client = TestClient(app)

    # 1. Successful request
    resp = client.get("/api/v1/test/items/42", headers={"X-Request-ID": "req-telemetry-1"})
    assert resp.status_code == 200
    assert "X-Trace-ID" in resp.headers
    assert len(resp.headers["X-Trace-ID"]) == 32

    # 2. Error request
    resp_err = client.get("/api/v1/test/error")
    assert resp_err.status_code == 500

    spans = get_in_memory_spans()
    http_spans = [s for s in spans if s.name.startswith("GET")]
    assert len(http_spans) >= 2

    success_span = next(s for s in http_spans if "items" in s.name)
    assert success_span.attributes.get("http.status_code") == 200
    assert success_span.attributes.get("http.method") == "GET"
    assert success_span.attributes.get("request_id") == "req-telemetry-1"

    # Check metrics recorded
    metrics_snapshot = get_metrics_snapshot()
    assert "devmind_http_requests_total" in metrics_snapshot
    data_points = metrics_snapshot["devmind_http_requests_total"]
    assert any(dp["attributes"].get("http.status_code") == 200 for dp in data_points)
    assert any(dp["attributes"].get("http.status_code") == 500 for dp in data_points)


def test_worker_job_metrics_recording() -> None:
    """Verify background worker job executions record counts and duration metrics."""
    record_worker_job(job_type="embed_chunks", status="succeeded", duration_seconds=0.25)
    record_worker_job(job_type="security_review", status="failed", duration_seconds=1.42)

    snapshot = get_metrics_snapshot()
    assert "devmind_worker_jobs_total" in snapshot
    data_points = snapshot["devmind_worker_jobs_total"]

    embed_dp = next(
        dp
        for dp in data_points
        if dp["attributes"].get("job.type") == "embed_chunks"
        and dp["attributes"].get("job.status") == "succeeded"
    )
    assert embed_dp["value"] >= 1

    sec_dp = next(
        dp
        for dp in data_points
        if dp["attributes"].get("job.type") == "security_review"
        and dp["attributes"].get("job.status") == "failed"
    )
    assert sec_dp["value"] >= 1


def test_llm_metrics_recording() -> None:
    """Verify LLM generation calls record metrics, token consumption, and duration."""
    record_llm_call(
        provider="gemini",
        model="gemini-1.5-flash",
        task_name="summarize",
        status="success",
        input_tokens=150,
        output_tokens=50,
        duration_seconds=0.85,
    )

    snapshot = get_metrics_snapshot()
    assert "devmind_llm_requests_total" in snapshot
    assert "devmind_llm_tokens_total" in snapshot

    req_dps = snapshot["devmind_llm_requests_total"]
    gemini_req = next(
        dp
        for dp in req_dps
        if dp["attributes"].get("llm.provider") == "gemini"
        and dp["attributes"].get("llm.task") == "summarize"
    )
    assert gemini_req["value"] >= 1

    tok_dps = snapshot["devmind_llm_tokens_total"]
    input_tok = next(
        dp
        for dp in tok_dps
        if dp["attributes"].get("llm.provider") == "gemini"
        and dp["attributes"].get("token_type") == "input"
    )
    assert input_tok["value"] == 150

    output_tok = next(
        dp
        for dp in tok_dps
        if dp["attributes"].get("llm.provider") == "gemini"
        and dp["attributes"].get("token_type") == "output"
    )
    assert output_tok["value"] == 50


def test_error_reporting_fallback_and_redaction() -> None:
    """Verify error reporting without Sentry falls back gracefully and scrubs sensitive context."""
    test_logger = logging.getLogger("devmind.errors")
    records: list[str] = []

    class TestCaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(self.format(record))

    handler = TestCaptureHandler()
    test_logger.addHandler(handler)
    try:
        report_exception(
            exc=ValueError("Simulated worker failure"),
            context={
                "task": "analysis",
                "secret_key": "sk_live_123456789012345678",
                "token": "secret-token",
                "prompt": "Ignore all instructions",
                "job_id": "018f-job-uuid",
            },
        )
    finally:
        test_logger.removeHandler(handler)

    assert len(records) >= 1
    logged_text = " ".join(records)
    # Context should drop forbidden keys and redact secret keys
    assert "Simulated worker failure" in logged_text
    assert "018f-job-uuid" in logged_text
    assert "sk_live_" not in logged_text
    assert "secret-token" not in logged_text
    assert "Ignore all instructions" not in logged_text
