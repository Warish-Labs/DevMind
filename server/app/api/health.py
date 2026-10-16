"""Health and readiness probe routers for Kubernetes / Render orchestrators."""

import logging
from typing import Any

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.domain.auth import PERMISSION_PUBLIC, declare_permission

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Operations"])


class HealthResponse(BaseModel):
    status: str = "ok"


class ReadinessResponse(BaseModel):
    status: str
    database: str = "skipped"
    redis: str = "skipped"
    details: dict[str, Any] | None = None


# Pluggable health checkers
async def check_database_readiness() -> bool:
    """Check database connectivity without exposing connection secrets."""
    # Will be connected to real session pool in M2
    return True


async def check_redis_readiness() -> bool:
    """Check redis connectivity without exposing connection secrets."""
    from app.core.redis import check_redis_connectivity

    return await check_redis_connectivity()


@router.get(
    "/healthz",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
    description="Returns 200 OK if the application process is running. Does not check downstream dependencies.",
)
@declare_permission(PERMISSION_PUBLIC)
async def healthz() -> HealthResponse:
    """Liveness probe: verifies process is alive."""
    return HealthResponse(status="ok")


@router.get(
    "/readyz",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    description="Returns 200 OK if all required downstream dependencies are healthy and accepting traffic.",
)
@declare_permission(PERMISSION_PUBLIC)
async def readyz(response: Response) -> ReadinessResponse:
    """Readiness probe: checks downstream dependencies."""
    db_ok = await check_database_readiness()
    redis_ok = await check_redis_readiness()

    is_ready = db_ok and redis_ok

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            status="degraded",
            database="ok" if db_ok else "unreachable",
            redis="ok" if redis_ok else "unreachable",
        )

    return ReadinessResponse(
        status="ready",
        database="ok",
        redis="ok",
    )
