# Multi-stage, non-root Dockerfile for DevMind backend services
# Produces a single image deployable as api, worker, or scheduler (ADR-005, ADR-046)

# Stage 1: Build dependencies with uv
FROM python:3.12-slim-bookworm AS builder

# Copy uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Configure uv for container builds
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install dependencies using pinned uv.lock
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Stage 2: Production runtime image
FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

# Install curl for container health check probes and ca-certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root user and group
RUN groupadd -g 10001 devmind && \
    useradd -u 10001 -g devmind -s /bin/bash -m appuser

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:devmind /app/.venv /app/.venv

# Configure execution environment
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1

# Copy application source code and configurations
COPY --chown=appuser:devmind app /app/app
COPY --chown=appuser:devmind README.md /app/README.md

# Switch to non-root user
USER appuser

EXPOSE 8000

# Health check verifies liveness probe
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Default command runs FastAPI via uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
