"""Unit tests for Deployment Log Parser and Secret Redaction Pre-filter (docs/01 CAP-07, docs/07 §6)."""

from __future__ import annotations

from app.analysis.log_parser import LogParser, ParsedDeploymentLog


def test_log_parser_redaction_secrets_and_credentials() -> None:
    """Verify that credentials, tokens, and database passwords are redacted prior to analysis."""
    raw_log = """
2026-11-01T10:00:00Z [info] Starting application container on Render...
2026-11-01T10:00:01Z [error] Connecting to postgresql://postgres:SuperSecretPassword123@dpg-host.oregon-postgres.render.com/devmind
2026-11-01T10:00:02Z [error] Failed auth with CLERK_SECRET_KEY=my_dummy_clerk_secret_key_12345
2026-11-01T10:00:03Z [error] Webhook verification failed with whsec_1234567890abcdef1234567890abcdef
2026-11-01T10:00:04Z [error] GitHub API call failed using token ghp_1234567890abcdef1234567890abcdef12
2026-11-01T10:00:05Z [error] Anthropic client failed with sk-ant-api03-1234567890abcdef1234567890abcdef-1234
KeyError: 'DEVMIND_LLM_PRIMARY_API_KEY'
"""
    parsed: ParsedDeploymentLog = LogParser.redact_and_parse(raw_log)

    # Asserts that no raw secret strings appear in the parsed result
    assert "SuperSecretPassword123" not in parsed.redacted_text
    assert "my_dummy_clerk_secret_key_12345" not in parsed.redacted_text
    assert "whsec_1234567890abcdef1234567890abcdef" not in parsed.redacted_text
    assert "ghp_1234567890abcdef1234567890abcdef12" not in parsed.redacted_text
    assert "sk-ant-api03-1234567890abcdef" not in parsed.redacted_text

    # Asserts redaction tokens are inserted
    assert "[REDACTED:" in parsed.redacted_text
    assert parsed.redaction_count >= 5

    # Asserts failure classification
    assert parsed.failure_category == "missing_env_var"
    assert "DEVMIND_LLM_PRIMARY_API_KEY" in parsed.referenced_env_vars
    assert parsed.confidence >= 0.90


def test_log_parser_missing_env_var_pydantic() -> None:
    """Verify parsing Pydantic Settings missing environment variable validation failure."""
    raw_log = """
INFO:     Started server process [1]
INFO:     Waiting for application startup.
ERROR:    Traceback (most recent call last):
  File "/app/server/app/main.py", line 45, in create_app
    settings = Settings()
  File "/usr/local/lib/python3.12/site-packages/pydantic_settings/main.py", line 180, in __init__
    super().__init__(**values)
  File "/usr/local/lib/python3.12/site-packages/pydantic/main.py", line 214, in __init__
    validated_self = self.__pydantic_validator__.validate_python(data, self_instance=self)
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
DEVMIND_DATABASE_URL
  Field required [type=missing, input_value={}, input_type=dict]
ERROR:    Application startup failed. Exiting.
"""
    parsed = LogParser.redact_and_parse(
        raw_log, environment="production", service_name="devmind-api"
    )

    assert parsed.failure_category == "missing_env_var"
    assert "DEVMIND_DATABASE_URL" in parsed.referenced_env_vars
    assert "Missing required environment variable" in parsed.summary
    assert "DEVMIND_DATABASE_URL" in parsed.probable_cause
    assert "Render / Vercel" in parsed.recommended_action
    assert parsed.primary_log_line is not None
    assert parsed.confidence >= 0.95

    # Check code reference extraction
    project_refs = [r for r in parsed.referenced_files if r["is_project_code"]]
    assert len(project_refs) >= 1
    assert any("/app/server/app/main.py" in r["path"] for r in project_refs)


def test_log_parser_database_migration_failed() -> None:
    """Verify parsing Alembic and SQL schema migration errors."""
    raw_log = """
[alembic.runtime.migration] Context impl PostgresqlImpl.
[alembic.runtime.migration] Will assume transactional DDL.
FAILED: alembic.util.exc.CommandError: Can't locate revision identified by '0015_bug_memory'
Traceback (most recent call last):
  File "/usr/local/bin/alembic", line 8, in <module>
    sys.exit(main())
"""
    parsed = LogParser.redact_and_parse(raw_log)

    assert parsed.failure_category == "database_migration_failed"
    assert "0015_bug_memory" in parsed.summary
    assert "schema mismatch" in parsed.probable_cause
    assert "alembic upgrade head" in parsed.recommended_action
    assert parsed.confidence >= 0.90


def test_log_parser_dependency_mismatch() -> None:
    """Verify parsing ModuleNotFoundError and missing package imports."""
    raw_log = """
==> Starting service with 'uvicorn app.main:create_app --factory'
Traceback (most recent call last):
  File "/app/server/app/main.py", line 12, in <module>
    import some_missing_package
ModuleNotFoundError: No module named 'some_missing_package'
Container process exited with status 1
"""
    parsed = LogParser.redact_and_parse(raw_log)

    assert parsed.failure_category == "dependency_mismatch"
    assert "some_missing_package" in parsed.summary
    assert "some_missing_package" in parsed.probable_cause
    assert "pyproject.toml" in parsed.recommended_action
    assert parsed.confidence >= 0.90


def test_log_parser_port_binding_failed() -> None:
    """Verify parsing port binding conflicts."""
    raw_log = """
2026-11-01T10:00:00Z [info] Starting web server on 0.0.0.0:8000
Traceback (most recent call last):
  File "server.py", line 55, in start
    sock.bind(('0.0.0.0', 8000))
OSError: [Errno 98] Address already in use: 8000
"""
    parsed = LogParser.redact_and_parse(raw_log)

    assert parsed.failure_category == "port_binding_failed"
    assert "Port binding conflict" in parsed.summary
    assert "already in use" in parsed.probable_cause
    assert "$PORT" in parsed.recommended_action


def test_log_parser_build_compilation_failed() -> None:
    """Verify parsing Next.js and TypeScript build failures."""
    raw_log = """
> devmind-client@0.1.0 build
> next build

./app/page.tsx:14:22
Type error: Property 'unresolvedProp' does not exist on type 'UserProfile'.
   12 |   return (
   13 |     <div>
 > 14 |       <h1>{user.unresolvedProp}</h1>
      |                 ^
   15 |     </div>
   16 |   );
Failed to compile.
npm run build exited with code 1
"""
    parsed = LogParser.redact_and_parse(raw_log)

    assert parsed.failure_category == "build_compilation_failed"
    assert "Build compilation error" in parsed.summary
    assert "pnpm build" in parsed.recommended_action or "typecheck" in parsed.recommended_action


def test_log_parser_timeout_failure() -> None:
    """Verify parsing service startup timeout."""
    raw_log = """
==> Deploying service...
==> Waiting for container to report healthy status...
[error] Worker timeout: healthcheck probe to /healthz failed after 60000ms
Container failed to start before allocation timeout.
"""
    parsed = LogParser.redact_and_parse(raw_log)

    assert parsed.failure_category == "timeout"
    assert "timeout" in parsed.summary.lower()
    assert parsed.confidence >= 0.85


def test_log_parser_empty_and_insufficient_log() -> None:
    """Verify safe handling of empty or blank input."""
    parsed = LogParser.redact_and_parse("")
    assert parsed.failure_category == "unknown"
    assert parsed.confidence == 0.0
    assert "Empty or insufficient" in parsed.summary


def test_log_parser_deterministic_fingerprint() -> None:
    """Verify that identical failure logs produce identical deterministic fingerprints."""
    log_sample_a = """
Traceback (most recent call last):
  File "app.py", line 10, at 0x7ffd1234
KeyError: 'DATABASE_URL'
"""
    log_sample_b = """
Traceback (most recent call last):
  File "app.py", line 10, at 0x7ffdbbbb
KeyError: 'DATABASE_URL'
"""
    parsed_a = LogParser.redact_and_parse(log_sample_a)
    parsed_b = LogParser.redact_and_parse(log_sample_b)

    assert parsed_a.fingerprint == parsed_b.fingerprint
    assert len(parsed_a.fingerprint) == 64
