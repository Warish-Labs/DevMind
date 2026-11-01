"""Deployment Domain Service coordinating diagnosis, incident history, and resolution tracking (docs/01 CAP-07, docs/03 §3.4)."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext, SystemContext
from app.core.errors import NotFoundError
from app.domain.deployment.schemas import (
    DeploymentDiagnosisRequest,
    DeploymentDiagnosisResponse,
    DeploymentIncidentListResponse,
    DeploymentIncidentResponse,
    DeploymentResolutionUpdate,
)
from app.llm.router import LLMGatewayRouter
from app.orchestration.deploy_doctor import DeployDoctorAgent
from app.persistence.models.deployment import DeploymentIncident
from app.persistence.repositories.incident_repo import DeploymentIncidentRepository
from app.persistence.repositories.project_repo import ProjectRepository

logger = logging.getLogger("devmind.domain.deployment")


def incident_to_response(inc: DeploymentIncident) -> DeploymentIncidentResponse:
    """Map DB DeploymentIncident model to Pydantic DeploymentIncidentResponse."""
    return DeploymentIncidentResponse(
        id=inc.id,
        workspace_id=inc.workspace_id,
        project_id=inc.project_id,
        fingerprint=inc.fingerprint,
        summary=inc.summary,
        probable_cause=inc.probable_cause,
        resolution=inc.resolution,
        error_signature=inc.error_signature,
        environment=inc.environment,
        service_name=inc.service_name,
        failure_category=inc.failure_category,
        log_snippet=inc.log_snippet,
        occurrence_count=inc.occurrence_count,
        last_seen_at=inc.last_seen_at,
        resolved_at=inc.resolved_at,
        resolved_by=inc.resolved_by,
        created_at=inc.created_at,
        updated_at=inc.updated_at,
        metadata=inc.metadata_ or {},
    )


class DeploymentService:
    """Coordinates deployment failure diagnosis, incident history, and resolution workflows."""

    def __init__(
        self,
        session: AsyncSession,
        router: LLMGatewayRouter | None = None,
    ) -> None:
        self.session = session
        self.repo = DeploymentIncidentRepository(session)
        self.project_repo = ProjectRepository(session)
        self.agent = DeployDoctorAgent(session=session, router=router)

    async def diagnose_log(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        request: DeploymentDiagnosisRequest,
    ) -> DeploymentDiagnosisResponse:
        """Diagnose raw deployment log, identify probable causes, and persist incident."""
        return await self.agent.diagnose(ctx, project_id, request)

    async def list_incidents(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        environment: str | None = None,
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> DeploymentIncidentListResponse:
        """List historical deployment incidents for a project."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if not project:
            raise NotFoundError(detail=f"Project {project_id} not found")

        items, total = await self.repo.list_incidents(
            ctx,
            workspace_id=project.workspace_id,
            project_id=project_id,
            environment=environment,
            category=category,
            limit=limit,
            offset=offset,
        )

        return DeploymentIncidentListResponse(
            items=[incident_to_response(i) for i in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_incident(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        incident_id: UUID,
    ) -> DeploymentIncidentResponse:
        """Retrieve deployment incident details by ID."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if not project:
            raise NotFoundError(detail=f"Project {project_id} not found")

        inc = await self.repo.get_incident(
            ctx,
            workspace_id=project.workspace_id,
            project_id=project_id,
            incident_id=incident_id,
        )
        if not inc:
            raise NotFoundError(detail=f"Deployment incident {incident_id} not found")

        return incident_to_response(inc)

    async def update_resolution(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        incident_id: UUID,
        payload: DeploymentResolutionUpdate,
    ) -> DeploymentIncidentResponse:
        """Record or update resolution documentation for an incident."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if not project:
            raise NotFoundError(detail=f"Project {project_id} not found")

        user_id = ctx.user_id if isinstance(ctx, AuthContext) else None

        updated = await self.repo.update_resolution(
            ctx,
            workspace_id=project.workspace_id,
            project_id=project_id,
            incident_id=incident_id,
            resolution=payload.resolution,
            resolved_by=user_id,
        )
        if not updated:
            raise NotFoundError(detail=f"Deployment incident {incident_id} not found")

        return incident_to_response(updated)

    async def delete_incident(
        self,
        ctx: AuthContext | SystemContext,
        project_id: UUID,
        incident_id: UUID,
    ) -> bool:
        """Delete an incident record."""
        project = await self.project_repo.get_by_id(ctx, project_id)
        if not project:
            raise NotFoundError(detail=f"Project {project_id} not found")

        deleted = await self.repo.delete_incident(
            ctx,
            workspace_id=project.workspace_id,
            project_id=project_id,
            incident_id=incident_id,
        )
        if not deleted:
            raise NotFoundError(detail=f"Deployment incident {incident_id} not found")

        return True
