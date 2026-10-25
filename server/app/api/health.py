"""Health and readiness probe routers for Kubernetes / Render orchestrators (docs/10 §12, §14, §18)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field

from app.core.alerts import SystemAlert, evaluate_system_alerts, has_critical_alerts
from app.core.kill_switches import get_active_kill_switches
from app.core.settings import Settings, get_settings
from app.domain.auth import PERMISSION_PUBLIC, declare_permission

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Operations"])


class HealthResponse(BaseModel):
    """Liveness probe response model."""

    status: str = "ok"
    build_sha: str = "dev"


class ReadinessResponse(BaseModel):
    """Readiness probe response model."""

    status: str
    database: str = "skipped"
    redis: str = "skipped"
    migrations: str = "skipped"
    kill_switches: dict[str, bool] = Field(default_factory=dict)
    active_alerts_count: int = 0
    details: dict[str, Any] | None = None


class SystemAlertsResponse(BaseModel):
    """Operational alerts query response model."""

    status: str
    alerts_count: int
    alerts: list[SystemAlert] = Field(default_factory=list)
    evaluated_at: str


# Pluggable health checkers
async def check_database_readiness() -> bool:
    """Check database connectivity without exposing connection secrets."""
    from app.domain.auth import check_database_connectivity

    return await check_database_connectivity()


async def check_redis_readiness(settings: Settings | None = None) -> bool:
    """Check redis connectivity without exposing connection secrets."""
    from app.core.redis import check_redis_connectivity

    return await check_redis_connectivity(settings)


async def check_migrations_state(settings: Settings | None = None) -> tuple[bool, str, list[str]]:
    """Check migration readiness without exposing connection secrets."""
    from app.domain.auth import check_migrations_readiness

    return await check_migrations_readiness(settings)


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
    description="Returns 200 OK and build SHA if the application process is running. Does not check downstream dependencies.",
)
@router.get(
    "/healthz",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
    description="Returns 200 OK and build SHA if the application process is running. Does not check downstream dependencies.",
)
@declare_permission(PERMISSION_PUBLIC)
async def healthz(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Liveness probe: verifies process is alive and returns build SHA (docs/10 §12)."""
    return HealthResponse(status="ok", build_sha=settings.build_sha)


@router.get(
    "/readyz",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    description="Returns 200 OK if all required downstream dependencies (PostgreSQL, Redis, Alembic migration head) are healthy.",
)
@declare_permission(PERMISSION_PUBLIC)
async def readyz(
    response: Response,
    settings: Settings = Depends(get_settings),
) -> ReadinessResponse:
    """Readiness probe: checks downstream dependencies, migration heads, and kill switch status."""
    db_ok = await check_database_readiness()
    redis_ok = await check_redis_readiness(settings)
    mig_ok, mig_status, _ = await check_migrations_state(settings)
    switches = get_active_kill_switches(settings)

    # Evaluate background alerts (non-blocking best-effort)
    alerts = await evaluate_system_alerts(settings)

    is_ready = db_ok and redis_ok and mig_ok

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            status="degraded",
            database="ok" if db_ok else "unreachable",
            redis="ok" if redis_ok else "unreachable",
            migrations=mig_status,
            kill_switches=switches,
            active_alerts_count=len(alerts),
            details={"alerts_summary": [a.message for a in alerts]} if alerts else None,
        )

    return ReadinessResponse(
        status="ready",
        database="ok",
        redis="ok",
        migrations=mig_status,
        kill_switches=switches,
        active_alerts_count=len(alerts),
        details={"alerts_summary": [a.message for a in alerts]} if alerts else None,
    )


@router.get(
    "/readyz/alerts",
    response_model=SystemAlertsResponse,
    status_code=status.HTTP_200_OK,
    summary="Operational alerts overview",
    description="Returns evaluated system alerts against operational thresholds (docs/10 §14, §15, §18).",
)
@declare_permission(PERMISSION_PUBLIC)
async def readyz_alerts(
    settings: Settings = Depends(get_settings),
) -> SystemAlertsResponse:
    """Operations probe returning system health alerts without leaking secrets or source code."""
    alerts = await evaluate_system_alerts(settings)
    status_str = "critical" if has_critical_alerts(alerts) else ("warning" if alerts else "healthy")
    return SystemAlertsResponse(
        status=status_str,
        alerts_count=len(alerts),
        alerts=alerts,
        evaluated_at=datetime.now(UTC).isoformat(),
    )
