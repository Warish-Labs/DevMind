"""SQLAlchemy persistence models."""

from app.persistence.models.audit import AuditEvent
from app.persistence.models.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    UUID7PrimaryKeyMixin,
)
from app.persistence.models.brain import (
    AnalysisJob,
    ChunkEmbedding,
    CodeChunk,
    CodeRelationship,
    CodeSymbol,
    EmbeddingSpace,
    File,
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
from app.persistence.models.consent import ConsentRecord
from app.persistence.models.extension import ExtensionRegistration, ExtensionToken
from app.persistence.models.project import Project, ProjectMembership
from app.persistence.models.usage import UsageRecord
from app.persistence.models.user import User
from app.persistence.models.workspace import Workspace, WorkspaceMembership

__all__ = [
    "AnalysisJob",
    "AuditEvent",
    "Base",
    "ChunkEmbedding",
    "CodeChunk",
    "CodeRelationship",
    "CodeSymbol",
    "ConsentRecord",
    "EmbeddingSpace",
    "ExtensionRegistration",
    "ExtensionToken",
    "File",
    "FileVersion",
    "Finding",
    "FindingEvidence",
    "FindingStatusHistory",
    "JobEvent",
    "LocalWorkspaceRegistration",
    "Project",
    "ProjectFile",
    "ProjectMembership",
    "ProjectSnapshot",
    "ScanRun",
    "SnapshotFile",
    "SoftDeleteMixin",
    "TimestampMixin",
    "UUID7PrimaryKeyMixin",
    "UsageRecord",
    "User",
    "Workspace",
    "WorkspaceMembership",
]
