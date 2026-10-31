"""Unit and tenant isolation tests for Bug Memory (M12-01, docs/01 CAP-03, docs/03 §3.4, docs/05 §6.6).

Verifies:
1. ErrorNormalizer deterministic sanitization (scrubbing UUIDs, timestamps, memory addresses, absolute paths).
2. ErrorNormalizer stack trace parsing across Python and JavaScript/TypeScript error traces.
3. Signature determinism: identical logical errors across environments produce the exact same fingerprint.
4. Error uniqueness: distinct exception types or root causes yield different fingerprints.
5. BugRecord persistence models and BugRecordRepository upsert, deduplication, and occurrence counter.
6. BugResolution persistence and linking to BugRecord and Finding.
7. Multi-tenant isolation: Tenant B cannot read or resolve Tenant A's bug records.
8. Context validation: repository rejects non-AuthContext/SystemContext callers.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.analysis.error_normalizer import ErrorNormalizer, NormalizedError
from app.core.auth_context import AuthContext
from app.persistence.models.bug_memory import BugRecord
from app.persistence.repositories.bug_record_repo import BugRecordRepository

# ---------------------------------------------------------------------------
# 1. Error Normalizer Unit Tests
# ---------------------------------------------------------------------------


def test_error_normalizer_python_trace() -> None:
    """Verifies that Python tracebacks strip ephemeral paths, memory pointers, and UUIDs."""
    raw_trace = """Traceback (most recent call last):
  File "/home/ubuntu/Projects/DevMind/server/app/main.py", line 124, in handle_request
    response = await router.dispatch(request)
  File "/home/ubuntu/Projects/DevMind/server/app/api/v1/users.py", line 89, in get_user
    user = db.lookup(user_id="0192b1c0-3d1e-7a3b-9c11-5f6a7a8b9c01", ctx=<Context object at 0x7fa3b1c0a890>)
  File "/home/ubuntu/Projects/DevMind/server/app/domain/users/service.py", line 45, in lookup
    raise KeyError("User '0192b1c0-3d1e-7a3b-9c11-5f6a7a8b9c01' not found in cache")
KeyError: "User '0192b1c0-3d1e-7a3b-9c11-5f6a7a8b9c01' not found in cache"
"""
    norm: NormalizedError = ErrorNormalizer.normalize(raw_trace)

    assert norm.exception_type == "KeyError"
    assert norm.module_hint == "server/app/main.py"
    assert len(norm.top_frames) == 3
    assert norm.fingerprint and len(norm.fingerprint) == 64
    # Ensure ephemeral UUID and memory address were scrubbed from normalized signature
    assert "0192b1c0-3d1e-7a3b-9c11-5f6a7a8b9c01" not in norm.normalized_signature
    assert "0x7fa3b1c0a890" not in norm.normalized_signature
    assert "<uuid>" in norm.normalized_signature or "<value>" in norm.normalized_signature
    assert "<hex>" in norm.raw_preview


def test_error_normalizer_js_ts_trace() -> None:
    """Verifies that JavaScript/TypeScript error traces extract exception type and app frames."""
    raw_js = """TypeError: Cannot read properties of undefined (reading 'access_token')
    at authenticate (src/auth/session.ts:42:15)
    at processTicksAndRejections (node:internal/process/task_queues:95:5)
    at async handler (packages/client/src/routes/login.ts:88:20)
"""
    norm: NormalizedError = ErrorNormalizer.normalize(raw_js)

    assert norm.exception_type == "TypeError"
    assert norm.module_hint == "src/auth/session.ts"
    assert len(norm.fingerprint) == 64
    assert any("session.ts:authenticate" in f for f in norm.top_frames)


def test_error_normalizer_determinism_across_environments() -> None:
    """Two error instances with different local home dirs, timestamps, and request IDs must yield the SAME fingerprint."""
    env1_trace = """Traceback (most recent call last):
  File "/Users/alice/repo/server/app/auth/guard.py", line 55, in check_permission
    raise PermissionError("Denied at 2026-10-31T08:15:30Z for req 11111111-2222-3333-4444-555555555555")
PermissionError: Denied at 2026-10-31T08:15:30Z for req 11111111-2222-3333-4444-555555555555
"""
    env2_trace = """Traceback (most recent call last):
  File "/var/task/server/app/auth/guard.py", line 55, in check_permission
    raise PermissionError("Denied at 2026-10-31T11:45:00Z for req 99999999-8888-7777-6666-000000000000")
PermissionError: Denied at 2026-10-31T11:45:00Z for req 99999999-8888-7777-6666-000000000000
"""
    norm1 = ErrorNormalizer.normalize(env1_trace)
    norm2 = ErrorNormalizer.normalize(env2_trace)

    assert norm1.exception_type == norm2.exception_type
    assert norm1.fingerprint == norm2.fingerprint


def test_error_normalizer_distinct_errors_produce_different_fingerprints() -> None:
    """Distinct exception types or call sites must yield different fingerprints."""
    trace_a = """Traceback (most recent call last):
  File "server/app/db/session.py", line 12, in connect
    raise ConnectionRefusedError("Database host unreachable at 127.0.0.1:5432")
ConnectionRefusedError: Database host unreachable
"""
    trace_b = """Traceback (most recent call last):
  File "server/app/db/session.py", line 12, in connect
    raise TimeoutError("Connection timed out waiting for lock")
TimeoutError: Connection timed out
"""
    norm_a = ErrorNormalizer.normalize(trace_a)
    norm_b = ErrorNormalizer.normalize(trace_b)

    assert norm_a.fingerprint != norm_b.fingerprint


def test_error_normalizer_empty_and_fallback() -> None:
    """Empty or unformatted strings fallback safely to UnknownError."""
    norm_empty = ErrorNormalizer.normalize("")
    assert norm_empty.exception_type == "UnknownError"
    assert norm_empty.fingerprint

    norm_plain = ErrorNormalizer.normalize("Something went catastrophically wrong with worker task")
    assert norm_plain.exception_type in ("Error", "UnknownError")
    assert norm_plain.clean_message == "Something went catastrophically wrong with worker task"


# ---------------------------------------------------------------------------
# 2. Repository & Tenancy Isolation Tests
# ---------------------------------------------------------------------------


def _make_context(
    workspace_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> AuthContext:
    wid = workspace_id or uuid.uuid4()
    uid = user_id or uuid.uuid4()
    return AuthContext(
        user_id=uid,
        clerk_user_id="user_test_clerk",
        email="dev@example.com",
        workspace_id=wid,
        permissions=frozenset(["project:read", "project:write"]),
    )


@pytest.mark.asyncio
async def test_bug_record_repo_create_new_record() -> None:
    """New raw error generates a fresh BugRecord with occurrence_count=1."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    # Existing query returns None (new bug)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    repo = BugRecordRepository(session=mock_session)
    wid = uuid.uuid4()
    pid = uuid.uuid4()
    ctx = _make_context(workspace_id=wid)

    raw_error = "ValueError: Invalid tenant scope provided for operation"
    record, is_new = await repo.record_bug(
        ctx,
        workspace_id=wid,
        project_id=pid,
        raw_error=raw_error,
        title="Invalid tenant scope",
    )

    assert is_new is True
    assert record.workspace_id == wid
    assert record.project_id == pid
    assert record.occurrence_count == 1
    assert record.fingerprint
    assert record.title == "Invalid tenant scope"
    assert mock_session.add.called
    assert mock_session.flush.called


@pytest.mark.asyncio
async def test_bug_record_repo_upsert_existing_increments_counter() -> None:
    """Recording the same error signature increments occurrence_count and updates last_seen_at."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    existing_record = BugRecord(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        fingerprint="d" * 64,
        error_signature="ValueError: Invalid tenant scope",
        title="Existing Error",
        occurrence_count=3,
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_record
    mock_session.execute.return_value = mock_result

    repo = BugRecordRepository(session=mock_session)
    ctx = _make_context(workspace_id=existing_record.workspace_id)

    record, is_new = await repo.record_bug(
        ctx,
        workspace_id=existing_record.workspace_id,
        project_id=existing_record.project_id,
        raw_error="ValueError: Invalid tenant scope",
    )

    assert is_new is False
    assert record.occurrence_count == 4
    assert mock_session.flush.called
    # add() should not be called for an existing record
    assert not mock_session.add.called


@pytest.mark.asyncio
async def test_bug_record_repo_add_resolution() -> None:
    """Attaches a BugResolution record to a known BugRecord."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()

    bug_id = uuid.uuid4()
    wid = uuid.uuid4()
    ctx = _make_context(workspace_id=wid)

    fake_record = BugRecord(
        id=bug_id,
        workspace_id=wid,
        project_id=uuid.uuid4(),
        fingerprint="a" * 64,
        error_signature="TypeError: null check",
        title="Null pointer bug",
    )

    repo = BugRecordRepository(session=mock_session)
    repo.get_by_id = AsyncMock(return_value=fake_record)

    resolution = await repo.add_resolution(
        ctx,
        bug_record_id=bug_id,
        cause="Missing optional chaining on payload.user",
        fix_summary="Added user?.id null check before accessing properties",
        files=[{"path": "server/app/api/auth.py", "lines": "45-50"}],
        resolved_by=ctx.user_id,
    )

    assert resolution.bug_record_id == bug_id
    assert resolution.cause == "Missing optional chaining on payload.user"
    assert resolution.fix_summary == "Added user?.id null check before accessing properties"
    assert len(resolution.files) == 1
    assert resolution.resolved_by == ctx.user_id
    assert mock_session.add.called


@pytest.mark.asyncio
async def test_bug_record_repo_cross_tenant_isolation() -> None:
    """Tenant B actor querying Tenant A bug record is constrained by workspace predicate."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    repo = BugRecordRepository(session=mock_session)

    tenant_b_wid = uuid.uuid4()
    tenant_b_ctx = _make_context(workspace_id=tenant_b_wid)

    target_bug_id = uuid.uuid4()
    record = await repo.get_by_id(tenant_b_ctx, target_bug_id)
    assert record is None

    # The executed SQL statement must be scoped to tenant B's workspace_id
    stmt = mock_session.execute.call_args[0][0]
    compiled_str = str(stmt)
    assert "bug_records.workspace_id = :workspace_id_1" in compiled_str


@pytest.mark.asyncio
async def test_bug_record_repo_invalid_context_rejection() -> None:
    """Repository operations without AuthContext or SystemContext must raise TypeError."""
    mock_session = AsyncMock()
    repo = BugRecordRepository(session=mock_session)

    with pytest.raises(TypeError, match="require an AuthContext or SystemContext"):
        await repo.get_by_id(None, uuid.uuid4())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_bug_record_repo_delete() -> None:
    """Deleting a bug record invokes session.delete."""
    mock_session = AsyncMock()
    mock_session.delete = AsyncMock()
    mock_session.flush = AsyncMock()

    bug_id = uuid.uuid4()
    fake_record = BugRecord(id=bug_id, workspace_id=uuid.uuid4(), project_id=uuid.uuid4())
    repo = BugRecordRepository(session=mock_session)
    repo.get_by_id = AsyncMock(return_value=fake_record)

    ctx = _make_context(workspace_id=fake_record.workspace_id)
    deleted = await repo.delete_bug_record(ctx, bug_id)

    assert deleted is True
    assert mock_session.delete.called
    assert mock_session.flush.called
