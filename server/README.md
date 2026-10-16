# DevMind Server

FastAPI + Celery backend modular monolith for DevMind.

## Architecture

Per [`docs/02-system-architecture.md`](../docs/02-system-architecture.md):

- **FastAPI application factory**: `server/app/main.py`
- **Configuration & settings**: `server/app/core/settings.py` (Pydantic v2 Settings)
- **Structured JSON logging & redaction**: `server/app/core/logging.py`
- **RFC 9457 Problem Details errors**: `server/app/core/errors.py`
- **Health & readiness probes**: `/healthz`, `/readyz`

## Local Development

```bash
cd server
uv venv
uv sync
uv run pytest
```
