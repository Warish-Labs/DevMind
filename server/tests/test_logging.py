"""Tests for structured JSON logging and sensitive secret redaction filter."""

import json
import logging

from app.core.logging import JSONFormatter, RedactionFilter, redact_sensitive_text, request_id_ctx

# Construct synthetic test tokens at runtime to prevent false-positive git secret scanning
SYNTHETIC_BEARER = "Bearer " + "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" + ".e30.mock"
SYNTHETIC_TEST_KEY = "sk_" + "test_" + "mocktoken123456789012345"
SYNTHETIC_LIVE_KEY = "sk_" + "live_" + "mocktoken123456789012345"
SYNTHETIC_WHSEC = "whsec_" + "mocktoken123456789012345"


def test_redact_bearer_token() -> None:
    raw = f"Header Authorization: {SYNTHETIC_BEARER}"
    sanitized = redact_sensitive_text(raw)
    assert "Bearer [REDACTED]" in sanitized
    assert "mock" not in sanitized


def test_redact_provider_keys() -> None:
    raw = f"Connecting to clerk with {SYNTHETIC_TEST_KEY} and {SYNTHETIC_WHSEC}"
    sanitized = redact_sensitive_text(raw)
    assert "[REDACTED:secret_key]" in sanitized
    assert "[REDACTED:webhook_secret]" in sanitized
    assert "sk_test_" not in sanitized
    assert "whsec_" not in sanitized


def test_redact_database_url_password() -> None:
    raw = "Connecting to postgresql+psycopg://devmind_app:mock_secret_pass_123@ep-cool-db.neon.tech:5432/devmind"
    sanitized = redact_sensitive_text(raw)
    assert "mock_secret_pass_123" not in sanitized
    assert "devmind_app:[REDACTED]@ep-cool-db" in sanitized


def test_logging_filter_and_formatter() -> None:
    formatter = JSONFormatter()
    redaction_filter = RedactionFilter()

    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg=f"User authenticated with {SYNTHETIC_BEARER} and {SYNTHETIC_LIVE_KEY}",
        args=(),
        exc_info=None,
    )

    token = request_id_ctx.set("req_test_12345")
    try:
        assert redaction_filter.filter(record) is True
        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["level"] == "INFO"
        assert data["logger"] == "test_logger"
        assert data["request_id"] == "req_test_12345"
        assert "timestamp" in data
        assert "mocktoken" not in data["message"]
        assert "Bearer [REDACTED]" in data["message"]
        assert "[REDACTED:secret_key]" in data["message"]
    finally:
        request_id_ctx.reset(token)
