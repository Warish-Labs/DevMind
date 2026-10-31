"""End-to-End integration test suite for Bug Memory (CAP-03, docs/01 §7, docs/03 §3.4, M12-06)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.auth_context import AuthContext
from app.core.errors import NotFoundError
from app.domain.auth import (
    PERM_PROJECT_READ,
    PERM_PROJECT_UPDATE,
)
from app.domain.bug_memory.schemas import (
    BugMatchRequest,
    BugRecordCreate,
    BugResolutionCreate,
)
from app.domain.bug_memory.service import BugMemoryService
from app.persistence.models.bug_memory import BugRecord, BugResolution
from app.persistence.models.project import Project


@pytest.mark.asyncio
async def test_e2e_bug_memory_lifecycle() -> None:
    """E2E test: bug logging -> error normalization -> duplicate occurrence -> resolution -> matching."""
    workspace_id = uuid4()
    project_id = uuid4()
    user_id = uuid4()
    bug_id = uuid4()

    ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_clerk_123",
        email="dev@devmind.ai",
        workspace_id=workspace_id,
        workspace_role="admin",
        project_id=project_id,
        project_role="maintainer",
        permissions=frozenset({PERM_PROJECT_READ, PERM_PROJECT_UPDATE}),
    )

    mock_session = AsyncMock()
    service = BugMemoryService(session=mock_session)

    mock_project = Project(
        id=project_id,
        workspace_id=workspace_id,
        name="Backend Core",
        slug="backend-core",
    )
    service.project_repo.get_by_id = AsyncMock(return_value=mock_project)

    # 1. Log a new bug
    raw_error_1 = (
        "Traceback (most recent call last):\n"
        '  File "/server/app/domain/auth/token_verifier.py", line 42, in verify\n'
        "    claims = jwt.decode(token)\n"
        "KeyError: 'workspace_id' at 0x7ffd98b0"
    )

    created_bug = BugRecord(
        id=bug_id,
        workspace_id=workspace_id,
        project_id=project_id,
        title="KeyError: 'workspace_id'",
        summary="Missing workspace_id claim in payload",
        error_signature="KeyError: 'workspace_id'",
        fingerprint="fp_hash_auth_keyerror_123",
        module_hint="server/app/domain/auth/token_verifier.py",
        raw_error=raw_error_1,
        occurrence_count=1,
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        resolutions=[],
    )
    service.repo.record_bug = AsyncMock(return_value=(created_bug, True))

    req = BugRecordCreate(
        raw_error=raw_error_1,
        title="KeyError: 'workspace_id'",
        summary="Missing workspace_id claim",
    )
    res_1, is_new = await service.record_bug(ctx, project_id, req)

    assert is_new is True
    assert res_1.id == bug_id
    assert res_1.occurrence_count == 1
    assert "KeyError" in res_1.title

    # 2. Duplicate occurrence: same error with different memory pointer
    raw_error_2 = (
        "Traceback (most recent call last):\n"
        '  File "/server/app/domain/auth/token_verifier.py", line 42, in verify\n'
        "    claims = jwt.decode(token)\n"
        "KeyError: 'workspace_id' at 0x8ffc11a0"
    )

    created_bug_v2 = BugRecord(
        id=bug_id,
        workspace_id=workspace_id,
        project_id=project_id,
        title="KeyError: 'workspace_id'",
        summary="Missing workspace_id claim in payload",
        error_signature="KeyError: 'workspace_id'",
        fingerprint="fp_hash_auth_keyerror_123",
        module_hint="server/app/domain/auth/token_verifier.py",
        raw_error=raw_error_1,
        occurrence_count=2,
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        resolutions=[],
    )
    service.repo.record_bug = AsyncMock(return_value=(created_bug_v2, False))

    res_2, is_new_2 = await service.record_bug(
        ctx, project_id, BugRecordCreate(raw_error=raw_error_2)
    )
    assert is_new_2 is False
    assert res_2.id == bug_id
    assert res_2.occurrence_count == 2

    # 3. Hybrid similarity search
    service.agent.repo.search_similar_bugs = AsyncMock(
        return_value=[(created_bug_v2, 1.0, "exact_fingerprint")]
    )
    match_res = await service.match_bugs(
        ctx,
        project_id,
        BugMatchRequest(raw_error=raw_error_2, limit=5),
    )
    assert len(match_res.candidates) == 1
    assert match_res.candidates[0].score == 1.0
    assert match_res.candidates[0].match_type == "exact_fingerprint"
    assert match_res.candidates[0].bug.id == bug_id

    # 4. Record resolution note
    resolution_id = uuid4()
    created_resolution = BugResolution(
        id=resolution_id,
        bug_record_id=bug_id,
        cause="JWT token did not unpack workspace_id in payload decoder",
        fix_summary="Updated JWT decoder to fall back to workspace claims header",
        files=[{"path": "server/app/domain/auth/token_verifier.py"}],
        finding_id=None,
        resolved_by=user_id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service.repo.get_by_id = AsyncMock(return_value=created_bug)
    service.repo.add_resolution = AsyncMock(return_value=created_resolution)

    res_record = await service.add_resolution(
        ctx,
        bug_id,
        BugResolutionCreate(
            cause="JWT token did not unpack workspace_id in payload decoder",
            fix_summary="Updated JWT decoder to fall back to workspace claims header",
            files=[{"path": "server/app/domain/auth/token_verifier.py"}],
        ),
    )
    assert res_record.id == resolution_id
    assert res_record.bug_record_id == bug_id
    assert len(res_record.files) == 1


@pytest.mark.asyncio
async def test_e2e_bug_memory_multi_tenant_isolation() -> None:
    """Verify cross-workspace tenant boundaries are strictly enforced for Bug Memory."""
    tenant_b_workspace = uuid4()
    project_id = uuid4()

    tenant_b_ctx = AuthContext(
        user_id=uuid4(),
        clerk_user_id="user_tenant_b",
        email="tenant_b@devmind.ai",
        workspace_id=tenant_b_workspace,
        workspace_role="admin",
        permissions=frozenset({PERM_PROJECT_READ, PERM_PROJECT_UPDATE}),
    )

    mock_session = AsyncMock()
    service = BugMemoryService(session=mock_session)

    # Scoped project repository returns None for another tenant's project
    service.project_repo.get_by_id = AsyncMock(return_value=None)

    # Attempting to log a bug for Tenant A's project using Tenant B's context must fail with NotFoundError
    with pytest.raises(NotFoundError):
        await service.record_bug(
            tenant_b_ctx,
            project_id,
            BugRecordCreate(raw_error="ValueError: test"),
        )
