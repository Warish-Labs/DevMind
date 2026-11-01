# Deployment Diagnosis and DeployDoctor Operational Runbook

> **Governing documents:** [docs/01 §4 (CAP-07)](../01-product-requirements.md) · [docs/03 §3.4, §11](../03-data-model-and-api.md) · [docs/05 §6.9](../05-agents-and-llm-workflows.md) · [docs/07 §6, §15](../07-security-privacy-and-threat-model.md) · [docs/08 §Screen S-18](../08-ui-ux-design-specification.md) · [docs/09 §9, §14.1 E2E-10](../09-testing-and-quality-strategy.md) · [docs/10 §11, §22](../10-deployment-and-operations.md) · [ADR-046 (Free-Only)](../12-architecture-decisions-and-open-questions.md#adr-046-free-only-constraint-and-free-deployment-profile) · [ADR-047 (Public Repo)](../12-architecture-decisions-and-open-questions.md#adr-047-repository-ownership-and-visibility).
> **Non-negotiable security:** Never store, parse, or log unredacted credentials, tokens, or environment variable values. All log content undergoes deterministic secret redaction and ANSI stripping before persistence or LLM invocation. Tenant isolation is strictly enforced across `workspace_id` and `project_id`.

---

## 1. Subsystem overview

Release 1.4 introduces **Deployment Diagnosis (CAP-07)**, an automated root-cause diagnostic assistant and incident tracking ledger for container, build, and platform boot failures (Render, Vercel, Docker, Kubernetes):

1. **Dual-Tier Credential Redaction:**
   - **Client-Side Visual Redaction:** Real-time client-side masking in the web browser previewing database connection URLs (`postgresql://...`), API tokens/PATs (`ghp_...`, bearer tokens), and sensitive environment variable assignments (`KEY=value`) before submission.
   - **Server-Side Deterministic Filter (`LogParser.redact_and_parse`):** Strips ANSI terminal escape color sequences (`\x1b[...m`) and replaces detected secrets with irreversible SHA-256 keyed token hashes (`[REDACTED:<type>:<hash>]`). Redaction occurs in memory *prior* to parsing, database persistence, or LLM synthesis.
2. **Deterministic Failure Classification:**
   - Classifies logs across 10 known deployment failure categories:
     - `missing_env_var`: Pydantic `ValidationError` missing fields, `KeyError`, missing required env var notices.
     - `database_migration_failed`: Alembic revision command errors, missing migrations, duplicate key violations, schema relation errors.
     - `dependency_mismatch`: `ModuleNotFoundError`, `ImportError`, npm `ERESOLVE` / `MODULE_NOT_FOUND`.
     - `port_binding_failed`: Socket collisions (`Errno 98 Address already in use`, `EADDRINUSE`).
     - `build_compilation_failed`: TypeScript compilation errors, Next.js build step crashes, webpack errors.
     - `timeout`: Platform health check expirations, container startup timeouts.
     - `unhandled_exception`: Generic unhandled runtime tracebacks and uncaught Node/Python errors.
     - `insufficient_log`: Truncated log payloads with zero stack traces or exit status codes.
     - `unknown`: Unclassified failure patterns.
   - Pinpoints the **primary log line index** (1-based) responsible for the failure and extracts stack trace code references.
3. **Environment Variable Checker (`EnvVarChecker`):**
   - **Key Names Only Guarantee:** Only accepts, validates, and compares variable *names* (keys). Never accepts, stores, parses, or logs variable values.
   - Cross-checks referenced variables extracted from crash logs against `.env.example` templates and deployment platform configured keys.
   - Identifies missing required settings and detects spelling typos/mismatches using `difflib.SequenceMatcher` (e.g. `DATABSE_URL` -> `DATABASE_URL`).
4. **Incident Ledger & Deduplication (`DeploymentIncidentRepository`):**
   - Canonical fingerprinting via SHA-256 (`category:error_signature`).
   - Deduplicates recurring failure logs, incrementing `occurrence_count` and updating `last_seen_at`.
   - Allows operators to document proven resolutions and root-cause fixes.
5. **Similar Incident Precedent Matching:**
   - Searches historical project incidents for identical fingerprints, failure categories, or similar error signatures.
   - Retrieves previously verified remediation steps to fast-track incident resolution.
6. **DeployDoctor Agent (`DeployDoctorAgent`):**
   - Formulates ranked hypotheses with likelihood percentages, cited log lines, and actionable remediation commands.
   - Provides deterministic synthesis when LLM gateway is unavailable or offline.

---

## 2. Architecture and data flow

```mermaid
flowchart TD
    subgraph Client["Web Client (Screen S-18)"]
        RawLog[Raw Crash Logs] --> ClientRedaction[Client Redaction Preview]
        ClientRedaction --> SubmitDiag[Submit Diagnosis Request]
    end

    subgraph ServerAnalysis["Log Processing & Analysis"]
        SubmitDiag --> ServerRedact[Server-Side Secret Redaction & ANSI Strip]
        ServerRedact --> HeuristicClassifier[LogParser Heuristic Classifier]
        HeuristicClassifier --> CatClass[Failure Category & Line Index]
        HeuristicClassifier --> EnvExtract[Extract Referenced Env Var Names]
        EnvExtract --> EnvChecker[EnvVarChecker: Typo & Missing Schema Validation]
    end

    subgraph IncidentStorage["Persistence Store (Neon PostgreSQL)"]
        CatClass --> Fingerprint[SHA-256 Fingerprint Generator]
        Fingerprint --> IncidentDedup{Incident Exists?}
        IncidentDedup -->|New Incident| InsertInc[Insert deployment_incidents count=1]
        IncidentDedup -->|Recurring Failure| UpdateInc[Increment occurrence_count & last_seen_at]
        InsertInc --> SearchSimilar[Query Similar Historical Incidents]
        UpdateInc --> SearchSimilar
    end

    subgraph Synthesis["DeployDoctor Specialist Agent"]
        SearchSimilar --> AgentSynth{LLM Gateway Available?}
        EnvChecker --> AgentSynth
        AgentSynth -->|Yes| LLMSynth[DeployDoctor Agent Hypothesis Generation]
        AgentSynth -->|No / Deterministic| FallbackSynth[Deterministic Diagnosis Formulator]
        LLMSynth --> FinalResponse[DeploymentDiagnosisResponse]
        FallbackSynth --> FinalResponse
    end
```

---

## 3. Data model and schema definitions

### 3.1 Deployment Incidents (`deployment_incidents`)

- **Table:** `deployment_incidents`
- **Columns:**
  - `id`: `UUID` (UUIDv7 primary key).
  - `workspace_id`: `UUID` (tenant workspace foreign key).
  - `project_id`: `UUID` (project foreign key).
  - `fingerprint`: `String(64)` SHA-256 canonical hash of `category:error_signature`.
  - `summary`: `String(255)` human-readable failure summary.
  - `probable_cause`: `Text` explanation of underlying trigger.
  - `resolution`: `Text` (nullable) documented operator fix or mitigation.
  - `error_signature`: `String(255)` normalized signature with memory addresses and timestamps stripped.
  - `environment`: `String(32)` target environment (`production`, `staging`, `preview`, `dev`).
  - `service_name`: `String(64)` (nullable) container or service name.
  - `failure_category`: `String(64)` enum failure category.
  - `log_snippet`: `Text` sanitized log excerpt (max 4,000 characters).
  - `occurrence_count`: `Integer` count of observed crashes with this fingerprint (default 1).
  - `last_seen_at`: `timestamptz` UTC timestamp of most recent crash.
  - `resolved_at`: `timestamptz` UTC timestamp when marked resolved.
  - `resolved_by`: `UUID` (nullable) user ID who recorded resolution.
  - `metadata_`: `JSONB` additional metadata attributes (citations, hypotheses).
  - `created_at`, `updated_at`: `timestamptz` UTC.
- **Constraints & Indexes:**
  - Unique constraint on `(project_id, fingerprint)` for deterministic deduplication.
  - Composite index on `(workspace_id, project_id)` for tenant isolation.
  - Filter index on `(project_id, failure_category)` for similar incident lookup.

### 3.2 API Contract Schemas

- `DeploymentDiagnosisRequest`:
  - `raw_log`: `str` raw deployment log content.
  - `environment`: `str` target environment (default `"production"`).
  - `service_name`: `str | None` optional failing service name.
  - `configured_env_vars`: `list[str] | None` optional list of dashboard variable *names* (keys only, never values).
  - `example_env_content`: `str | None` optional `.env.example` content from repository snapshot.
- `DeploymentDiagnosisResponse`:
  - `incident_id`: `UUID` persisted incident record ID.
  - `is_new_incident`: `bool` whether this crash is newly observed vs recurring.
  - `fingerprint`: `str` canonical incident fingerprint.
  - `failure_category`: `str` identified category.
  - `confidence`: `float` (0.0 to 1.0) diagnostic certainty score.
  - `summary`, `probable_cause`, `recommended_action`: `str` diagnostic explanations.
  - `hypotheses`: `list[DiagnosisHypothesis]` ranked hypotheses with citations.
  - `referenced_env_vars`: `list[str]` variable names extracted from log.
  - `env_var_check`: `EnvVarCheckResultSchema` missing and typo analysis.
  - `primary_log_line`: `int | None` 1-based line number of decisive error.
  - `similar_past_incidents`: `list[SimilarIncidentMatch]` historical precedent fixes.
  - `is_insufficient_log`: `bool` warning flag when log payload is incomplete.
  - `redaction_count`: `int` total number of credential secrets masked.

---

## 4. Security and confidentiality guarantees (non-negotiable)

1. **Zero Unredacted Secret Persistence (ADR-047, docs/07 §6):**
   - Database connection strings (`postgresql://user:password@host...`) have passwords stripped and replaced with `[REDACTED:connection_string:<hash>]`.
   - API tokens, GitHub PATs (`ghp_...`), JWT bearer tokens, and key-value assignments (`SECRET=...`, `KEY=...`, `PASSWORD=...`) are replaced with `[REDACTED:env_secret:<hash>]`.
   - Raw credentials are never stored in `deployment_incidents`, never logged to structured JSON logs, and never sent to external LLMs.
2. **Environment Variable Names Only:**
   - `EnvVarChecker` and API schemas strictly accept variable *names* (keys).
   - Values are never requested, accepted, or stored.
3. **Tenant Boundary Enforcement (docs/03 §4, docs/09 §6):**
   - Every incident query and mutation verifies `ctx.workspace_id == incident.workspace_id`.
   - Cross-tenant access attempts immediately raise RFC 9457 `403 ForbiddenError`.
4. **Deterministic Reproducibility:**
   - Category heuristics, error normalization, and variable typo matching are 100% deterministic, guaranteeing identical diagnostic outcomes without LLM variance.

---

## 5. Failure modes catalog and remediation playbooks

### Playbook 1: Missing Required Environment Variables (`missing_env_var`)

- **Symptom:** Application fails immediately at startup with Pydantic `ValidationError: Field required` or `KeyError: 'ENV_VAR_NAME'`.
- **Diagnostic Flow:**
  1. `LogParser` extracts variable name from the error block.
  2. `EnvVarChecker` cross-references with `.env.example`.
  3. If variable is missing from platform dashboard, flag under `missing_required`.
  4. If a similar variable exists (e.g. `DATABSE_URL` instead of `DATABASE_URL`), flag typo candidate with similarity ratio.
- **Remediation:**
  - Add missing key to the Render/Vercel environment dashboard.
  - If typo detected, rename the variable in platform settings.
  - Trigger redeploy.

### Playbook 2: Database Migration Revision Missing (`database_migration_failed`)

- **Symptom:** Migrator container exits with `alembic.util.exc.CommandError: Can't locate revision identified by 'xxxx'`.
- **Diagnostic Flow:**
  1. Pinpoint Alembic CommandError line.
  2. Search historical incidents for matching migration failure.
  3. If previously resolved, suggest historical resolution command (e.g. `alembic stamp head`).
- **Remediation:**
  - Verify migration script was committed to git branch.
  - If target revision was squashed or skipped, run `alembic stamp <revision>` to align database version table.

### Playbook 3: Python / Node Dependency Mismatch (`dependency_mismatch`)

- **Symptom:** Container exits with `ModuleNotFoundError: No module named 'xyz'` or `Cannot find module 'xyz'`.
- **Diagnostic Flow:**
  1. Extract missing module name from import traceback.
  2. Verify project dependency manifest (`pyproject.toml`, `package.json`).
- **Remediation:**
  - Add missing dependency to manifest (`uv add <pkg>` or `pnpm add <pkg>`).
  - Verify Dockerfile copies lockfile and executes package installation before running application.

### Playbook 4: Port Collision & Socket Binding Failure (`port_binding_failed`)

- **Symptom:** Web process crashes with `OSError: [Errno 98] Address already in use` or `EADDRINUSE`.
- **Diagnostic Flow:**
  1. Extract assigned port number from log line.
  2. Check platform runtime environment ($PORT).
- **Remediation:**
  - Ensure entrypoint script reads platform dynamic port `$PORT` (e.g. `uvicorn --port ${PORT:-8000}`).
  - Ensure background worker services do not attempt to bind to HTTP ports.

### Playbook 5: Build & Type Compilation Failures (`build_compilation_failed`)

- **Symptom:** Static build step exits with non-zero exit code, TypeScript type errors, or bundle failure.
- **Diagnostic Flow:**
  1. Extract offending file path and line number from compiler diagnostic.
  2. Flag compilation error in diagnostic summary.
- **Remediation:**
  - Run type checks locally (`pnpm typecheck` or `pnpm build`) to reproduce error.
  - Fix type annotations or syntax errors before pushing to deployment branch.

### Playbook 6: Startup & Health Check Timeouts (`timeout`)

- **Symptom:** Platform terminates container after 60–120s with `Health check timed out`.
- **Diagnostic Flow:**
  1. Classify timeout from log frame.
  2. Inspect initialization logs prior to timeout notice.
- **Remediation:**
  - Check for blocking synchronous network calls during application startup (e.g. synchronous database connect on main loop).
  - Check if readiness probe path (`/readyz`, `/healthz`) is responsive without database locks.
  - Increase health check threshold if initial model/cache warming requires additional duration.

### Playbook 7: Truncated or Insufficient Log Payloads (`insufficient_log`)

- **Symptom:** Pasted log ends abruptly without stack trace, exit code, or error reason.
- **Diagnostic Flow:**
  1. Detect absence of error traces (`failure_category == "unknown"` with confidence ≤ 0.50).
  2. Flag `is_insufficient_log = True`.
- **Remediation:**
  - Display user guidance in web UI requesting complete container initialization and platform runtime logs.
  - Direct operator to retrieve full log stream using platform CLI (`render logs` or `vercel logs`).

---

## 6. Verification and evaluation commands

```bash
# 1. Run deployment diagnosis benchmark evaluation harness
pnpm eval:deploy

# 2. Run E2E deployment integration test suite
cd server && uv run pytest tests/test_e2e_deployment.py

# 3. Run full monorepo fast quality checks
node scripts/test-all.mjs --fast
```
