"""Tests for SQLAlchemy models: table names, constraints, and attribute defaults."""

from app.core.ids import generate_uuid7
from app.persistence.models import (
    Base,
    Project,
    User,
    Workspace,
)


def test_model_tables_registered_in_metadata() -> None:
    """Verify that all initial tenancy models are registered in Base.metadata."""
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "users",
        "workspaces",
        "workspace_memberships",
        "projects",
        "project_memberships",
        "audit_events",
        "usage_records",
    }
    assert expected.issubset(table_names)


def test_user_model_instantiation() -> None:
    """Verify User model field assignments and UUID default."""
    user = User(
        clerk_user_id="user_clerk_test",
        email="warish@example.com",
        display_name="Warish",
    )
    assert user.clerk_user_id == "user_clerk_test"
    assert user.email == "warish@example.com"
    assert user.display_name == "Warish"
    assert user.deleted_at is None


def test_workspace_and_project_model_defaults() -> None:
    """Verify Workspace and Project default values."""
    user_id = generate_uuid7()
    workspace_id = generate_uuid7()

    workspace = Workspace(
        name="Personal Workspace",
        slug="personal-ws",
        kind="personal",
        created_by=user_id,
    )
    assert workspace.name == "Personal Workspace"
    assert workspace.kind == "personal"

    project = Project(
        workspace_id=workspace_id,
        name="DevMind Core",
        slug="devmind-core",
        visibility="workspace",
        sync_mode="metadata_only",
        source_kind="local",
        default_branch="main",
    )
    assert project.workspace_id == workspace_id
    assert project.slug == "devmind-core"
    assert project.default_branch == "main"
