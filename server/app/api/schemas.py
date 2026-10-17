"""Pydantic request and response schemas for Workspaces and Projects REST APIs (docs/03 §12)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.brain import (
    BatchRelationshipsRequest,
    BatchRelationshipsResponse,
    BatchSymbolsRequest,
    BatchSymbolsResponse,
    CodeRelationshipItem,
    CodeRelationshipPayload,
    CodeSymbolItem,
    CodeSymbolPayload,
    CreateSnapshotRequest,
    FileManifestEntry,
    GraphEdge,
    GraphNode,
    GraphResponse,
    ManifestDiffRequest,
    ManifestDiffResponse,
    MissingFileEntry,
    PutManifestRequest,
    PutManifestResponse,
    SnapshotDetail,
    SnapshotDiffItem,
    SnapshotDiffResponse,
    SnapshotFileItem,
    SnapshotItem,
)

# ---------------------------------------------------------------------------
# Workspace Schemas
# ---------------------------------------------------------------------------


class CreateWorkspaceRequest(BaseModel):
    """Payload for creating a new workspace."""

    name: str = Field(min_length=1, max_length=120, description="Display name of the workspace")
    slug: str = Field(min_length=2, max_length=64, description="URL-safe unique workspace slug")
    kind: str = Field(default="personal", description="personal | team | enterprise")


class UpdateWorkspaceRequest(BaseModel):
    """Payload for updating mutable workspace attributes."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, min_length=2, max_length=64)
    kind: str | None = Field(default=None)


class WorkspaceResponse(BaseModel):
    """Serialized workspace entity."""

    id: UUID
    name: str
    slug: str
    kind: str
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceMemberResponse(BaseModel):
    """Serialized workspace member record."""

    workspace_id: UUID
    user_id: UUID
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AddWorkspaceMemberRequest(BaseModel):
    """Payload for adding a member to a workspace."""

    user_id: UUID
    role: str = Field(default="member", description="owner | admin | member | viewer")


class UpdateWorkspaceMemberRequest(BaseModel):
    """Payload for updating a member's workspace role."""

    role: str = Field(description="owner | admin | member | viewer")


# ---------------------------------------------------------------------------
# Project Schemas
# ---------------------------------------------------------------------------


class CreateProjectRequest(BaseModel):
    """Payload for creating a new codebase project."""

    name: str = Field(min_length=1, max_length=120, description="Project display name")
    slug: str = Field(min_length=2, max_length=64, description="URL-safe unique project slug")
    visibility: str = Field(default="workspace", description="workspace | private")
    sync_mode: str = Field(default="metadata_only", description="metadata_only | indexed")
    source_kind: str = Field(default="local", description="local | github | gitlab | bitbucket")
    primary_language: str | None = Field(default=None, max_length=64)
    default_branch: str = Field(default="main", max_length=128)


class UpdateProjectRequest(BaseModel):
    """Payload for updating mutable project attributes."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, min_length=2, max_length=64)
    visibility: str | None = Field(default=None)
    sync_mode: str | None = Field(default=None)
    primary_language: str | None = Field(default=None)
    default_branch: str | None = Field(default=None)


class ProjectResponse(BaseModel):
    """Serialized codebase project entity."""

    id: UUID
    workspace_id: UUID
    name: str
    slug: str
    visibility: str
    sync_mode: str
    source_kind: str
    primary_language: str | None = None
    default_branch: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None

    model_config = {"from_attributes": True}


class ProjectMemberResponse(BaseModel):
    """Serialized project member record."""

    project_id: UUID
    user_id: UUID
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AddProjectMemberRequest(BaseModel):
    """Payload for adding an explicit member to a project."""

    user_id: UUID
    role: str = Field(default="contributor", description="maintainer | contributor | viewer")


class UpdateProjectMemberRequest(BaseModel):
    """Payload for updating a project member's role."""

    role: str = Field(description="maintainer | contributor | viewer")


# ---------------------------------------------------------------------------
# Me / Identity Schemas
# ---------------------------------------------------------------------------


class UserProfileResponse(BaseModel):
    """Current authenticated user profile."""

    id: UUID
    clerk_user_id: str
    email: str
    display_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserPermissionsResponse(BaseModel):
    """Effective caller permissions for the current workspace and/or project."""

    user_id: UUID
    workspace_id: UUID | None = None
    workspace_role: str | None = None
    project_id: UUID | None = None
    project_role: str | None = None
    permissions: list[str]


# ---------------------------------------------------------------------------
# Extension Schemas (docs/03 §11.2, ADR-012)
# ---------------------------------------------------------------------------


class ExtensionTokenRequest(BaseModel):
    """Payload for registering an extension installation and requesting scoped tokens."""

    name: str = Field(
        default="VS Code",
        min_length=1,
        max_length=255,
        description="Name of the client installation",
    )
    platform: str = Field(
        default="unknown",
        min_length=1,
        max_length=64,
        description="Operating system/platform (e.g. linux, darwin, win32)",
    )
    extension_version: str = Field(
        default="0.1.0",
        min_length=1,
        max_length=64,
        description="Installed extension semver string",
    )
    scope: str = Field(
        default="project:sync",
        max_length=255,
        description="Requested scope permissions",
    )


class ExtensionTokenResponse(BaseModel):
    """Issued extension scoped access and refresh token pair."""

    access_token: str = Field(description="Opaque scoped access token")
    token_type: str = Field(default="Bearer")
    expires_in: int = Field(description="Access token lifetime in seconds")
    refresh_token: str = Field(description="Rotating refresh token")
    scope: str = Field(description="Authorized scopes")
    registration_id: UUID = Field(description="Assigned extension registration ID")


class ExtensionRefreshTokenRequest(BaseModel):
    """Payload for rotating extension refresh token."""

    refresh_token: str = Field(
        min_length=10,
        description="Rotating refresh token issued previously",
    )


class ExtensionHeartbeatResponse(BaseModel):
    """Heartbeat response confirming active registration."""

    status: str = "ok"
    registration_id: UUID
    last_seen_at: datetime


# ---------------------------------------------------------------------------
# Manifest and Brain Sync Schemas (docs/03 §12.3)
# ---------------------------------------------------------------------------

__all__ = [
    "AddProjectMemberRequest",
    "BatchRelationshipsRequest",
    "BatchRelationshipsResponse",
    "BatchSymbolsRequest",
    "BatchSymbolsResponse",
    "CodeRelationshipItem",
    "CodeRelationshipPayload",
    "CodeSymbolItem",
    "CodeSymbolPayload",
    "CreateProjectRequest",
    "CreateSnapshotRequest",
    "CreateWorkspaceRequest",
    "ExtensionHeartbeatResponse",
    "ExtensionRefreshTokenRequest",
    "ExtensionTokenRequest",
    "ExtensionTokenResponse",
    "FileManifestEntry",
    "GraphEdge",
    "GraphNode",
    "GraphResponse",
    "ManifestDiffRequest",
    "ManifestDiffResponse",
    "MissingFileEntry",
    "ProjectMemberResponse",
    "ProjectResponse",
    "PutManifestRequest",
    "PutManifestResponse",
    "SnapshotDetail",
    "SnapshotDiffItem",
    "SnapshotDiffResponse",
    "SnapshotFileItem",
    "SnapshotItem",
    "UpdateProjectMemberRequest",
    "UpdateProjectRequest",
    "UpdateWorkspaceRequest",
    "WorkspaceMemberResponse",
    "WorkspaceResponse",
]
