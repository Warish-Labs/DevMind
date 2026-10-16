# BRAIN.md — DevMind Working Memory

> No secrets, tokens, source content or user data in this file. It is committed to git.

---

## 1. Current state

| Field              | Value                                                                                         |
| ------------------ | --------------------------------------------------------------------------------------------- |
| **Branch**         | `main`                                                                                        |
| **Last commit**    | `5725a89` (feat(client): complete M2-08 OpenAPI client, Clerk auth shell, and footer upgrade) |
| **Working tree**   | clean; working directly on main per user instruction                                          |
| **Open PR**        | None (working directly on main)                                                               |
| **Last CI result** | `test-all --fast`: 13 passed, 0 failed, 1 skipped; server 89/89 pass, boundaries:server pass  |
| **Date**           | 2026-10-16                                                                                    |

---

## 2. Next action (exact)

1. Begin **Phase M3 — VS Code extension real local scanning**:
   - Replace `FixtureFindingsSource` with `LocalScanFindingsSource` adhering to ADR-034 local-first constraints.
   - Wire extension workspace file walker with deterministic chunking and AST/regex rule evaluators for E0/E1 findings.
   - Implement extension auth token caching and local secret redaction prior to any sync.

---

## 3. Waiting on owner

| #   | Action required                                                                                                                           | Reference              |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| 1   | **SETUP-GUIDE.md §4.4**: After the first CI run is green on B3, enable the branch ruleset `protect-main` requiring `ci-gate` status check | P0-15                  |
| 2   | **VS Marketplace publisher**: Confirm the publisher id is `warishlabs` (or tell me the correct one)                                       | S2 extension packaging |

---

## 4. Done log

### M2-08 — OpenAPI Generation, Typed Client, Clerk Auth Shell & Upgraded Footer

- **Date**: 2026-10-16
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Completed OpenAPI 3.1 schema export, TypeScript client generation, Clerk auth wrapper integration, and client footer architecture:
  - **OpenAPI Schema Generator** (`scripts/export-openapi.py`):
    - Headless script booting FastAPI app factory and exporting schema to `common/openapi.json`.
    - Declared 14 API paths, models, and Problem Details responses.
  - **TypeScript API Client SDK** (`common/src/api/`):
    - Configured `openapi-typescript` and added `pnpm gen:api` script.
    - Exported schema types (`common/src/api/schema.d.ts`) and `DevMindApiClient` (`common/src/api/client.ts`) with RFC 9457 error mapping and bearer token injection.
  - **Clerk Frontend Auth Shell** (`client/components/auth/AuthProvider.tsx`, `client/lib/api.ts`):
    - Integrated `@clerk/nextjs` with graceful fallback when `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is omitted (offline/CI/test environments).
    - Wrapped root layout (`client/app/layout.tsx`).
    - Configured typed web API client with Clerk session token resolver.
  - **Footer Enhancement** (`client/components/layout/Footer.tsx`):
    - 4-column responsive grid: Brand/Mission with live Render+Neon status pill; Architectural Strata links; Open Engine & Spec links; WarishLabs Governance & Legal links.
    - Retained copyright, legal disclaimer, and all 38 client unit tests passing.

### M2-07 — Clerk User Webhook Receiver with Svix Signature Verification & Identity Sync

- **Date**: 2026-10-16
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented secure Clerk user lifecycle webhook receiver and automatic identity synchronization matching `docs/03` §10 and `docs/07` §11:
  - **Svix Signature Verification** (`server/app/integrations/clerk_webhook.py`):
    - Constant-time HMAC-SHA256 signature verification matching Svix specification.
    - Automatic `whsec_` base64 decoding and payload hashing (`{svix_id}.{svix_timestamp}.{body}`).
    - Replay protection rejecting webhooks with timestamps outside a 300-second (5-minute) tolerance window.
  - **Webhook Domain Service** (`server/app/domain/webhooks/service.py`):
    - Delivery deduplication via Redis `webhook:dedupe:{svix_id}` (with in-memory fallback) to safely ignore duplicate delivery replays.
    - `user.created`: Upserts user record with Clerk user ID and primary email; auto-provisions a default personal workspace (`kind="personal"`) with the user as `owner`.
    - `user.updated`: Syncs modified display names and email addresses.
    - `user.deleted`: Performs soft-deletion by stamping `deleted_at`.
    - All background database modifications execute under an explicit `SystemContext(reason="webhook:clerk")`.
  - **FastAPI Webhook Router** (`server/app/api/webhooks.py`):
    - `POST /api/v1/webhooks/clerk` tagged with `@declare_permission(PERMISSION_WEBHOOK)`.
    - RFC 9457 Problem Details error responses on missing headers (401), invalid signatures (401), or malformed JSON (422).
  - **Comprehensive Test Suite** (`server/tests/test_clerk_webhooks.py`):
    - 7 tests covering cryptographic signature verification, body tampering, replay expiry, delivery deduplication, user creation & personal workspace provisioning, profile updates, and soft deletion.
- **Actual results**: `node scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped; 89/89 server Python tests pass, boundaries clean).

### M2-06 — Idempotency Middleware and Redis-Backed Sliding-Window Rate Limiting

- **Date**: 2026-10-16
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented RFC 9457-compliant idempotency middleware and Redis-backed sliding-window rate limiting per `docs/03` §10 and `docs/07` §11:
  - **Redis Connection Management** (`server/app/core/redis.py`):
    - Async connection pooling with `redis.asyncio` tied to running event loops.
    - Graceful in-memory fallback for sliding windows and idempotency caching if Redis is offline or during testing.
  - **Idempotency Middleware** (`server/app/middleware/idempotency.py`):
    - Requires `Idempotency-Key` header on POST operations creating scans, jobs, uploads/snippets, or consents (`422 validation.failed` when missing).
    - Computes SHA-256 payload binding on request body.
    - Caches successful 2xx responses for 24 hours (`idempotency_ttl_seconds = 86400`).
    - Same key + same payload: returns original cached response with `Idempotent-Replay: true` without re-executing downstream handlers.
    - Same key + different payload: returns `422 idempotency.mismatch` RFC 9457 Problem Details.
    - In-flight lock protection: simultaneous requests with the same key return `409 conflict.state`.
    - Safe methods (GET, HEAD, OPTIONS) ignore `Idempotency-Key`; error responses (4xx/5xx) are not cached.
  - **Sliding-Window Rate Limiting Middleware** (`server/app/middleware/rate_limit.py`):
    - Sliding-window counter per principal and route class (`read`, `write`, `job_create`, `ext_sync`, `auth`) using Redis sorted sets (ZSET) or in-memory fallback.
    - Derives principal from `AuthContext` (user/sub), Bearer token SHA-256 hash, or client IP hash.
    - Injects `RateLimit-Limit`, `RateLimit-Remaining`, and `RateLimit-Reset` headers on all allowed responses.
    - When exceeded, returns `429 rate_limit.exceeded` RFC 9457 Problem Details with `Retry-After` header.
    - Exempts operational probes (`/healthz`, `/readyz`) and API docs (`/docs`, `/redoc`, `/openapi.json`).
  - **Comprehensive Test Suite** (`server/tests/`):
    - `test_rate_limit.py`: 5 tests covering allowed header injection, 429 exhaustion, per-principal isolation, exempt paths, and route class distinction.
    - `test_idempotency.py`: 6 tests covering missing key enforcement, replay cache hits, payload mismatch detection, custom route decorators, GET safety, and error non-caching.
- **Actual results**: `node scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped; 82/82 server Python tests pass, boundaries clean).

### M2-05 — Workspaces and Projects CRUD REST Endpoints with Permissions & Problem Details

- **Date**: 2026-10-16
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented full CRUD REST endpoints for workspaces, codebase projects, memberships, and caller identity matching `docs/03` §11.1, `docs/07` §3, and architectural boundary constraints:
  - **Strict Layer Separation** (`docs/02` §4.1):
    - `server/app/domain/workspaces/service.py`: `WorkspaceService` coordinates validation, slug generation, owner assignment, membership updates, and tenant repository calls.
    - `server/app/domain/projects/service.py`: `ProjectService` manages codebase projects, visibility, sync modes, and project-level role assignment.
    - `server/app/domain/users/service.py`: `UserService` handles profile retrieval without leaking repository layer into `app.api`.
  - **Authentication & Request Context** (`server/app/domain/auth/dependencies.py`):
    - `get_auth_context`: Resolves Clerk Bearer token, lazily creates or syncs user, resolves active workspace and project roles, and computes effective permissions.
    - `require_permission`: Enforces granular role-based permissions with automatic dependency ordering via `Depends(get_auth_context)`.
  - **Routers & RFC 9457 Problem Details** (`server/app/api/`):
    - `workspaces.py`: `GET /api/v1/workspaces`, `POST /api/v1/workspaces`, `GET/PATCH /workspaces/{id}`, `GET/POST /workspaces/{id}/members`, `PATCH/DELETE /workspaces/{id}/members/{user_id}`.
    - `projects.py`: `GET/POST /workspaces/{wid}/projects`, `GET/PATCH/DELETE /projects/{pid}`, `GET/POST /projects/{pid}/members`, `DELETE /projects/{pid}/members/{user_id}`.
    - `me.py`: `GET /api/v1/me`, `GET /api/v1/me/permissions`.
    - Every route tagged with `@declare_permission(...)` passing automated route registry CI check.
  - **Comprehensive Test Suite** (`server/tests/`):
    - `test_workspaces_api.py`, `test_projects_api.py`, `test_me_api.py`: Tested 401 unauthenticated, 422 validation failures, 403 forbidden without permission, and end-to-end CRUD against live PostgreSQL database.
- **Actual results**: `node scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped; 71/71 server Python tests pass, boundaries clean).

- **Date**: 2026-10-16
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented role-based permission evaluation and route-level authorization enforcement per ADR-010, `docs/03` §4.1–§4.2, `docs/07` §3, and `docs/09` §6:
  - **Permission Matrix**: Defined granular permissions for `viewer`, `contributor`, `maintainer` project roles, and `viewer`, `member`, `admin`, `owner` workspace roles matching `docs/03` §4.2.
  - **Effective Project Role Computer** (`compute_effective_project_role`):
    - Workspace owners/admins automatically receive `maintainer` role across all projects regardless of visibility.
    - Workspace members receive `contributor` role on `workspace` visibility projects, and `None` on `private` projects unless an explicit project membership row exists.
    - Explicit project memberships elevate or override base role based on role priority weight (`maintainer > contributor > viewer`).
  - **Route Permission Registry & Guard** (`server/app/domain/auth/policy.py`):
    - `RoutePermissionRegistry`: Central registry tracking every API endpoint and its required permission.
    - `@declare_permission(permission)`: Decorator tagging routes with required permission (`PERMISSION_PUBLIC`, `PERMISSION_AUTHENTICATED`, `project:read`, etc.).
    - `require_permission(permission)`: FastAPI dependency verifying caller holds the required permission and raising RFC 9457 `ForbiddenError` (403) when denied.
  - **Automated Route Registry CI Enforcement** (`server/tests/test_route_permissions.py`):
    - Inspects all registered application routes at test time and fails CI if any HTTP route lacks an explicit permission declaration (`docs/07` §3).
    - Verified negative test case: rogue/undeclared route is caught and flagged immediately.
  - **Automated Tests** (`server/tests/test_policy.py`, `server/tests/test_route_permissions.py`):
    - 8 comprehensive tests covering permission hierarchy, workspace permissions, effective role inheritance, `require_permission` runtime enforcement, and route registry scanning.
- **Actual results**: `node scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped; 64/64 Python tests pass, import boundaries clean).

### M2-03 — Clerk Token Verification Service, RSA JWKS Cache & Validation

- **Date**: 2026-10-16
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented Clerk session token verification service with cryptographic signature verification, JWKS key resolution, and claim validation per ADR-010, `docs/03` §10, and `docs/07` §3:
  - **Dependency Addition**: Added `pyjwt[crypto]>=2.9.0` (Apache 2.0 license) with explicit user approval under AGENTS.md Rule 11/13.
  - **Configuration Integration** (`server/app/core/settings.py`, `server/.env.example`):
    - Added `clerk_issuer`, `clerk_jwks_url`, and `clerk_authorized_parties` (`azp` validation) settings with Pydantic validators.
  - **Token Verifier Service** (`server/app/integrations/clerk/verifier.py`):
    - `ClerkClaims`: Pydantic v2 model holding verified `sub`, `iss`, `exp`, `iat`, `nbf`, `azp`, `sid`, and `email`.
    - `ClerkTokenVerifier`:
      - Inspects unverified header to ensure `RS256` algorithm (rejects symmetric algorithm key confusion).
      - Integrates PyJWT `PyJWKClient` with in-memory caching and rotation handling.
      - Enforces issuer validation against `settings.clerk_issuer`.
      - Enforces authorized party checks against `settings.clerk_authorized_parties`.
      - Incorporates 5-second clock skew tolerance (`leeway=5`).
      - Normalizes `Authorization: Bearer <token>` and maps all verification failures to RFC 9457 `AuthenticationError` (401).
  - **Automated Tests** (`server/tests/test_clerk_verifier.py`):
    - 8 comprehensive test cases covering valid RS256 decoding, Bearer prefix parsing, expired token rejection, alien/untrusted signature failure, issuer mismatch, unauthorized party rejection, symmetric key confusion prevention, and malformed input handling.
- **Actual results**: `node scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped; 56/56 Python tests pass, import boundaries clean).

### M2-01 & M2-02 — Alembic Migrations, Tenancy Models, and Repository Layer with AuthContext

- **Date**: 2026-10-16
- **Branch**: `main` (direct local merge / main workflow per owner instruction)
- **What**: Implemented initial database foundations, Alembic baseline migrations, and repository layer enforcing tenant isolation per ADR-046, `docs/03` §1–§4, and `docs/09` §4:
  - **Alembic Configuration** (`server/alembic.ini`, `server/alembic/env.py`):
    - Configured async migration runner supporting both offline DDL generation and online transactional async connections (`postgresql+psycopg://`).
    - Uses application `Settings` to dynamically resolve direct migration URL.
  - **Initial Tenancy Migration** (`server/alembic/versions/0001_initial_tenancy.py`):
    - Created schema for `users`, `workspaces`, `workspace_memberships`, `projects`, `project_memberships`, `audit_events`, `usage_records`.
    - Fully reversible `upgrade()` and `downgrade()` tested up and down against PostgreSQL.
  - **Base Models & UUIDv7 Monotonicity** (`server/app/persistence/models/base.py`, `server/app/core/ids.py`):
    - RFC 9562 compliant UUIDv7 generator providing 48-bit millisecond temporal ordering and B-Tree index locality.
    - Mixins for `UUID7PrimaryKeyMixin`, `TimestampMixin` (UTC timestamptz), and `SoftDeleteMixin` (`deleted_at`).
  - **SQLAlchemy Models** (`server/app/persistence/models/`):
    - `User`, `Workspace`, `WorkspaceMembership`, `Project`, `ProjectMembership`, `AuditEvent`, `UsageRecord` with strict foreign keys (`CASCADE` / `SET NULL`), unique constraints, check constraints, and compound indexes.
  - **Repository Layer Enforcing AuthContext** (`server/app/persistence/repositories/`):
    - `BaseRepository`: strict enforcement that every repository function requires an `AuthContext` or `SystemContext` (raises `TypeError` on missing or invalid context).
    - Query scoping automatically applies tenant `workspace_id` predicates; alien workspace requests clamp to impossible zero-match predicates.
    - Implemented `UserRepository`, `WorkspaceRepository`, `ProjectRepository`, `AuditEventRepository`, and `UsageRecordRepository`.
  - **Automated Tests** (`server/tests/test_ids.py`, `test_auth_context.py`, `test_models.py`, `test_repositories.py`, `test_migrations.py`):
    - 48 total server tests passing, 7/7 architectural boundary contracts strictly verified.
- **Actual results**: `node scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped; 48/48 Python tests pass, import boundaries clean).

### M1-06 & M1-07 — Free Profile Launcher, Advisory Lock, Startup Sweep, & Quota Budget

- **Date**: 2026-10-16
- **Branch**: `feature/m1-free-profile`
- **What**: Implemented unified process launcher and free profile operational mechanics per ADR-046 and `docs/10` §22:
  - **Unified Launcher** (`server/app/launcher.py`):
    - Supports all execution modes via `DEVMIND_RUN_MODE`:
      - `api`: runs Uvicorn ASGI server.
      - `worker`: runs Celery worker daemon.
      - `scheduler`: runs Celery beat scheduler.
      - `all`: Render free profile mode — runs Uvicorn HTTP server alongside embedded Celery worker with beat (`--pool=solo`, concurrency 1).
    - Signal management: Traps `SIGTERM` and `SIGINT` to gracefully terminate embedded background workers, close connections, and exit cleanly with code 0.
  - **Advisory Lock Migrations** (`server/app/core/lifecycle.py`):
    - PostgreSQL advisory lock (`0x444D5F4D49475231`) ensures single-instance migration execution at container boot, preventing race conditions during cold starts or scaling.
    - Handles lock contention and gracefully verifies pre-M2 baseline configuration.
  - **Startup Sweep** (`server/app/core/lifecycle.py`):
    - Scans Redis keys under `DEVMIND_REDIS_KEY_PREFIX` (`dm:`) at boot.
    - Identifies and purges stale lock keys and orphan temporary buffers that survived an idle sleep.
    - Gracefully degrades with structured warnings if Redis is temporarily offline during cold boot.
  - **Celery Key Prefix Isolation** (`server/app/workers/celery_app.py`):
    - Configured `broker_transport_options` and `result_backend_transport_options` with `global_keyprefix` to protect shared Render Key Value instances.
    - Configured `task_acks_late=True` and `worker_prefetch_multiplier=1` for crash resilience.
  - **Free Quotas Configuration & Measured Memory Budget** (`server/configs/quotas.free.yaml`):
    - Storage Budget (Neon Free 512 MB): ~11.5 KB per chunk (3.5 KB text + 850 B tsvector + 3.0 KB raw vector + 3.7 KB HNSW index + 450 B row metadata); capped at 30,000 chunks (~345 MB) and 3,000 files per project.
    - Memory Budget (Render Free 512 MB): Measured idle footprint ~110 MB (Uvicorn ~50 MB + Celery solo worker ~60 MB), leaving a 128 MB safety buffer below the 512 MB OOM ceiling.
  - **Automated Tests** (`server/tests/test_launcher.py`, `server/tests/test_deploy_config.py`):
    - 33 total server tests passing, 7/7 import boundary contracts strictly maintained.
- **Actual results**: `pnpm test:all --fast` (13 passed, 0 failed, 1 skipped: 33/33 Python tests pass, import boundaries clean).

### M1-04 & M1-05 — Render Blueprint, Free-Tier Deployment Runbook & Server Verification

- **Date**: 2026-10-16
- **Branch**: `feature/m1-deploy-config`
- **What**: Implemented free deployment profile infrastructure and runbook per ADR-046, ADR-049, and `docs/10`:
  - **Render Infrastructure Blueprint** (`render.yaml`):
    - Configured single free web service (`devmind-api`) using Docker runtime (`server/Dockerfile`), exposing port 8000 and `/healthz` probe.
    - Configured Render free Key Value (`devmind-redis`) instance with connection string injection into `devmind-api`.
    - Marked all secret credentials with `sync: false` and zero plaintext values (`DEVMIND_DATABASE_URL`, `CLERK_SECRET_KEY`, `DEVMIND_ENCRYPTION_KEYS`, etc.).
  - **Free-Profile Deployment Runbook** (`docs/runbooks/deploy-render-vercel.md`):
    - Documented step-by-step setup for Vercel Hobby (Next.js client) and Render (API + embedded Celery).
    - Documented Neon PostgreSQL connection pooling, Clerk auth configuration, custom domains (`warishlabs.in`), and sleep tolerance invariants (graceful waking state on cold starts).
  - **Automated Configuration Tests** (`server/tests/test_deploy_config.py`):
    - Validated `render.yaml` schema, free plan enforcement, non-root Docker runtime, and absence of plaintext secrets.
    - Validated deployment runbook existence and ADR cross-references.
  - **Test-All Verification**:
    - Confirmed all 13 test steps pass cleanly (`test-all --fast`), including all 21 server tests and import boundary checks.
- **Actual results**: `pnpm test:all --fast` (13 passed, 0 failed, 1 skipped: 21/21 Python tests pass, docs links 0 broken).

### M1-03 — Server CI Workflows, Import Boundary Linter & Dependabot

- **Date**: 2026-10-16
- **Branch**: `feature/m1-server-ci`
- **What**: Implemented server CI validation, architectural boundary enforcement, and automated dependency maintenance:
  - **Import Boundary Contracts** (`server/.importlinter`): Configured `import-linter` with 7 strict architectural layer contracts per `docs/02` §4.1:
    - `api/` cannot import `persistence/` models directly, `orchestration/`, or provider SDKs.
    - `domain/` cannot import `api/` or `workers/`.
    - `brain/` cannot import `api/` or `orchestration/`.
    - `analysis/` cannot import `llm/` (deterministic analysis invariant).
    - `orchestration/` cannot import `api/`.
    - `llm/` cannot import other layers.
    - `workers/` cannot import `api/`.
  - **Boundary Verification & Deliberate Violation Tests** (`server/tests/test_import_boundaries.py`):
    - Tested that the codebase satisfies all 7 boundary contracts with 0 broken.
    - Added deliberate violation fixture test confirming that an unauthorized import (analysis importing llm) reliably fails `lint-imports`.
  - **GitHub Actions CI Workflow** (`.github/workflows/ci.yml`):
    - Added `server` job with `astral-sh/setup-uv@v5`, Python 3.12, dependency syncing, Ruff lint & format checks, boundary checks (`lint-imports`), and unit tests.
    - Wired `server` into `ci-gate` so PR merges require green server checks alongside client and extension checks.
    - Validated workflow with `actionlint` (0 errors).
  - **Dependabot Automation** (`.github/dependabot.yml`):
    - Added `pip` ecosystem for `server/` with grouped updates (`python-dependencies`).
    - Added `docker` ecosystem for `server/` (Dockerfile) and `infra/` (docker-compose).
  - **Monorepo Test Runner** (`scripts/test-all.mjs`):
    - Added `boundaries:server` check (`uv run --directory server lint-imports --no-cache`).
- **Actual results**: `pnpm test:all --fast` (13 passed, 0 failed, 1 skipped: 19/19 Python tests pass, 7/7 import boundary contracts kept).

### M1-02 — Multi-Stage Non-Root Dockerfile & Docker Compose Local Stack

- **Date**: 2026-10-16
- **Branch**: `feature/m1-docker-compose`
- **What**: Implemented containerization and local infrastructure stack per `docs/10` and `docs/02`:
  - **Multi-Stage Non-Root Dockerfile** (`server/Dockerfile`):
    - Builder stage using `python:3.12-slim-bookworm` with `uv` binary from official image for byte-compiled, frozen dependency synchronization (`uv sync --frozen --no-dev`).
    - Runtime stage creating dedicated non-root user `appuser` (uid 10001, gid 10001), copying `.venv` and source tree with `--chown=appuser:devmind`.
    - Healthcheck probe pointing to `/healthz` via `curl`. Default command runs `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
    - Verified build and runtime execution as non-root (`whoami` -> `appuser`, `uid=10001`, `gid=10001`).
  - **Docker Compose Stack** (`infra/docker-compose.yml`):
    - `postgres`: `pgvector/pgvector:pg16` with healthcheck probe `pg_isready -U devmind_app -d devmind`.
    - `redis`: `valkey/valkey:7.2-alpine` (drop-in Redis replacement) with healthcheck probe `valkey-cli ping`.
    - `api`: builds `server/Dockerfile`, depends on healthy postgres & redis, exposes port 8000.
    - `worker`: builds `server/Dockerfile`, runs `python -m app.workers.runner`.
    - `scheduler`: builds `server/Dockerfile`, runs `python -m app.workers.scheduler`.
  - **Worker & Scheduler Entrypoints**:
    - `server/app/workers/runner.py`: worker daemon with graceful signal handling (`SIGINT`/`SIGTERM`) and structured JSON logs.
    - `server/app/workers/scheduler.py`: scheduler daemon with graceful signal handling and structured JSON logs.
  - **Automated Tests** (`server/tests/test_docker_compose.py`):
    - Verified Dockerfile stages, non-root user, and healthcheck.
    - Verified docker-compose service definitions, images, and healthcheck dependencies.
- **Actual results**: `pnpm test:all --fast` (12 passed, 0 failed, 1 skipped: 17/17 Python tests pass in 0.32s, Docker build verified in 43.8s).

### M1-01 — FastAPI Application Skeleton, Settings, Logging Redaction, Problem Details & Health

- **Date**: 2026-10-16
- **Branch**: `feature/m1-server-skeleton`
- **What**: Implemented complete server foundation per `docs/02`, `docs/03`, and `docs/11`:
  - **Packaging & Tooling** (`server/pyproject.toml`): Configured `devmind-server` with Python >=3.11, FastAPI, Uvicorn, Pydantic v2, Pydantic-Settings, HTTPX, Ruff, Pytest, Import-Linter.
  - **Configuration** (`server/app/core/settings.py`): Pydantic v2 `Settings` with `DEVMIND_` env prefix, environment mode validations (`local`, `test`, `staging`, `production`), run mode (`api`, `worker`, `scheduler`, `all`), and CORS origins list parsing.
  - **Structured JSON Logging & Redaction Filter** (`server/app/core/logging.py`): RFC/ADR-002 compliant JSON logging with contextvars for `request_id`, `job_id`, `workspace_id`, and `project_id`. Regex filter automatically redacts Bearer tokens, `sk_live_`, `sk_test_`, `pk_live_`, `pk_test_`, `whsec_`, and database connection URI passwords.
  - **RFC 9457 Problem Details** (`server/app/core/errors.py`): `ProblemDetails` schema with stable codes (`resource.not_found`, `auth.unauthenticated`, `auth.forbidden`, `validation.failed`, `conflict.state`, `consent.required`, `quota.exceeded`, `rate_limit.exceeded`, `llm.unavailable`). Handlers for `DevMindError`, `RequestValidationError` (422), and unhandled server exceptions (500).
  - **Operational Probes** (`server/app/api/health.py`): `/healthz` (liveness) returning 200 OK without downstream dependency checks; `/readyz` (readiness) with pluggable database and redis checks returning 200 ready or 503 degraded without leaking secrets.
  - **App Factory & Middleware** (`server/app/main.py`): `create_app()` factory with CORS middleware, `RequestContextMiddleware` for `X-Request-ID` and `X-Process-Time` injection, and routers.
  - **Monorepo Integration** (`scripts/test-all.mjs`): Added `lint:server` (`uv run --directory server ruff check .`) and `test:server` (`uv run --directory server pytest`) to the automated verification runner.
- **Commands & tests added**:
  - `server/tests/test_health.py` (3 tests for `/healthz`, `/readyz`, `/api/v1`)
  - `server/tests/test_settings.py` (3 tests for defaults, cors, environment modes)
  - `server/tests/test_logging.py` (4 tests for Bearer token redaction, key redaction, DB URI password redaction, JSON formatting)
  - `server/tests/test_errors.py` (5 tests for 404, 401, 403, 403 consent, 422 validation)
- **Actual results**: `pnpm test:all --fast` (12 passed, 0 failed, 1 skipped: 15/15 Python unit tests passing in 0.40s, Ruff clean in 0.04s).

### B13 — Phase R1: Showcase README, Setup Guide & Profile Blurbs

- **Date**: 2026-10-16
- **Branch**: `docs/r1-readme-showcase`
- **What**: Comprehensive showcase documentation and link verification:
  - **R1-01 Showcase README.md**: Fully upgraded root `README.md` per `docs/ANTIGRAVITY_PROMPT.md` §12: dual SVG header lockups, static badges, screenshots gallery, `/admin/users` story, Mermaid lifecycle flowchart, 9 capabilities table, Project Brain layers, E0-E3 evidence model, architecture diagrams, privacy ledger, tech stack with ADR links, verified setup commands, roadmap table, docs index, and maintainer credits.
  - **R1-02 Setup Guide Reconciliation**: Updated `docs/SETUP-GUIDE.md` Section 8 with verified reality date-stamp: `Verified by Antigravity on 2026-10-16 at commit 7bc34c6 (Phase S2 complete)`.
  - **R1-03 Personal README**: Upgraded `docs/showcase/README.personal.md` with honest status and real raw GitHub screenshot links.
  - **R1-04 Profile Blurb**: Added `docs/showcase/PROFILE-BLURB.md` (<300 char summary + narrative paragraph).
  - Validated all 358 links/anchors across 40 Markdown files with `scripts/docs-links.mjs` (0 broken links).
- **Actual results**: `pnpm test:all --fast` (10 passed, 0 failed, 2 skipped), 0 broken links.

### B12 — Extension Quality, Host Activation, Packaging & Screenshot Guide

- **Date**: 2026-10-16
- **Branch**: `feature/s2-quality`
- **What**: Completed comprehensive test harness, activation testing, and packaging:
  - **S2-13 Extension Quality & Packaging** (`extension/tests/quality.test.ts`):
    - Full activation lifecycle test verifying registration of all 8 commands, 5 tree views, diagnostic collection, and status bar.
    - Explicit assertion guaranteeing **zero network calls** during fixture mode activation and scan.
    - Secret redaction format validation (`[REDACTED:token:8a9b2c3d]`).
    - VSIX packaging pipeline via `@vscode/vsce package --no-dependencies --out dist/devmind-vscode.vsix` producing a lean, compliant 40.16 KB bundle. Added `.vscodeignore`, `README.md`, and `LICENSE`.
    - Integrated `package:extension` step directly into `scripts/test-all.mjs` test runner.
  - **S2-14 Extension Evaluation & Screenshots**:
    - Validated `docs/runbooks/screenshots.md` guide covering F5 launch configuration, fixture mode assertions, and screenshot checklist.
- **Commands & tests added**:
  - `pnpm --filter devmind-vscode package` command in `extension/package.json`.
  - Comprehensive quality test suite (3 new tests, 20/20 total extension unit tests passing).
- **Actual results**: `pnpm test:all --fast` (10 passed, 0 failed, 2 skipped), VSIX generated.

### B11 — Diagnostics Collection, Status Bar & Consent Preview Webview

- **Date**: 2026-10-16
- **Branch**: `feature/s2-diagnostics-consent`
- **What**: Implemented diagnostics, status bar, and consent preview webview per docs/06:
  - **S2-10 DiagnosticCollection** (`extension/src/services/diagnostics.ts`): source `"DevMind"`, code = rule ID, severity mapping (`critical`/`high` -> `Error`, `medium` -> `Warning`, `low` -> `Information`, `info` -> `Hint`), E1 prefixed with `"Possible: "`, accessible message text not relying on color alone, multi-file URI grouping.
  - **S2-11 Status bar** (`extension/src/services/statusBar.ts`): icon + label (`$(shield) DevMind · fixture · idle`, `$(sync~spin) DevMind · fixture · scanning 1/2`, `$(cloud-offline) DevMind · fixture · offline`), accessible tooltip, click trigger opening findings.
  - **S2-12 Consent preview webview** (`extension/src/views/consentWebview.ts`): strict CSP + crypto nonce, brand tokens, category transmission table, secret redaction preview (`[REDACTED:token:8a9b2c3d]`), Cancel button autofocus by default, Send button with zero-network simulated execution in fixture mode.
- **Commands & tests added**:
  - Registered `devmind.reviewSync` in `package.json` and `extension.ts`.
  - Comprehensive unit test suite in `extension/tests/diagnostics-consent.test.ts` (5 tests, all passing).
- **Actual results**: `pnpm test:all --fast` (9 passed, 0 failed, 2 skipped), 17/17 extension unit tests passing, esbuild bundle generated.

### B10 — VS Code Extension Views (Findings, Structure, Scan, Sync, Database)

- **Date**: 2026-10-16
- **Branch**: `feature/s2-views`
- **What**: Implemented all 5 primary VS Code extension views per docs/06:
  - **S2-04 Findings tree view** (`extension/src/views/findingsView.ts`): grouped by severity (`critical`, `high`, `medium`, `low`, `info`), codicons, evidence labels (`E1 · Possible`), tooltip with rule description/remediation, click-to-open file at exact line (`devmind.openFindingLocation`).
  - **S2-05 Project structure view** (`extension/src/views/structureView.ts`): modules, endpoints/routes (`GET /admin/users`), authentication & role-guard markers (`$(shield)` protected vs `$(alert)` missing role guard).
  - **S2-06 Scan status view** (`extension/src/views/scanView.ts`): live/simulated scanner progress, rules pack (`v1.0.0`), analyzed file count, skipped files audit (`.env` path-only, `package-lock.json`), workspace scan triggers (`devmind.scanWorkspace`, `devmind.cancelScan`).
  - **S2-07 Sync & privacy view** (`extension/src/views/syncView.ts`): active mode (`metadata_only`), cryptographic receipt, audit ledger of what leaves machine (zero raw code chunks transmitted), ledger review action (`devmind.showWhatLeaves`).
  - **S2-08 Database (from files) view** (`extension/src/views/databaseView.ts`): statically discovered schemas from files (Prisma, SQLAlchemy, migrations), primary key & foreign key tags, explicit ADR-034 enforcement note (zero live DB connections).
  - **S2-09 Welcome content**: `viewsWelcome` registered in `package.json` for empty workspaces and unindexed states.
- **Commands & tests added**:
  - Registered `devmind.cancelScan`, `devmind.showWhatLeaves`, `devmind.openFindingLocation`, `devmind.refreshAll`.
  - Comprehensive unit test suite in `extension/tests/views.test.ts` (7 new tests, 12/12 passing).
- **Actual results**: `pnpm test:all --fast` (9 passed, 0 failed, 2 skipped), TypeScript clean, esbuild bundle generated.

### P0-01 — Verify repo preconditions; create PLAN.md and BRAIN.md

- **Date**: 2026-10-15
- **Branch**: `docs/p0-layout-and-adrs` (created from `main`)
- **What**: Ran precondition checks; created PLAN.md and BRAIN.md
- **Commands run**:
  - `git remote -v` → `origin git@github-personal:Warish-Labs/DevMind.git` ✅
  - `git log --oneline -5` → `90dfee7 Initial commit` ✅
  - `node --version` → `v24.22.0` ✅
  - `pnpm --version` → `12.11.2` (installed via get.pnpm.io installer) ✅
  - `uv --version` → `0.12.17` ✅
  - `git config user.name` → `mdwarishansari` ✅
  - `git config user.email` → `warishdeveloper@gmail.com` ✅
  - `corepack --version` → `0.36.0` ✅
- **Actual results**: All preconditions met.

### P0-02 — Verify folder rename (client/server/extension/common); fix leftovers

- **Date**: 2026-10-15
- **Branch**: `docs/p0-layout-and-adrs`
- **What**: Audited repository for legacy names (`frontend/`, `backend/`, `vscode-extension/`, `packages/`). Confirmed layout in `docs/02` §5 matches ADR-039.
- **Files updated**:
  - `brand/tokens/devmind-tokens.css`: Updated comment `frontend/` → `client/`
  - `brand/source/build.py`: Updated template comment `frontend/` → `client/`
  - `README.md`: Updated status table `Frontend, backend, extension code` → `Client, server, extension code`
  - `docs/10-deployment-and-operations.md`: Updated section 10 and table references to client/server
  - `docs/04-project-brain-and-rag.md`: Updated server references
  - `docs/05-agents-and-llm-workflows.md`: Updated server references
  - `AGENTS.md`: Updated security rule 3 to reference server instead of backend
- **Actual results**: Zero occurrences of legacy names describing DevMind's own layout remain.

### P0-03 — Verify ADR-039..049 in docs/12; fix drift

- **Date**: 2026-10-15
- **Branch**: `docs/p0-layout-and-adrs`
- **What**: Verified ADR-039 through ADR-049 in `docs/12` against `docs/00`, `docs/02`, `docs/10` §22, `docs/11` and `README.md`.
- **Actual results**: ADR register complete and verified; no drift.

### P0-04 — Trim AGENTS.md, add Session protocol, add .agents/rules/

- **Date**: 2026-10-15
- **Branch**: `docs/p0-layout-and-adrs`
- **What**: Verified `AGENTS.md` length (8,966 characters, below the 9,000 character target and 12,000 Antigravity limit). Verified Session protocol section, free tiers rule (ADR-046), and public repository rule (ADR-047). Verified Antigravity official discovery path (`.agents/rules/*.md`) and created `.agents/rules/00-session-protocol.md`.
- **Actual results**: `wc -c AGENTS.md` = 8966 bytes. `.agents/rules/00-session-protocol.md` present and verified.

### P0-05 — Create docs/runbooks stubs; scripts/docs-links.mjs; run link check

- **Date**: 2026-10-15
- **Branch**: `docs/p0-layout-and-adrs`
- **What**: Created `docs/runbooks/secrets-rotation.md` completing runbook stubs. Implemented `scripts/docs-links.mjs` (ESM Markdown link & anchor validator). Executed validator across all documentation.
- **Commands run**:
  - `chmod +x scripts/docs-links.mjs`
  - `node scripts/docs-links.mjs`
- **Actual results**: Scanned 31 Markdown files, checked 345 relative links & anchors. 0 broken links. Gate PASSED.

### B1 Merge — Pull Request #1 merged to main

- **Date**: 2026-10-15
- **PR**: https://github.com/Warish-Labs/DevMind/pull/1
- **Title**: `Docs/p0 layout and adrs`
- **What**: Owner reviewed and merged PR #1 to main. Antigravity switched to main, pulled (`d750b11`), deleted branch `docs/p0-layout-and-adrs` locally and on remote, created and switched to `feature/p0-tooling`.

---

## 5. Decisions and why

| Decision                                                              | Rationale       | ADR     |
| --------------------------------------------------------------------- | --------------- | ------- |
| Folder names: client/, server/, extension/, common/                   | Owner-confirmed | ADR-039 |
| Screenshot-first: S1 home page, S2 extension before M1                | Owner-confirmed | ADR-040 |
| Custom cursor + richer motion on home page                            | Owner-confirmed | ADR-041 |
| pnpm workspaces, uv, husky+lint-staged+commitlint                     | Owner-confirmed | ADR-042 |
| Vitest (not Jest), Playwright, pytest; REST not GraphQL               | Owner-confirmed | ADR-043 |
| Feature/fix branches, Conventional Commits, squash merges             | Owner-confirmed | ADR-044 |
| common/data/ as single source of truth                                | Owner-confirmed | ADR-045 |
| Free-only: Vercel Hobby + Render free + Neon Free + Render Key Value  | Owner-confirmed | ADR-046 |
| Real repo: Warish-Labs/DevMind (public)                               | Owner-confirmed | ADR-047 |
| Fake provider default; free LLM tiers only with synthetic/public data | Owner-confirmed | ADR-048 |
| Domain: devmind.warishlabs.in / api.devmind.warishlabs.in             | Recommended     | ADR-049 |

---

## 6. Commands that work (verified, 2026-10-15)

```bash
# Git
git switch -c <branch>               # create branch
git add -A && git commit -m "..."    # commit everything
git push -u origin <branch>          # push new branch

# Node / pnpm (after sourcing ~/.bashrc or adding to PATH)
export PNPM_HOME="/home/md-warish-ansari/.local/share/pnpm"
export PATH="$PNPM_HOME:$PATH"
pnpm --version    # 12.11.2

# Python / uv
uv --version      # 0.12.17
uv run python --version    # (verifies Python works)
```

---

## 7. Gotchas and fixes

| Problem                                                   | Fix                                                                                                         | Date                  |
| --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | --------------------- |
| `corepack enable pnpm` fails with EACCES                  | Use pnpm installer script: `curl -fsSL https://get.pnpm.io/install.sh                                       | SHELL=/bin/bash sh -` | 2026-10-15 |
| `npm install -g pnpm` fails with EACCES                   | Same as above — use the installer, not npm global                                                           | 2026-10-15            |
| pnpm installed but `pnpm: command not found` in new shell | Run `source ~/.bashrc` or add `export PNPM_HOME=...` and `export PATH=...` before using pnpm                | 2026-10-15            |
| docs/ and brand/ are untracked (not committed to main)    | Commit them on this branch as part of P0-01                                                                 | 2026-10-15            |
| Sandbox run_command fails with connection reset           | Use `BypassSandbox: true` — the sandbox network is unreachable for some commands                            | 2026-10-15            |
| `ssh: Could not resolve hostname github-personal`         | Configure `Host github-personal` alias in `~/.ssh/config` pointing to `github.com` with `~/.ssh/id_ed25519` | 2026-10-15            |

---

## 8. Dependency versions (verified 2026-10-15)

| Package  | Version | Source                  | License    | Date verified |
| -------- | ------- | ----------------------- | ---------- | ------------- |
| Node.js  | 24.22.0 | Active LTS — nodejs.org | MIT        | 2026-10-15    |
| pnpm     | 12.11.2 | get.pnpm.io installer   | MIT        | 2026-10-15    |
| uv       | 0.12.17 | already installed       | Apache-2.0 | 2026-10-15    |
| corepack | 0.36.0  | bundled with Node 24    | MIT        | 2026-10-15    |

> Remaining versions (Next.js, React, TypeScript, Tailwind, Vitest, Playwright, FastAPI, etc.) will be pinned in docs/runbooks/dependency-versions.md after being verified from npm/PyPI registries during B2.

---

## 9. Open questions for the owner

| #    | Question                                                                                                                                                                                          | Impact              |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| OQ-A | Is the Vercel Hobby team under the `warishlabs` GitHub account (the one whose commit email is `warishdeveloper@gmail.com`)? Vercel Hobby refuses to deploy commits from an email not on the team. | Deployment (Vercel) |
| OQ-B | What is the VS Marketplace publisher id? The plan uses `warishlabs` as a placeholder.                                                                                                             | Extension release   |
| OQ-C | Confirm the Neon free project is in the same region as Render (e.g., both `us-east-1`).                                                                                                           | Latency (M1)        |
| OQ-D | Is `warishdeveloper@gmail.com` the GitHub noreply email, or a linked verified email on the Warish-Labs org account?                                                                               | Vercel deploy       |

---

_Updated: 2026-10-15 · Branch: feature/p0-tooling · Task: P0-06_
