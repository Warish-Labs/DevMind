"""Project Brain persistence models: files, versions, snapshots, symbols, relationships, jobs, findings (docs/03 §3.2-§3.4)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.models.base import (
    Base,
    TimestampMixin,
    UUID7PrimaryKeyMixin,
)
from app.persistence.models.vector import PGVector

if TYPE_CHECKING:
    from app.persistence.models.extension import ExtensionRegistration
    from app.persistence.models.project import Project
    from app.persistence.models.user import User
    from app.persistence.models.workspace import Workspace


class ScanRun(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """A single scanning run pass over a project (docs/03 §3.3)."""

    __tablename__ = "scan_runs"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "idempotency_key", name="uq_scan_runs_project_idempotency_key"
        ),
        CheckConstraint(
            "origin IN ('extension', 'cloud_fetch', 'github_pr')",
            name="ck_scan_runs_origin",
        ),
        CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'cancelled')",
            name="ck_scan_runs_status",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    origin: Mapped[str] = mapped_column(String(32), nullable=False, default="extension")
    registration_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("extension_registrations.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rules_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stats: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    project: Mapped[Project] = relationship("Project", foreign_keys=[project_id])
    registration: Mapped[ExtensionRegistration | None] = relationship(
        "ExtensionRegistration", foreign_keys=[registration_id]
    )


class LocalWorkspaceRegistration(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """A local folder linked to a project from an extension installation (docs/03 §3.1)."""

    __tablename__ = "local_workspace_registrations"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "registration_id",
            "root_fingerprint",
            name="uq_local_workspace_reg_triple",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    registration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("extension_registrations.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace_label: Mapped[str] = mapped_column(String(255), nullable=False)
    root_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash of the root folder path, never the raw absolute path",
    )
    last_scan_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scan_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    project: Mapped[Project] = relationship("Project", foreign_keys=[project_id])
    registration: Mapped[ExtensionRegistration] = relationship(
        "ExtensionRegistration", foreign_keys=[registration_id]
    )
    last_scan_run: Mapped[ScanRun | None] = relationship("ScanRun", foreign_keys=[last_scan_run_id])


class ProjectFile(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """A path within a project repository (docs/03 §3.2)."""

    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("project_id", "path", name="uq_files_project_path"),
        CheckConstraint("tier IN (1, 2, 3)", name="ck_files_tier"),
        Index("ix_files_path", "path"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    language: Mapped[str] = mapped_column(String(64), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("file_versions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    project: Mapped[Project] = relationship("Project", foreign_keys=[project_id])
    current_version: Mapped[FileVersion | None] = relationship(
        "FileVersion",
        foreign_keys=[current_version_id],
        post_update=True,
    )
    versions: Mapped[list[FileVersion]] = relationship(
        "FileVersion",
        primaryjoin="ProjectFile.id == FileVersion.file_id",
        back_populates="file",
        cascade="all, delete-orphan",
    )


# Alias
File = ProjectFile


class FileVersion(Base, UUID7PrimaryKeyMixin):
    """Immutable content identity and metrics for a file (docs/03 §3.2)."""

    __tablename__ = "file_versions"
    __table_args__ = (
        UniqueConstraint("file_id", "content_hash", name="uq_file_versions_file_content_hash"),
        Index("ix_file_versions_project_content_hash", "project_id", "content_hash"),
        CheckConstraint("origin IN ('extension', 'github')", name="ck_file_versions_origin"),
    )

    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    line_count: Mapped[int] = mapped_column(Integer, nullable=False)
    scan_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scan_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    origin: Mapped[str] = mapped_column(String(32), nullable=False, default="extension")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    file: Mapped[ProjectFile] = relationship(
        "ProjectFile", foreign_keys=[file_id], back_populates="versions"
    )
    project: Mapped[Project] = relationship("Project", foreign_keys=[project_id])
    scan_run: Mapped[ScanRun | None] = relationship("ScanRun", foreign_keys=[scan_run_id])
    symbols: Mapped[list[CodeSymbol]] = relationship(
        "CodeSymbol", back_populates="file_version", cascade="all, delete-orphan"
    )
    chunks: Mapped[list[CodeChunk]] = relationship(
        "CodeChunk", back_populates="file_version", cascade="all, delete-orphan"
    )


class ProjectSnapshot(Base, UUID7PrimaryKeyMixin):
    """Named snapshot of project file versions (docs/03 §3.2)."""

    __tablename__ = "project_snapshots"
    __table_args__ = (
        Index("ix_project_snapshots_project_created", "project_id", "created_at"),
        CheckConstraint("kind IN ('scan', 'commit', 'manual')", name="ck_project_snapshots_kind"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="scan")
    ref: Mapped[str] = mapped_column(String(255), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    project: Mapped[Project] = relationship("Project", foreign_keys=[project_id])
    snapshot_files: Mapped[list[SnapshotFile]] = relationship(
        "SnapshotFile", back_populates="snapshot", cascade="all, delete-orphan"
    )


class SnapshotFile(Base, UUID7PrimaryKeyMixin):
    """File version mapping within a snapshot (docs/03 §3.2)."""

    __tablename__ = "snapshot_files"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "file_id", name="uq_snapshot_files_snapshot_file"),
    )

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("file_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    snapshot: Mapped[ProjectSnapshot] = relationship(
        "ProjectSnapshot", back_populates="snapshot_files"
    )
    file: Mapped[ProjectFile] = relationship("ProjectFile", foreign_keys=[file_id])
    file_version: Mapped[FileVersion] = relationship("FileVersion", foreign_keys=[file_version_id])


class CodeSymbol(Base, UUID7PrimaryKeyMixin):
    """Named program element extracted from semantic parsing (docs/03 §3.2)."""

    __tablename__ = "code_symbols"
    __table_args__ = (
        Index("ix_code_symbols_project_symbol_key", "project_id", "symbol_key"),
        Index("ix_code_symbols_project_name", "project_id", "name"),
        Index("ix_code_symbols_project_current", "project_id", "is_current"),
        CheckConstraint(
            "kind IN ('function', 'method', 'class', 'route_handler', 'server_action', 'model', 'constant', 'module')",
            name="ck_code_symbols_kind",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("file_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol_key: Mapped[str] = mapped_column(String(512), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    qualified_name: Mapped[str] = mapped_column(String(512), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    framework_tags: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    project: Mapped[Project] = relationship("Project", foreign_keys=[project_id])
    file_version: Mapped[FileVersion] = relationship(
        "FileVersion", foreign_keys=[file_version_id], back_populates="symbols"
    )
    chunks: Mapped[list[CodeChunk]] = relationship("CodeChunk", back_populates="symbol")


class CodeRelationship(Base, UUID7PrimaryKeyMixin):
    """Typed structural edge between symbols or external references (docs/03 §3.2)."""

    __tablename__ = "code_relationships"
    __table_args__ = (
        Index("ix_code_relationships_from_kind", "project_id", "from_symbol_id", "kind"),
        Index("ix_code_relationships_to_kind", "project_id", "to_symbol_id", "kind"),
        CheckConstraint(
            "kind IN ('imports', 'calls', 'defines_route', 'guarded_by', 'reads_model', 'writes_model', 'tests', 'documents')",
            name="ck_code_relationships_kind",
        ),
        CheckConstraint(
            "resolution IN ('resolved', 'inferred', 'unresolved')",
            name="ck_code_relationships_resolution",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_symbol_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("code_symbols.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_symbol_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("code_symbols.id", ondelete="SET NULL"),
        nullable=True,
    )
    to_external: Mapped[str | None] = mapped_column(String(512), nullable=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    resolution: Mapped[str] = mapped_column(String(32), nullable=False, default="resolved")
    file_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("file_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    project: Mapped[Project] = relationship("Project", foreign_keys=[project_id])
    from_symbol: Mapped[CodeSymbol] = relationship("CodeSymbol", foreign_keys=[from_symbol_id])
    to_symbol: Mapped[CodeSymbol | None] = relationship("CodeSymbol", foreign_keys=[to_symbol_id])
    file_version: Mapped[FileVersion] = relationship("FileVersion", foreign_keys=[file_version_id])


class CodeChunk(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Searchable code piece with consented, redacted text and full-text/trigram indices (docs/03 §3.2, docs/04 §4)."""

    __tablename__ = "code_chunks"
    __table_args__ = (
        UniqueConstraint(
            "file_version_id",
            "start_line",
            "end_line",
            "content_hash",
            name="uq_code_chunks_version_lines_hash",
        ),
        Index("ix_code_chunks_workspace_id", "workspace_id"),
        Index("ix_code_chunks_project_id", "project_id"),
        Index("ix_code_chunks_file_version_id", "file_version_id"),
        Index("ix_code_chunks_symbol_id", "symbol_id"),
        Index("ix_code_chunks_project_current", "project_id", "is_current"),
        Index(
            "ix_code_chunks_search_tsvector",
            func.to_tsvector(text("'english'"), text("search_text")),
            postgresql_using="gin",
        ),
        Index(
            "ix_code_chunks_search_trgm",
            text("search_text"),
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
        CheckConstraint(
            "start_line >= 1 AND end_line >= start_line",
            name="ck_code_chunks_lines",
        ),
        CheckConstraint(
            "kind IN ('module_prelude', 'function', 'class', 'statement', 'heading', 'window')",
            name="ck_code_chunks_kind",
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("file_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("code_symbols.id", ondelete="SET NULL"),
        nullable=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    search_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False)
    redaction_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=func.true()
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship("Workspace", foreign_keys=[workspace_id])
    project: Mapped[Project] = relationship("Project", foreign_keys=[project_id])
    file_version: Mapped[FileVersion] = relationship(
        "FileVersion", foreign_keys=[file_version_id], back_populates="chunks"
    )
    symbol: Mapped[CodeSymbol | None] = relationship(
        "CodeSymbol", foreign_keys=[symbol_id], back_populates="chunks"
    )
    embeddings: Mapped[list[ChunkEmbedding]] = relationship(
        "ChunkEmbedding", back_populates="chunk", cascade="all, delete-orphan"
    )


class EmbeddingSpace(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Embedding space record identifying provider, model, dimension, and status (docs/03 §3.2, docs/04 §10)."""

    __tablename__ = "embedding_spaces"
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "model_id",
            "dimension",
            name="uq_embedding_spaces_provider_model_dim",
        ),
        Index("ix_embedding_spaces_status", "status"),
        Index("ix_embedding_spaces_provider_model", "provider_id", "model_id"),
        CheckConstraint(
            "status IN ('building', 'active', 'deprecated')",
            name="ck_embedding_spaces_status",
        ),
        CheckConstraint("dimension > 0", name="ck_embedding_spaces_dimension"),
    )

    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="building", server_default="building"
    )
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class ChunkEmbedding(Base):
    """Vector embedding for a code chunk in a specific embedding space (docs/03 §3.2, docs/04 §9)."""

    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        PrimaryKeyConstraint("chunk_id", "space_id", name="pk_chunk_embeddings"),
        Index("ix_chunk_embeddings_project_id", "project_id"),
        Index("ix_chunk_embeddings_space_id", "space_id"),
        Index(
            "ix_chunk_embeddings_hnsw",
            text("embedding vector_cosine_ops"),
            postgresql_using="hnsw",
        ),
    )

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("code_chunks.id", ondelete="CASCADE"),
        nullable=False,
    )
    space_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("embedding_spaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    embedding: Mapped[list[float]] = mapped_column(PGVector(64), nullable=False)
    embedded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    chunk: Mapped[CodeChunk] = relationship(
        "CodeChunk", foreign_keys=[chunk_id], back_populates="embeddings"
    )
    space: Mapped[EmbeddingSpace] = relationship("EmbeddingSpace", foreign_keys=[space_id])
    project: Mapped[Project] = relationship("Project", foreign_keys=[project_id])


class AnalysisJob(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Asynchronous background work unit (docs/03 §3.3)."""

    __tablename__ = "analysis_jobs"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "idempotency_key", name="uq_analysis_jobs_project_idempotency_key"
        ),
        Index("ix_analysis_jobs_status_heartbeat", "status", "heartbeat_at"),
        CheckConstraint(
            "status IN ('queued', 'running', 'awaiting_approval', 'succeeded', 'partially_succeeded', 'failed', 'cancel_requested', 'cancelled', 'timed_out')",
            name="ck_analysis_jobs_status",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    params: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    queue: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    result_ref: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    consent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    budget: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    project: Mapped[Project] = relationship("Project", foreign_keys=[project_id])
    user: Mapped[User | None] = relationship("User", foreign_keys=[requested_by])
    events: Mapped[list[JobEvent]] = relationship(
        "JobEvent", back_populates="job", cascade="all, delete-orphan"
    )


class JobEvent(Base, UUID7PrimaryKeyMixin):
    """Milestone event log for an asynchronous job (docs/03 §3.3)."""

    __tablename__ = "job_events"
    __table_args__ = (UniqueConstraint("job_id", "seq", name="uq_job_events_job_seq"),)

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(String(1024), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    job: Mapped[AnalysisJob] = relationship("AnalysisJob", back_populates="events")


class Finding(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """Reportable security, authorization or quality finding (docs/03 §3.4)."""

    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint("project_id", "fingerprint", name="uq_findings_project_fingerprint"),
        Index("ix_findings_project_status_severity", "project_id", "status", "severity"),
        CheckConstraint(
            "source IN ('scanner', 'devmind_rule', 'llm_verified')",
            name="ck_findings_source",
        ),
        CheckConstraint(
            "category IN ('authentication', 'authorization', 'secret_exposure', 'input_validation', 'error_handling', 'testing', 'documentation', 'configuration', 'dependency', 'quality', 'other')",
            name="ck_findings_category",
        ),
        CheckConstraint(
            "severity IN ('critical', 'high', 'medium', 'low', 'info')",
            name="ck_findings_severity",
        ),
        CheckConstraint(
            "confidence IN ('low', 'medium', 'high')",
            name="ck_findings_confidence",
        ),
        CheckConstraint(
            "evidence_level IN ('E0', 'E1', 'E2', 'E3')",
            name="ck_findings_evidence_level",
        ),
        CheckConstraint(
            "status IN ('open', 'acknowledged', 'in_progress', 'dismissed', 'accepted_risk', 'fix_proposed', 'stale', 'resolved', 'reopened')",
            name="ck_findings_status",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="scanner")
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    evidence_level: Mapped[str] = mapped_column(String(8), nullable=False, default="E1")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    first_seen_scan_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scan_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_seen_scan_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scan_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    primary_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="SET NULL"),
        nullable=True,
    )
    primary_start_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    primary_end_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    suggested_fix: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    project: Mapped[Project] = relationship("Project", foreign_keys=[project_id])
    primary_file: Mapped[ProjectFile | None] = relationship(
        "ProjectFile", foreign_keys=[primary_file_id]
    )
    first_seen_scan_run: Mapped[ScanRun | None] = relationship(
        "ScanRun", foreign_keys=[first_seen_scan_run_id]
    )
    last_seen_scan_run: Mapped[ScanRun | None] = relationship(
        "ScanRun", foreign_keys=[last_seen_scan_run_id]
    )
    evidence_items: Mapped[list[FindingEvidence]] = relationship(
        "FindingEvidence", back_populates="finding", cascade="all, delete-orphan"
    )
    status_history: Mapped[list[FindingStatusHistory]] = relationship(
        "FindingStatusHistory", back_populates="finding", cascade="all, delete-orphan"
    )


class FindingEvidence(Base, UUID7PrimaryKeyMixin):
    """Machine-checkable evidence item supporting a finding (docs/03 §3.4)."""

    __tablename__ = "finding_evidence"
    __table_args__ = (
        Index("ix_finding_evidence_project_path", "project_id", "path"),
        CheckConstraint(
            "role IN ('primary', 'supporting', 'missing_check')",
            name="ck_finding_evidence_role",
        ),
    )

    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("file_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    snippet_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    snippet_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Consented snippet text only; never store unconsented source text (ADR-047)",
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="primary")
    detail: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    finding: Mapped[Finding] = relationship("Finding", back_populates="evidence_items")
    project: Mapped[Project] = relationship("Project", foreign_keys=[project_id])
    file_version: Mapped[FileVersion | None] = relationship(
        "FileVersion", foreign_keys=[file_version_id]
    )


class FindingStatusHistory(Base, UUID7PrimaryKeyMixin):
    """Audit transition log for finding status changes (docs/03 §3.4, §5.1)."""

    __tablename__ = "finding_status_history"
    __table_args__ = (
        CheckConstraint(
            "actor_kind IN ('user', 'system')",
            name="ck_finding_status_history_actor_kind",
        ),
    )

    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[str] = mapped_column(String(32), nullable=False)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    finding: Mapped[Finding] = relationship("Finding", back_populates="status_history")


class AgentRun(Base, UUID7PrimaryKeyMixin, TimestampMixin):
    """A single LangGraph workflow execution pass (docs/03 §3.3, docs/05 §4.5)."""

    __tablename__ = "agent_runs"
    __table_args__ = (
        UniqueConstraint("thread_id", name="uq_agent_runs_thread_id"),
        Index("ix_agent_runs_job_id", "job_id"),
        Index("ix_agent_runs_project_id", "project_id"),
        Index("ix_agent_runs_workspace_id", "workspace_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow: Mapped[str] = mapped_column(String(64), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    prompt_versions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    model_choices: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    state_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    usage_totals: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # Relationships
    project: Mapped[Project] = relationship("Project", foreign_keys=[project_id])
    workspace: Mapped[Workspace] = relationship("Workspace", foreign_keys=[workspace_id])
    job: Mapped[AnalysisJob] = relationship("AnalysisJob", foreign_keys=[job_id])
