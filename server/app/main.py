"""DevMind FastAPI Application Factory and main entry point."""

import time
import uuid
from typing import Any

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.api.health import router as health_router
from app.core.errors import (
    DevMindError,
    devmind_error_handler,
    unhandled_exception_handler,
    validation_error_handler,
)
from app.core.logging import request_id_ctx, setup_logging
from app.core.settings import Settings, get_settings


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware for correlation request_id and request timing."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Extract or generate request ID
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = req_id
        token = request_id_ctx.set(req_id)

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            process_time = time.perf_counter() - start_time
            response.headers["X-Request-ID"] = req_id
            response.headers["X-Process-Time"] = f"{process_time:.4f}"
            return response
        finally:
            request_id_ctx.reset(token)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory for DevMind FastAPI server."""
    if settings is None:
        settings = get_settings()

    # Configure structured logging with secret redaction
    setup_logging(log_level=settings.log_level)

    # Initialize OpenTelemetry and error reporting (docs/02 §12, docs/10 §13, ADR-030)
    from app.core.error_reporting import init_error_reporting
    from app.core.telemetry import TelemetryMiddleware, init_telemetry

    init_telemetry(settings=settings)
    init_error_reporting(settings=settings)

    app = FastAPI(
        title="DevMind API",
        version="0.1.0",
        description="DevMind Backend API: AI-powered code analysis and architecture intelligence.",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    # Attach settings to application state and dependency overrides
    app.state.settings = settings
    app.dependency_overrides[get_settings] = lambda: settings

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # OpenTelemetry tracing and metrics middleware (docs/02 §12, docs/10 §13)
    app.add_middleware(TelemetryMiddleware)

    # Request context middleware (correlation ID & timing)
    app.add_middleware(RequestContextMiddleware)

    # Rate limiting middleware (sliding-window per principal and route class, docs/03 §10)
    from app.middleware.rate_limit import RateLimitMiddleware

    app.add_middleware(RateLimitMiddleware, settings=settings)

    # Idempotency middleware (SHA-256 payload binding & 24h caching, docs/03 §10)
    from app.middleware.idempotency import IdempotencyMiddleware

    app.add_middleware(IdempotencyMiddleware, settings=settings)

    # RFC 9457 Problem Details error handlers
    app.add_exception_handler(DevMindError, devmind_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Health & readiness probes (unauthenticated, operational)
    app.include_router(health_router)

    # API v1 router placeholder
    api_v1_router = APIRouter(prefix="/api/v1")

    from app.api.audit import project_audit_router, workspace_audit_router
    from app.api.brain import router as brain_router
    from app.api.bug_memory import bug_memory_router
    from app.api.consents import router as consents_router
    from app.api.deployment import deployment_router
    from app.api.extension import router as extension_router
    from app.api.findings import router as findings_router
    from app.api.integrations import (
        integrations_router,
        project_github_router,
        pull_requests_router,
        workspace_integrations_router,
    )
    from app.api.invitations import router as invitations_router
    from app.api.jobs import jobs_router, project_analyses_router
    from app.api.living_docs import living_docs_router
    from app.api.me import router as me_router
    from app.api.mentor import mentor_router
    from app.api.projects import projects_router, workspace_projects_router
    from app.api.public import router as public_router
    from app.api.retention import project_retention_router, workspace_retention_router
    from app.api.review_rules import review_rules_router
    from app.api.scans import router as scans_router
    from app.api.webhooks import router as webhooks_router
    from app.api.workspaces import router as workspaces_router
    from app.domain.auth import PERMISSION_PUBLIC, declare_permission

    @api_v1_router.get("", tags=["System"])
    @declare_permission(PERMISSION_PUBLIC)
    async def v1_root() -> dict[str, Any]:
        return {
            "name": "DevMind API",
            "version": "v1",
            "environment": settings.env,
            "status": "operational",
        }

    api_v1_router.include_router(public_router)
    api_v1_router.include_router(invitations_router)
    api_v1_router.include_router(workspaces_router)
    api_v1_router.include_router(workspace_projects_router)
    api_v1_router.include_router(workspace_integrations_router)
    api_v1_router.include_router(workspace_retention_router)
    api_v1_router.include_router(workspace_audit_router)
    api_v1_router.include_router(integrations_router)
    api_v1_router.include_router(project_github_router)
    api_v1_router.include_router(pull_requests_router)
    api_v1_router.include_router(projects_router)
    api_v1_router.include_router(review_rules_router)
    api_v1_router.include_router(bug_memory_router)
    api_v1_router.include_router(living_docs_router)
    api_v1_router.include_router(mentor_router)
    api_v1_router.include_router(deployment_router)
    api_v1_router.include_router(project_analyses_router)
    api_v1_router.include_router(project_retention_router)
    api_v1_router.include_router(project_audit_router)
    api_v1_router.include_router(jobs_router)
    api_v1_router.include_router(brain_router)
    api_v1_router.include_router(scans_router)
    api_v1_router.include_router(findings_router)
    api_v1_router.include_router(consents_router)
    api_v1_router.include_router(me_router)
    api_v1_router.include_router(webhooks_router)
    api_v1_router.include_router(extension_router)

    app.include_router(api_v1_router)

    return app


# Default app instance for ASGI servers (uvicorn app.main:app)
app = create_app()
