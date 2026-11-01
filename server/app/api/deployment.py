"""Deployment Diagnosis and Incident Management REST API endpoints (docs/01 CAP-07, docs/03 §3.4).

Provides endpoints for:
- Diagnosing deployment failure logs with automated secret redaction and hypothesis ranking
- Browsing historical deployment incidents and recurring failure frequency
- Documenting proven resolutions and root cause fixes
- Managing deployment incident lifecycles
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_context import AuthContext
from app.domain.auth import (
    PERM_ANALYSIS_CREATE,
    PERM_PROJECT_DELETE,
    PERM_PROJECT_READ,
    PERM_PROJECT_UPDATE,
    declare_permission,
    get_auth_context,
    get_db_session,
)
from app.domain.deployment.schemas import (
    DeploymentDiagnosisRequest,
    DeploymentDiagnosisResponse,
    DeploymentIncidentListResponse,
    DeploymentIncidentResponse,
    DeploymentResolutionUpdate,
)
from app.domain.deployment.service import DeploymentService

logger = logging.getLogger("devmind.api.deployment")

deployment_router = APIRouter(tags=["Deployment Diagnosis"])


def _get_deployment_service(session: AsyncSession = Depends(get_db_session)) -> DeploymentService:
    return DeploymentService(session=session)


# ---------------------------------------------------------------------------
# Deployment Diagnosis Endpoints
# ---------------------------------------------------------------------------


@deployment_router.post(
    "/projects/{project_id}/deployment-diagnoses",
    response_model=DeploymentDiagnosisResponse,
    status_code=status.HTTP_200_OK,
    summary="Diagnose deployment failure log",
    description="Sanitizes credentials, extracts failure categories and referenced environment variables, and synthesizes root causes.",
)
@declare_permission(PERM_ANALYSIS_CREATE)
async def diagnose_deployment(
    project_id: UUID,
    payload: DeploymentDiagnosisRequest,
    ctx: AuthContext = Depends(get_auth_context),
    service: DeploymentService = Depends(_get_deployment_service),
) -> DeploymentDiagnosisResponse:
    """Analyze raw deployment logs and return ranked hypotheses with citations."""
    return await service.diagnose_log(ctx, project_id, payload)


@deployment_router.get(
    "/projects/{project_id}/deployment-incidents",
    response_model=DeploymentIncidentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List deployment incidents",
    description="Retrieve paginated history of past deployment incidents, filtered by environment or failure category.",
)
@declare_permission(PERM_PROJECT_READ)
async def list_deployment_incidents(
    project_id: UUID,
    environment: str | None = Query(
        default=None, description="Filter by environment (e.g. production, staging)"
    ),
    category: str | None = Query(default=None, description="Filter by failure category"),
    limit: int = Query(default=50, ge=1, le=100, description="Items per page"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    ctx: AuthContext = Depends(get_auth_context),
    service: DeploymentService = Depends(_get_deployment_service),
) -> DeploymentIncidentListResponse:
    """Retrieve historical deployment incidents for a project."""
    return await service.list_incidents(
        ctx,
        project_id,
        environment=environment,
        category=category,
        limit=limit,
        offset=offset,
    )


@deployment_router.get(
    "/projects/{project_id}/deployment-incidents/{incident_id}",
    response_model=DeploymentIncidentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get deployment incident details",
    description="Retrieve full details, error signature, and resolution for a specific deployment incident.",
)
@declare_permission(PERM_PROJECT_READ)
async def get_deployment_incident(
    project_id: UUID,
    incident_id: UUID,
    ctx: AuthContext = Depends(get_auth_context),
    service: DeploymentService = Depends(_get_deployment_service),
) -> DeploymentIncidentResponse:
    """Retrieve an incident record by primary ID."""
    return await service.get_incident(ctx, project_id, incident_id)


@deployment_router.patch(
    "/projects/{project_id}/deployment-incidents/{incident_id}/resolution",
    response_model=DeploymentIncidentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update incident resolution",
    description="Document the root cause resolution or remediation fix applied to resolve this incident.",
)
@declare_permission(PERM_PROJECT_UPDATE)
async def update_incident_resolution(
    project_id: UUID,
    incident_id: UUID,
    payload: DeploymentResolutionUpdate,
    ctx: AuthContext = Depends(get_auth_context),
    service: DeploymentService = Depends(_get_deployment_service),
) -> DeploymentIncidentResponse:
    """Record or update resolution documentation for a deployment incident."""
    return await service.update_resolution(ctx, project_id, incident_id, payload)


@deployment_router.delete(
    "/projects/{project_id}/deployment-incidents/{incident_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete deployment incident",
    description="Permanently delete a deployment incident record.",
)
@declare_permission(PERM_PROJECT_DELETE)
async def delete_deployment_incident(
    project_id: UUID,
    incident_id: UUID,
    ctx: AuthContext = Depends(get_auth_context),
    service: DeploymentService = Depends(_get_deployment_service),
) -> Response:
    """Delete an incident record from project history."""
    await service.delete_incident(ctx, project_id, incident_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
