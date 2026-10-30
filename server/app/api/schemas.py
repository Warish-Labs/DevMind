"""Pydantic request and response schemas for Workspaces and Projects REST APIs (docs/03 §12)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.brain import (
    BatchFindingsRequest,
    BatchFindingsResponse,
    BatchRelationshipsRequest,
    BatchRelationshipsResponse,
    BatchSymbolsRequest,
    BatchSymbolsResponse,
    BrainCitation,
    BrainFileDetail,
    BrainFileItem,
    BrainFileVersionItem,
    BrainSearchItem,
    BrainSearchRequest,
    BrainSearchResponse,
    BrainSummaryResponse,
    CodeRelationshipItem,
    CodeRelationshipPayload,
    CodeSymbolItem,
    CodeSymbolPayload,
    ContextPack,
    CreateSnapshotRequest,
    FileManifestEntry,
    FindingDetailItem,
    FindingEvidenceItem,
    FindingEvidencePayload,
    FindingItem,
    FindingLocationPayload,
    FindingPayload,
    FindingStatusHistoryItem,
    FindingStatusTransitionRequest,
    GraphEdge,
    GraphNode,
    GraphResponse,
    ManifestDiffRequest,
    ManifestDiffResponse,
    MissingFileEntry,
    PutManifestRequest,
    PutManifestResponse,
    ScanRunItem,
    SnapshotDetail,
    SnapshotDiffItem,
    SnapshotDiffResponse,
    SnapshotFileItem,
    SnapshotItem,
    SuggestedFixPayload,
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


class CreateInvitationRequest(BaseModel):
    """Payload for inviting a user to a workspace."""

    email: str = Field(min_length=3, max_length=255, description="Email address of the invitee")
    role: str = Field(default="member", description="admin | member | viewer")


class WorkspaceInvitationResponse(BaseModel):
    """Serialized workspace invitation entity."""

    id: UUID
    workspace_id: UUID
    email: str
    role: str
    invited_by: UUID | None = None
    expires_at: datetime
    accepted_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateInvitationResponse(BaseModel):
    """Response returned when an invitation is issued."""

    invitation: WorkspaceInvitationResponse
    accept_url: str


class VerifyInvitationResponse(BaseModel):
    """Verification metadata for an invitation preview."""

    invitation_id: UUID
    workspace_id: UUID
    workspace_name: str
    email: str
    role: str
    inviter_name: str
    expires_at: datetime


class AcceptInvitationRequest(BaseModel):
    """Payload for accepting a workspace invitation."""

    token: str = Field(min_length=1, description="Raw invitation token")


class AcceptInvitationResponse(BaseModel):
    """Response returned after successfully accepting an invitation."""

    status: str
    workspace_id: UUID
    workspace_name: str
    role: str
    user_id: UUID


class AuditEventItem(BaseModel):
    """Serialized audit event for workspace governance and security logs (docs/03 §3.5 & docs/07 §16)."""

    id: UUID
    workspace_id: UUID
    actor_id: UUID | None = None
    actor_kind: str
    action: str
    target_kind: str
    target_id: str | None = None
    ip_hash: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def populate_metadata(cls, data: Any) -> Any:
        if hasattr(data, "metadata_json") and not isinstance(data, dict):
            return {
                "id": data.id,
                "workspace_id": data.workspace_id,
                "actor_id": data.actor_id,
                "actor_kind": data.actor_kind,
                "action": data.action,
                "target_kind": data.target_kind,
                "target_id": data.target_id,
                "ip_hash": data.ip_hash,
                "metadata": data.metadata_json or {},
                "created_at": data.created_at,
            }
        return data


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


class UpdateSyncModeRequest(BaseModel):
    """Payload for transitioning project synchronization mode (ADR-022)."""

    sync_mode: str = Field(description="Target sync mode: metadata_only | indexed")


class SyncModeTransitionResponse(BaseModel):
    """Result of transitioning project synchronization mode with purge metrics."""

    project_id: UUID
    workspace_id: UUID
    previous_sync_mode: str
    new_sync_mode: str
    purged_counts: dict[str, int]
    transitioned_at: datetime


class PurgeProjectDataRequest(BaseModel):
    """Payload for executing a project data purge (M9-03)."""

    scope: str = Field(default="all", description="Purge scope: all | chunks_and_embeddings")
    confirmation_slug: str | None = Field(
        default=None, description="Typed confirmation slug matching the target project"
    )


class DeletionVerificationReport(BaseModel):
    """Cryptographically signed deletion verification report (docs/11, Screen S-10)."""

    project_id: str
    workspace_id: str
    requested_by: str
    purged_at: str
    scope: str
    stores: dict[str, dict[str, int]]
    verification_hash: str
    sync_mode: str
    status: str


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
# Consented Snippet Upload Schemas (docs/03 §12.4)
# ---------------------------------------------------------------------------


class SnippetItem(BaseModel):
    """Individual code snippet payload."""

    path: str = Field(description="Repo-relative file path.")
    file_content_hash: str = Field(description="SHA-256 hash of the full file content.")
    start_line: int = Field(ge=1, description="1-indexed starting line number.")
    end_line: int = Field(ge=1, description="1-indexed ending line number.")
    content: str = Field(description="Redacted code snippet content.")
    redaction_count: int = Field(default=0, ge=0, description="Client-performed redaction count.")
    client_redaction_version: str = Field(default="1", description="Redaction engine version.")


class SnippetPurpose(BaseModel):
    """Purpose descriptor for the snippet transmission."""

    kind: str = Field(default="analysis", description="Purpose kind: analysis | chat | review.")
    job_type: str = Field(default="security_review", description="Job type if kind is analysis.")


class SnippetUploadRequest(BaseModel):
    """Consented snippet upload request payload (docs/03 §12.4)."""

    consent_id: str = Field(description="Active consent record UUID.")
    purpose: SnippetPurpose = Field(default_factory=SnippetPurpose)
    snippets: list[SnippetItem] = Field(default_factory=list, max_length=50)


class SnippetReceiptItem(BaseModel):
    """Receipt item confirming accepted snippet metadata (no raw code stored in receipt)."""

    path: str
    start_line: int
    end_line: int
    redaction_count: int


class SnippetUploadResponse(BaseModel):
    """Receipt response confirming accepted snippets and server-side redactions."""

    accepted_snippets_count: int
    total_redaction_count: int
    receipt_hash: str
    server_redactions_added: int
    snippets: list[SnippetReceiptItem] = Field(default_factory=list)
    job: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Background Analysis Jobs and Event Streaming Schemas (docs/03 §5.2, §12.2)
# ---------------------------------------------------------------------------


class CreateAnalysisRequest(BaseModel):
    """Request to initiate a background analysis or agent workflow (docs/03 §12.2)."""

    type: str = Field(
        ...,
        description="Type of analysis to execute: ask_project, security_review, comprehensive_review, embed_chunks",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Execution parameters, query strings, and scope configuration",
    )
    consent_id: UUID | None = Field(
        default=None,
        description="Optional active consent UUID for accessing code snippets",
    )


class AnalysisJobResponse(BaseModel):
    """Analysis job model representing asynchronous work (docs/03 §3.3)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    type: str
    status: str
    attempt: int | None = 0
    max_attempts: int | None = 3
    queue: str | None = "default"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_code: str | None = None
    error_detail: str | None = None
    result_ref: dict[str, Any] | None = None
    created_at: datetime


class AnalysisJobCreatedResponse(BaseModel):
    """202 Accepted response containing created job and streaming links (docs/03 §12.2)."""

    job: AnalysisJobResponse
    links: dict[str, str] = Field(
        description="Navigation and event streaming links for the created job"
    )


class JobEventResponse(BaseModel):
    """Milestone event log emitted by a running job (docs/03 §3.3)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    seq: int
    kind: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


# ---------------------------------------------------------------------------
# Retention Policy Schemas (docs/03 §3.1, docs/07 §9, ADR-026)
# ---------------------------------------------------------------------------


class UpdateRetentionPolicyRequest(BaseModel):
    """Payload to update retention period for a category."""

    days: int = Field(ge=1, le=3650, description="Retention period in days (minimum 1 day)")


class RetentionPolicyResponse(BaseModel):
    """Configured retention policy record."""

    id: str
    workspace_id: str
    project_id: str | None = None
    kind: str
    days: int
    is_override: bool = False
    created_at: str
    updated_at: str


class EffectiveRetentionCategory(BaseModel):
    """Effective retention category status."""

    kind: str
    days: int
    default_days: int
    description: str
    is_custom: bool
    source: str


class EffectiveRetentionResponse(BaseModel):
    """Effective retention window settings for workspace or project."""

    workspace_id: str
    project_id: str | None = None
    backup_retention_notice: str
    categories: list[EffectiveRetentionCategory]


class RetentionSweepResponse(BaseModel):
    """Summary of executed retention cleanup sweep."""

    project_id: str
    swept_at: str
    purged_counts: dict[str, int]
    effective_windows: dict[str, int]


# ---------------------------------------------------------------------------
# Manifest and Brain Sync Schemas (docs/03 §12.3)
# ---------------------------------------------------------------------------

__all__ = [
    "AnalysisJobCreatedResponse",
    "AnalysisJobResponse",
    "AuditEventItem",
    "CreateAnalysisRequest",
    "JobEventResponse",
    "AddProjectMemberRequest",
    "BatchFindingsRequest",
    "BatchFindingsResponse",
    "BatchRelationshipsRequest",
    "BatchRelationshipsResponse",
    "BatchSymbolsRequest",
    "BatchSymbolsResponse",
    "BrainCitation",
    "BrainFileDetail",
    "BrainFileItem",
    "BrainFileVersionItem",
    "BrainSearchItem",
    "BrainSearchRequest",
    "BrainSearchResponse",
    "BrainSummaryResponse",
    "CodeRelationshipItem",
    "CodeRelationshipPayload",
    "CodeSymbolItem",
    "CodeSymbolPayload",
    "ContextPack",
    "CreateProjectRequest",
    "CreateSnapshotRequest",
    "CreateWorkspaceRequest",
    "ExtensionHeartbeatResponse",
    "ExtensionRefreshTokenRequest",
    "ExtensionTokenRequest",
    "ExtensionTokenResponse",
    "FileManifestEntry",
    "FindingDetailItem",
    "FindingEvidenceItem",
    "FindingEvidencePayload",
    "FindingItem",
    "FindingLocationPayload",
    "FindingPayload",
    "FindingStatusHistoryItem",
    "FindingStatusTransitionRequest",
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
    "ScanRunItem",
    "SnapshotDetail",
    "SnapshotDiffItem",
    "SnapshotDiffResponse",
    "SnapshotFileItem",
    "SnapshotItem",
    "SnippetItem",
    "SnippetPurpose",
    "SnippetReceiptItem",
    "SnippetUploadRequest",
    "SnippetUploadResponse",
    "SuggestedFixPayload",
    "UpdateProjectMemberRequest",
    "UpdateProjectRequest",
    "UpdateWorkspaceRequest",
    "WorkspaceMemberResponse",
    "WorkspaceResponse",
]
