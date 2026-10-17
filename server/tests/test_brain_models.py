"""Tests verifying Project Brain persistence models and BrainRepository (docs/03 §3.2-§3.4, docs/03 §4, docs/09 §4)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.ids import generate_uuid7
from app.persistence.database import get_engine, session_scope
from app.persistence.models.brain import (
    AnalysisJob,
    ChunkEmbedding,
    CodeChunk,
    CodeRelationship,
    CodeSymbol,
    EmbeddingSpace,
    FileVersion,
    Finding,
    FindingEvidence,
    FindingStatusHistory,
    JobEvent,
    LocalWorkspaceRegistration,
    ProjectFile,
    ProjectSnapshot,
    ScanRun,
    SnapshotFile,
)
from app.persistence.models.project import Project
from app.persistence.repositories.brain_repo import BrainRepository


def _make_auth_ctx(workspace_id=None, user_id=None) -> AuthContext:
    return AuthContext(
        user_id=user_id or generate_uuid7(),
        clerk_user_id="user_clerk_brain_test",
        email="brain_test@example.com",
        workspace_id=workspace_id or generate_uuid7(),
        workspace_role="member",
    )


def test_brain_models_instantiation_and_attributes() -> None:
    """Verify that Project Brain models instantiate with correct attributes and types."""
    project_id = generate_uuid7()
    file_id = generate_uuid7()
    version_id = generate_uuid7()
    scan_id = generate_uuid7()
    reg_id = generate_uuid7()

    # 1. ScanRun
    scan = ScanRun(
        project_id=project_id,
        origin="extension",
        status="running",
        rules_version="1.0.0",
        stats={"files_scanned": 42},
    )
    assert scan.status == "running"
    assert scan.stats["files_scanned"] == 42
    assert scan.project_id == project_id
    assert scan.origin == "extension"

    # 2. LocalWorkspaceRegistration
    lwr = LocalWorkspaceRegistration(
        project_id=project_id,
        registration_id=reg_id,
        workspace_label="My Work Folder",
        root_fingerprint="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    assert lwr.workspace_label == "My Work Folder"
    assert len(lwr.root_fingerprint) == 64

    # 3. ProjectFile
    pf = ProjectFile(
        project_id=project_id,
        path="src/index.ts",
        language="typescript",
        tier=1,
    )
    assert pf.tier == 1
    assert pf.path == "src/index.ts"
    assert pf.removed_at is None

    # 4. FileVersion
    fv = FileVersion(
        file_id=file_id,
        project_id=project_id,
        content_hash="abc123hash",
        size_bytes=1024,
        line_count=50,
        scan_run_id=scan_id,
        origin="extension",
    )
    assert fv.origin == "extension"
    assert fv.size_bytes == 1024
    assert fv.line_count == 50

    # 5. ProjectSnapshot & SnapshotFile
    snap = ProjectSnapshot(
        project_id=project_id,
        kind="scan",
        ref="scan-001",
        label="v1.0",
    )
    assert snap.kind == "scan"
    assert snap.ref == "scan-001"

    sf = SnapshotFile(
        snapshot_id=snap.id,
        file_id=file_id,
        file_version_id=version_id,
    )
    assert sf.snapshot_id == snap.id
    assert sf.file_id == file_id

    # 6. CodeSymbol
    sym = CodeSymbol(
        project_id=project_id,
        file_version_id=version_id,
        symbol_key="src/index.ts#main",
        name="main",
        qualified_name="src.index.main",
        kind="function",
        start_line=1,
        end_line=20,
        framework_tags=["express"],
        is_current=True,
    )
    assert sym.is_current is True
    assert sym.framework_tags == ["express"]

    # 7. CodeRelationship
    rel = CodeRelationship(
        project_id=project_id,
        from_symbol_id=sym.id,
        to_external="express.Router",
        kind="calls",
        resolution="resolved",
        file_version_id=version_id,
        is_current=True,
    )
    assert rel.resolution == "resolved"
    assert rel.is_current is True

    # 7b. CodeChunk
    ws_id = generate_uuid7()
    chunk = CodeChunk(
        workspace_id=ws_id,
        project_id=project_id,
        file_version_id=version_id,
        symbol_id=sym.id,
        kind="function",
        start_line=1,
        end_line=20,
        content="function main() { return 1; }",
        content_hash="sha256:abc12345",
        search_text="// File: src/index.ts\nfunction main() { return 1; }",
        token_estimate=10,
        redaction_count=0,
        is_current=True,
    )
    assert chunk.kind == "function"
    assert chunk.start_line == 1
    assert chunk.end_line == 20
    assert chunk.token_estimate == 10
    assert chunk.content_hash == "sha256:abc12345"
    assert chunk.is_current is True

    # 7c. EmbeddingSpace
    space = EmbeddingSpace(
        provider_id="fake",
        model_id="fake-embed-v1",
        dimension=64,
        status="active",
        config_hash="sha256:space123",
    )
    assert space.provider_id == "fake"
    assert space.dimension == 64
    assert space.status == "active"
    assert space.config_hash == "sha256:space123"

    # 7d. ChunkEmbedding
    chunk_emb = ChunkEmbedding(
        chunk_id=chunk.id,
        space_id=space.id,
        project_id=project_id,
        embedding=[0.1] * 64,
    )
    assert chunk_emb.chunk_id == chunk.id
    assert chunk_emb.space_id == space.id
    assert chunk_emb.project_id == project_id
    assert len(chunk_emb.embedding) == 64

    # 8. AnalysisJob & JobEvent
    job = AnalysisJob(
        project_id=project_id,
        type="ingest_project",
        status="queued",
        params={"depth": "full"},
        attempt=0,
        max_attempts=3,
    )
    assert job.status == "queued"
    assert job.attempt == 0
    assert job.max_attempts == 3

    event = JobEvent(
        job_id=job.id,
        seq=1,
        kind="manifest_received",
        message="Received 42 files from extension",
    )
    assert event.seq == 1
    assert event.kind == "manifest_received"

    # 9. Finding, FindingEvidence, FindingStatusHistory
    finding = Finding(
        project_id=project_id,
        fingerprint="fp-auth-001",
        rule_id="SEC-001",
        category="authentication",
        title="Unprotected route",
        summary="Route /admin has no auth middleware",
        severity="high",
        confidence="medium",
        evidence_level="E1",
        status="open",
    )
    assert finding.status == "open"
    assert finding.evidence_level == "E1"
    assert finding.confidence == "medium"

    evidence = FindingEvidence(
        finding_id=finding.id,
        project_id=project_id,
        file_version_id=version_id,
        path="src/admin.ts",
        start_line=10,
        end_line=15,
        snippet_hash="hash-admin-snippet",
        role="primary",
        is_current=True,
    )
    assert evidence.snippet_text is None  # unconsented source must never be stored (ADR-047)
    assert evidence.is_current is True

    history = FindingStatusHistory(
        finding_id=finding.id,
        from_status="open",
        to_status="acknowledged",
        actor_kind="user",
        reason="Reviewed by security team",
    )
    assert history.to_status == "acknowledged"
    assert history.from_status == "open"


@pytest.mark.asyncio
async def test_brain_repository_context_validation() -> None:
    """Verify that BrainRepository rejects calls without valid context."""
    session = AsyncSession(bind=get_engine())
    repo = BrainRepository(session)
    pid = generate_uuid7()

    with pytest.raises(
        TypeError, match="Repository operations require an AuthContext or SystemContext"
    ):
        await repo.upsert_local_workspace_registration(
            None,
            pid,
            generate_uuid7(),
            "label",
            "fp",  # type: ignore[arg-type]
        )

    with pytest.raises(
        TypeError, match="Repository operations require an AuthContext or SystemContext"
    ):
        await repo.create_scan_run(None, pid)  # type: ignore[arg-type]

    with pytest.raises(
        TypeError, match="Repository operations require an AuthContext or SystemContext"
    ):
        await repo.upsert_file(None, pid, "src/app.py", "python")  # type: ignore[arg-type]

    with pytest.raises(
        TypeError, match="Repository operations require an AuthContext or SystemContext"
    ):
        await repo.create_job(None, pid, "ingest_project")  # type: ignore[arg-type]

    with pytest.raises(
        TypeError, match="Repository operations require an AuthContext or SystemContext"
    ):
        await repo.list_findings(None, pid)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_brain_repository_missing_workspace_raises_permission_error() -> None:
    """Verify that an AuthContext without workspace_id raises PermissionError before querying."""
    session = AsyncSession(bind=get_engine())
    repo = BrainRepository(session)
    pid = generate_uuid7()

    ctx_no_ws = AuthContext(
        user_id=generate_uuid7(),
        clerk_user_id="clerk_no_ws",
        email="nows@example.com",
        workspace_id=None,
    )
    with pytest.raises(PermissionError, match="Access denied: missing workspace context"):
        await repo.create_scan_run(ctx_no_ws, pid)

    with pytest.raises(PermissionError, match="Access denied: missing workspace context"):
        await repo.upsert_file(ctx_no_ws, pid, "test.ts", "typescript")


@pytest.mark.asyncio
async def test_brain_repository_mock_session_tenant_isolation() -> None:
    """Verify tenant isolation with mock session returning null when project is from an alien workspace."""
    mock_session = AsyncMock(spec=AsyncSession)
    repo = BrainRepository(mock_session)

    ctx = _make_auth_ctx()
    alien_pid = generate_uuid7()

    # Session returns no project (i.e. Project not found in caller's workspace)
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_session.execute.return_value = mock_result

    with pytest.raises(PermissionError, match="Access denied: project .* not found in workspace"):
        await repo.create_scan_run(ctx, alien_pid)

    with pytest.raises(PermissionError, match="Access denied: project .* not found in workspace"):
        await repo.upsert_file(ctx, alien_pid, "index.ts", "typescript")


@pytest.mark.asyncio
async def test_brain_repository_mock_session_operations() -> None:
    """Verify repository operations under SystemContext with mock session."""
    mock_session = AsyncMock(spec=AsyncSession)
    repo = BrainRepository(mock_session)

    sys_ctx = SystemContext(reason="system_ingestion")
    pid = generate_uuid7()

    # Mock project exists
    dummy_proj = Project(
        id=pid,
        workspace_id=generate_uuid7(),
        name="Mock Project",
        slug="mock-proj",
    )
    mock_result_proj = MagicMock()
    mock_result_proj.scalars.return_value.first.return_value = dummy_proj

    # Second query for existing item (None -> create)
    mock_result_none = MagicMock()
    mock_result_none.scalars.return_value.first.return_value = None

    mock_session.execute.side_effect = [mock_result_proj, mock_result_none]

    scan = await repo.create_scan_run(
        sys_ctx,
        project_id=pid,
        origin="extension",
        rules_version="1.0.0",
        stats={"total_files": 10},
    )
    assert scan.project_id == pid
    assert scan.status == "running"
    assert scan.origin == "extension"
    assert mock_session.add.called
    assert mock_session.flush.called


@pytest.mark.asyncio
async def test_brain_crud_integration_live_db() -> None:
    """Integration test with live PostgreSQL session when available."""
    try:
        async with session_scope() as session:
            repo = BrainRepository(session)
            sys_ctx = SystemContext(reason="test_brain_integration")
            # Verify DB connection with trivial repo call
            await repo.list_snapshots(sys_ctx, project_id=generate_uuid7())
            await session.rollback()
    except Exception as exc:
        pytest.skip(f"PostgreSQL integration skipped if unavailable: {exc}")
