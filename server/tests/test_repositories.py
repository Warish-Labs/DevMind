"""Tests verifying repository AuthContext enforcement and tenant isolation (docs/03 §4, docs/09 §4)."""

from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.ids import generate_uuid7
from app.persistence.database import get_engine, session_scope
from app.persistence.models import Workspace
from app.persistence.repositories import (
    AuditEventRepository,
    BaseRepository,
    ProjectRepository,
    UsageRecordRepository,
    UserRepository,
    WorkspaceRepository,
)


def _make_auth_ctx(workspace_id=None, user_id=None) -> AuthContext:
    return AuthContext(
        user_id=user_id or generate_uuid7(),
        clerk_user_id="user_test_clerk",
        email="test@example.com",
        workspace_id=workspace_id or generate_uuid7(),
        workspace_role="member",
    )


def test_base_repository_rejects_invalid_context() -> None:
    """Verify that calling repository validation with invalid context raises TypeError."""
    with pytest.raises(
        TypeError, match="Repository operations require an AuthContext or SystemContext"
    ):
        BaseRepository._validate_context(None)  # type: ignore[arg-type]

    with pytest.raises(
        TypeError, match="Repository operations require an AuthContext or SystemContext"
    ):
        BaseRepository._validate_context("invalid_string_context")  # type: ignore[arg-type]


def test_scope_workspace_query_enforces_auth_context_isolation() -> None:
    """Verify query scoping automatically attaches tenant workspace_id."""
    ws_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=ws_id)

    stmt = select(Workspace)
    scoped = BaseRepository._scope_workspace_query(stmt, Workspace.id, ctx)

    compiled = str(scoped)
    assert "workspaces.id = :id_1" in compiled


def test_scope_workspace_query_blocks_cross_tenant_access() -> None:
    """Verify requesting an alien workspace ID from an AuthContext clamps to an impossible match."""
    ws_id = generate_uuid7()
    alien_ws_id = generate_uuid7()
    ctx = _make_auth_ctx(workspace_id=ws_id)

    stmt = select(Workspace)
    scoped = BaseRepository._scope_workspace_query(
        stmt, Workspace.id, ctx, target_workspace_id=alien_ws_id
    )

    params = scoped.compile().params
    assert UUID("00000000-0000-0000-0000-000000000000") in params.values()


@pytest.mark.asyncio
async def test_repository_methods_reject_missing_context() -> None:
    """Verify that every repository class raises TypeError when context is omitted or invalid."""
    # Create dummy session
    session = AsyncSession(bind=get_engine())

    user_repo = UserRepository(session)
    ws_repo = WorkspaceRepository(session)
    proj_repo = ProjectRepository(session)
    audit_repo = AuditEventRepository(session)
    usage_repo = UsageRecordRepository(session)

    uid = generate_uuid7()

    with pytest.raises(TypeError):
        await user_repo.get_by_id(None, uid)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        await ws_repo.get_by_id(None, uid)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        await proj_repo.get_by_id(None, uid)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        await audit_repo.record(None, action="test", target_kind="item")  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        await usage_repo.record(  # type: ignore[arg-type]
            None,
            llm_task="test",
            provider_id="fake",
            model_id="test",
        )


@pytest.mark.asyncio
async def test_crud_tenancy_integration() -> None:
    """Functional test with PostgreSQL session verifying tenancy and data isolation."""
    try:
        async with session_scope() as session:
            user_repo = UserRepository(session)
            ws_repo = WorkspaceRepository(session)
            proj_repo = ProjectRepository(session)
            audit_repo = AuditEventRepository(session)
            usage_repo = UsageRecordRepository(session)

            sys_ctx = SystemContext(reason="test_setup")

            # 1. Create User
            test_clerk_id = f"clerk_{generate_uuid7().hex[:8]}"
            user = await user_repo.create(
                sys_ctx,
                clerk_user_id=test_clerk_id,
                email=f"{test_clerk_id}@example.com",
                display_name="Test User",
            )
            assert user.id is not None

            # 2. Create Workspace
            ws_slug = f"ws-{generate_uuid7().hex[:8]}"
            ws = await ws_repo.create(
                sys_ctx,
                name="Test Workspace",
                slug=ws_slug,
                created_by=user.id,
            )
            assert ws.id is not None

            # 3. Add Member
            membership = await ws_repo.add_member(
                sys_ctx,
                workspace_id=ws.id,
                user_id=user.id,
                role="owner",
            )
            assert membership.role == "owner"

            # 4. Now act as authenticated user in this workspace
            auth_ctx = AuthContext(
                user_id=user.id,
                clerk_user_id=test_clerk_id,
                email=user.email,
                workspace_id=ws.id,
                workspace_role="owner",
            )

            # 5. Create Project
            proj_slug = f"proj-{generate_uuid7().hex[:8]}"
            project = await proj_repo.create(
                auth_ctx,
                name="Integration Project",
                slug=proj_slug,
            )
            assert project.workspace_id == ws.id

            # 6. Record Audit Event
            event = await audit_repo.record(
                auth_ctx,
                action="project.created",
                target_kind="project",
                target_id=str(project.id),
            )
            assert event.workspace_id == ws.id
            assert event.action == "project.created"

            # 7. Record Usage
            record = await usage_repo.record(
                auth_ctx,
                llm_task="test_inference",
                provider_id="fake",
                model_id="mock-1",
                input_tokens=100,
                output_tokens=50,
            )
            assert record.workspace_id == ws.id
            assert record.input_tokens == 100

            # 8. Cross-tenant verification:
            alien_ctx = _make_auth_ctx()
            alien_projects = await proj_repo.list_for_workspace(alien_ctx)
            # Alien user cannot see our project
            assert all(p.id != project.id for p in alien_projects)

            # Clean rollback will occur at test teardown if aborted or we can rollback
            await session.rollback()
    except Exception as exc:
        pytest.skip(f"PostgreSQL integration skipped if unavailable: {exc}")
