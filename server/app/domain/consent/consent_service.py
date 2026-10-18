"""Domain service for managing source transmission consent records and enforcement (docs/03 §4, docs/07 §7)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import ConsentRequiredError, NotFoundError, ValidationError
from app.persistence.database import session_scope
from app.persistence.models.consent import ConsentRecord
from app.persistence.repositories.audit_repo import AuditEventRepository
from app.persistence.repositories.brain_repo import BrainRepository
from app.persistence.repositories.consent_repo import ConsentRepository
from app.persistence.repositories.project_repo import ProjectRepository

ConsentScopeType = Literal["snippet_transmission", "cloud_index", "llm_processing"]
ConsentGrantedForType = Literal["single_request", "project"]

VALID_SCOPES = {"snippet_transmission", "cloud_index", "llm_processing"}
VALID_GRANTED_FOR = {"single_request", "project"}


class ConsentItem(BaseModel):
    """Consent record representation returned by API."""

    id: str
    workspace_id: str
    project_id: str
    user_id: str
    scope: str
    provider_ids: list[str]
    data_categories: list[str]
    granted_for: str
    policy_version: str
    preview_hash: str | None
    granted_at: str
    expires_at: str | None
    revoked_at: str | None
    is_active: bool
    purged_counts: dict[str, int] | None = None
    sync_mode_updated: bool = False
    new_sync_mode: str | None = None

    @classmethod
    def from_model(
        cls,
        record: ConsentRecord,
        purged_counts: dict[str, int] | None = None,
        sync_mode_updated: bool = False,
        new_sync_mode: str | None = None,
    ) -> ConsentItem:
        return cls(
            id=str(record.id),
            workspace_id=str(record.workspace_id),
            project_id=str(record.project_id),
            user_id=str(record.user_id),
            scope=record.scope,
            provider_ids=record.provider_ids or [],
            data_categories=record.data_categories or [],
            granted_for=record.granted_for,
            policy_version=record.policy_version,
            preview_hash=record.preview_hash,
            granted_at=record.granted_at.isoformat(),
            expires_at=record.expires_at.isoformat() if record.expires_at else None,
            revoked_at=record.revoked_at.isoformat() if record.revoked_at else None,
            is_active=record.is_active(),
            purged_counts=purged_counts,
            sync_mode_updated=sync_mode_updated,
            new_sync_mode=new_sync_mode,
        )


class CreateConsentRequest(BaseModel):
    """Payload for granting source-transmission or indexing consent."""

    scope: str = Field(
        ...,
        description="Scope of consent: snippet_transmission | cloud_index | llm_processing",
        examples=["snippet_transmission"],
    )
    provider_ids: list[str] = Field(
        default_factory=list,
        description="List of AI/embedding provider IDs consented to receive data.",
    )
    data_categories: list[str] = Field(
        default_factory=list,
        description="Categories of data consented (e.g. ['code_snippets', 'ast_metadata']).",
    )
    granted_for: str = Field(
        default="project",
        description="Duration/lifetime: 'single_request' or 'project'.",
    )
    policy_version: str = Field(
        default="1.0",
        description="Policy version agreed to by the user.",
    )
    preview_hash: str | None = Field(
        default=None,
        description="SHA-256 hash of the exact consent preview payload shown to the user.",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="Optional ISO timestamp when consent expires.",
    )


class ConsentListResponse(BaseModel):
    """List of consent records."""

    items: list[ConsentItem]
    total: int


class ConsentService:
    """Service providing business logic and security enforcement for consent records."""

    @classmethod
    async def list_consents(
        cls,
        ctx: AuthContext | SystemContext,
        project_id: uuid.UUID,
        active_only: bool = False,
        scope: str | None = None,
    ) -> list[ConsentItem]:
        """List consent records for a project."""
        async with session_scope() as session:
            repo = ConsentRepository(session)
            records = await repo.list_consents(
                ctx=ctx,
                project_id=project_id,
                active_only=active_only,
                scope=scope,
            )
            return [ConsentItem.from_model(r) for r in records]

    @classmethod
    async def create_consent(
        cls,
        ctx: AuthContext | SystemContext,
        project_id: uuid.UUID,
        req: CreateConsentRequest,
    ) -> ConsentItem:
        """Create a new consent grant after validating scope and duration."""
        if req.scope not in VALID_SCOPES:
            raise ValidationError(
                detail=f"Invalid consent scope '{req.scope}'. Must be one of: {sorted(VALID_SCOPES)}",
                code="validation.failed",
            )
        if req.granted_for not in VALID_GRANTED_FOR:
            raise ValidationError(
                detail=f"Invalid granted_for '{req.granted_for}'. Must be one of: {sorted(VALID_GRANTED_FOR)}",
                code="validation.failed",
            )

        async with session_scope() as session:
            repo = ConsentRepository(session)
            record = await repo.create_consent(
                ctx=ctx,
                project_id=project_id,
                scope=req.scope,
                provider_ids=req.provider_ids,
                data_categories=req.data_categories,
                granted_for=req.granted_for,
                policy_version=req.policy_version,
                preview_hash=req.preview_hash,
                expires_at=req.expires_at,
            )

            # Record immutable audit event for consent grant per ADR-047
            audit_repo = AuditEventRepository(session)
            actor_id = ctx.user_id if isinstance(ctx, AuthContext) and ctx.user_id else None
            await audit_repo.record(
                ctx=ctx,
                action="consent.granted",
                actor_id=actor_id,
                target_type="consent",
                target_id=str(record.id),
                metadata={
                    "scope": record.scope,
                    "provider_ids": record.provider_ids,
                    "data_categories": record.data_categories,
                    "granted_for": record.granted_for,
                    "policy_version": record.policy_version,
                },
            )

            return ConsentItem.from_model(record)

    @classmethod
    async def revoke_consent(
        cls,
        ctx: AuthContext | SystemContext,
        project_id: uuid.UUID,
        consent_id: uuid.UUID,
    ) -> ConsentItem:
        """Revoke a consent record immediately and execute dependent data purges (docs/07 §7, docs/11)."""
        async with session_scope() as session:
            repo = ConsentRepository(session)
            record = await repo.revoke_consent(
                ctx=ctx, project_id=project_id, consent_id=consent_id
            )
            if not record:
                raise NotFoundError(
                    detail=f"Consent record '{consent_id}' not found for project '{project_id}'"
                )

            purged_counts: dict[str, int] = {"code_chunks": 0, "embeddings": 0}
            sync_mode_updated = False
            new_sync_mode: str | None = None

            # Consequence check: If revoked consent covered cloud_index, check remaining active grants
            if record.scope == "cloud_index":
                has_active_index = await repo.has_active_consent(
                    ctx=ctx, project_id=project_id, scope="cloud_index"
                )
                if not has_active_index:
                    # Irreversibly purge all chunks and embeddings from the cloud
                    brain_repo = BrainRepository(session)
                    purged_counts = await brain_repo.purge_project_chunks(ctx, project_id)

                    # Update project sync_mode to metadata_only
                    project_repo = ProjectRepository(session)
                    project = await project_repo.get_by_id(ctx, project_id)
                    if project and project.sync_mode == "indexed":
                        await project_repo.update(ctx, project_id, sync_mode="metadata_only")
                        sync_mode_updated = True
                        new_sync_mode = "metadata_only"

            # Emit immutable audit event for revocation per ADR-047
            audit_repo = AuditEventRepository(session)
            actor_id = ctx.user_id if isinstance(ctx, AuthContext) and ctx.user_id else None
            await audit_repo.record(
                ctx=ctx,
                action="consent.revoked",
                actor_id=actor_id,
                target_type="consent",
                target_id=str(consent_id),
                metadata={
                    "scope": record.scope,
                    "provider_ids": record.provider_ids,
                    "purged_counts": purged_counts,
                    "sync_mode_updated": sync_mode_updated,
                    "new_sync_mode": new_sync_mode,
                },
            )

            return ConsentItem.from_model(
                record,
                purged_counts=purged_counts,
                sync_mode_updated=sync_mode_updated,
                new_sync_mode=new_sync_mode,
            )

    @classmethod
    async def get_consent(
        cls,
        ctx: AuthContext | SystemContext,
        project_id: uuid.UUID,
        consent_id: uuid.UUID,
    ) -> ConsentItem | None:
        """Retrieve a specific consent record by ID within workspace and project boundaries."""
        async with session_scope() as session:
            repo = ConsentRepository(session)
            record = await repo.get_consent(ctx=ctx, project_id=project_id, consent_id=consent_id)
            return ConsentItem.from_model(record) if record else None

    @classmethod
    async def verify_consent(
        cls,
        ctx: AuthContext | SystemContext,
        project_id: uuid.UUID,
        scope: str,
        provider_id: str | None = None,
        consent_id: uuid.UUID | None = None,
    ) -> None:
        """Verify that active consent exists for the operation.

        Raises:
            ConsentRequiredError: If valid consent is missing, revoked, or expired (403 Problem Details).
        """
        async with session_scope() as session:
            repo = ConsentRepository(session)
            if consent_id is not None:
                record = await repo.get_consent(
                    ctx=ctx, project_id=project_id, consent_id=consent_id
                )
                if not record or not record.is_active() or record.scope != scope:
                    raise ConsentRequiredError(
                        detail=f"Consent '{consent_id}' is invalid, expired, revoked, or does not cover scope '{scope}'. Review and approve what will be sent.",
                    )
                return

            has_consent = await repo.has_active_consent(
                ctx=ctx,
                project_id=project_id,
                scope=scope,
                provider_id=provider_id,
            )
            if not has_consent:
                provider_detail = f" for provider '{provider_id}'" if provider_id else ""
                raise ConsentRequiredError(
                    detail=f"This operation requires active '{scope}' consent{provider_detail}. Review and approve what will be sent.",
                )
