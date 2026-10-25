# PLAN.md

Legend: `[ ]` todo · `[~]` in progress · `[x]` done+verified · `[!]` blocked
Rule: update this file and `BRAIN.md` in every branch before opening its PR.
Branch per slice; PR merged by owner before the next slice starts.

---

## Phase P0: Repository foundation

### B1 `docs/p0-layout-and-adrs`

PR title: `docs(repo): verify layout and ADRs, add PLAN, BRAIN and agent session files`

- [x] P0-01 Verify repo preconditions; create PLAN.md and BRAIN.md
  - Acceptance: git remote = Warish-Labs/DevMind; PLAN.md and BRAIN.md committed
- [x] P0-02 Verify the folder rename already applied (client/server/extension/common); fix leftovers; check mapping in docs/02 §5
  - Acceptance: zero occurrences of frontend/backend/vscode-extension/packages describing DevMind's own layout
- [x] P0-03 Verify ADR-039..049 in docs/12 agree with docs/00, 02, 10 §22, 11 and README; fix drift
  - Acceptance: ADR register complete; no stale paths in referenced docs
- [x] P0-04 Trim AGENTS.md (≤~9,000 chars), add Session protocol, add .agents/rules/ after verifying current Antigravity docs
  - Acceptance: AGENTS.md under limit; .agents/rules/00-session-protocol.md exists; Session protocol section added
- [x] P0-05 Create docs/runbooks/ stubs; scripts/docs-links.mjs; run link check
  - Acceptance: link check = 0 broken; all runbook stubs committed

Gate: link check = 0 broken; AGENTS.md under limit (PASSED: 0 broken links; AGENTS.md is 8,966 chars)

---

### B2 `feature/p0-tooling`

PR title: `feat(repo): add workspace tooling, hooks and test-all runner`

- [x] P0-06 Root package.json, pnpm-workspace.yaml (supply-chain settings), node/python pins, tsconfig.base, eslint, prettier, editorconfig, gitattributes, gitignore
  - Acceptance: pnpm install --frozen-lockfile succeeds; tsc --noEmit exits 0 on empty project
- [x] P0-07 .env.example files (root, client/, server/, extension/), LICENSE placeholder, SECURITY.md, CONTRIBUTING.md, CHANGELOG.md
  - Acceptance: all .env.example files present; every server variable has a placeholder and a comment
- [x] P0-08 common/ package skeleton + schema validators + tests
  - Acceptance: pnpm --filter common test passes; subpath exports resolve
- [x] P0-09 Husky, lint-staged, commitlint, pre-push guard (blocks pushes to main and force-pushes)
  - Acceptance: a bad commit message is rejected; a push to main is rejected
- [x] P0-10 scripts/sync-brand.mjs, scripts/test-all.mjs, docs/runbooks/testing.md
  - Acceptance: pnpm brand:check passes; pnpm test:all --fast runs (steps PASS or SKIP not silent)
- [x] P0-11 docs/runbooks/dependency-versions.md with verified versions and dates
  - Acceptance: every pinned dep has a version, source URL, date, and license

Gate: fresh clone → pnpm install --frozen-lockfile → pnpm test:all --fast passes (or SKIP with reason)

---

### B3 `feature/p0-ci-github`

PR title: `ci(repo): add CI with ci-gate, PR title check, Dependabot, templates`

- [x] P0-12 ci.yml with all jobs + ci-gate aggregator (all jobs always run; no path filters)
  - Acceptance: ci-gate job present; every job listed in needs[]; jq check on results
- [x] P0-13 pr-title.yml; dependabot.yml; PR/issue templates; CODEOWNERS; codeql.yml; main-guard.yml
  - Acceptance: actionlint clean; templates exist and render; CODEOWNERS has @mdwarishansari
- [x] P0-14 release-extension.yml (inert until secrets) + docs/runbooks/release-extension.md
  - Acceptance: workflow exists; publish jobs gated on extension-release environment; secrets absence documented
- [x] P0-15 actionlint clean; first PR run green
  - Acceptance: actionlint exits 0; first CI run on this branch passes (or only skips)

Gate: CI green on the PR; owner enables ruleset requiring ci-gate (docs/SETUP-GUIDE.md §4.4)

---

## Phase S1: Home page (screenshot-first)

### B4 `feature/s1-foundation`

PR title: `feat(client): scaffold Next.js app, tokens, fonts, brand sync, data sources`

- [x] S1-01 Next.js App Router in client/ (TS strict, Tailwind, ESLint, Vitest, Playwright)
  - Acceptance: pnpm --filter client build succeeds; / and /early-access render
- [x] S1-02 tokens.css + Tailwind mapping + no-hex lint rule; fonts via next/font (self-hosted)
  - Acceptance: brand:check passes; no hard-coded hex in components
- [x] S1-03 brand sync (logos inline SVG, favicons, manifest, OG); metadata; robots/sitemap
  - Acceptance: /robots.txt and /sitemap.xml resolve; OG tags present; favicon shows in browser tab
- [x] S1-04 common/data/*.json + schemas + integrity tests (rule-catalog, release-status, privacy-ledger, capabilities, walkthrough)
  - Acceptance: pnpm --filter common test passes; all JSON files validate; devmind.authz.missing_role_check present in rule-catalog.json; walkthrough has exactly 14 steps
- [x] S1-05 Layout: gutter rail (01–08), header, footer, skip link, /early-access, not-found
  - Acceptance: skip link present; landmarks in HTML; /early-access renders; 404 shows not-found.tsx

### B5 `feature/s1-hero`

PR title: `feat(client): add hero Trace with scripted sequence`

- [x] S1-06 Trace component (real selectable text, SVG shapes not emoji, syntax tones, margin note)
  - Acceptance: Trace renders with correct rule id from rule-catalog.json; ✓ and ✗ are SVG shapes; final frame visible without JS
- [x] S1-07 Hero sequence (WAAPI/CSS ~7s, once), replay button, reduced-motion final frame
  - Acceptance: sequence runs once on load; replay button works; prefers-reduced-motion shows final frame immediately
- [x] S1-08 Pointer-lit border (CSS --mx/--my, opacity ≤0.35) + subtle parallax on margin note (fine pointers only, ≤6px)
  - Acceptance: no glow orb; effect absent under touch emulation; opacity under threshold

### B6 `feature/s1-sections`

PR title: `feat(client): add homepage sections 02-08`

- [x] S1-09 02: One change / five consequences (diff hunk + consequence questions + drawn connectors)
- [x] S1-10 03: Project Brain strata (interactive SVG, keyboard, 10 layers from docs/04 §2)
- [x] S1-11 04: Capability index table with release labels from release-status.json
- [x] S1-12 05: Walkthrough sticky timeline (14 steps, click-to-jump, id="walkthrough")
- [x] S1-13 06: Local-first diptych + 07: Privacy ledger (mode toggle, table from privacy-ledger.json)
- [x] S1-14 08: CTA + footer + Preferences control (cursor on/off, reduced motion on/off, localStorage)
  - Acceptance: all sections render; links in section 08 to /early-access and github.com/Warish-Labs/DevMind work

### B7 `feature/s1-cursor-motion`

PR title: `feat(client): add custom cursor and motion system`

- [x] S1-15 lib/motion/ (tokens, usePrefersReducedMotion, useInView, sequence helper)
- [x] S1-16 DevMindCursor (core dot + ring, states: link/button/text/hotspot/pressed/hidden, magnetic ≤8px, caret bar, toggle, localStorage)
  - Acceptance: cursor mounts only with (hover:hover) and (pointer:fine) and !reducedMotion; touch profile has no cursor; toggle persists; aria-hidden; pointer-events:none
- [x] S1-17 View Transitions for / → /early-access (@view-transition navigation: auto; progressive enhancement)

### B8 `feature/s1-quality`

PR title: `test(client): add e2e, a11y, performance checks and screenshots`

- [x] S1-18 Vitest (content integrity, token contrast, cursor math, hooks) + Playwright + axe (keyboard, reduced-motion, touch, section nav)
- [x] S1-19 pnpm screenshots → docs/assets/screenshots/home-*.png (8 shots, compressed)
- [x] S1-20 Design review checklist (docs/08 §18) completed in PR body; fix findings
  - Acceptance: Lighthouse CWV numbers recorded in BRAIN.md; axe no serious violations; screenshots exist

Gate: pnpm --filter client build + pnpm test:all --fast + e2e green; owner screenshots and merges

---

## Phase S2: Extension UI shell (fixture data)

### B9 `feature/s2-extension-scaffold`

PR title: `feat(extension): scaffold extension, fixtures and activation`

- [x] S2-01 evals/scanner/fixtures/express-admin/ and fastapi-admin/ with expected.json
- [x] S2-02 Extension scaffold (esbuild, @vscode/vsce, launch/tasks config, media sync)
- [x] S2-03 FindingsSource + FixtureFindingsSource; Output channel; settings (apiBaseUrl machine-scope, fixtureMode, syncMode)

### B10 `feature/s2-views`

PR title: `feat(extension): add Findings, Structure, Scan, Sync, Database views`

- [x] S2-04 Findings tree (grouped by severity, tooltip, context actions)
- [x] S2-05 Project structure tree (modules, routes, handlers, guard chips, missing-role marker)
- [x] S2-06 Scan view (simulated progress, Cancel button, devmind.scanWorkspace command)
- [x] S2-07 Sync view (mode, last sync, what-was-sent log, review action)
- [x] S2-08 Database (from files) view placeholder (labeled example)
- [x] S2-09 Welcome content (viewsWelcome for no-workspace, not-signed-in, fixture-mode)

### B11 `feature/s2-diagnostics-consent`

PR title: `feat(extension): add diagnostics, status bar and consent preview`

- [x] S2-10 DiagnosticCollection (source "DevMind", E1 prefixed "Possible:", code = rule id, severity mapping from docs/06)
- [x] S2-11 Status bar ($(shield) DevMind · fixture · idle / scanning N/M / offline; text not color alone; click opens Scan view)
- [x] S2-12 Consent preview webview (CSP + nonce, tokens, table of example files, Send/Cancel; Send in fixture mode shows message, no network; default focus Cancel)

### B12 `feature/s2-quality`

PR title: `test(extension): add unit, host and package tests and screenshot guide`

- [x] S2-13 Vitest (grouping, severity, text builders, redaction) + extension-host test (activates, fixture scan, diagnostics count, no network) + vsce package/ls; CI artifact
- [x] S2-14 docs/runbooks/screenshots.md; verify F5 flow end to end
  - Acceptance: vsce package succeeds; host test passes; F5 shows all views with fixture data; nothing makes a network call

Gate: package builds; host test passes; F5 verified; owner screenshots and merges

---

## Phase R1: GitHub showcase README

### B13 `docs/r1-readme-showcase`

PR title: `docs(repo): add showcase README with diagrams and screenshots`

- [x] R1-01 Root README per ANTIGRAVITY_PROMPT.md §12 (logo, badges, screenshots, Mermaid diagrams, honest status table)
- [x] R1-02 Reconcile docs/SETUP-GUIDE.md commands and env table with verified reality (date-stamped)
- [x] R1-03 Upgrade docs/showcase/README.personal.md with real screenshots and honest status; owner copies to personal repo by hand
- [x] R1-04 Add docs/showcase/PROFILE-BLURB.md (under 300 chars + longer paragraph)
  - Acceptance: all README links resolve; Mermaid renders (validate); every claim matches PLAN status

Gate: all README links resolve; Mermaid renders; every claim matches PLAN.md status

---

## Phase M: Product milestones (docs/11)

### M1 · Repository foundation, rules, CI, Docker, configuration

- [x] M1-01 server/ skeleton (FastAPI app factory, settings, structured logging + redaction, error mapping RFC 9457, /healthz, /readyz) (feature/m1-server-skeleton)
- [x] M1-02 Dockerfile (multi-stage, non-root) + infra/docker-compose.yml (pgvector, Valkey/Redis, api, worker, scheduler) (feature/m1-docker-compose)
- [x] M1-03 Server CI jobs added to ci-gate; import-linter; pytest layout; Dependabot pip/docker (feature/m1-server-ci)
- [x] M1-04 render.yaml Blueprint (free profile: one free web service + free Key Value); docs/runbooks/deploy-render-vercel.md (feature/m1-deploy-config)
- [x] M1-05 test-all server steps; SETUP-GUIDE commands verified (feature/m1-deploy-config)
- [x] M1-06 launcher: DEVMIND_RUN_MODE=api|worker|scheduler|all (uvicorn + embedded Celery, --pool=solo, signal handling); migrations at start under advisory lock; startup sweep; DEVMIND_REDIS_KEY_PREFIX (feature/m1-free-profile)
- [x] M1-07 server/configs/quotas.free.yaml from measured bytes per chunk; memory measurement recorded in BRAIN.md (feature/m1-free-profile)

### M2 · Authentication, workspaces, projects, database, API foundations

- [x] M2-01 Alembic baseline setup and initial tenancy/identity migrations: users, workspaces, workspace_memberships, projects, project_memberships, audit_events, usage_records (feature/m2-db-migrations)
- [x] M2-02 Database engine session factory, base model with UUIDv7 PK, and repository layer enforcing AuthContext (feature/m2-db-migrations)
- [x] M2-03 Clerk token verification service (issuer, JWKS signature, expiry, authorized parties, cache) (feature/m2-auth-clerk)
- [x] M2-04 Policy service, permission evaluator, and route permission registry with CI enforcement (feature/m2-auth-policy)
- [x] M2-05 Workspaces and projects CRUD REST endpoints with permission checks and Problem Details (feature/m2-workspaces-projects)
- [x] M2-06 Idempotency middleware and Redis-backed sliding-window rate limiting (feature/m2-middleware)
- [x] M2-07 Clerk user webhook receiver with Svix signature verification and sync (feature/m2-webhooks)
- [x] M2-08 OpenAPI spec generation, TypeScript client generation (pnpm gen:api), and frontend authentication shell integration (feature/m2-client-auth)

### M3 · VS Code extension real local scanning

- [x] M3-01 File discovery, ignore engine (.gitignore, .devmindignore, hard exclusions, credential file path guard), and SHA-256 hasher (feature/m3-discovery-hasher)
- [x] M3-02 Local manifest store outside repository tracking file hashes, language tiers, parse statuses, and findings (feature/m3-manifest-store)
- [x] M3-03 Semantic parser and extractor for TypeScript/JavaScript (Next.js/Express, Prisma) and Python (FastAPI, SQLAlchemy) (feature/m3-parser-extractor)
- [x] M3-04 Local rule engine and E0/E1 security finding evaluator with redaction (unprotected routes, missing guards, hardcoded secrets) (feature/m3-rules-engine)
- [x] M3-05 LocalScanFindingsSource implementation replacing FixtureFindingsSource, wired to TreeViews, Status Bar, and DiagnosticsCollection (feature/m3-local-scanner)
- [x] M3-06 Backend extension tokens table, authentication endpoints (POST /api/v1/ext/token), and VS Code SecretStorage auth integration (feature/m3-extension-auth)

### M4 · Project Brain ingestion: metadata, symbols, relationships, snapshots

- [x] M4-01 Project Brain database migrations, persistence models (13 tables), and BrainRepository with AuthContext tenant isolation (feature/m4-brain-models)
- [x] M4-02 Job lifecycle (claim, heartbeat, reaper, sweep) and Celery worker configuration (docs/10 §9) (feature/m4-job-lifecycle)
- [x] M4-03 Manifest diff and upload endpoint with sync.stale_base (feature/m4-manifest-diff)
- [x] M4-04 Snapshot and file versioning logic with current version tracking (feature/m4-snapshots)
- [x] M4-05 Symbol and relationship batch upsert and graph derivation (feature/m4-symbols)
- [x] M4-06 Findings batch ingestion with fingerprinting and lifecycle state machine (docs/03 §5.1) (feature/m4-findings)
- [x] M4-07 Staleness marking on file change/removal (feature/m4-staleness)
- [x] M4-08 Browser read endpoints for scans, findings, Brain summary, symbols, graph, snapshots (feature/m4-browser-api)
- [x] M4-09 Extension metadata-only sync client and command integration (feature/m4-sync-client)

### M5 · Indexed mode, consent, embeddings, hybrid retrieval

- [x] M5-01 Consent model, consent records table, and consent.required enforcement (feature/m5-consent-enforcement)
- [x] M5-02 Extension consent preview webview and sent-bytes equality check (feature/m5-consent-preview)
- [x] M5-03 Redaction pipeline: extension client + server-side redaction re-check (feature/m5-redaction-pipeline)
- [x] M5-04 Code-aware chunker per language (TypeScript/JavaScript, Python) (feature/m5-chunker)
- [x] M5-05 Chunk storage, tsvector full-text, and trigram indices (feature/m5-chunk-storage)
- [x] M5-06 Embedding gateway slice: adapter interface, embedding spaces, embed_chunks job (feature/m5-embedding-gateway)
- [x] M5-07 Chunk embeddings with pgvector and per-space HNSW vector index (feature/m5-vector-index)
- [x] M5-08 Hybrid retrieval with fusion and context-pack builder (POST /api/v1/projects/{pid}/brain/search) (feature/m5-hybrid-retrieval)
- [x] M5-09 Retrieval evaluation harness and test dataset (feature/m5-eval-harness)
- [x] M5-10 Record retrieval baselines in docs/09 §9 (feature/m5-retrieval-baselines)
- [x] M5-11 Failure-state behavior: embedding provider outage degradation to keyword/symbol (feature/m5-outage-degradation)

### M6 · LLM gateway, adapters, model configuration

- [x] M6-01 LLM provider adapter interfaces, capabilities, and common request/response types (feature/m6-llm-interfaces)
- [x] M6-02 Fake LLM provider adapter with scripted responses and fault injection (feature/m6-fake-provider)
- [x] M6-03 Gateway YAML config loaders (providers.yaml, models.yaml, tasks.yaml) with Pydantic validation (feature/m6-gateway-config)
- [x] M6-04 First real generation adapter (Google Gemini via official SDK with free tier key support) (feature/m6-gemini-adapter)
- [x] M6-05 Second generation adapter (alternative provider, e.g. Groq/OpenAI, disabled until configured) (feature/m6-alternative-adapter)
- [x] M6-06 Gateway router with capability matching, fallback rules, and source-code-allowed privacy guard (feature/m6-gateway-router)
- [x] M6-07 Quotas, concurrency semaphores, and sliding-window rate limiting for LLM calls (feature/m6-llm-quotas)
- [x] M6-08 Usage recording (input/output tokens, latency, cost tracking) persisted to usage_records (feature/m6-usage-records)
- [x] M6-09 Structured-output schema repair and validation layer (feature/m6-output-repair)
- [x] M6-10 Versioned prompt template loader with untrusted context escaping (feature/m6-prompt-loader)
- [x] M6-11 LLM evaluation benchmark harness skeleton and prompt injection test corpus (feature/m6-llm-eval)

### M7 · LangGraph, CodeMate, AuthCheck

- [x] M7-01 State schema and checkpointer (PostgreSQL checkpointer, ADR-037, OQ-12) (feature/m7-state-checkpointer)
- [x] M7-02 Tools with scoped access: search_brain, get_symbol, get_file_range, get_relationships (feature/m7-agent-tools)
- [x] M7-03 Agent Manager graph and plan execution routing (feature/m7-manager-routing)
- [x] M7-04 CodeMate workflow nodes and citation validation (feature/m7-codemate)
- [x] M7-05 Guard resolution and structural route check (E2 deterministic confirmation) (feature/m7-guard-resolution)
- [x] M7-06 AuthCheck workflow nodes and evidence-constrained explanation (feature/m7-authcheck)
- [x] M7-07 Evidence verifier for grounding and citations (feature/m7-evidence-verifier)
- [x] M7-08 Job integration (ask_project, security_review) and SSE job event streaming (feature/m7-agent-jobs)
- [x] M7-09 Evaluation sets with baselines (answer-quality, faithfulness) (feature/m7-eval-baselines)
- [x] M7-10 Injection corpus run against graph workflows (docs/09 §12) (feature/m7-injection-run)

### M8 · Website app (conversation, findings, Brain explorer, jobs)

- [x] M8-01 Tokens and base UI components (Button, Badge, Card, Dialog, Skeleton, Input, Tabs) (feature/m8-components)
- [x] M8-02 Authentication and onboarding (S-02: Clerk SignIn/SignUp pages, onboarding wizard) (feature/m8-auth-onboarding)
- [x] M8-03 App shell, navigation, and workspace/project selection (S-03) (feature/m8-app-shell)
- [x] M8-04 Project overview with health score, coverage, and recent jobs (S-04) (feature/m8-project-overview)
- [x] M8-05 Findings list and detail views with evidence transitions (S-07, S-08) (feature/m8-findings-ui)
- [x] M8-06 Job center and SSE streaming event client with fallback (S-09) (feature/m8-jobs-sse)
- [x] M8-07 Conversation interface with citations and insufficient evidence banner (S-06) (feature/m8-conversation-ui)
- [x] M8-09 Usage dashboard, quotas, and extension devices (S-12) (feature/m8-usage-ui)
- [x] M8-10 Empty, error, loading states, accessibility audit, and keyboard navigation pass (feature/m8-a11y-polish)

### M9 · Sync modes, privacy controls, history, deletion

- [x] M9-01 Sync-mode transitions and consequences API & UI (switching to metadata_only purges chunks/embeddings) (feature/m9-sync-mode)
- [x] M9-02 Consent revoke flow (feature/m9-consent-revoke)
- [x] M9-03 Purge jobs and verification counts (feature/m9-purge-verification)
- [x] M9-04 Retention windows and scheduler cleanup (feature/m9-retention-windows)
- [x] M9-05 Snapshot history (feature/m9-snapshot-history)
- [x] M9-06 Audit endpoints (feature/m9-audit-endpoints)
- [x] M9-07 Extension sync log (feature/m9-extension-sync-log)

### M10 · Hardening, observability, capacity

- [x] M10-01 Complete authorization and tenant isolation test suite across all routes (feature/m10-authz-suite)
- [x] M10-02 Observability stack & OpenTelemetry traces (feature/m10-observability)
- [x] M10-03 Alerting thresholds, health checks, and kill switches (feature/m10-alerts)
- [x] M10-04 Free-profile load and capacity tests (feature/m10-load-tests)
- [x] M10-05 Queue soak and Redis failure drills (feature/m10-queue-drills)
- [x] M10-06 Database restore drill (feature/m10-restore-drill)
- [x] M10-07 Prompt-injection corpus expansion and abuse tests (feature/m10-injection-expansion)
- [x] M10-08 Operational runbooks (feature/m10-runbooks)
- [x] M10-09 Threat-model review and residual risk ledger update (feature/m10-threat-model)
- [x] M10-10 Staging promotion rehearsal (feature/m10-staging-rehearsal)

### M13 · UI polish and MVP release readiness

- [x] M13-01 Public homepage & navigation audit (sections 01-08, CTAs, data sync with common/data) (feature/m13-homepage-audit)
- [x] M13-02 Motion polish, custom cursor, and keyboard accessibility pass (feature/m13-motion-a11y)
- [x] M13-03 Authenticated app shell & screen states review (empty, error, loading, citations) (feature/m13-app-shell-polish)
- [x] M13-04 Extension packaging & marketplace release readiness (vsce package, pre-release) (feature/m13-extension-packaging)
- [ ] M13-05 Documentation consistency, broken link, and brand audit (docs/00 to 13) (feature/m13-docs-audit)
- [ ] M13-06 MVP release checklist, release notes, and known limitations ledger (feature/m13-release-checklist)

### M11 · Release 1.1 (GitHub, PR Intelligence, Review Intelligence)

### M12 · Releases 1.2–1.4 (Bug Memory, Living Docs, Mentor, Evaluation, Deployment Diagnosis)

Expand each M-item into task lines (from docs/11) when its phase starts; keep branch-per-slice.

---

_Last updated: 2026-10-15 by Antigravity on branch docs/p0-layout-and-adrs_
