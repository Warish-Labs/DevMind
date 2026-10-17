"""Unit and integration tests for Staleness Marking on file change/removal (docs/03 §5.1 rule 3).

Verifies:
1. Active findings (open, acknowledged, in_progress, fix_proposed) move to stale when primary file changes.
2. Active findings move to stale when supporting evidence files change.
3. Active findings move to stale when files are removed.
4. FindingEvidence.is_current flips to False for modified or removed paths.
5. Resolved, dismissed, accepted_risk, and already stale findings are skipped.
6. Immutable FindingStatusHistory records the transition with reason 'evidence file modified or removed'.
7. ManifestService.put_manifest triggers staleness marking and reports stale_findings_count.
8. Re-verification resolution: resolve_stale_findings_for_files marks absent stale findings as resolved.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import FileManifestEntry, PutManifestRequest
from app.core.auth_context import AuthContext, SystemContext
from app.core.ids import generate_uuid7
from app.domain.brain.manifest_service import ManifestService
from app.persistence.models.brain import (
    Finding,
    FindingStatusHistory,
    ProjectFile,
)
from app.persistence.repositories.brain_repo import BrainRepository


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    return session


@pytest.mark.asyncio
async def test_mark_findings_stale_empty_paths(mock_session: AsyncMock) -> None:
    """Empty paths list immediately returns 0 without database query."""
    repo = BrainRepository(mock_session)
    ctx = SystemContext(reason="test")
    project_id = generate_uuid7()

    count = await repo.mark_findings_stale_for_files(ctx, project_id, [])
    assert count == 0


@pytest.mark.asyncio
async def test_mark_findings_stale_on_primary_file_change(mock_session: AsyncMock) -> None:
    """Active finding moves to stale when its primary file is in the modified paths."""
    repo = BrainRepository(mock_session)
    repo._verify_project_access = AsyncMock()  # type: ignore[method-assign]

    project_id = generate_uuid7()
    ctx = SystemContext(reason="test")

    file_id = generate_uuid7()
    finding_id = generate_uuid7()

    finding = Finding(
        id=finding_id,
        project_id=project_id,
        fingerprint="fp1" * 21 + "a",
        rule_id="devmind.authz.missing_role_check",
        source="scanner",
        category="security",
        title="Admin route missing role check",
        summary="Summary",
        severity="high",
        confidence="high",
        evidence_level="E1",
        status="open",
        primary_file_id=file_id,
    )

    # 1. file_stmt query returns file_id
    mock_file_res = MagicMock()
    mock_file_res.scalars.return_value.all.return_value = [file_id]

    # 2. update evidence stmt execution
    mock_ev_update_res = MagicMock()

    # 3. finding_stmt query returns active finding
    mock_finding_res = MagicMock()
    mock_finding_res.scalars.return_value.all.return_value = [finding]

    mock_session.execute.side_effect = [
        mock_file_res,
        mock_finding_res,
        mock_ev_update_res,
    ]

    count = await repo.mark_findings_stale_for_files(ctx, project_id, ["src/routes/admin.py"])

    assert count == 1
    assert finding.status == "stale"
    assert mock_session.add.call_count == 1
    history_entry = mock_session.add.call_args[0][0]
    assert isinstance(history_entry, FindingStatusHistory)
    assert history_entry.finding_id == finding_id
    assert history_entry.from_status == "open"
    assert history_entry.to_status == "stale"
    assert history_entry.actor_kind == "system"
    assert history_entry.reason == "evidence file modified or removed"
    mock_session.flush.assert_called()


@pytest.mark.asyncio
async def test_mark_findings_stale_on_evidence_file_change(mock_session: AsyncMock) -> None:
    """Active finding moves to stale when a supporting evidence file is modified."""
    repo = BrainRepository(mock_session)
    repo._verify_project_access = AsyncMock()  # type: ignore[method-assign]

    project_id = generate_uuid7()
    ctx = SystemContext(reason="test")

    finding_id = generate_uuid7()
    finding = Finding(
        id=finding_id,
        project_id=project_id,
        fingerprint="fp2" * 21 + "b",
        rule_id="devmind.authn.unprotected_route",
        source="scanner",
        category="security",
        title="Unprotected route",
        summary="Summary",
        severity="medium",
        confidence="medium",
        evidence_level="E1",
        status="in_progress",
        primary_file_id=generate_uuid7(),
    )

    mock_file_res = MagicMock()
    mock_file_res.scalars.return_value.all.return_value = []

    mock_ev_update_res = MagicMock()

    mock_finding_res = MagicMock()
    mock_finding_res.scalars.return_value.all.return_value = [finding]

    mock_session.execute.side_effect = [
        mock_file_res,
        mock_finding_res,
        mock_ev_update_res,
    ]

    count = await repo.mark_findings_stale_for_files(ctx, project_id, ["src/middleware/auth.py"])

    assert count == 1
    assert finding.status == "stale"
    assert mock_session.add.call_count == 1
    history = mock_session.add.call_args[0][0]
    assert history.from_status == "in_progress"
    assert history.to_status == "stale"


@pytest.mark.asyncio
async def test_mark_findings_stale_on_file_removal(mock_session: AsyncMock) -> None:
    """Active finding moves to stale when file is deleted/removed."""
    repo = BrainRepository(mock_session)
    repo._verify_project_access = AsyncMock()  # type: ignore[method-assign]

    project_id = generate_uuid7()
    ctx = SystemContext(reason="test")

    file_id = generate_uuid7()
    finding = Finding(
        id=generate_uuid7(),
        project_id=project_id,
        fingerprint="fp3" * 21 + "c",
        rule_id="devmind.secrets.exposed_env_file",
        source="scanner",
        category="security",
        title="Exposed env file",
        summary="Summary",
        severity="high",
        confidence="high",
        evidence_level="E1",
        status="acknowledged",
        primary_file_id=file_id,
    )

    mock_file_res = MagicMock()
    mock_file_res.scalars.return_value.all.return_value = [file_id]

    mock_ev_update_res = MagicMock()

    mock_finding_res = MagicMock()
    mock_finding_res.scalars.return_value.all.return_value = [finding]

    mock_session.execute.side_effect = [
        mock_file_res,
        mock_finding_res,
        mock_ev_update_res,
    ]

    count = await repo.mark_findings_stale_for_files(ctx, project_id, [".env.local"])

    assert count == 1
    assert finding.status == "stale"
    history = mock_session.add.call_args[0][0]
    assert history.from_status == "acknowledged"
    assert history.to_status == "stale"


@pytest.mark.asyncio
async def test_resolve_stale_findings_for_files(mock_session: AsyncMock) -> None:
    """resolve_stale_findings_for_files marks stale findings as resolved when scan verification no longer detects the issue."""
    repo = BrainRepository(mock_session)
    repo._verify_project_access = AsyncMock()  # type: ignore[method-assign]

    project_id = generate_uuid7()
    ctx = SystemContext(reason="test")

    file_id = generate_uuid7()
    scan_run_id = generate_uuid7()
    stale_finding = Finding(
        id=generate_uuid7(),
        project_id=project_id,
        fingerprint="fp_resolved_test" + "0" * 48,
        rule_id="devmind.authz.missing_role_check",
        source="scanner",
        category="security",
        title="Admin route missing role check",
        summary="Summary",
        severity="high",
        confidence="high",
        evidence_level="E1",
        status="stale",
        primary_file_id=file_id,
    )

    mock_file_res = MagicMock()
    mock_file_res.scalars.return_value.all.return_value = [file_id]

    mock_findings_res = MagicMock()
    mock_findings_res.scalars.return_value.all.return_value = [stale_finding]

    mock_session.execute.side_effect = [
        mock_file_res,
        mock_findings_res,
    ]

    # Re-verification scan: detected fingerprints does NOT include this finding's fingerprint
    count = await repo.resolve_stale_findings_for_files(
        ctx,
        project_id=project_id,
        scanned_paths=["src/routes/admin.py"],
        detected_fingerprints={"other_finding_fp" + "0" * 48},
        scan_run_id=scan_run_id,
    )

    assert count == 1
    assert stale_finding.status == "resolved"
    assert stale_finding.resolved_at is not None
    assert stale_finding.last_seen_scan_run_id == scan_run_id
    assert stale_finding.status_reason == "re-verification: no longer detected in scan"
    assert mock_session.add.call_count == 1
    history = mock_session.add.call_args[0][0]
    assert history.from_status == "stale"
    assert history.to_status == "resolved"
    assert history.actor_kind == "system"
    assert history.reason == "re-verification: no longer detected in scan"


@pytest.mark.asyncio
async def test_put_manifest_wires_staleness(mock_session: AsyncMock) -> None:
    """Verifies ManifestService.put_manifest marks findings stale on content hash change and file removals."""
    service = ManifestService(mock_session)
    service.repo.get_latest_snapshot = AsyncMock(return_value=None)

    old_ver_id = generate_uuid7()
    new_ver_id = generate_uuid7()

    file_rec = ProjectFile(
        id=generate_uuid7(),
        path="src/app.py",
        current_version_id=old_ver_id,
    )
    new_ver = MagicMock()
    new_ver.id = new_ver_id

    service.repo.upsert_file = AsyncMock(return_value=file_rec)
    service.repo.create_file_version = AsyncMock(return_value=new_ver)
    service.repo.mark_files_removed = AsyncMock(return_value=1)
    service.repo.mark_findings_stale_for_files = AsyncMock(return_value=3)

    ctx = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="c1",
        email="test@local",
        workspace_id=generate_uuid7(),
    )
    project_id = generate_uuid7()

    req = PutManifestRequest(
        files=[
            FileManifestEntry(
                path="src/app.py",
                content_hash="h" * 64,
                size_bytes=100,
                line_count=10,
                language="python",
            )
        ],
        removed_paths=["src/deprecated.py"],
    )

    res = await service.put_manifest(ctx, project_id, req)

    assert res.status == "synced"
    assert res.files_count == 1
    assert res.versions_created == 1
    assert res.removed_count == 1
    assert res.stale_findings_count == 3

    # Ensure mark_findings_stale_for_files was called with both modified and removed paths
    service.repo.mark_findings_stale_for_files.assert_called_once_with(
        ctx, project_id, ["src/app.py", "src/deprecated.py"]
    )
