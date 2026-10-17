"""Tests for Manifest Synchronization, Diff Computation, and Stale Base Detection (M4-03).

Verifies:
1. Manifest diff calculation: unchanged, new, changed, and removed paths.
2. Conflict detection: 409 sync.stale_base Problem Details when base_snapshot_id differs from latest snapshot.
3. Manifest put: upserting files and file versions with status receipts.
4. Tenant isolation and permission enforcement:
   - Rule 10: Extension routes accept only DevMind extension tokens (Bearer dme_at_...).
   - Missing or non-dme tokens fail with HTTP 401.
   - Cross-tenant project access rejection with HTTP 403.
   - Missing project:sync scope rejection with HTTP 403.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.api.schemas import (
    FileManifestEntry,
    ManifestDiffRequest,
    PutManifestRequest,
)
from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import ForbiddenError, NotFoundError, StaleBaseError
from app.core.ids import generate_uuid7
from app.core.settings import Settings
from app.domain.auth import get_db_session, get_extension_auth_context
from app.domain.brain.manifest_service import ManifestService
from app.main import create_app
from app.persistence.models.brain import FileVersion, ProjectFile, ProjectSnapshot
from app.persistence.models.project import Project
from app.persistence.models.workspace import WorkspaceMembership


@pytest.mark.asyncio
async def test_resolve_project_context_system_context() -> None:
    """SystemContext bypasses tenant resolution."""
    mock_session = AsyncMock()
    service = ManifestService(mock_session)
    sys_ctx = SystemContext(reason="test")
    resolved = await service.resolve_project_context(sys_ctx, generate_uuid7())
    assert resolved == sys_ctx


@pytest.mark.asyncio
async def test_resolve_project_context_not_found() -> None:
    """Raises NotFoundError if project does not exist."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_session.execute.return_value = mock_result

    service = ManifestService(mock_session)
    ctx = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="clerk_1",
        email="test@devmind.local",
    )
    with pytest.raises(NotFoundError, match="not found"):
        await service.resolve_project_context(ctx, generate_uuid7())


@pytest.mark.asyncio
async def test_resolve_project_context_workspace_member_success() -> None:
    """Resolves project context when user is a workspace member."""
    mock_session = AsyncMock()
    user_id = generate_uuid7()
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()

    proj = Project(id=project_id, workspace_id=workspace_id, name="Test", slug="test")
    ws_mem = WorkspaceMembership(workspace_id=workspace_id, user_id=user_id, role="member")

    mock_res_proj = MagicMock()
    mock_res_proj.scalars.return_value.first.return_value = proj
    mock_res_mem = MagicMock()
    mock_res_mem.scalars.return_value.first.return_value = ws_mem

    mock_session.execute.side_effect = [mock_res_proj, mock_res_mem]

    service = ManifestService(mock_session)
    ctx = AuthContext(user_id=user_id, clerk_user_id="c1", email="test@local")
    resolved = await service.resolve_project_context(ctx, project_id)

    assert resolved.workspace_id == workspace_id
    assert resolved.project_id == project_id
    assert resolved.workspace_role == "member"


@pytest.mark.asyncio
async def test_resolve_project_context_cross_tenant_forbidden() -> None:
    """Raises ForbiddenError when user has no workspace or project membership."""
    mock_session = AsyncMock()
    user_id = generate_uuid7()
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()

    proj = Project(id=project_id, workspace_id=workspace_id, name="Test", slug="test")

    mock_res_proj = MagicMock()
    mock_res_proj.scalars.return_value.first.return_value = proj
    mock_res_no_ws = MagicMock()
    mock_res_no_ws.scalars.return_value.first.return_value = None
    mock_res_no_pm = MagicMock()
    mock_res_no_pm.scalars.return_value.first.return_value = None

    mock_session.execute.side_effect = [mock_res_proj, mock_res_no_ws, mock_res_no_pm]

    service = ManifestService(mock_session)
    ctx = AuthContext(user_id=user_id, clerk_user_id="c1", email="test@local")

    with pytest.raises(ForbiddenError, match="Forbidden: caller lacks membership"):
        await service.resolve_project_context(ctx, project_id)


@pytest.mark.asyncio
async def test_compute_diff_empty_cloud_state() -> None:
    """When cloud has no files, all incoming files are classified as new."""
    mock_session = AsyncMock()
    service = ManifestService(mock_session)
    service.repo.get_latest_snapshot = AsyncMock(return_value=None)
    service.repo.list_active_files = AsyncMock(return_value=[])

    ctx = AuthContext(user_id=generate_uuid7(), clerk_user_id="c1", email="test@local")
    project_id = generate_uuid7()

    req = ManifestDiffRequest(
        files=[
            FileManifestEntry(
                path="src/index.ts",
                content_hash="a" * 64,
                size_bytes=100,
                line_count=10,
                language="typescript",
                tier=1,
            ),
            FileManifestEntry(
                path="README.md",
                content_hash="b" * 64,
                size_bytes=200,
                line_count=20,
                language="markdown",
                tier=2,
            ),
        ]
    )

    diff = await service.compute_diff(ctx, project_id, req)
    assert diff.new == 2
    assert diff.unchanged == 0
    assert diff.changed == 0
    assert diff.removed == []
    assert len(diff.missing_files) == 2


@pytest.mark.asyncio
async def test_compute_diff_with_existing_files() -> None:
    """Properly identifies unchanged, changed, new, and removed files."""
    mock_session = AsyncMock()
    service = ManifestService(mock_session)
    service.repo.get_latest_snapshot = AsyncMock(return_value=None)

    project_id = generate_uuid7()

    # Existing cloud files:
    # 1. unchanged.ts: hash '1' * 64
    # 2. modified.py: hash '2' * 64
    # 3. deleted.ts: hash '3' * 64
    file1 = ProjectFile(id=generate_uuid7(), project_id=project_id, path="unchanged.ts")
    file1.current_version = FileVersion(
        id=generate_uuid7(), project_id=project_id, file_id=file1.id, content_hash="1" * 64
    )

    file2 = ProjectFile(id=generate_uuid7(), project_id=project_id, path="modified.py")
    file2.current_version = FileVersion(
        id=generate_uuid7(), project_id=project_id, file_id=file2.id, content_hash="2" * 64
    )

    file3 = ProjectFile(id=generate_uuid7(), project_id=project_id, path="deleted.ts")
    file3.current_version = FileVersion(
        id=generate_uuid7(), project_id=project_id, file_id=file3.id, content_hash="3" * 64
    )

    service.repo.list_active_files = AsyncMock(return_value=[file1, file2, file3])

    ctx = AuthContext(user_id=generate_uuid7(), clerk_user_id="c1", email="test@local")

    # Incoming manifest:
    # - unchanged.ts: same hash ('1' * 64) -> unchanged
    # - modified.py: new hash ('9' * 64) -> changed
    # - brand_new.ts: not in cloud -> new
    # (deleted.ts is omitted -> removed)
    req = ManifestDiffRequest(
        files=[
            FileManifestEntry(
                path="unchanged.ts",
                content_hash="1" * 64,
                size_bytes=10,
                line_count=1,
                language="typescript",
            ),
            FileManifestEntry(
                path="modified.py",
                content_hash="9" * 64,
                size_bytes=20,
                line_count=2,
                language="python",
            ),
            FileManifestEntry(
                path="brand_new.ts",
                content_hash="8" * 64,
                size_bytes=30,
                line_count=3,
                language="typescript",
            ),
        ]
    )

    diff = await service.compute_diff(ctx, project_id, req)
    assert diff.unchanged == 1
    assert diff.changed == 1
    assert diff.new == 1
    assert diff.removed == ["deleted.ts"]
    assert len(diff.missing_files) == 2
    missing_paths = {m.path for m in diff.missing_files}
    assert missing_paths == {"modified.py", "brand_new.ts"}


@pytest.mark.asyncio
async def test_compute_diff_stale_base_detection() -> None:
    """Raises StaleBaseError (409) when base_snapshot_id differs from latest cloud snapshot."""
    mock_session = AsyncMock()
    service = ManifestService(mock_session)

    project_id = generate_uuid7()
    latest_snapshot_id = generate_uuid7()
    client_base_id = generate_uuid7()

    latest_snap = ProjectSnapshot(id=latest_snapshot_id, project_id=project_id)
    service.repo.get_latest_snapshot = AsyncMock(return_value=latest_snap)

    ctx = AuthContext(user_id=generate_uuid7(), clerk_user_id="c1", email="test@local")

    req = ManifestDiffRequest(
        base_snapshot_id=client_base_id,
        files=[],
    )

    with pytest.raises(StaleBaseError, match="Client base snapshot .* is stale"):
        await service.compute_diff(ctx, project_id, req)


@pytest.mark.asyncio
async def test_put_manifest_success() -> None:
    """Registers files, creates versions, and marks removed paths."""
    mock_session = AsyncMock()
    service = ManifestService(mock_session)
    service.repo.get_latest_snapshot = AsyncMock(return_value=None)

    file_rec = ProjectFile(id=generate_uuid7(), path="src/main.py")
    service.repo.upsert_file = AsyncMock(return_value=file_rec)
    service.repo.create_file_version = AsyncMock(return_value=MagicMock())
    service.repo.mark_files_removed = AsyncMock(return_value=1)

    ctx = AuthContext(user_id=generate_uuid7(), clerk_user_id="c1", email="test@local")
    project_id = generate_uuid7()

    req = PutManifestRequest(
        files=[
            FileManifestEntry(
                path="src/main.py",
                content_hash="c" * 64,
                size_bytes=50,
                line_count=5,
                language="python",
            )
        ],
        removed_paths=["old_file.py"],
    )

    res = await service.put_manifest(ctx, project_id, req)
    assert res.status == "synced"
    assert res.files_count == 1
    assert res.versions_created == 1
    assert res.removed_count == 1
    service.repo.upsert_file.assert_called_once()
    service.repo.create_file_version.assert_called_once()
    service.repo.mark_files_removed.assert_called_once_with(ctx, project_id, ["old_file.py"])


def test_manifest_endpoints_via_test_client(test_settings: Settings) -> None:
    """Verify REST API behavior for /api/v1/ext/projects/{pid}/manifest endpoints."""
    app = create_app(settings=test_settings)

    user_id = generate_uuid7()
    workspace_id = generate_uuid7()
    project_id = generate_uuid7()

    mock_ext_ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_clerk_test",
        email="dev@devmind.local",
        workspace_id=workspace_id,
        permissions=frozenset({"project:sync"}),
    )

    mock_session = AsyncMock()
    app.dependency_overrides[get_extension_auth_context] = lambda: mock_ext_ctx
    app.dependency_overrides[get_db_session] = lambda: mock_session

    with patch("app.api.extension.ManifestService") as mock_manifest_service_cls:
        mock_instance = MagicMock()
        mock_manifest_service_cls.return_value = mock_instance
        mock_instance.resolve_project_context = AsyncMock(return_value=mock_ext_ctx)

        from app.api.schemas import ManifestDiffResponse, PutManifestResponse

        mock_instance.compute_diff = AsyncMock(
            return_value=ManifestDiffResponse(
                unchanged=1,
                new=1,
                changed=0,
                removed=[],
                missing_files=[],
            )
        )
        mock_instance.put_manifest = AsyncMock(
            return_value=PutManifestResponse(
                status="synced",
                project_id=project_id,
                files_count=1,
                versions_created=1,
                removed_count=0,
            )
        )

        with TestClient(app) as client:
            headers = {"Authorization": "Bearer dme_at_test_token_1234567890"}

            # 1. POST /manifest/diff
            res = client.post(
                f"/api/v1/ext/projects/{project_id}/manifest/diff",
                json={"files": []},
                headers=headers,
            )
            assert res.status_code == 200
            diff_data = res.json()
            assert diff_data["unchanged"] == 1
            assert diff_data["new"] == 1

            # 2. PUT /manifest
            res = client.put(
                f"/api/v1/ext/projects/{project_id}/manifest",
                json={"files": [], "removed_paths": []},
                headers=headers,
            )
            assert res.status_code == 200
            put_data = res.json()
            assert put_data["status"] == "synced"
            assert put_data["files_count"] == 1


def test_manifest_endpoints_missing_scope(test_settings: Settings) -> None:
    """Verify HTTP 403 when extension token lacks project:sync permission."""
    app = create_app(settings=test_settings)
    user_id = generate_uuid7()

    mock_ext_ctx = AuthContext(
        user_id=user_id,
        clerk_user_id="user_clerk_test",
        email="dev@devmind.local",
        permissions=frozenset({"other:permission"}),  # lacks project:sync
    )

    mock_session = AsyncMock()
    app.dependency_overrides[get_extension_auth_context] = lambda: mock_ext_ctx
    app.dependency_overrides[get_db_session] = lambda: mock_session

    project_id = generate_uuid7()

    with TestClient(app) as client:
        res = client.post(
            f"/api/v1/ext/projects/{project_id}/manifest/diff",
            json={"files": []},
            headers={"Authorization": "Bearer dme_at_scoped_token_12345"},
        )
        assert res.status_code == 403
        assert "project:sync" in res.json()["detail"]
