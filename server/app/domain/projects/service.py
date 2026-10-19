"""Project domain service implementing business logic for codebases and project access."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.persistence.models.project import Project, ProjectMembership
from app.persistence.repositories.audit_repo import AuditEventRepository
from app.persistence.repositories.brain_repo import BrainRepository
from app.persistence.repositories.project_repo import ProjectRepository

SLUG_REGEX = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ProjectService:
    """Domain service managing codebase project lifecycle and members."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ProjectRepository(session)
        self.brain_repo = BrainRepository(session)
        self.audit_repo = AuditEventRepository(session)

    @staticmethod
    def validate_slug(slug: str) -> str:
        """Validate project slug format."""
        slug = slug.strip().lower()
        if len(slug) < 2 or len(slug) > 64 or not SLUG_REGEX.match(slug):
            raise ValidationError(
                detail="Project slug must be between 2 and 64 characters, using lowercase letters, numbers, and single hyphens"
            )
        return slug

    async def create_project(
        self,
        ctx: AuthContext | SystemContext,
        *,
        workspace_id: UUID,
        name: str,
        slug: str,
        visibility: str = "workspace",
        sync_mode: str = "metadata_only",
        source_kind: str = "local",
        primary_language: str | None = None,
        default_branch: str = "main",
    ) -> Project:
        """Create a new codebase project inside a workspace."""
        clean_name = name.strip()
        if not clean_name or len(clean_name) > 120:
            raise ValidationError(detail="Project name must be between 1 and 120 characters")

        clean_slug = self.validate_slug(slug)

        if visibility not in ("private", "workspace"):
            raise ValidationError(detail="Project visibility must be 'private' or 'workspace'")

        if sync_mode not in ("metadata_only", "indexed"):
            raise ValidationError(detail="Project sync_mode must be 'metadata_only' or 'indexed'")

        if source_kind not in ("local", "github", "gitlab", "bitbucket"):
            raise ValidationError(detail="Invalid source_kind")

        # Check slug availability in workspace
        existing = await self.repo.get_by_slug(ctx, clean_slug, workspace_id=workspace_id)
        if existing is not None:
            raise ConflictError(
                detail=f"Project with slug '{clean_slug}' already exists in workspace"
            )

        return await self.repo.create(
            ctx,
            workspace_id=workspace_id,
            name=clean_name,
            slug=clean_slug,
            visibility=visibility,
            sync_mode=sync_mode,
            source_kind=source_kind,
            primary_language=primary_language,
            default_branch=default_branch,
        )

    async def get_project(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
    ) -> Project:
        """Find project by ID or raise NotFoundError."""
        project = await self.repo.get_by_id(ctx, project_id)
        if project is None:
            raise NotFoundError(detail=f"Project '{project_id}' not found")
        return project

    async def list_workspace_projects(
        self,
        ctx: AuthContext | SystemContext,
        workspace_id: UUID,
        include_archived: bool = False,
    ) -> list[Project]:
        """List all projects in workspace."""
        return await self.repo.list_for_workspace(
            ctx, workspace_id=workspace_id, include_archived=include_archived
        )

    async def update_project(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        *,
        name: str | None = None,
        slug: str | None = None,
        visibility: str | None = None,
        sync_mode: str | None = None,
        primary_language: str | None = None,
        default_branch: str | None = None,
    ) -> Project:
        """Update mutable project settings."""
        project = await self.get_project(ctx, project_id)

        updates: dict[str, Any] = {}
        if name is not None:
            clean_name = name.strip()
            if not clean_name or len(clean_name) > 120:
                raise ValidationError(detail="Project name must be between 1 and 120 characters")
            updates["name"] = clean_name

        if slug is not None:
            clean_slug = self.validate_slug(slug)
            if clean_slug != project.slug:
                existing = await self.repo.get_by_slug(
                    ctx, clean_slug, workspace_id=project.workspace_id
                )
                if existing is not None and existing.id != project_id:
                    raise ConflictError(
                        detail=f"Project with slug '{clean_slug}' already exists in workspace"
                    )
                updates["slug"] = clean_slug

        if visibility is not None:
            if visibility not in ("private", "workspace"):
                raise ValidationError(detail="Project visibility must be 'private' or 'workspace'")
            updates["visibility"] = visibility

        if sync_mode is not None:
            if sync_mode not in ("metadata_only", "indexed"):
                raise ValidationError(
                    detail="Project sync_mode must be 'metadata_only' or 'indexed'"
                )
            if project.sync_mode == "indexed" and sync_mode == "metadata_only":
                purged = await self.brain_repo.purge_project_chunks(ctx, project_id)
                await self.audit_repo.record(
                    ctx,
                    workspace_id=project.workspace_id,
                    action="project.sync_mode_updated",
                    target_kind="project",
                    target_id=str(project_id),
                    metadata={
                        "previous_sync_mode": project.sync_mode,
                        "new_sync_mode": sync_mode,
                        "purged_counts": purged,
                    },
                )
            elif project.sync_mode != sync_mode:
                await self.audit_repo.record(
                    ctx,
                    workspace_id=project.workspace_id,
                    action="project.sync_mode_updated",
                    target_kind="project",
                    target_id=str(project_id),
                    metadata={
                        "previous_sync_mode": project.sync_mode,
                        "new_sync_mode": sync_mode,
                        "purged_counts": {"code_chunks": 0, "embeddings": 0},
                    },
                )
            updates["sync_mode"] = sync_mode

        if primary_language is not None:
            updates["primary_language"] = primary_language.strip().lower()

        if default_branch is not None:
            updates["default_branch"] = default_branch.strip()

        updated = await self.repo.update(ctx, project_id, **updates)
        assert updated is not None
        return updated

    async def update_sync_mode(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        new_sync_mode: str,
    ) -> dict[str, Any]:
        """Transition project synchronization mode and execute purge consequences (ADR-022)."""
        if new_sync_mode not in ("metadata_only", "indexed"):
            raise ValidationError(detail="Project sync_mode must be 'metadata_only' or 'indexed'")

        project = await self.get_project(ctx, project_id)
        previous_sync_mode = project.sync_mode
        purged_counts = {"code_chunks": 0, "embeddings": 0}

        # Consequence: switching from indexed to metadata_only purges all stored code chunks and embeddings
        if previous_sync_mode == "indexed" and new_sync_mode == "metadata_only":
            purged_counts = await self.brain_repo.purge_project_chunks(ctx, project_id)

        if previous_sync_mode != new_sync_mode:
            await self.repo.update(ctx, project_id, sync_mode=new_sync_mode)

            # Record audit event (ADR-047 / docs/07: no source content logged, counts only)
            await self.audit_repo.record(
                ctx,
                workspace_id=project.workspace_id,
                action="project.sync_mode_updated",
                target_kind="project",
                target_id=str(project_id),
                metadata={
                    "previous_sync_mode": previous_sync_mode,
                    "new_sync_mode": new_sync_mode,
                    "purged_counts": purged_counts,
                },
            )

        return {
            "project_id": project.id,
            "workspace_id": project.workspace_id,
            "previous_sync_mode": previous_sync_mode,
            "new_sync_mode": new_sync_mode,
            "purged_counts": purged_counts,
            "transitioned_at": datetime.now(UTC),
        }

    async def purge_project_data(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        scope: str = "all",
        confirmation_slug: str | None = None,
    ) -> dict[str, Any]:
        """Purge project data across stores and generate Deletion Verification Report (M9-03, docs/11).

        Acceptance:
        - Per-store deletion counts across PostgreSQL, Redis, and LangGraph checkpoints.
        - Cryptographic verification hash (SHA-256) over report content.
        - Automatic fallback/reset of project sync_mode to 'metadata_only'.
        - Immutable AuditEvent recorded per ADR-047 (no source code logged).
        """
        project = await self.get_project(ctx, project_id)

        if confirmation_slug is not None and confirmation_slug != project.slug:
            raise ValidationError(
                detail=f"Confirmation slug '{confirmation_slug}' does not match project slug '{project.slug}'"
            )

        # 1. Execute per-store purge
        stores_breakdown = await self.brain_repo.purge_project_data(ctx, project_id, scope=scope)

        # 2. Reset sync_mode to metadata_only
        if project.sync_mode != "metadata_only":
            await self.repo.update(ctx, project_id, sync_mode="metadata_only")

        purged_at = datetime.now(UTC).isoformat()
        requested_by = (
            str(ctx.user_id) if isinstance(ctx, AuthContext) and ctx.user_id else "system"
        )

        # 3. Build deterministic canonical report dictionary for hashing
        report_data = {
            "project_id": str(project.id),
            "workspace_id": str(project.workspace_id),
            "requested_by": requested_by,
            "purged_at": purged_at,
            "scope": scope,
            "stores": stores_breakdown,
            "sync_mode": "metadata_only",
            "status": "completed",
        }

        canonical_json = json.dumps(
            {
                "project_id": report_data["project_id"],
                "workspace_id": report_data["workspace_id"],
                "requested_by": report_data["requested_by"],
                "purged_at": report_data["purged_at"],
                "scope": report_data["scope"],
                "stores": report_data["stores"],
                "sync_mode": report_data["sync_mode"],
            },
            sort_keys=True,
        )
        verification_hash = f"sha256:{hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()}"
        report_data["verification_hash"] = verification_hash

        # 4. Record audit event per ADR-047 (counts & hash only, zero source content)
        await self.audit_repo.record(
            ctx,
            workspace_id=project.workspace_id,
            action="project.data_purged",
            target_kind="project",
            target_id=str(project_id),
            metadata={
                "scope": scope,
                "stores": stores_breakdown,
                "verification_hash": verification_hash,
                "sync_mode": "metadata_only",
            },
        )

        return report_data

    async def delete_project(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
    ) -> bool:
        """Soft delete a project."""
        await self.get_project(ctx, project_id)
        await self.repo.soft_delete(ctx, project_id)
        return True

    async def list_members(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
    ) -> list[ProjectMembership]:
        """List all explicit members of a project."""
        await self.get_project(ctx, project_id)
        return await self.repo.list_members(ctx, project_id)

    async def add_member(
        self,
        ctx: AuthContext | SystemContext,
        *,
        project_id: UUID,
        user_id: UUID,
        role: str = "contributor",
    ) -> ProjectMembership:
        """Add or elevate project membership."""
        await self.get_project(ctx, project_id)

        if role not in ("maintainer", "contributor", "viewer"):
            raise ValidationError(
                detail="Invalid project role; expected maintainer, contributor, or viewer"
            )

        existing = await self.repo.get_membership(ctx, project_id=project_id, user_id=user_id)
        if existing is not None:
            raise ConflictError(
                detail=f"User '{user_id}' already has an explicit membership in project '{project_id}'"
            )

        return await self.repo.add_member(ctx, project_id=project_id, user_id=user_id, role=role)

    async def remove_member(
        self,
        ctx: AuthContext | SystemContext,
        *,
        project_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Remove explicit project membership."""
        await self.get_project(ctx, project_id)
        removed = await self.repo.remove_member(ctx, project_id=project_id, user_id=user_id)
        if not removed:
            raise NotFoundError(
                detail=f"Membership for user '{user_id}' not found in project '{project_id}'"
            )
        return True
