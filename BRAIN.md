# BRAIN.md — DevMind Working Memory

> No secrets, tokens, source content or user data in this file. It is committed to git.

---

## 1. Current state

| Field              | Value                                                                                                       |
| ------------------ | ----------------------------------------------------------------------------------------------------------- |
| **Branch**         | `main`                                                                                                      |
| **Last commit**    | `0c939d8` (chore: add DEPLOYMENT_GUIDE.md to .gitignore)                                                    |
| **Working tree**   | clean; working directly on main per user instruction                                                        |
| **Open PR**        | None (working directly on main)                                                                             |
| **Last CI result** | `test-all --fast`: 13 passed, 0 failed, 1 skipped; server 158/158 pass, extension 64/64 pass (39 API paths) |
| **Date**           | 2026-10-17                                                                                                  |

---

## 2. Next action (exact)

1. Implement **Milestone M5-03: Redaction Pipeline (Extension Client + Server-Side Redaction Re-check)**:
   - Inspect `docs/07 §6` and `docs/03 §12.4` for redaction specification:
     - Deterministic replacement format: `[REDACTED:<type>:<hash8>]`, where 8-char SHA-256 slice correlates repeats without revealing secrets.
     - Extension redaction pipeline: scans and redacts high-entropy secrets, bearer tokens, API keys, private keys, connection strings.
     - Server-side redaction re-check: on snippet/chunk ingestion, the server independently validates and re-redacts all payload text; increments `redaction_count` if missed patterns are found; fails closed if redaction fails.
   - Add unit tests in `extension/tests/redaction.test.ts` and `server/tests/test_redaction.py`.
   - Run verification test suite `node scripts/test-all.mjs --fast`.

---

## 3. Waiting on owner

| #   | Action required                                                                                                                           | Reference |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| 1   | **SETUP-GUIDE.md §4.4**: After the first CI run is green on B3, enable the branch ruleset `protect-main` requiring `ci-gate` status check | P0-15     |

---

## 4. Done log

### M5-02 — Extension Consent Preview Webview and Sent-Bytes Equality Check

- **Date**: 2026-10-17
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented dynamic consent preview webview, cryptographic canonical payload hashing, and sent-bytes equality verification per `docs/06 §12` and `docs/07 §7`:
  - **Sent-Bytes Equality & Canonical Hashing** (`extension/src/views/consentWebview.ts`):
    - `computeCanonicalPayload`: Deterministically sorts all keys, file paths, line ranges, AI providers, and secret categories.
    - `computePreviewHash`: Calculates `sha256:...` over the canonical payload JSON.
    - `verifySentBytesEquality`: Byte-for-byte verification confirming that payload about to leave the machine matches the exact hash consented to by the user.
  - **Dynamic Webview Experience** (`extension/src/views/consentWebview.ts`):
    - Upgraded webview to render dynamic file lists, line ranges, chunk counts, byte sizes, and secret redaction summaries by type (`[REDACTED:<type>:*]`).
    - Displays destination AI providers, purpose, guarded exclusions (e.g. `.env`), and the calculated `previewHash`.
    - Three-button action flow: "Cancel" (default focus), "Allow for This Project" (indexed mode), and "Send for This Request".
    - `ConsentWebviewManager.requestConsent`: Promise-based API returning `ConsentDecision`.
    - Retained backward-compatible `renderLegacyHtml` for S2 preview tests.
  - **Unit & Integration Tests** (`extension/tests/consentWebview.test.ts`):
    - 6 unit tests covering deterministic SHA-256 hashing, key permutation invariance, tampering detection, sent-bytes equality verification, HTML rendering with CSP nonce, and user action resolutions.
    - All 13 extension test files (64 tests) pass.
  - **Deployment Guide & Local Ignore**:
    - Created comprehensive `DEPLOYMENT_GUIDE.md` covering Neon PostgreSQL, Render Web Service & Key Value, Clerk Auth, Vercel frontend, and VS Code extension marketplace publishing.
    - Added `DEPLOYMENT_GUIDE.md` to `.gitignore`.

### M5-01 — Consent Model, Consent Records Table, and consent.required Enforcement

- **Date**: 2026-10-17
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented the consent records architecture, database migration, tenant-scoped repository, domain service with `403 consent.required` enforcement, and browser REST endpoints per `docs/03 §3.5, §11.1`, and `docs/07 §7`:
  - **Alembic Migration** (`server/alembic/versions/0004_consent_records.py`):
    - Created `consent_records` table with UUIDv7 PK, `workspace_id` (FK CASCADE), `project_id` (FK CASCADE), `user_id` (FK CASCADE).
    - Added columns: `scope` (check constraint for `snippet_transmission`, `cloud_index`, `llm_processing`), `provider_ids` (text[]), `data_categories` (text[]), `granted_for` (check constraint for `single_request`, `project`), `policy_version`, `preview_hash`, `granted_at`, `expires_at`, `revoked_at`.
    - Added composite indexes: `ix_consent_records_project_scope`, `ix_consent_records_workspace_id`, `ix_consent_records_user_id`.
  - **Persistence Model** (`server/app/persistence/models/consent.py`):
    - `ConsentRecord` model with `is_active` helper method evaluating non-revocation and expiration timestamps.
    - Exported in `server/app/persistence/models/__init__.py`.
  - **ConsentRepository** (`server/app/persistence/repositories/consent_repo.py`):
    - Enforces workspace-level tenant isolation via `AuthContext`.
    - Methods: `create_consent`, `get_consent`, `list_consents` (with `active_only` and `scope` filters), `revoke_consent`, and `has_active_consent` (supporting provider-specific evaluation).
  - **ConsentService & ProblemDetails Enforcement** (`server/app/domain/consent/consent_service.py`):
    - Validates scopes and durations before recording grants.
    - `verify_consent`: checks whether active consent exists; immediately raises RFC 9457 `ConsentRequiredError` (`403 consent.required`) if unconsented, expired, or revoked.
  - **REST Endpoints & Permission Registry** (`server/app/api/consents.py`):
    - `GET /api/v1/projects/{pid}/consents` (@declare_permission(PERM_CONSENT_MANAGE)).
    - `POST /api/v1/projects/{pid}/consents` (@declare_permission(PERM_CONSENT_MANAGE)) requiring `Idempotency-Key`.
    - `DELETE /api/v1/projects/{pid}/consents/{cid}` (@declare_permission(PERM_CONSENT_MANAGE)).
    - `GET /api/v1/projects/{pid}/consents/check` (@declare_permission(PERM_CONSENT_MANAGE)).
    - Regenerated TypeScript API schema with 39 OpenAPI paths (`pnpm gen:api`).
  - **Unit & Integration Test Suite** (`server/tests/test_consent.py`):
    - Tests for model active/expired/revoked states, repository tenant boundaries, service validation, `ConsentRequiredError` raising, and REST endpoints with idempotency and permissions.
    - All 158 server tests pass.

### M4-09 — Extension Metadata-Only Sync Client and Command Integration

- **Date**: 2026-10-17
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented the complete VS Code extension cloud sync client and commands for Project Brain metadata-only synchronization per `docs/06 §9`, `docs/06 §11`, and `docs/03 §11.2`:
  - **Extension Sync Client** (`extension/src/services/syncClient.ts`):
    - Computes cloud diff against Project Brain via `POST /api/v1/ext/projects/{pid}/manifest/diff`.
    - Handles base snapshot drift automatically: detects `409 sync.stale_base` and re-diffs cleanly from scratch.
    - Uploads file manifests and registers file versions via `PUT /api/v1/ext/projects/{pid}/manifest`.
    - Upserts extracted code symbols via `PUT /api/v1/ext/projects/{pid}/symbols`.
    - Upserts structural relationships via `PUT /api/v1/ext/projects/{pid}/relationships`.
    - Batches scanner findings via `POST /api/v1/ext/projects/{pid}/findings:batch`, enforcing the Rule 5 evidence ceiling (capped strictly at `<= E1` with deterministic snippet hashing).
    - Single-retry automatic token refresh on `401 Unauthorized` via `ExtensionAuthService.refreshTokens`.
    - Records cryptographic sync receipts in `LocalManifestStore` outside the workspace.
  - **VS Code Commands & UI Wiring** (`extension/src/extension.ts`, `extension/package.json`):
    - Added `devmind.projectId` setting in extension settings.
    - Wired `devmind.syncNow` and `devmind.syncProject` with progress notification (`vscode.window.withProgress`) and status bar indicator.
    - Added `devmind.linkProject` command to set or update the project ID in workspace configuration.
    - Exported `getManifestStore` on `LocalScanFindingsSource`.
  - **Unit & Integration Test Suite** (`extension/tests/syncClient.test.ts`):
    - 5 tests covering unauthenticated abort, end-to-end sync, 409 stale base recovery, 401 token refresh retry, and network error handling.
    - Verified all 12 extension test files (58 tests) pass.
    - Successfully built and packaged `dist/devmind-vscode.vsix` (49.9 KB) under publisher `WarishLabs`.

### M4-08 — Browser Read Endpoints for Scans, Brain Summary, Files, Symbols, and Graph

- **Date**: 2026-10-17
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented browser-facing REST read endpoints for scan runs, Project Brain summary metrics, active files, and version history per `docs/03 §11.1`:
  - **BrainRepository Read Extensions** (`server/app/persistence/repositories/brain_repo.py`):
    - `list_scan_runs`: Paginated scan query ordered by `created_at desc` with optional status filtering.
    - `get_latest_scan_run`: Efficient single query retrieving the most recent project scan run.
    - `get_file_by_id`: Retrieves project file by ID with `current_version` and eagerly loaded historical `versions`.
    - `get_brain_summary_stats`: Aggregates active file counts, language distribution, total content versions, snapshots, current symbols, structural relationships, findings by status, latest snapshot, and latest scan.
  - **Domain Services & Schemas**:
    - `ScanService` (`server/app/domain/brain/scan_service.py`): `ScanRunItem`, `list_scans`, `get_scan` (with RFC 9457 NotFoundError).
    - `BrainService` (`server/app/domain/brain/brain_service.py`): `BrainSummaryResponse`, `BrainFileItem`, `BrainFileVersionItem`, `BrainFileDetail`, `get_summary`, `list_files`, `get_file_detail`.
  - **REST Endpoints & Permission Enforcement**:
    - `GET /api/v1/projects/{pid}/scans` (@declare_permission(PERM_PROJECT_READ)).
    - `GET /api/v1/projects/{pid}/scans/{sid}` (@declare_permission(PERM_PROJECT_READ)).
    - `GET /api/v1/projects/{pid}/brain/summary` (@declare_permission(PERM_BRAIN_READ)).
    - `GET /api/v1/projects/{pid}/brain/files` (@declare_permission(PERM_BRAIN_READ)).
    - `GET /api/v1/projects/{pid}/brain/files/{fid}` (@declare_permission(PERM_BRAIN_READ)).
    - Mounted `scans_router` in `server/app/main.py`.
  - **OpenAPI Schema & Client Generation**:
    - Re-exported OpenAPI schema (36 paths) to `common/openapi.json`.
    - Regenerated TypeScript API client SDK via `pnpm gen:api` (`common/src/api/schema.d.ts`).
  - **Tests & Verification**:
    - Added 5 comprehensive tests in `server/tests/test_browser_api.py`.
    - Verified route permissions registry check (`test_all_api_routes_declare_permission`).
    - Verified 7/7 architecture boundary import contracts kept.
    - Full server pytest suite: 154 passed, 0 failed, 4 skipped.
    - Full monorepo fast suite: 13 passed, 0 failed, 1 skipped.

### M4-07 — Staleness Marking on File Change and Removal

- **Date**: 2026-10-17
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented staleness marking on file modification and removal, evidence currency invalidation, re-verification resolution, and manifest sync integration per `docs/03 §5.1 rule 3` and `rule 1`:
  - **BrainRepository Staleness Extensions** (`server/app/persistence/repositories/brain_repo.py`):
    - `mark_findings_stale_for_files`: Identifies all active findings (`open`, `acknowledged`, `in_progress`, `fix_proposed`) whose primary file or supporting evidence files match changed or removed paths. Transitions them to `stale`, records immutable `FindingStatusHistory` audit entries (`reason="evidence file modified or removed"`, `actor_kind="system"`), and sets `FindingEvidence.is_current = False` for all matching evidence records.
    - `resolve_stale_findings_for_files`: When re-verification scans run on previously stale files and confirm the finding is no longer detected, transitions finding status `stale -> resolved`, stamps `resolved_at` and `last_seen_scan_run_id`, and logs `FindingStatusHistory` (`reason="re-verification: no longer detected in scan"`).
  - **Manifest Domain Service Integration** (`server/app/domain/brain/manifest_service.py`):
    - In `put_manifest`: tracks changed file content versions (`old_version_id != ver.id`) and removed paths (`payload.removed_paths`).
    - Automatically invokes `mark_findings_stale_for_files` when paths change or are removed.
    - Added `stale_findings_count: int = 0` to `PutManifestResponse`.
  - **OpenAPI Schema & Client Generation**:
    - Regenerated OpenAPI schema (`common/openapi.json`) and TypeScript client types (`common/src/api/schema.d.ts`).
  - **Tests & Verification**:
    - Added comprehensive unit and integration test suite `server/tests/test_staleness.py` (6 tests covering primary file changes, supporting evidence changes, file removals, evidence `is_current` invalidation, status history recording, re-verification resolution, and `put_manifest` wiring).
    - Updated `server/tests/test_manifest_diff.py` to assert `stale_findings_count`.
    - Full server pytest suite: 149 passed, 0 failed, 4 skipped.
    - Full monorepo fast suite: 13 passed, 0 failed, 1 skipped.

### M4-06 — Findings Batch Ingestion with Fingerprinting and Lifecycle State Machine

- **Date**: 2026-10-17
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented findings batch ingestion, stable line-shift resilient fingerprinting, evidence ceiling enforcement (capping scanner evidence at E1), complete lifecycle state machine transitions, and browser/extension endpoints:
  - **Findings Domain Service** (`server/app/domain/brain/findings_service.py`):
    - `compute_finding_fingerprint`: Stable 64-character SHA-256 fingerprint generation prioritizing `rule_id:normalized_path:canonical_identifier` over volatile line numbers.
    - `batch_ingest_findings`: Ingests findings batches, validates categories/severities/confidences, caps extension evidence level at E1 (Rule 5 invariant), deduplicates against existing findings by `(project_id, fingerprint)`, merges new machine-checkable evidence, automatically reopens previously `resolved` findings upon recurrence, and restores `stale` findings back to `open` upon scan re-verification.
    - `transition_status`: Validates requested state transition against `ALLOWED_TRANSITIONS` matrix (docs/03 §5.1). Enforces mandatory reason code on dismissal (`false_positive`, `not_applicable`, `duplicate`, `other`), stamps `resolved_at` on resolution, and records append-only `FindingStatusHistory` entries.
    - `list_findings` & `get_finding_detail`: Filtered finding queries by status, severity, category, with eager-loaded evidence and complete status audit history.
  - **REST Endpoints & Permission Enforcement**:
    - Extension: `POST /api/v1/ext/projects/{pid}/findings:batch` (@declare_permission(PERM_PROJECT_SYNC)).
    - Browser: `GET /api/v1/projects/{pid}/findings` (@declare_permission(PERM_FINDINGS_READ)).
    - Browser: `GET /api/v1/projects/{pid}/findings/{fid}` (@declare_permission(PERM_FINDINGS_READ)).
    - Browser: `POST /api/v1/projects/{pid}/findings/{fid}/transitions` (@declare_permission(PERM_FINDING_PROGRESS), additionally requiring `PERM_FINDING_TRIAGE` for `dismissed` or `accepted_risk`).
  - **OpenAPI & Layer Boundaries**:
    - Regenerated TypeScript types via `pnpm gen:api` (31 OpenAPI paths).
    - Preserved 7/7 import linter contracts (`lint-imports` clean).
  - **Tests & Verification**:
    - Added 8 tests in `server/tests/test_findings.py`.
    - Full server pytest suite: 143 passed, 0 failed, 4 skipped.
    - Full monorepo fast suite: 13 passed, 0 failed, 1 skipped.

### M4-05 — Symbol and Relationship Batch Upsert and Graph Derivation

- **Date**: 2026-10-17
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented symbol batch upsert with transactional `is_current` invariants, graph relationship resolution, and recursive architectural graph derivation:
  - **BrainRepository Graph & Symbol Extensions** (`server/app/persistence/repositories/brain_repo.py`):
    - `get_symbol_by_id` & `get_symbols_by_keys`: Querying symbols with workspace/project tenant scoping.
    - `list_relationships`: Filtered relationship queries by target and relationship kind.
    - `resolve_relationships`: Auto-resolution of pending or external relationships against active project symbols.
    - `get_graph_data`: Recursive depth traversal building graph nodes and directional structural edges.
  - **Symbol Domain Service** (`server/app/domain/brain/symbol_service.py`):
    - Models: `CodeSymbolPayload`, `BatchSymbolsRequest`, `CodeSymbolItem`, `BatchSymbolsResponse`, `CodeRelationshipPayload`, `BatchRelationshipsRequest`, `CodeRelationshipItem`, `BatchRelationshipsResponse`, `GraphNode`, `GraphEdge`, `GraphResponse`.
    - `upsert_symbols`: Validates kinds against allowed vocabulary (`function`, `class`, `interface`, `method`, `variable`, `type`, `route`, `model`), marks previous versions of updated files `is_current = False`, inserts new symbol versions, and automatically attempts resolution of pending unresolved relationships.
    - `upsert_relationships`: Resolves keys to symbol IDs, validates kind vocabulary (`imports`, `calls`, `defines_route`, `guarded_by`, `reads_model`, `writes_model`, `implements`, `extends`), marks existing relationships non-current on version bumps, and tracks resolution status (`resolved` vs `unresolved`).
    - `list_current_symbols`: Efficient listing of active symbols by kind/limit.
    - `get_graph`: Traverses architectural dependencies up to specified max depth (default 3, max 10) for full project or centered at a root symbol.
  - **REST Endpoints & Permission Enforcement**:
    - Extension: `PUT /api/v1/ext/projects/{pid}/symbols` (@declare_permission(PERM_PROJECT_SYNC)).
    - Extension: `PUT /api/v1/ext/projects/{pid}/relationships` (@declare_permission(PERM_PROJECT_SYNC)).
    - Browser: `GET /api/v1/projects/{pid}/brain/symbols` (@declare_permission(PERM_BRAIN_READ)).
    - Browser: `GET /api/v1/projects/{pid}/brain/graph` (@declare_permission(PERM_BRAIN_READ)).
  - **OpenAPI & Layer Boundary Cleanliness**:
    - Regenerated TypeScript types via `pnpm gen:api` (27 OpenAPI paths).
    - Preserved 7/7 import linter contracts (`lint-imports` clean).
  - **Tests & Verification**:
    - Added 6 tests in `server/tests/test_symbols.py`.
    - Full server pytest suite: 135 passed, 0 failed, 4 skipped.
    - Full monorepo fast suite: 13 passed, 0 failed, 1 skipped.

### M4-04 — Snapshot and File Versioning Logic with Current Version Tracking

- **Date**: 2026-10-17
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented point-in-time immutable snapshot creation, current version tracking, historical snapshot comparison, and Project Brain REST endpoints:
  - **BrainRepository Snapshot Enhancements** (`server/app/persistence/repositories/brain_repo.py`):
    - `create_snapshot_from_active_files`: Captures active files (`removed_at IS NULL` and `current_version_id IS NOT NULL`), persisting immutable `SnapshotFile` mappings.
    - `get_snapshot_files`: Retrieves all file version associations for a snapshot with eagerly loaded `ProjectFile` and `FileVersion`.
    - `count_snapshot_files`: Efficient scalar count of files captured within a snapshot.
  - **Snapshot Domain Service** (`server/app/domain/brain/snapshot_service.py`):
    - `create_snapshot`: Validates origin (`scan`, `commit`, `manual`) and captures point-in-time snapshot.
    - `get_snapshot` and `get_snapshot_detail`: Returns serialized snapshot summary and full file composition.
    - `list_snapshots`: Lists recent project snapshots with file counts.
    - `compare_snapshots`: Computes file-level diff between two snapshots or against current active workspace state (`added`, `removed`, `modified`, `unchanged`).
    - Immutability guarantee: Historical snapshots remain completely unaltered when files are modified or deleted subsequently.
  - **Project Brain REST Router** (`server/app/api/brain.py`):
    - `POST /api/v1/projects/{pid}/brain/snapshots` (@declare_permission(PERM_PROJECT_UPDATE)).
    - `GET /api/v1/projects/{pid}/brain/snapshots` (@declare_permission(PERM_BRAIN_READ)).
    - `GET /api/v1/projects/{pid}/brain/snapshots/{sid}` (@declare_permission(PERM_BRAIN_READ)).
    - `GET /api/v1/projects/{pid}/brain/snapshots/{sid}/diff` (@declare_permission(PERM_BRAIN_READ)).
    - Enforced tenant boundary isolation and permission checks with HTTP 403 Forbidden.
  - **OpenAPI & Layer Boundaries**:
    - Regenerated TypeScript types via `pnpm gen:api` (23 OpenAPI paths).
    - Preserved 7/7 import linter contracts (`lint-imports` clean).
  - **Tests & Verification**:
    - Added 8 tests in `server/tests/test_snapshots.py`.
    - Full server pytest suite: 129 passed, 0 failed, 4 skipped.
    - Full monorepo fast suite: 13 passed, 0 failed, 1 skipped.

### M4-03 — Manifest Diff, Sync Upload Endpoints, Stale Base Detection, and Extension Publisher Configuration

- **Date**: 2026-10-17
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented cloud-to-local manifest diffing, atomic file metadata sync, stale snapshot base conflict detection, and extension publisher configuration:
  - **Extension Publisher Configuration**:
    - Configured `"publisher": "WarishLabs"` in `extension/package.json` and updated `extension/tests/quality.test.ts`. Verified VSIX package builds cleanly (47.75 KB).
  - **Manifest Domain Service** (`server/app/domain/brain/manifest_service.py`):
    - `resolve_project_context`: Verifies caller workspace/project membership and scopes AuthContext to target project tenant.
    - `compute_diff`: Computes diff between client manifest files and cloud active files, detecting `unchanged`, `new`, `changed`, `removed`, and missing files requiring symbol extractions.
    - `put_manifest`: Upserts file records, creates immutable `FileVersion` entries, updates `current_version_id` pointers, and marks absent files as removed.
    - `StaleBaseError`: Detects concurrent base snapshot drift (`sync.stale_base`) returning HTTP 409 Problem Details for automatic client re-sync.
  - **REST API Endpoints** (`server/app/api/extension.py`):
    - `POST /api/v1/ext/projects/{pid}/manifest/diff` (@declare_permission(PERM_PROJECT_SYNC)).
    - `PUT /api/v1/ext/projects/{pid}/manifest` (@declare_permission(PERM_PROJECT_SYNC)).
    - Strictly enforces Rule 10 (`Bearer dme_at_...` extension token only; rejects browser Clerk tokens with 401).
    - Strictly enforces permission check (`project:sync`) and cross-tenant boundary isolation with HTTP 403.
  - **Architecture & Layer Boundary Compliance**:
    - Manifest schemas (`FileManifestEntry`, `MissingFileEntry`, `ManifestDiffRequest`, `ManifestDiffResponse`, `PutManifestRequest`, `PutManifestResponse`) defined in domain layer and re-exported in API schemas, ensuring zero forbidden `domain -> api` imports (`lint-imports` 7/7 contracts kept).
  - **Tests & Verification**:
    - Added 10 tests in `server/tests/test_manifest_diff.py`.
    - Full server pytest suite: 121 passed, 0 failed, 4 skipped.
    - Full monorepo fast suite: 13 passed, 0 failed, 1 skipped.

### M4-02 — Job Lifecycle (Claim, Heartbeat, Reaper, Sweep) and Celery Worker Configuration

- **Date**: 2026-10-17
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented asynchronous job state machine, worker claiming, heartbeat lease tracking, stale worker reaping, enqueuer sweep, and Celery multi-queue topology:
  - **Job Lifecycle Domain Service** (`server/app/domain/jobs/service.py`):
    - `claim_job`: Atomic compare-and-set query (`UPDATE analysis_jobs SET status='running', attempt=attempt+1, heartbeat_at=now WHERE id=:id AND status='queued'`), preventing double execution across distributed workers.
    - `record_heartbeat`: Updates active worker heartbeat lease.
    - `is_cancelled_or_requested`: Cooperative cancellation check between processing steps, updating status to `cancelled`.
    - `complete_job`: Marks status `succeeded` and records `result_ref` JSONB.
    - `fail_job`: Budgeted retry handling — requeues to `queued` if `attempt < max_attempts` and error is retryable, otherwise sets `failed` and records failure reason.
    - `reap_stale_jobs`: Finds running jobs with expired heartbeats (>120s timeout), requeuing if attempts remain or permanently failing on exhausted budgets with `DEAD_WORKER_HEARTBEAT_TIMEOUT`.
    - `sweep_stranded_jobs`: Identifies stranded queued jobs (>60s old) across container reboots/sleeps for re-enqueuing.
    - Sequential audit logging to `job_events` for all lifecycle transitions.
  - **Celery Worker Configuration & Queue Topology** (`server/app/workers/celery_app.py`):
    - Multi-queue separation (docs/10 §9): `default`, `ingest`, `embed`, `analysis` with prefix isolation (`redis_key_prefix`).
    - Task routes mapping `devmind.ingest_*` -> `ingest`, `devmind.embed_*` -> `embed`, `devmind.analysis_*` -> `analysis`, and `devmind.*` -> `default`.
    - Reliability settings: `task_acks_late=True`, `task_reject_on_worker_lost=True`, `worker_prefetch_multiplier=1`, `visibility_timeout=3600`.
    - JSON-only serialization (`task_serializer="json"`, `accept_content=["json"]`).
    - Periodic beat schedule for `devmind.enqueuer_sweep` (60s) and `devmind.stale_job_reaper` (60s).
    - `devmind.process_job` worker task coordinating atomic claim, cancellation check, handler execution, and failure recording.
  - **Automated Verification**:
    - `server/tests/test_job_lifecycle.py`: 10 comprehensive unit tests verifying Celery queues/routing, compare-and-set claim uniqueness, heartbeat leasing, cooperative cancellation, retry budgeting, dead-worker reaping, and stranded job sweep.
    - Server pytest: 111 passed, 4 skipped, 0 failed.
    - Import boundaries: 7 kept, 0 broken.
    - Monorepo fast verification: 13 passed, 0 failed, 1 skipped.

### M4-01 — Project Brain Database Migrations, Models, and Repository

- **Date**: 2026-10-17
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented Project Brain schema migrations, SQLAlchemy persistence models, and repository layer with tenant isolation:
  - **Alembic Migration** (`server/alembic/versions/0003_project_brain.py`):
    - Created 13 core Brain tables (docs/03 §3.2-§3.4) with UUIDv7 PKs, tenant foreign keys, cascading deletions, and uniqueness constraints:
      - `scan_runs`: Scanning passes over projects with status, rules_version, stats JSONB, and idempotency key.
      - `local_workspace_registrations`: Folder mappings with SHA-256 root fingerprint (never raw paths).
      - `files`: Repo-relative file paths, language tiering (1/2/3), removed_at tracking, and current_version_id FK.
      - `file_versions`: Immutable content versions by `(file_id, content_hash)` with line/size metrics.
      - `project_snapshots` & `snapshot_files`: Point-in-time immutable file version snapshots.
      - `code_symbols`: Extracted program elements with qualified names, lines, framework tags JSONB, and `is_current` partial indexing.
      - `code_relationships`: Structural edges (`imports`, `calls`, `defines_route`, `guarded_by`, etc.).
      - `analysis_jobs` & `job_events`: Asynchronous work queue state machine and sequential event logging.
      - `findings`, `finding_evidence`, & `finding_status_history`: Security/auth findings, machine-checkable evidence (unconsented code forbidden at rest per ADR-047), and immutable lifecycle status history (docs/03 §5.1).
  - **SQLAlchemy Persistence Models** (`server/app/persistence/models/brain.py`):
    - Declared all 13 entities with strict typed mapped columns, foreign keys, relationships, and check constraints.
    - Exported in `server/app/persistence/models/__init__.py`.
  - **Brain Repository** (`server/app/persistence/repositories/brain_repo.py`):
    - Subclasses `BaseRepository` with mandatory `AuthContext` or `SystemContext` validation.
    - Implemented `_verify_project_access` enforcing cross-workspace isolation (`PermissionError` on alien workspace access).
    - Operations for scan runs, workspace registrations, files, versions, snapshots, symbols, relationships, jobs, and findings.
    - Exported in `server/app/persistence/repositories/__init__.py`.
  - **Automated Verification**:
    - `server/tests/test_brain_models.py`: Model instantiations, field defaults, AuthContext validation, and mock/live tenant isolation.
    - `server/tests/test_migrations.py`: Updated to assert migration head is `0003_project_brain` and all 22 tables registered in metadata.
    - Server pytest: 102 passed, 3 skipped, 0 failed.
    - Import boundaries: 7 kept, 0 broken.
    - Monorepo fast verification: 13 passed, 0 failed, 1 skipped.

### M3-06 — Backend Extension Tokens Table, Authentication Endpoints, and SecretStorage Integration

- **Date**: 2026-10-17
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented complete backend extension token lifecycle and VS Code SecretStorage client integration:
  - **Alembic Migration** (`server/alembic/versions/0002_extension_tokens.py`):
    - Created `extension_registrations` table (UUIDv7 PK, `user_id` FK -> `users.id`, `name`, `platform`, `extension_version`, `last_seen_at`, `revoked_at`).
    - Created `extension_tokens` table (UUIDv7 PK, `registration_id` FK, `token_hash` unique index, `kind`, `scope`, `expires_at`, `rotated_from`, `revoked_at`).
  - **Persistence Models & Repository**:
    - Created `ExtensionRegistration` and `ExtensionToken` models (`server/app/persistence/models/extension.py`).
    - Created `ExtensionRepository` (`server/app/persistence/repositories/extension_repo.py`) with strict AuthContext/SystemContext enforcement. Raw tokens are never stored at rest; only SHA-256 hashes are persisted.
  - **Domain Service & Authentication Dependency**:
    - `ExtensionService` (`server/app/domain/extension/service.py`): Token issuance, SHA-256 hashing, token rotation, and replay detection revocation (reusing an already rotated token revokes the entire registration per docs/07 §3).
    - `get_extension_auth_context` (`server/app/domain/auth/extension_dependencies.py`): Validates `Bearer dme_at_...` header, verifies token hash and expiration, checks registration active state, and resolves AuthContext.
  - **Extension REST Endpoints** (`server/app/api/extension.py`):
    - `POST /api/v1/ext/token`: Registers extension installation and issues access/refresh token pair.
    - `POST /api/v1/ext/token/refresh`: Rotates refresh token and issues new access token.
    - `POST /api/v1/ext/registrations/self/heartbeat`: Activity heartbeat using extension token.
    - `DELETE /api/v1/ext/registrations/self`: Revokes registration and tokens.
    - Mounted under `api_v1_router` in `server/app/main.py` with declared permissions for CI verification.
  - **VS Code Extension SecretStorage Integration**:
    - `ExtensionAuthService` (`extension/src/services/auth.ts`): Securely persists tokens in `vscode.SecretStorage`. Performs transparent automatic token refresh on expired access tokens and purges credentials on revocation.
    - Registered `devmind.signIn` and `devmind.signOut` commands in `extension.ts` and `package.json`.
  - **Comprehensive Tests**:
    - Server: 9 unit and endpoint tests in `server/tests/test_extension_auth.py` verifying token hashing, lifecycle, rotation, replay revocation, and Rule 10 scheme separation. All 96 server tests pass.
    - Extension: 5 tests in `extension/tests/auth.test.ts` verifying SecretStorage token storage, auto-refresh, sign-out, and 401 handling. All 53 extension tests pass.

### M3-05 — LocalScanFindingsSource Implementation and View Wiring

- **Date**: 2026-10-17
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented `LocalScanFindingsSource` coordinating discovery, manifest dirty-checking, AST extraction, and local rule evaluation into a unified scanning pipeline:
  - **LocalScanFindingsSource** (`extension/src/sources/localScanFindingsSource.ts`):
    - Implements `FindingsSource` interface (`getFindings`, `getStructure`, `getDatabaseModels`).
    - Unified pipeline coordinating `FileDiscoveryEngine`, `LocalManifestStore`, `SemanticExtractor`, and `LocalRuleEngine`.
    - Real local scanning with incremental dirty checking, evidence ceiling capping (`<= E1`), zero network calls, zero live DB connections (ADR-034), and deterministic secret redaction (ADR-047).
    - Preserves seamless fixture fallback when `devmind.fixtureMode: true`.
  - **Extension Wiring** (`extension/src/extension.ts`):
    - Default source upgraded to `LocalScanFindingsSource(storageDir)`.
    - Wired `devmind.scanWorkspace` command and notification progress to real scan execution, updating tree views, diagnostics, and status bar.
    - Synchronized settings listener to clear cache and refresh all views on mode change.
  - **View & Diagnostics Integration**:
    - `ScanViewProvider` updated to accept real `analyzedFilesCount` and dynamic `skippedFiles` list.
    - `StructureViewProvider` cleaned to enforce non-negotiable invariant: removed forbidden "vulnerable" wording in route tooltips.
  - **Unit & Integration Tests** (`extension/tests/localScanFindingsSource.test.ts`):
    - 5 tests validating real scanning on `express-admin` and `fastapi-admin`, ADR-047 deterministic secret redaction, treeview and diagnostics wiring, and fixture delegation. All 48 extension tests pass.

### M3-04 — Local Rule Engine and E0/E1 Security Finding Evaluator

- **Date**: 2026-10-17
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented local rule engine evaluating authorization invariants, authentication gaps, hardcoded credentials with deterministic redaction, and path-only credential file exposure:
  - **Secret Scanner with Redaction** (`extension/src/scanner/rules/secretScanner.ts`):
    - Identifies Stripe keys (`sk_live_...`), GitHub PATs (`ghp_...`), AWS keys (`AKIA...`), private key headers, Clerk keys, and webhook secrets.
    - Strictly enforces ADR-047 redaction: replaces all secret tokens with `[REDACTED:token:hash8]` using `computeRedactedTokenHash()`. Never exposes raw secrets in snippets, messages, or logs.
  - **Authorization & Authentication Rules** (`extension/src/scanner/rules/authRules.ts`):
    - `devmind.authz.missing_role_check` (E1): Identifies sensitive administrative routes (`/admin`, `/manage`, `/internal`, etc.) having `auth: true` but lacking role/permission checks (`roleGuard: false`). Matches `expected.json` fixtures for Express and FastAPI.
    - `devmind.authn.unprotected_route` (E1): Identifies sensitive administrative endpoints lacking authentication entirely.
  - **Credential File Rule** (`extension/src/scanner/rules/credentialFileRule.ts`):
    - `devmind.secrets.exposed_env_file` (E1): Path-only detection for unignored `.env` or credential files without reading file content.
  - **Unified Local Rule Engine** (`extension/src/scanner/rulesEngine.ts`):
    - Evaluates discovered files and extracted route modules.
    - Strictly caps extension-local evidence at `E1` (`E0` or `E1` only; never `E2` or `E3`).
  - **Comprehensive Unit Tests** (`extension/tests/rules.test.ts`):
    - 5 unit tests validating exact matches against `express-admin` and `fastapi-admin` expected findings, deterministic secret redaction verification, path-only credential handling, and the evidence ceiling invariant. All 43 extension tests pass.

### M3-03 — Semantic Parsers and Extractors for TS/JS and Python

- **Date**: 2026-10-16
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented semantic parsers and extractors for Tier 1 languages (TS, JS, PY) and Prisma matching `docs/06` §8:
  - **TypeScript/JavaScript Extractor** (`extension/src/scanner/extractors/typescriptExtractor.ts`):
    - Express router extraction: extracts HTTP method, route path, line numbers, and middleware token stacks (`requireAuth`, `requireRole`, `hasRole`, `authorize`).
    - Next.js App Router extraction: parses `route.ts` / `route.js`, maps filesystem folder paths to API paths (`app/api/workspaces/[id]/route.ts` -> `/api/workspaces/:id`), detects exported HTTP verbs and server session auth guards.
    - Prisma schema extractor: parses `model <Name> { ... }`, fields, types, `@id` (primary key), `@unique`, and `@relation` (foreign key).
  - **Python Extractor** (`extension/src/scanner/extractors/pythonExtractor.ts`):
    - FastAPI router extraction: detects `APIRouter(prefix=...)` and combines with route decorators (`@router.get(...)`, `@router.delete(...)`), evaluates dependency guards (`Depends(get_current_user)`, `Depends(require_admin)`, `Security(...)`), captures line numbers.
    - SQLAlchemy model extraction: extracts declarative models (`class User(Base):`), columns (`Column(...)`, `Mapped[...]`), primary keys, unique constraints, and foreign keys.
  - **Unified Dispatcher** (`extension/src/scanner/extractor.ts`):
    - `SemanticExtractor`: routes files by extension to appropriate extractors, returns structured `ProjectModule[]` and `DatabaseModel[]`, and calculates symbol and relationship counts.
  - **Comprehensive Unit Tests** (`extension/tests/extractors.test.ts`):
    - 6 tests evaluating against real fixtures (`evals/scanner/fixtures/express-admin` and `evals/scanner/fixtures/fastapi-admin`), Next.js App Router, Prisma schema, and SQLAlchemy models. All 38 extension tests pass.

### M3-02 — Local Manifest Store Outside Repository

- **Date**: 2026-10-16
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented local manifest store tracking file hashes, language tiers, parse statuses, and finding IDs outside the repository according to `docs/06` §5:
  - **LocalManifestStore** (`extension/src/scanner/manifest.ts`):
    - Persists manifest in an isolated directory (`context.storageUri`) outside the workspace repository, preventing accidental git commits.
    - Tracks per-file metadata: `relativePath`, `size`, `mtimeMs`, `contentHash`, `languageTier`, `languageId`, `parseStatus`, `symbolCount`, `relationshipCount`, `rulesVersion`, `findingIds`, `lastSyncedHash`.
    - Implemented fast incremental dirty-checking algorithm: unchanged `(size, mtimeMs)` skips content rehashing; modified files trigger content hash comparison; false-alarm timestamp touches are absorbed without rescan.
    - Implemented `pruneRemovedFiles` to drop deleted paths and their derived findings.
    - Implemented `getPendingSyncFiles` and `markSynced` with receipt hash stamping.
  - **Comprehensive Unit Tests** (`extension/tests/manifest.test.ts`):
    - 3 tests covering disk persistence, fast-path dirty checking, content hash modification detection, removed file pruning, and sync receipt tracking. All 32 extension unit tests passing.

### Client Vercel Monorepo Build Fix

- **Date**: 2026-10-16
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Fixed Vercel deployment build failure where `@devmind/common/api` could not be resolved during Next.js build:
  - Added `transpilePackages: ["@devmind/common"]` to `client/next.config.ts`.
  - Added workspace path alias to `client/tsconfig.json` (`@devmind/common/* -> ../common/src/*`).
  - Added `"prebuild": "pnpm --filter @devmind/common build"` to `client/package.json` ensuring `@devmind/common` is compiled before `next build`.
  - Moved `@devmind/common` to `dependencies` in `client/package.json`.

### M3-01 — File Discovery Engine, Ignore Engine & Raw Byte Hasher

- **Date**: 2026-10-16
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented local workspace file discovery, hard exclusions, credential path protection, and raw byte hasher according to `docs/06` §4-§5:
  - **Types & Language Tiers** (`extension/src/scanner/types.ts`):
    - Language tiers 1 (semantic: TS, JS, PY), 2 (text-level: JSON, YAML, SQL, PRISMA, MD), and 3 (unsupported/binary).
    - Scan status states: `ok`, `skipped_too_large`, `skipped_binary`, `skipped_credential`, `skipped_ignored`, `partial`, `failed`.
  - **Ignore & Credential Engine** (`extension/src/scanner/ignore.ts`):
    - Hard-excluded directory set (`node_modules`, `.git`, `dist`, `build`, `.next`, `.venv`, etc.) preventing traversal.
    - Credential path guard identifying `.env`, `.env.*`, `*.pem`, `*.key`, `id_rsa*`, `credentials*.json`, `*.kdbx` — content is strictly never read.
    - Generated/minified artifact detection (`*.min.js`, `*.map`, `*.bundle.js`, `@generated` / `Generated by` headers).
    - Binary extension identification and 512-byte null-byte (`\0`) sniffing.
    - Gitignore-compliant pattern matcher supporting `.gitignore` and `.devmindignore`.
  - **Deterministic Hasher** (`extension/src/scanner/hasher.ts`):
    - Raw byte SHA-256 hash calculation with hard security guard refusing to read credential files.
    - Normalized text hasher (CRLF -> LF) for stable cross-platform chunk hashes.
    - Redacted token 8-char digest helper `[REDACTED:token:hash8]`.
  - **File Discovery Engine** (`extension/src/scanner/discovery.ts`):
    - Recursive workspace directory walker respecting order of exclusions.
    - Per-file analysis ceiling (default 1 MB).
    - Produces structured `ScanSummary` with breakdown of discovered, included, tier counts, and skipped files.
  - **Comprehensive Unit Tests** (`extension/tests/discovery.test.ts`, `extension/tests/hasher.test.ts`):
    - 9 tests covering hard exclusions, credential path guards, gitignore globs, file size ceiling, binary sniffing, and raw byte SHA-256 calculation. All 29 extension tests pass.

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
