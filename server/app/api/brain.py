"""Project Brain REST endpoints for snapshots, structure, and search (docs/03 §11.1)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    BrainFileDetail,
    BrainFileItem,
    BrainSearchRequest,
    BrainSearchResponse,
    BrainSummaryResponse,
    CodeSymbolItem,
    CreateSnapshotRequest,
    GraphResponse,
    SnapshotDetail,
    SnapshotDiffResponse,
    SnapshotItem,
)
from app.core.auth_context import AuthContext
from app.domain.auth import (
    PERM_BRAIN_READ,
    PERM_PROJECT_UPDATE,
    declare_permission,
    get_auth_context,
    get_db_session,
    require_permission,
)
from app.domain.brain import BrainService, RetrievalService, SnapshotService, SymbolService

router = APIRouter(
    prefix="/projects/{pid}/brain",
    tags=["Project Brain"],
    dependencies=[Depends(get_auth_context)],
)


@router.post(
    "/snapshots",
    response_model=SnapshotItem,
    status_code=status.HTTP_201_CREATED,
    summary="Capture a point-in-time project snapshot",
)
@declare_permission(PERM_PROJECT_UPDATE)
async def create_snapshot(
    pid: UUID,
    payload: CreateSnapshotRequest,
    ctx: AuthContext = Depends(require_permission(PERM_PROJECT_UPDATE)),
    session: AsyncSession = Depends(get_db_session),
) -> SnapshotItem:
    """Capture an immutable point-in-time snapshot of current project files and versions."""
    service = SnapshotService(session)
    scoped_ctx = await service.resolve_project_context(ctx, pid)
    return await service.create_snapshot(scoped_ctx, pid, payload)


@router.get(
    "/snapshots",
    response_model=list[SnapshotItem],
    summary="List recent project snapshots",
)
@declare_permission(PERM_BRAIN_READ)
async def list_snapshots(
    pid: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    ctx: AuthContext = Depends(require_permission(PERM_BRAIN_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> list[SnapshotItem]:
    """List recent snapshots captured for the project."""
    service = SnapshotService(session)
    scoped_ctx = await service.resolve_project_context(ctx, pid)
    return await service.list_snapshots(scoped_ctx, pid, limit=limit)


@router.get(
    "/snapshots/{sid}",
    response_model=SnapshotDetail,
    summary="Get snapshot details and file version mappings",
)
@declare_permission(PERM_BRAIN_READ)
async def get_snapshot_detail(
    pid: UUID,
    sid: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_BRAIN_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> SnapshotDetail:
    """Retrieve complete metadata and all file version mappings for a specific snapshot."""
    service = SnapshotService(session)
    scoped_ctx = await service.resolve_project_context(ctx, pid)
    return await service.get_snapshot_detail(scoped_ctx, pid, sid)


@router.get(
    "/snapshots/{sid}/diff",
    response_model=SnapshotDiffResponse,
    summary="Compare snapshot against another snapshot or active state",
)
@declare_permission(PERM_BRAIN_READ)
async def compare_snapshots(
    pid: UUID,
    sid: UUID,
    target_snapshot_id: UUID | None = Query(default=None),
    ctx: AuthContext = Depends(require_permission(PERM_BRAIN_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> SnapshotDiffResponse:
    """Compare a base snapshot against a target snapshot or the current active project state."""
    service = SnapshotService(session)
    scoped_ctx = await service.resolve_project_context(ctx, pid)
    return await service.compare_snapshots(
        scoped_ctx, pid, base_snapshot_id=sid, target_snapshot_id=target_snapshot_id
    )


@router.get(
    "/symbols",
    response_model=list[CodeSymbolItem],
    summary="List active code symbols in project",
)
@declare_permission(PERM_BRAIN_READ)
async def list_symbols(
    pid: UUID,
    kind: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    ctx: AuthContext = Depends(require_permission(PERM_BRAIN_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> list[CodeSymbolItem]:
    """List current active semantic code symbols discovered in the project."""
    service = SymbolService(session)
    scoped_ctx = await service.resolve_project_context(ctx, pid)
    return await service.list_current_symbols(scoped_ctx, pid, kind=kind, limit=limit)


@router.get(
    "/graph",
    response_model=GraphResponse,
    summary="Get architectural symbol and relationship graph",
)
@declare_permission(PERM_BRAIN_READ)
async def get_graph(
    pid: UUID,
    symbol_key: str | None = Query(default=None),
    depth: int = Query(default=2, ge=1, le=5),
    limit: int = Query(default=200, ge=1, le=500),
    ctx: AuthContext = Depends(require_permission(PERM_BRAIN_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> GraphResponse:
    """Derive and return the architectural symbol dependency graph."""
    service = SymbolService(session)
    scoped_ctx = await service.resolve_project_context(ctx, pid)
    return await service.get_graph(
        scoped_ctx, pid, root_symbol_key=symbol_key, depth=depth, limit=limit
    )


@router.get(
    "/summary",
    response_model=BrainSummaryResponse,
    summary="Get aggregated Project Brain summary metrics",
)
@declare_permission(PERM_BRAIN_READ)
async def get_brain_summary(
    pid: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_BRAIN_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> BrainSummaryResponse:
    """Retrieve health and structural aggregation metrics for the project brain."""
    service = BrainService(session)
    scoped_ctx = await service.resolve_project_context(ctx, pid)
    return await service.get_summary(scoped_ctx, pid)


@router.get(
    "/files",
    response_model=list[BrainFileItem],
    summary="List active files with current version metadata",
)
@declare_permission(PERM_BRAIN_READ)
async def list_brain_files(
    pid: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_BRAIN_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> list[BrainFileItem]:
    """List all non-removed files with their current content hash and metrics."""
    service = BrainService(session)
    scoped_ctx = await service.resolve_project_context(ctx, pid)
    return await service.list_files(scoped_ctx, pid)


@router.get(
    "/files/{fid}",
    response_model=BrainFileDetail,
    summary="Get file detail and version history",
)
@declare_permission(PERM_BRAIN_READ)
async def get_brain_file_detail(
    pid: UUID,
    fid: UUID,
    ctx: AuthContext = Depends(require_permission(PERM_BRAIN_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> BrainFileDetail:
    """Retrieve detailed file metadata and all historical versions."""
    service = BrainService(session)
    scoped_ctx = await service.resolve_project_context(ctx, pid)
    return await service.get_file_detail(scoped_ctx, pid, fid)


@router.post(
    "/search",
    response_model=BrainSearchResponse,
    summary="Multi-channel hybrid brain search with fusion and context pack",
)
@declare_permission(PERM_BRAIN_READ)
async def search_brain(
    pid: UUID,
    payload: BrainSearchRequest,
    ctx: AuthContext = Depends(require_permission(PERM_BRAIN_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> BrainSearchResponse:
    """Execute multi-channel hybrid search (symbols, keywords, vectors) with RRF fusion and context pack."""
    service = BrainService(session)
    scoped_ctx = await service.resolve_project_context(ctx, pid)
    retrieval_service = RetrievalService(session)
    return await retrieval_service.search(scoped_ctx, pid, payload)

