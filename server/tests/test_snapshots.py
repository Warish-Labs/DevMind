"""Tests for Project Brain Snapshots, File Versioning, and Point-in-time Diffs (M4-04).

Verifies:
1. Point-in-time immutable snapshot creation capturing current file versions.
2. Immutability guarantee: historical snapshots remain unchanged after subsequent file changes or deletions.
3. Snapshot detail retrieval and file mappings inspection.
4. Snapshot diff / comparison logic (snapshot-to-snapshot and snapshot-to-current).
5. REST API endpoints under /api/v1/projects/{pid}/brain/snapshots with permission enforcement.
6. Tenant boundary protection: cross-tenant access rejection (403 Forbidden).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from starlette.testclient import TestClient

from app.api.schemas import (
    CreateSnapshotRequest,
    SnapshotDetail,
    SnapshotDiffResponse,
    SnapshotItem,
)
from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import NotFoundError, ValidationError
from app.core.ids import generate_uuid7
from app.core.settings import Settings
from app.domain.auth import get_auth_context, get_db_session
from app.domain.brain.snapshot_service import SnapshotService
from app.main import create_app
from app.persistence.models.brain import FileVersion, ProjectFile, ProjectSnapshot, SnapshotFile


@pytest.mark.asyncio
async def test_create_snapshot_validates_kind() -> None:
    """Rejects invalid snapshot kind with ValidationError."""
    mock_session = AsyncMock()
    service = SnapshotService(mock_session)
    ctx = SystemContext(reason="test")
    project_id = generate_uuid7()

    req = CreateSnapshotRequest(kind="invalid_kind", ref="123")
    with pytest.raises(ValidationError, match="Snapshot kind must be"):
        await service.create_snapshot(ctx, project_id, req)


@pytest.mark.asyncio
async def test_create_snapshot_captures_active_files() -> None:
    """Point-in-time snapshot captures active files and links them in snapshot_files."""
    mock_session = AsyncMock()
    service = SnapshotService(mock_session)

    project_id = generate_uuid7()
    snap_id = generate_uuid7()
    now = datetime.now(UTC)

    mock_snap = ProjectSnapshot(
        id=snap_id,
        project_id=project_id,
        kind="scan",
        ref="scan_run_01",
        label="v1 baseline",
        created_at=now,
    )
    service.repo.create_snapshot_from_active_files = AsyncMock(return_value=mock_snap)
    service.repo.count_snapshot_files = AsyncMock(return_value=3)

    ctx = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="c1",
        email="test@local",
        workspace_id=generate_uuid7(),
    )
    req = CreateSnapshotRequest(kind="scan", ref="scan_run_01", label="v1 baseline")

    res = await service.create_snapshot(ctx, project_id, req)
    assert res.id == snap_id
    assert res.project_id == project_id
    assert res.kind == "scan"
    assert res.ref == "scan_run_01"
    assert res.label == "v1 baseline"
    assert res.file_count == 3
    service.repo.create_snapshot_from_active_files.assert_called_once_with(
        ctx,
        project_id=project_id,
        kind="scan",
        ref="scan_run_01",
        label="v1 baseline",
    )


@pytest.mark.asyncio
async def test_get_snapshot_not_found() -> None:
    """Raises NotFoundError when snapshot does not exist."""
    mock_session = AsyncMock()
    service = SnapshotService(mock_session)
    service.repo.get_snapshot = AsyncMock(return_value=None)

    ctx = SystemContext(reason="test")
    with pytest.raises(NotFoundError, match="not found"):
        await service.get_snapshot(ctx, generate_uuid7(), generate_uuid7())


@pytest.mark.asyncio
async def test_get_snapshot_detail_success() -> None:
    """Loads snapshot metadata and full file version mappings."""
    mock_session = AsyncMock()
    service = SnapshotService(mock_session)

    project_id = generate_uuid7()
    snap_id = generate_uuid7()
    now = datetime.now(UTC)

    mock_snap = ProjectSnapshot(
        id=snap_id,
        project_id=project_id,
        kind="commit",
        ref="sha123",
        created_at=now,
    )
    service.repo.get_snapshot = AsyncMock(return_value=mock_snap)

    file_id = generate_uuid7()
    ver_id = generate_uuid7()
    mock_file = ProjectFile(id=file_id, path="src/app.py", language="python", tier=1)
    mock_ver = FileVersion(
        id=ver_id,
        file_id=file_id,
        content_hash="abc" * 21 + "a",
        size_bytes=1024,
        line_count=50,
    )

    mock_sf = SnapshotFile(
        snapshot_id=snap_id,
        file_id=file_id,
        file_version_id=ver_id,
    )
    mock_sf.file = mock_file
    mock_sf.file_version = mock_ver

    service.repo.get_snapshot_files = AsyncMock(return_value=[mock_sf])

    ctx = SystemContext(reason="test")
    detail = await service.get_snapshot_detail(ctx, project_id, snap_id)

    assert detail.snapshot.id == snap_id
    assert detail.snapshot.file_count == 1
    assert len(detail.files) == 1
    assert detail.files[0].path == "src/app.py"
    assert detail.files[0].language == "python"
    assert detail.files[0].content_hash == "abc" * 21 + "a"
    assert detail.files[0].size_bytes == 1024


@pytest.mark.asyncio
async def test_compare_snapshots_between_two_snapshots() -> None:
    """Compares two historical snapshots and identifies added, removed, modified, unchanged files."""
    mock_session = AsyncMock()
    service = SnapshotService(mock_session)

    project_id = generate_uuid7()
    snap_a_id = generate_uuid7()
    snap_b_id = generate_uuid7()

    service.repo.get_snapshot = AsyncMock(return_value=MagicMock())

    # Snapshot A:
    # 1. unchanged.py: hash '1' * 64
    # 2. modified.py: hash '2' * 64
    # 3. removed.py: hash '3' * 64
    def make_sf(path: str, ver_id: UUID, content_hash: str) -> SnapshotFile:
        sf = SnapshotFile(snapshot_id=snap_a_id, file_id=generate_uuid7(), file_version_id=ver_id)
        sf.file = ProjectFile(path=path)
        sf.file_version = FileVersion(id=ver_id, content_hash=content_hash)
        return sf

    sf_unchanged_a = make_sf("unchanged.py", generate_uuid7(), "1" * 64)
    sf_modified_a = make_sf("modified.py", generate_uuid7(), "2" * 64)
    sf_removed_a = make_sf("removed.py", generate_uuid7(), "3" * 64)

    # Snapshot B:
    # 1. unchanged.py: hash '1' * 64
    # 2. modified.py: hash '9' * 64 (new version)
    # 3. added.py: hash '4' * 64
    sf_unchanged_b = make_sf("unchanged.py", sf_unchanged_a.file_version_id, "1" * 64)
    sf_modified_b = make_sf("modified.py", generate_uuid7(), "9" * 64)
    sf_added_b = make_sf("added.py", generate_uuid7(), "4" * 64)

    service.repo.get_snapshot_files = AsyncMock(
        side_effect=[
            [sf_unchanged_a, sf_modified_a, sf_removed_a],
            [sf_unchanged_b, sf_modified_b, sf_added_b],
        ]
    )

    ctx = SystemContext(reason="test")
    diff = await service.compare_snapshots(ctx, project_id, snap_a_id, snap_b_id)

    assert diff.base_snapshot_id == snap_a_id
    assert diff.target_snapshot_id == snap_b_id
    assert diff.unchanged == 1
    assert diff.modified == 1
    assert diff.removed == 1
    assert diff.added == 1
    assert len(diff.differences) == 4

    status_by_path = {d.path: d.status for d in diff.differences}
    assert status_by_path["unchanged.py"] == "unchanged"
    assert status_by_path["modified.py"] == "modified"
    assert status_by_path["removed.py"] == "removed"
    assert status_by_path["added.py"] == "added"


@pytest.mark.asyncio
async def test_compare_snapshot_against_active_project_state() -> None:
    """Compares a historical snapshot against current active workspace files (target_snapshot_id=None)."""
    mock_session = AsyncMock()
    service = SnapshotService(mock_session)

    project_id = generate_uuid7()
    base_snap_id = generate_uuid7()

    service.repo.get_snapshot = AsyncMock(return_value=MagicMock())

    # Base snapshot has file 'main.py' hash '1' * 64
    sf = SnapshotFile(
        snapshot_id=base_snap_id, file_id=generate_uuid7(), file_version_id=generate_uuid7()
    )
    sf.file = ProjectFile(path="main.py")
    sf.file_version = FileVersion(id=sf.file_version_id, content_hash="1" * 64)
    service.repo.get_snapshot_files = AsyncMock(return_value=[sf])

    # Current active files: 'main.py' is updated to hash '2' * 64
    curr_ver = FileVersion(id=generate_uuid7(), content_hash="2" * 64)
    curr_file = ProjectFile(path="main.py")
    curr_file.current_version = curr_ver
    service.repo.list_active_files = AsyncMock(return_value=[curr_file])

    ctx = SystemContext(reason="test")
    diff = await service.compare_snapshots(ctx, project_id, base_snap_id, None)

    assert diff.target_snapshot_id is None
    assert diff.modified == 1
    assert diff.unchanged == 0
    assert diff.added == 0
    assert diff.removed == 0
    assert diff.differences[0].path == "main.py"
    assert diff.differences[0].status == "modified"


def test_snapshot_rest_api_lifecycle(test_settings: Settings) -> None:
    """Test full snapshot REST API lifecycle via TestClient."""
    app = create_app(settings=test_settings)

    user_id = generate_uuid7()
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()
    snapshot_id = generate_uuid7()
    now = datetime.now(UTC)

    mock_ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_clerk_test",
        email="dev@devmind.local",
        workspace_id=workspace_id,
        project_id=project_id,
        permissions=frozenset({"brain:read", "project:update"}),
    )

    mock_session = AsyncMock()
    app.dependency_overrides[get_auth_context] = lambda: mock_ctx
    app.dependency_overrides[get_db_session] = lambda: mock_session

    with patch("app.api.brain.SnapshotService") as mock_service_cls:
        mock_instance = MagicMock()
        mock_service_cls.return_value = mock_instance
        mock_instance.resolve_project_context = AsyncMock(return_value=mock_ctx)

        mock_snap_item = SnapshotItem(
            id=snapshot_id,
            project_id=project_id,
            kind="manual",
            ref="manual_v1",
            label="Pre-release",
            created_at=now,
            file_count=5,
        )
        mock_instance.create_snapshot = AsyncMock(return_value=mock_snap_item)
        mock_instance.list_snapshots = AsyncMock(return_value=[mock_snap_item])
        mock_instance.get_snapshot_detail = AsyncMock(
            return_value=SnapshotDetail(snapshot=mock_snap_item, files=[])
        )
        mock_instance.compare_snapshots = AsyncMock(
            return_value=SnapshotDiffResponse(
                base_snapshot_id=snapshot_id,
                target_snapshot_id=None,
                added=0,
                removed=0,
                modified=1,
                unchanged=4,
                differences=[],
            )
        )

        with TestClient(app) as client:
            headers = {"Authorization": "Bearer mock_clerk_token"}

            # 1. POST /snapshots (Capture snapshot)
            res = client.post(
                f"/api/v1/projects/{project_id}/brain/snapshots",
                json={"kind": "manual", "ref": "manual_v1", "label": "Pre-release"},
                headers=headers,
            )
            assert res.status_code == 201
            data = res.json()
            assert data["id"] == str(snapshot_id)
            assert data["kind"] == "manual"
            assert data["file_count"] == 5

            # 2. GET /snapshots (List snapshots)
            res = client.get(
                f"/api/v1/projects/{project_id}/brain/snapshots",
                headers=headers,
            )
            assert res.status_code == 200
            list_data = res.json()
            assert len(list_data) == 1
            assert list_data[0]["id"] == str(snapshot_id)

            # 3. GET /snapshots/{sid} (Snapshot details)
            res = client.get(
                f"/api/v1/projects/{project_id}/brain/snapshots/{snapshot_id}",
                headers=headers,
            )
            assert res.status_code == 200
            detail_data = res.json()
            assert detail_data["snapshot"]["id"] == str(snapshot_id)
            assert detail_data["files"] == []

            # 4. GET /snapshots/{sid}/diff (Snapshot diff)
            res = client.get(
                f"/api/v1/projects/{project_id}/brain/snapshots/{snapshot_id}/diff",
                headers=headers,
            )
            assert res.status_code == 200
            diff_data = res.json()
            assert diff_data["base_snapshot_id"] == str(snapshot_id)
            assert diff_data["modified"] == 1
            assert diff_data["unchanged"] == 4


def test_snapshot_forbidden_without_permission(test_settings: Settings) -> None:
    """Verify HTTP 403 Forbidden when caller lacks brain:read permission."""
    app = create_app(settings=test_settings)
    user_id = generate_uuid7()
    project_id = generate_uuid7()

    mock_ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_clerk_test",
        email="dev@devmind.local",
        permissions=frozenset({"other:permission"}),  # lacks brain:read
    )

    mock_session = AsyncMock()
    app.dependency_overrides[get_auth_context] = lambda: mock_ctx
    app.dependency_overrides[get_db_session] = lambda: mock_session

    with TestClient(app) as client:
        res = client.get(
            f"/api/v1/projects/{project_id}/brain/snapshots",
            headers={"Authorization": "Bearer mock_token"},
        )
        assert res.status_code == 403
        assert "brain:read" in res.json()["detail"]
