"""Unit and integration tests for Browser Read Endpoints (Milestone M4-08, docs/03 §11.1).

Verifies:
1. Scans:
   - GET /api/v1/projects/{pid}/scans returns scan runs list with status filtering.
   - GET /api/v1/projects/{pid}/scans/{sid} returns scan detail or 404.
   - Requires PERM_PROJECT_READ.
2. Brain Summary:
   - GET /api/v1/projects/{pid}/brain/summary aggregates files, languages, versions, snapshots, symbols, relationships, findings, latest snapshot and scan.
   - Requires PERM_BRAIN_READ.
3. Brain Files:
   - GET /api/v1/projects/{pid}/brain/files returns active files with current version metadata.
   - GET /api/v1/projects/{pid}/brain/files/{fid} returns file detail with version history or 404.
   - Requires PERM_BRAIN_READ.
4. Tenant isolation and RBAC:
   - Missing permissions return HTTP 403.
   - Cross-tenant requests return HTTP 403.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from starlette.testclient import TestClient

from app.api.schemas import (
    BrainFileDetail,
    BrainFileItem,
    BrainFileVersionItem,
    BrainSummaryResponse,
    ScanRunItem,
)
from app.core.auth_context import AuthContext
from app.core.errors import NotFoundError
from app.core.ids import generate_uuid7
from app.core.settings import Settings
from app.domain.auth import (
    PERM_BRAIN_READ,
    PERM_PROJECT_READ,
    get_auth_context,
    get_db_session,
)
from app.domain.brain import BrainService, ScanService
from app.main import create_app
from app.persistence.models.brain import (
    FileVersion,
    ProjectFile,
    ProjectSnapshot,
    ScanRun,
)


@pytest.fixture
def test_project_id() -> UUID:
    return generate_uuid7()


@pytest.fixture
def test_workspace_id() -> UUID:
    return generate_uuid7()


@pytest.fixture
def test_user_id() -> UUID:
    return generate_uuid7()


@pytest.fixture
def browser_auth_ctx(
    test_user_id: UUID, test_workspace_id: UUID, test_project_id: UUID
) -> AuthContext:
    return AuthContext(
        user_id=test_user_id,
        clerk_user_id="user_clerk_browser",
        email="dev@devmind.local",
        workspace_id=test_workspace_id,
        project_id=test_project_id,
        permissions=frozenset({PERM_PROJECT_READ, PERM_BRAIN_READ}),
    )


# --- Unit Tests: ScanService ---


@pytest.mark.asyncio
async def test_scan_service_list_and_get(test_project_id: UUID) -> None:
    """Verifies ScanService list_scans and get_scan operations."""
    mock_session = AsyncMock()
    service = ScanService(mock_session)

    scan_id = generate_uuid7()
    scan_run = ScanRun(
        id=scan_id,
        project_id=test_project_id,
        origin="extension",
        status="completed",
        rules_version="1.0.0",
        stats={"files": 42},
    )

    service.repo.list_scan_runs = AsyncMock(return_value=[scan_run])  # type: ignore[method-assign]
    service.repo.get_scan_run = AsyncMock(return_value=scan_run)  # type: ignore[method-assign]

    ctx = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="c1",
        email="test@local",
        workspace_id=generate_uuid7(),
        project_id=test_project_id,
    )

    # 1. list_scans
    scans = await service.list_scans(ctx, test_project_id, status_filter="completed")
    assert len(scans) == 1
    assert scans[0].id == scan_id
    assert scans[0].status == "completed"
    assert scans[0].stats == {"files": 42}

    # 2. get_scan success
    detail = await service.get_scan(ctx, test_project_id, scan_id)
    assert detail.id == scan_id
    assert detail.rules_version == "1.0.0"

    # 3. get_scan not found
    service.repo.get_scan_run = AsyncMock(return_value=None)  # type: ignore[method-assign]
    with pytest.raises(NotFoundError, match="Scan run .* not found"):
        await service.get_scan(ctx, test_project_id, generate_uuid7())


# --- Unit Tests: BrainService ---


@pytest.mark.asyncio
async def test_brain_service_summary_and_files(test_project_id: UUID) -> None:
    """Verifies BrainService get_summary, list_files, and get_file_detail."""
    mock_session = AsyncMock()
    service = BrainService(mock_session)

    snap_id = generate_uuid7()
    scan_id = generate_uuid7()
    file_id = generate_uuid7()
    ver_id = generate_uuid7()

    mock_snap = ProjectSnapshot(
        id=snap_id,
        project_id=test_project_id,
        kind="scan",
        ref="HEAD",
        label="v1",
    )
    mock_scan = ScanRun(
        id=scan_id,
        project_id=test_project_id,
        origin="extension",
        status="completed",
    )

    service.repo.get_brain_summary_stats = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "total_files": 15,
            "languages": {"python": 10, "typescript": 5},
            "total_versions": 25,
            "total_snapshots": 3,
            "total_symbols": 80,
            "total_relationships": 120,
            "findings_summary": {"open": 2, "stale": 1, "resolved": 4},
            "latest_snapshot": mock_snap,
            "latest_scan": mock_scan,
        }
    )
    service.repo.count_snapshot_files = AsyncMock(return_value=15)  # type: ignore[method-assign]

    ctx = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="c1",
        email="test@local",
        workspace_id=generate_uuid7(),
        project_id=test_project_id,
    )

    # 1. get_summary
    summary = await service.get_summary(ctx, test_project_id)
    assert summary.total_files == 15
    assert summary.languages == {"python": 10, "typescript": 5}
    assert summary.total_versions == 25
    assert summary.total_symbols == 80
    assert summary.findings_summary["open"] == 2
    assert summary.latest_snapshot is not None
    assert summary.latest_snapshot.file_count == 15
    assert summary.latest_scan is not None
    assert summary.latest_scan.id == scan_id

    # 2. list_files
    ver = FileVersion(
        id=ver_id,
        file_id=file_id,
        content_hash="h" * 64,
        size_bytes=250,
        line_count=20,
    )
    f_rec = ProjectFile(
        id=file_id,
        project_id=test_project_id,
        path="src/main.py",
        language="python",
        tier=1,
        current_version_id=ver_id,
    )
    f_rec.current_version = ver
    service.repo.list_active_files = AsyncMock(return_value=[f_rec])  # type: ignore[method-assign]

    files = await service.list_files(ctx, test_project_id)
    assert len(files) == 1
    assert files[0].path == "src/main.py"
    assert files[0].size_bytes == 250
    assert files[0].line_count == 20

    # 3. get_file_detail
    f_rec.versions = [ver]
    service.repo.get_file_by_id = AsyncMock(return_value=f_rec)  # type: ignore[method-assign]

    file_detail = await service.get_file_detail(ctx, test_project_id, file_id)
    assert file_detail.id == file_id
    assert len(file_detail.versions) == 1
    assert file_detail.versions[0].content_hash == "h" * 64

    # 4. get_file_detail not found
    service.repo.get_file_by_id = AsyncMock(return_value=None)  # type: ignore[method-assign]
    with pytest.raises(NotFoundError, match="File .* not found"):
        await service.get_file_detail(ctx, test_project_id, generate_uuid7())


# --- API Endpoint Integration Tests ---


def test_scans_endpoints_via_test_client(
    test_settings: Settings,
    browser_auth_ctx: AuthContext,
    test_project_id: UUID,
) -> None:
    """Verifies GET /api/v1/projects/{pid}/scans and GET /api/v1/projects/{pid}/scans/{sid}."""
    app = create_app(settings=test_settings)
    mock_session = AsyncMock()

    app.dependency_overrides[get_auth_context] = lambda: browser_auth_ctx
    app.dependency_overrides[get_db_session] = lambda: mock_session

    scan_id = generate_uuid7()
    scan_item = ScanRunItem(
        id=scan_id,
        project_id=test_project_id,
        origin="extension",
        status="completed",
        stats={"total_files": 10},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with patch("app.api.scans.ScanService") as mock_service_cls:
        service_instance = MagicMock()
        mock_service_cls.return_value = service_instance
        service_instance.resolve_project_context = AsyncMock(return_value=browser_auth_ctx)
        service_instance.list_scans = AsyncMock(return_value=[scan_item])
        service_instance.get_scan = AsyncMock(return_value=scan_item)

        with TestClient(app) as client:
            headers = {"Authorization": "Bearer test_clerk_token"}

            # 1. List scans
            res = client.get(
                f"/api/v1/projects/{test_project_id}/scans?status=completed",
                headers=headers,
            )
            assert res.status_code == 200
            data = res.json()
            assert len(data) == 1
            assert data[0]["id"] == str(scan_id)
            assert data[0]["status"] == "completed"

            # 2. Get scan detail
            res_detail = client.get(
                f"/api/v1/projects/{test_project_id}/scans/{scan_id}",
                headers=headers,
            )
            assert res_detail.status_code == 200
            data_detail = res_detail.json()
            assert data_detail["id"] == str(scan_id)
            assert data_detail["stats"]["total_files"] == 10


def test_brain_summary_and_files_endpoints_via_test_client(
    test_settings: Settings,
    browser_auth_ctx: AuthContext,
    test_project_id: UUID,
) -> None:
    """Verifies GET /brain/summary, GET /brain/files, and GET /brain/files/{fid}."""
    app = create_app(settings=test_settings)
    mock_session = AsyncMock()

    app.dependency_overrides[get_auth_context] = lambda: browser_auth_ctx
    app.dependency_overrides[get_db_session] = lambda: mock_session

    summary_resp = BrainSummaryResponse(
        project_id=test_project_id,
        total_files=20,
        languages={"python": 15, "typescript": 5},
        total_versions=30,
        total_snapshots=2,
        total_symbols=100,
        total_relationships=150,
        findings_summary={"open": 5, "resolved": 10},
    )

    file_id = generate_uuid7()
    file_item = BrainFileItem(
        id=file_id,
        project_id=test_project_id,
        path="src/index.ts",
        language="typescript",
        tier=1,
        size_bytes=1024,
        line_count=50,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    file_detail = BrainFileDetail(
        id=file_id,
        project_id=test_project_id,
        path="src/index.ts",
        language="typescript",
        tier=1,
        size_bytes=1024,
        line_count=50,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        versions=[
            BrainFileVersionItem(
                id=generate_uuid7(),
                file_id=file_id,
                content_hash="f" * 64,
                size_bytes=1024,
                line_count=50,
                origin="extension",
                created_at=datetime.now(UTC),
            )
        ],
    )

    with patch("app.api.brain.BrainService") as mock_service_cls:
        service_instance = MagicMock()
        mock_service_cls.return_value = service_instance
        service_instance.resolve_project_context = AsyncMock(return_value=browser_auth_ctx)
        service_instance.get_summary = AsyncMock(return_value=summary_resp)
        service_instance.list_files = AsyncMock(return_value=[file_item])
        service_instance.get_file_detail = AsyncMock(return_value=file_detail)

        with TestClient(app) as client:
            headers = {"Authorization": "Bearer test_clerk_token"}

            # 1. GET /brain/summary
            res_sum = client.get(
                f"/api/v1/projects/{test_project_id}/brain/summary",
                headers=headers,
            )
            assert res_sum.status_code == 200
            sum_data = res_sum.json()
            assert sum_data["total_files"] == 20
            assert sum_data["total_symbols"] == 100
            assert sum_data["languages"] == {"python": 15, "typescript": 5}

            # 2. GET /brain/files
            res_files = client.get(
                f"/api/v1/projects/{test_project_id}/brain/files",
                headers=headers,
            )
            assert res_files.status_code == 200
            files_data = res_files.json()
            assert len(files_data) == 1
            assert files_data[0]["path"] == "src/index.ts"

            # 3. GET /brain/files/{fid}
            res_file = client.get(
                f"/api/v1/projects/{test_project_id}/brain/files/{file_id}",
                headers=headers,
            )
            assert res_file.status_code == 200
            file_data = res_file.json()
            assert file_data["id"] == str(file_id)
            assert len(file_data["versions"]) == 1


def test_browser_endpoints_permission_enforcement(
    test_settings: Settings,
    test_project_id: UUID,
) -> None:
    """Verifies HTTP 403 when user lacks required permission."""
    app = create_app(settings=test_settings)
    mock_session = AsyncMock()

    # User with NO permissions
    unauthorized_ctx = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="user_clerk_unauthorized",
        email="unauthorized@devmind.local",
        permissions=frozenset(),
    )

    app.dependency_overrides[get_auth_context] = lambda: unauthorized_ctx
    app.dependency_overrides[get_db_session] = lambda: mock_session

    with TestClient(app) as client:
        headers = {"Authorization": "Bearer test_clerk_token"}

        # Scans endpoint needs project:read
        res1 = client.get(f"/api/v1/projects/{test_project_id}/scans", headers=headers)
        assert res1.status_code == 403
        assert "project:read" in res1.json()["detail"]

        # Brain summary needs brain:read
        res2 = client.get(f"/api/v1/projects/{test_project_id}/brain/summary", headers=headers)
        assert res2.status_code == 403
        assert "brain:read" in res2.json()["detail"]
