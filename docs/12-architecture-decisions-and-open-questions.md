# 12 · Architecture Decisions and Open Questions

**Purpose.** This is the single register of architectural decisions for DevMind. Every other document refers to decisions here by ID (`ADR-0xx`) and to unresolved items by ID (`OQ-xx`). If a design choice changes materially, update the authoritative document **and** the matching record here in the same change.

**Status of this document.** Specification only. Nothing described here has been implemented or tested. Documents: [index](00-documentation-index.md) · [glossary](13-glossary-and-domain-terminology.md).

---

## 1. Status legend

| Status | Meaning | May an AI coding agent change it? |
|---|---|---|
| **Confirmed** | Fixed by the project owner (the master prompt or the source vision document). | No. Propose a change and wait for human approval. |
| **Recommended** | A default proposed by this documentation package. Reasonable, not yet validated. | Only by adding a superseding ADR and getting approval. |
| **Deferred** | Deliberately out of the first release. Design hooks may exist. | No. Do not build early. |
| **Open** | Needs research or an experiment before it can be decided. Names a default to use meanwhile. | Use the stated interim default; do not decide silently. |

Source of each decision is stated as **Source: prompt** (confirmed by the owner), **Source: vision** (the original `DevMind_Project_Document.md`), or **Source: design** (this package's recommendation).

## 2. Decision index

| ID | Decision | Status |
|---|---|---|
| ADR-001 | Website is the primary application; VS Code extension is a lightweight companion | Confirmed |
| ADR-002 | Frontend: Next.js + TypeScript, deployed separately from the backend | Confirmed |
| ADR-003 | Frontend rendering, data-fetching and styling strategy | Recommended |
| ADR-004 | Backend: Python + FastAPI modular monolith, Dockerized, on Render | Confirmed |
| ADR-005 | API service and worker service are separate deployables sharing one codebase | Confirmed |
| ADR-006 | LangGraph for agent workflows only; ordinary services for CRUD and deterministic work | Confirmed |
| ADR-007 | PostgreSQL (Neon) with pgvector as the system of record | Confirmed |
| ADR-008 | Redis-backed asynchronous job queue on managed, persistent Redis | Confirmed |
| ADR-009 | Celery as the initial worker implementation | Recommended |
| ADR-010 | Clerk for web authentication; authorization is implemented by DevMind | Confirmed |
| ADR-011 | DevMind-owned workspaces and memberships rather than Clerk Organizations | Recommended |
| ADR-012 | Extension authentication through DevMind-issued, scoped, revocable tokens | Recommended |
| ADR-013 | Cloudflare R2 for suitable artifacts only | Confirmed |
| ADR-014 | Resend for transactional email, introduced only when a feature needs it | Deferred |
| ADR-015 | GitHub: OAuth first, GitHub App evaluated for webhooks and automated PR review | Confirmed (direction) |
| ADR-016 | Provider-adapter LLM layer with configuration-driven routing | Confirmed |
| ADR-017 | Choice of generation provider(s) and exact models | **Open** |
| ADR-018 | Hybrid retrieval inside PostgreSQL (keyword + vector + metadata + symbols) | Confirmed |
| ADR-019 | Hosted embedding API, independent of generation provider; versioned embedding spaces | Confirmed (approach) / Recommended (mechanics) |
| ADR-020 | Code relationships stored in PostgreSQL tables; no graph database | Recommended |
| ADR-021 | Local-first scanning with selective cloud synchronization | Confirmed |
| ADR-022 | Two project sync modes: `metadata_only` and `indexed` | Recommended |
| ADR-023 | Static analysis stack; TypeScript/JavaScript and Python as first-class languages | Confirmed (languages) / Recommended (tools) |
| ADR-024 | Evidence levels E0–E3 and a mandatory verification step for findings | Recommended |
| ADR-025 | Tenant isolation by application-layer authorization, with optional RLS as defense in depth | Recommended |
| ADR-026 | Default data-retention periods | **Open** |
| ADR-027 | Model routing and fallback policy | Recommended |
| ADR-028 | Prompts are versioned files in the repository | Recommended |
| ADR-029 | Billing deferred; usage accounting and quotas included from the start | Confirmed |
| ADR-030 | Observability: structured logs, OpenTelemetry, error monitoring | Recommended (vendor Open) |
| ADR-031 | Managed Redis provider | **Open** |
| ADR-032 | Frontend hosting | Recommended |
| ADR-033 | Local manifest store technology in the extension | **Open** |
| ADR-034 | Live database connectivity from the extension | Deferred |
| ADR-035 | UI visual direction | Confirmed (direction) / Recommended (tokens) |
| ADR-036 | Python and TypeScript engineering toolchain | Recommended |
| ADR-037 | LangGraph checkpointing in PostgreSQL | Recommended |
| ADR-038 | MVP scope and breadth | **Open** (interim default stated) |
| ADR-039 | Repository folder names `client/`, `server/`, `extension/`, `common/` | Confirmed (owner, 2026-10-13) |
| ADR-040 | Screenshot-first build order (home page and extension shell before M1) | Confirmed (owner) |
| ADR-041 | Custom cursor and richer home-page motion (exception to the restraint in 08 §7) | Confirmed (owner) |
| ADR-042 | Tooling: pnpm workspaces for `client`, `extension`, `common`; `uv` for `server`; husky, lint-staged, commitlint; no Turborepo or Nx initially | Confirmed (owner) |
| ADR-043 | Test stack: Vitest, Playwright, pytest; REST/OpenAPI, no GraphQL | Confirmed (owner) |
| ADR-044 | Git workflow: `feature/*` and `fix/*` branches, Conventional Commits, squash merge by the owner, no direct pushes to `main` | Confirmed (owner) |
| ADR-045 | Shared single sources of truth in `common/data/` | Confirmed (owner) |
| ADR-046 | Free-only operating constraint and the **free deployment profile** | Confirmed (owner) |
| ADR-047 | Repository ownership: code in the public `Warish-Labs/DevMind`; personal `mdwarishansari/DevMind` is a showcase redirect | Confirmed (owner) |
| ADR-048 | Free LLM and embedding policy (fake provider by default; free tiers only with synthetic or public data) | Confirmed (owner) |
| ADR-049 | Domain plan under `warishlabs.in` (`devmind.` for the site, `api.devmind.` for the API) | Recommended |

---

## 3. Decision records

### ADR-001 · Website primary, extension companion
- **Status:** Confirmed. **Source:** prompt.
- **Context:** The vision describes one continuous intelligence over a project. A full chat and project-management experience in two places would double the work.
- **Decision:** All AI conversations, agent workflows, project management and comprehensive reports live on the website. The VS Code extension scans locally, shows diagnostics and structure, controls synchronization, and links to the website.
- **Rationale:** One place for the rich experience; the extension stays small and fast.
- **Alternatives:** Extension-first with chat (rejected for v1: duplicated UI, harder privacy story); web only (rejected: loses local scanning and the no-silent-upload privacy model).
- **Trade-offs:** Developers switch to the browser for deep conversations.
- **Consequences:** The extension has no chat view in v1. The handoff is defined in [06](06-vscode-extension-and-local-scanning.md) §14.
- **Revisit when:** User research shows the browser switch is the main drop-off point.

### ADR-002 · Next.js + TypeScript frontend, separate deploy
- **Status:** Confirmed. **Source:** prompt.
- **Decision:** Next.js (App Router) with TypeScript, deployed independently of the backend.
- **Rationale:** Matches the owner's stack; strong support for streaming UI and server rendering for public pages.
- **Alternatives:** Vite SPA (weaker SEO for the public site); Remix. Not pursued.
- **Consequences:** Frontend and backend meet only through the versioned HTTP API ([03](03-data-model-and-api.md)).
- **Revisit when:** Never expected during v1.

### ADR-003 · Rendering, data fetching and styling
- **Status:** Recommended. **Source:** design.
- **Decision:** Public marketing pages are statically rendered. The authenticated shell and static project metadata use Server Components that call the API with the user's Clerk token. Interactive and live surfaces (chat, job progress, findings filters) are client components using TanStack Query. Streaming uses Server-Sent Events from the API. Types come from the backend OpenAPI schema through a generated client. Styling uses Tailwind CSS driven by CSS-variable design tokens from [08](08-ui-ux-design-specification.md).
- **Rationale:** Each surface gets the cheapest pattern that meets its freshness need. Generated types prevent frontend/backend drift.
- **Alternatives:** Browser-only SPA data layer; a Next.js route-handler proxy (BFF) in front of FastAPI.
- **Trade-offs:** Direct browser-to-API calls need strict CORS and bearer tokens; a BFF would hide the backend URL but add a hop and complicate SSE.
- **Consequences:** CORS allowlist per environment ([10](10-deployment-and-operations.md)).
- **Revisit when:** A requirement appears that needs cookies, server-side secrets per request, or request shaping.

### ADR-004 · FastAPI modular monolith on Render with Docker
- **Status:** Confirmed. **Source:** prompt.
- **Decision:** One Python codebase, modular by layer (API, domain services, persistence, brain, analysis, LLM, orchestration, integrations, workers). Docker is part of the deployment workflow. Render hosts it.
- **Rationale:** Smallest operational surface that supports the product.
- **Alternatives:** Microservices per agent (rejected: premature, high operational cost).
- **Consequences:** Module boundaries are enforced by import rules ([02](02-system-architecture.md) §5).

### ADR-005 · API and worker are separate deployables
- **Status:** Confirmed. **Source:** prompt.
- **Decision:** The same image runs as a web service (API) and as one or more background worker services with a different start command. No single container runs both.
- **Rationale:** Independent scaling, restarts and failure isolation; long scans must not starve request handling.
- **Consequences:** Shared code must not assume an in-process queue. Health checks differ per service ([10](10-deployment-and-operations.md)).

### ADR-006 · LangGraph for agents, services for everything else
- **Status:** Confirmed. **Source:** prompt.
- **Decision:** Use LangGraph for multi-step reasoning workflows that need shared state, branching, checkpointing or human approval. Use plain Python services for CRUD, ingestion, scoring and verification.
- **Rationale:** Avoids hiding deterministic logic inside graphs where it is harder to test.
- **Consequences:** [05](05-agents-and-llm-workflows.md) §3 lists which jobs are graph workflows and which are not.

### ADR-007 · PostgreSQL on Neon with pgvector
- **Status:** Confirmed. **Source:** prompt.
- **Decision:** All structured data and vectors live in PostgreSQL. Alembic manages migrations. Pooled connections for the API, direct connections for migrations and anything incompatible with transaction pooling.
- **Alternatives:** A separate vector database (rejected unless measurements demand it).
- **Trade-offs:** Vector search at large scale may eventually need tuning or partitioning ([04](04-project-brain-and-rag.md) §9).
- **Revisit when:** Measured recall or latency requirements cannot be met in PostgreSQL. See OQ-12 for pooling caveats.

### ADR-008 · Redis-backed queue on managed Redis
- **Status:** Confirmed. **Source:** prompt.
- **Decision:** Asynchronous work goes through a Redis-backed queue. Redis must be a managed or otherwise persistent service, never an undocumented process inside an application container.
- **Consequences:** PostgreSQL job rows are the source of truth for job state; Redis is the transport. Losing Redis must not lose job intent ([02](02-system-architecture.md) §10).

### ADR-009 · Celery workers
- **Status:** Recommended (prompt names Celery as the initial recommendation). **Source:** prompt/design.
- **Decision:** Celery with `acks_late`, prefetch of 1, explicit time limits, and named queues (`ingest`, `analysis`, `embeddings`, `default`).
- **Rationale:** Mature, supports retries, time limits and routing.
- **Alternatives:** ARQ or RQ (simpler, fewer features); Dramatiq; Temporal (powerful, heavier). 
- **Trade-offs:** Celery on Redis has a visibility-timeout redelivery behavior that must be configured above the longest task ([10](10-deployment-and-operations.md) §9).
- **Revisit when:** Workflow durability needs exceed what job rows plus LangGraph checkpoints provide.

### ADR-010 · Clerk authentication, DevMind authorization
- **Status:** Confirmed. **Source:** prompt.
- **Decision:** Clerk authenticates web users. The API verifies Clerk session tokens server-side on every request. Every sensitive operation is authorized by DevMind against workspace and project membership. Authentication never implies access to a project.
- **Consequences:** Every route declares a required permission; a test fails if one does not ([09](09-testing-and-quality-strategy.md) §6).

### ADR-011 · Own workspaces rather than Clerk Organizations
- **Status:** Recommended. **Source:** design.
- **Decision:** `workspaces`, `workspace_memberships` and project-level membership are DevMind tables. Clerk supplies identity only.
- **Rationale:** Authorization data must sit next to the data it protects and be queryable in joins; avoids coupling to a vendor feature set.
- **Trade-offs:** Invitation and membership UI must be built.
- **Revisit when:** Enterprise SSO or SCIM becomes a requirement.

### ADR-012 · Extension tokens issued by DevMind
- **Status:** Recommended. **Source:** design. See OQ-08.
- **Decision:** The extension signs the user in through the browser (custom URI handler with PKCE and `state`). The backend then issues an opaque, scoped, short-lived access token and a rotating refresh token, stored hashed, revocable per extension registration. The extension stores them in VS Code `SecretStorage`.
- **Rationale:** Extension-facing APIs need narrower scopes than a full web session, and tokens must be revocable per installation.
- **Alternatives:** Reusing Clerk session tokens in the extension (broader scope, harder revocation); personal access tokens pasted by the user (weaker UX and storage hygiene).
- **Revisit when:** Clerk offers a mechanism that meets scoping and revocation needs without custom code.

### ADR-013 · Cloudflare R2 for suitable artifacts
- **Status:** Confirmed. **Source:** prompt.
- **Decision:** R2 stores exported reports, uploaded documents and uploaded logs. PostgreSQL stays the source of truth for metadata. No relational data goes to R2.
- **Consequences:** Objects are untrusted on upload and are served only as attachments through short-lived signed URLs ([07](07-security-privacy-and-threat-model.md) §13).

### ADR-014 · Resend
- **Status:** Deferred. **Source:** prompt.
- **Decision:** Not part of the MVP. Introduce for workspace invitations and notifications when a feature requires it.

### ADR-015 · GitHub integration path
- **Status:** Confirmed (direction). **Source:** prompt. Details Recommended. See OQ-11.
- **Decision:** Start with GitHub OAuth for repository and pull-request reads. Evaluate a GitHub App when automated PR reviews, webhooks or CI status are needed. OAuth alone is never assumed to grant every needed permission.
- **Trade-offs:** OAuth app scopes for private repositories are coarse; a GitHub App offers fine-grained permissions and webhooks but requires more setup.
- **Consequences:** `github_connections` is modeled to hold either credential kind ([03](03-data-model-and-api.md)).

### ADR-016 · Provider-adapter LLM layer
- **Status:** Confirmed. **Source:** prompt.
- **Decision:** Agents call an internal LLM gateway by **task name**, never by provider or model. Providers, models and task routing live in YAML ([05](05-agents-and-llm-workflows.md) §11). Credentials come only from environment or a secret manager.
- **Alternatives:** Direct provider SDK calls in agents (rejected); adopting a third-party gateway library wholesale (evaluate, see §5 of doc 05).

### ADR-017 · Generation provider and models
- **Status:** **Open.** **Source:** prompt.
- **Context:** The master prompt explicitly leaves provider and model unresolved.
- **Decision:** Keep model identifiers as configuration. Select by running the benchmark in [05](05-agents-and-llm-workflows.md) §16 against a defined evaluation set.
- **Interim default:** Ship configuration with placeholder identifiers that fail startup validation until a real, evaluated model is written in. No model name appears in code.
- **Revisit when:** Evaluation results exist (record them here).

### ADR-018 · Hybrid retrieval in PostgreSQL
- **Status:** Confirmed. **Source:** prompt.
- **Decision:** Combine keyword search (PostgreSQL full-text plus trigram on identifiers), vector similarity (pgvector), metadata filters, symbol and path lookups, and relationship expansion. Fuse ranked lists with reciprocal rank fusion as the starting method.
- **Consequences:** See [04](04-project-brain-and-rag.md) §8.

### ADR-019 · Hosted embeddings and embedding spaces
- **Status:** Confirmed (hosted, independent of generation provider); mechanics Recommended.
- **Decision:** An `embedding_spaces` record identifies provider, model, dimension and status. Changing model creates a new space and a re-embedding job; the old space is retired only after validation on the retrieval evaluation set.
- **Open:** Exact embedding model and dimension (OQ-02).

### ADR-020 · Relationships in PostgreSQL, no graph database
- **Status:** Recommended. **Source:** design.
- **Decision:** `code_symbols` and `code_relationships` tables, traversed with bounded recursive queries (depth limit ≤ 3 by default).
- **Alternatives:** Neo4j or another graph database.
- **Rationale:** Relationship queries needed (callers, callees, importers, route-to-handler) are shallow; a second datastore adds cost, sync problems and tenant-isolation surface.
- **Revisit when:** Required traversals regularly exceed depth 4 or measured query latency fails its target.

### ADR-021 · Local-first scanning, selective synchronization
- **Status:** Confirmed. **Source:** prompt.
- **Decision:** The extension scans locally first. Only task-specific, consented, redacted source snippets leave the machine. No silent whole-repository upload.

### ADR-022 · Sync modes
- **Status:** Recommended. **Source:** design. See OQ-06.
- **Decision:** Each project has a `sync_mode`: `metadata_only` (paths, hashes, languages, symbol signatures, relationships, finding records without code bodies) or `indexed` (consented, redacted chunks stored and embedded for persistent retrieval). Default for new projects: `metadata_only`.
- **Rationale:** Website chat needs retrievable code context; the confirmed privacy model needs explicit consent before storing it. Two modes make this tradeoff explicit and reversible.
- **Consequences:** In `metadata_only`, code-level answers need the user to attach snippets to a request.

### ADR-023 · Static analysis stack and languages
- **Status:** Confirmed (TypeScript/JavaScript and Python first); tool choices Recommended. See OQ-07, OQ-17.
- **Decision:** Tree-sitter for parsing; custom DevMind rules for authentication/authorization structure; established scanners as optional adapters (secret scanning, dependency audit, a pattern engine); LLM reasoning only after deterministic evidence exists or for explanations.
- **Trade-offs:** Rule licensing for third-party pattern engines must be checked; DevMind-authored rules avoid that.
- **Consequences:** A language support table ([06](06-vscode-extension-and-local-scanning.md) §7) states exactly what each language gets.

### ADR-024 · Evidence levels and verification
- **Status:** Recommended. **Source:** design (implements vision §8.1).
- **Decision:** Findings carry an evidence level E0–E3 and a confidence. A deterministic verifier checks every draft finding's evidence against current file versions. LLM-only claims with no verifiable evidence are not persisted as findings.
- **Consequences:** UI states "possible" vs "verified" explicitly. Nothing is described as proven unless E3 exists (not in MVP).

### ADR-025 · Tenant isolation
- **Status:** Recommended. **Source:** design. See OQ-09.
- **Decision:** All repository-layer queries require an `AuthContext`; every tenant table carries `workspace_id`. PostgreSQL row-level security is added as defense in depth once the application layer is stable.
- **Trade-offs:** RLS with pooled connections needs `SET LOCAL` per transaction and adds testing burden.

### ADR-026 · Retention defaults
- **Status:** **Open.** See OQ-03.
- **Interim default:** Retention is a per-workspace setting with conservative defaults proposed in [07](07-security-privacy-and-threat-model.md) §9. The numbers there are proposals, not commitments.

### ADR-027 · Routing and fallback policy
- **Status:** Recommended. **Source:** design.
- **Decision:** Each task names a primary model and an ordered fallback list. A fallback is allowed only if it satisfies the task's required capabilities and data policy. Fallbacks trigger on timeouts, rate limits and provider errors, never on invalid output after repair attempts, which is a hard failure.

### ADR-028 · Versioned prompts
- **Status:** Recommended. **Decision:** Prompts are files under `server/app/llm/prompts/` with a version header, loaded by task, recorded in `agent_runs` so a result can be tied to a prompt version.

### ADR-029 · Billing deferred, usage accounting included
- **Status:** Confirmed. **Source:** prompt.
- **Decision:** No payment system in v1. `usage_records` and configurable `workspace_quotas` exist from the start to bound inference spend.

### ADR-030 · Observability
- **Status:** Recommended (vendor Open, OQ-15).
- **Decision:** Structured JSON logs, OpenTelemetry traces and metrics, an error-monitoring service. Prompt and source payloads are excluded from logs and traces by default.

### ADR-031 · Redis provider
- **Status:** **Open.** See OQ-04. **Interim default:** Render's managed Key Value store, provided the chosen plan persists data across restarts. Per-request-priced Redis services need a usage test with Celery before adoption.

### ADR-032 · Frontend hosting
- **Status:** Recommended: Vercel (matches the owner's existing stack). See OQ-14. Any host that runs Next.js and supports streaming responses is acceptable.

### ADR-033 · Extension manifest store
- **Status:** **Open.** See OQ-05. **Interim default:** SQLite compiled to WebAssembly, stored in the workspace storage folder provided by VS Code (never inside the repository).

### ADR-034 · Live database connectivity
- **Status:** Deferred. A direct connection to a user database is a separate capability requiring its own specification, threat model and consent flow. Until then, database information comes only from project files ([06](06-vscode-extension-and-local-scanning.md) §10).

### ADR-035 · UI direction
- **Status:** Confirmed (dark, code-native, green and blue accents, selective glass); concrete tokens Recommended and derived in [08](08-ui-ux-design-specification.md).

### ADR-036 · Toolchain
- **Status:** Recommended. Python: `uv`, `ruff`, `pyright` (or `mypy`), `pytest`, SQLAlchemy 2.x, Alembic, Pydantic v2. TypeScript: `pnpm`, ESLint, strict `tsconfig`, Vitest, Playwright. Versions are pinned at repository setup, after checking current releases.

### ADR-037 · LangGraph checkpointing
- **Status:** Recommended. Use the LangGraph PostgreSQL checkpointer, keyed by agent run, in its own schema. See OQ-12 for Neon pooling compatibility.

### ADR-038 · MVP scope and breadth
- **Status:** **Open.** See OQ-10. **Interim default:** MVP = Code Intelligence and a focused Security Intelligence on top of the Project Brain, extension and website. The other seven capabilities follow in [11](11-mvp-and-implementation-roadmap.md) releases.

### ADR-039 · Repository folder names
- **Status:** Confirmed (owner, 2026-10-13). **Decision:** the four code folders are `client/` (Next.js), `server/` (FastAPI, Celery), `extension/` (VS Code), `common/` (shared TypeScript). They replace `frontend/`, `backend/`, `vscode-extension/`, `packages/` in all documents. Root-only folders: `docs/`, `brand/`, `evals/`, `infra/`, `scripts/`, `.github/`, `.agents/`; `render.yaml` stays at the root because Render looks for it there. **Consequences:** layout in [02](02-system-architecture.md) §5; Docker build context for Render is `./server`; Vercel root directory is `client` with "include source files outside the root directory" enabled because `client` imports `common`.

### ADR-040 · Screenshot-first build order
- **Status:** Confirmed (owner). **Decision:** build the public home page (phase S1) and the extension UI shell with fixture data (phase S2) before milestone M1; then follow [11](11-mvp-and-implementation-roadmap.md). Everything shown is labeled example/fixture data. **Consequences:** M13 becomes polish and audit for the home page; `FixtureFindingsSource` is replaced by the real scanner in M3 behind the same interface.

### ADR-041 · Custom cursor and richer home-page motion
- **Status:** Confirmed (owner). **Decision:** the home page may use a theme-matched custom cursor and richer, choreographed motion, as an explicit exception to the restraint in [08](08-ui-ux-design-specification.md) §7. Safeguards: fine pointers only, off with reduced motion or via a Preferences toggle, native cursor fallback, `aria-hidden`, no scroll-jacking libraries, compositor-only animation. **Revisit when:** accessibility or performance testing shows harm.

### ADR-042 · Tooling
- **Status:** Confirmed (owner). pnpm workspaces (`client`, `extension`, `common`), `uv` (`server`), husky + lint-staged + commitlint, a single `scripts/test-all.mjs` runner. No Turborepo or Nx until a measured need. Supply-chain settings (`minimumReleaseAge`, `blockExoticSubdeps`, `trustPolicy`) per the prompt; exact keys verified against current pnpm docs.

### ADR-043 · Test stack and API style
- **Status:** Confirmed (owner). Vitest (Jest-compatible API, Vite-native), Playwright, pytest. The API is REST with an OpenAPI schema; there is no GraphQL. Supersedes nothing; refines ADR-036.

### ADR-044 · Git workflow
- **Status:** Confirmed (owner). Branches `feature/*`, `fix/*` (also `docs/*`, `chore/*`); Conventional Commits; one commit per task; the owner squash-merges PRs after the required check `ci-gate` is green; merged branches are deleted; no direct pushes to `main` (repository ruleset plus a local pre-push hook plus a `main-guard` workflow that flags pushes to `main` that did not come from a PR).

### ADR-045 · Shared single sources of truth
- **Status:** Confirmed (owner). `common/data/{rule-catalog,release-status,privacy-ledger,capabilities,walkthrough}.json` feed the home page, the extension and server tests so that docs, UI and scanner cannot drift. Matches [08](08-ui-ux-design-specification.md) §8.5 and §9.

### ADR-046 · Free-only constraint and free deployment profile
- **Status:** Confirmed (owner, 2026-10-13). **Context:** the owner can use only free tiers. Facts relevant here, checked 2026-10-13 (see §5; several from secondary sources): Render free web service has 512 MB RAM, sleeps after about 15 minutes without traffic and takes about a minute to wake, with 750 instance hours per workspace per month; Render has **no free background worker** and allows one free Key Value instance (25 MB, no persistence) per workspace; Neon Free suspends compute after about five minutes idle and has a small per-project storage cap (0.5 GB on the pricing page, 1 GB in a 2026-10-02 changelog entry; plan for 0.5 GB); Clerk Free includes a generous monthly-active-user allowance and a custom domain; Vercel Hobby is for personal, non-commercial use and can deploy organization repositories only if they are public; GitHub Free gives rulesets, environment protection and unlimited Actions minutes only on public repositories.
- **Decision:** keep the target architecture ([02](02-system-architecture.md); ADR-005, ADR-008, ADR-009) for a funded profile, and define the **free profile** actually deployed now: (1) client on Vercel Hobby; (2) **one** Render free web service running `DEVMIND_RUN_MODE=all`, a small launcher that starts uvicorn and an embedded Celery worker with beat (`--pool=solo`, concurrency 1) in one container and exits if either dies; the code keeps API, worker and scheduler as separate entry points and `DEVMIND_RUN_MODE=api|worker|scheduler` remain supported; (3) Render free Key Value as the broker and rate-limit store, treated as disposable because PostgreSQL holds job state; (4) Neon Free with the pooled endpoint; (5) migrations run at container start under an advisory lock (the Render pre-deploy command is not relied on); (6) clients tolerate a sleeping server (cold-start retry and "server waking" states in the website and extension, SSE reconnect, a sweep at startup that re-enqueues stranded jobs); (7) quotas sized for the storage limit (embedding dimension at most 768 or `halfvec`, per-project chunk budget measured, not guessed); (8) no paid service is added; a task that appears to need one stops and proposes a free alternative.
- **Alternatives considered:** a Postgres-backed queue instead of Celery (valid fallback if the 512 MB budget is exceeded; requires its own ADR); a keep-alive pinger (consumes the 750-hour pool and may breach fair use; off by default); Cloudflare Pages or Netlify instead of Vercel if the project becomes commercial.
- **Trade-offs:** no always-on worker; jobs run only while the service is awake; cold starts; tight memory; free-tier terms can change.
- **Consequences:** [10](10-deployment-and-operations.md) §22; `render.yaml` defines one free web service plus one free Key Value; docs in [06](06-vscode-extension-and-local-scanning.md) §14 gain the "server waking" behavior. **Revisit when:** funds exist, memory measurement fails, or a vendor changes its free tier.

### ADR-047 · Repository ownership and visibility
- **Status:** Confirmed (owner, 2026-10-13). The real repository is the public `github.com/Warish-Labs/DevMind`, where code, CI, deployments and releases live. The personal `github.com/mdwarishansari/DevMind` is a **showcase redirect** (detailed README, screenshots, live link, pointer to the source), the same pattern as ForgeFlow-AI. **Rationale:** Vercel Hobby deploys organization repositories only when public; rulesets, environment protection, secret scanning and unlimited Actions minutes are free only for public repositories; doing the work in the final home avoids migrating CI secrets, host integrations, OAuth callbacks, webhooks and history later. **Consequences:** no secrets, no private data and no user source in the repository ever; `BRAIN.md` and logs stay clean; the commit author email must belong to the GitHub account that owns the Vercel Hobby team; a license decision is still open (no license means all rights reserved).

### ADR-048 · Free LLM and embedding policy
- **Status:** Confirmed (owner). The built-in fake provider is the default for tests, CI and demos. Free tiers (for example Google AI Studio's) may be used for development with **synthetic fixtures or public code only**, because free tiers can use submitted content to improve products and have unpublished or changing rate limits. Private code is not sent to any provider until its terms are reviewed ([07](07-security-privacy-and-threat-model.md) §6, OQ-03). Model names stay in configuration; selection follows measurement ([05](05-agents-and-llm-workflows.md) §16).

### ADR-049 · Domain plan
- **Status:** Recommended. The owner controls `warishlabs.in` (verified, with Resend). Proposed names: `devmind.warishlabs.in` (client on Vercel), `api.devmind.warishlabs.in` (server on Render), mail from a `devmind` subdomain. Clerk's production instance uses the site domain. Revisit if the project gets its own domain.

---

## 4. Open questions

| ID | Question | Why it matters | How to resolve | Interim default |
|---|---|---|---|---|
| OQ-01 | Which generation provider(s) and models? (same as ADR-017) | Quality, cost, data terms | Benchmark in doc 05 §16 | Placeholders that fail validation |
| OQ-02 | Which embedding model and dimension? | Vector column dimension, retrieval quality, cost | Retrieval evaluation set, doc 04 §14 | One configurable space; dimension read from config |
| OQ-03 | Retention defaults and provider data terms | Privacy promise to users | Review each candidate provider's current terms; legal read | Doc 07 §9 proposals; providers flagged `terms_reviewed: false` cannot be enabled in production |
| OQ-04 | Which managed Redis? | Persistence, cost model under Celery polling | Confirmed: Upstash Redis with standard TLS connection string (`rediss://`) | Upstash Redis |
| OQ-05 | Extension manifest store technology | Packaging, performance | Prototype with 10k and 50k files | WASM SQLite |
| OQ-06 | Default sync mode and whether `metadata_only` is useful enough | Core product value vs privacy | Usability test with 5 real projects | `metadata_only` default, easy opt-in to `indexed` |
| OQ-07 | Pattern-engine rule licensing and whether to rely only on custom rules | Legal and maintenance | Read current license terms before bundling any third-party rules | DevMind-authored rules only |
| OQ-08 | Can Clerk alone satisfy extension auth scoping/revocation? | Avoid custom token code | Review current Clerk docs | DevMind-issued tokens (ADR-012) |
| OQ-09 | Adopt PostgreSQL RLS, and when? | Defense in depth vs complexity | Prototype with pooled Neon connections | App-layer authorization first |
| OQ-10 | MVP breadth for the academic demonstration | Viva expectations vs engineering focus | Decide with supervisor; see doc 11 §3 | Depth on two capabilities |
| OQ-11 | When to move from OAuth to a GitHub App | Webhooks, permissions | Review current GitHub permission model | OAuth read-only first |
| OQ-12 | Does the LangGraph PostgreSQL checkpointer work through Neon's pooled endpoint? | Workflow resume | Test; otherwise use direct endpoint for workers | Workers use direct connection |
| OQ-13 | Does SSE survive the hosting proxy idle timeouts? | Streaming UX | Test with keep-alive comments | Poll fallback |
| OQ-14 | Frontend host | Streaming support, cost | Deploy a probe | Vercel |
| OQ-15 | Error-monitoring vendor | Privacy of payloads | Compare scrubbing controls | Choose before M10 |
| OQ-16 | Font licensing and self-hosting for the chosen typefaces | Legal | Read licenses at adoption | Self-host, with system fallbacks |
| OQ-17 | Tree-sitter grammar packaging as WASM in the extension; grammar version pinning | Bundle size, parse accuracy | Prototype | Pin versions, load lazily |
| OQ-18 | How is the "Functionality" dimension of project health measured? | The vision lists it; it cannot be inferred from code alone | Define against the project's declared feature checklist and test results | Derived from user-declared features and CI results; labeled low-confidence otherwise |

## 5. Vendor verification register

Most vendor-specific facts in this package were not verified when it was drafted (**2026-10-10**). The rows marked 2026-10-13 below were checked once on that date, in part from secondary sources, and must be re-checked when a milestone depends on them. Before implementing any item below, read the vendor's current documentation and record the date and result in this table.

| Area | Facts to verify | Verified on | Result |
|---|---|---|---|
| GitHub plans (free) | Rulesets, environment protection, Actions minutes on private vs public repositories | 2026-10-13 | Public repositories get the full free feature set; private repositories on the Free plan do not get enforceable branch protection (GitHub docs and plan summaries) |
| Render free | Web service limits, workers, Key Value | 2026-10-13 | One free web service per workload (512 MB, sleeps after about 15 minutes, 750 hours per workspace), no free background worker, one free Key Value (25 MB, no persistence) per workspace; pre-deploy command on free unverified, so not relied on (render.com/docs/free and secondary sources) |
| Neon Free | Storage, compute, suspend | 2026-10-13 | 0.5 GB per project on the pricing page, 1 GB in a 2026-10-02 changelog entry (conflict; plan for 0.5 GB); compute suspends after about 5 minutes idle; pgvector available |
| Clerk Free | Active-user allowance, custom domain | 2026-10-13 | Sources disagree on the exact allowance (10,000 to 50,000 monthly active users); custom domain included; confirm on clerk.com/pricing |
| Vercel Hobby | Commercial use, organization repositories | 2026-10-13 | Personal, non-commercial use only; organization-owned repositories deployable only if public; commit author must be the Hobby team owner (Vercel docs and forum threads) |
| Google AI Studio free tier | Rate limits, data use | 2026-10-13 | Limits are shown per account in AI Studio and change; free-tier content may be used to improve products (secondary sources; confirm in the Gemini API terms) |
| Visual Studio Marketplace publishing | Token types | 2026-10-13 | VS Code docs state global Azure DevOps PATs retire on 2026-12-01; `vsce publish --azure-credential` exists |
| Antigravity | Rules and AGENTS.md support | 2026-10-13 | AGENTS.md is read by recent Antigravity versions; rules files have a 12,000-character limit; workspace rules folder name differs between sources (`.agents/rules` vs `.agent/rules`), so verify in the app |
| Node.js | LTS status | 2026-10-13 | Node 24 is Active LTS; Node 26 is due to enter LTS in late October 2026 (secondary sources; confirm on nodejs.org) |
| Neon | Pooled vs direct endpoints, pgvector version, backup/restore window | not yet | |
| pgvector | HNSW options, iterative scan support for filtered queries | not yet | |
| Render | Pre-deploy commands, health check behavior, worker service and Key Value persistence by plan, graceful-shutdown timeout, SSE idle limits | not yet | |
| Clerk | Token claims, authorized-party checks, webhooks, any extension or device flow | not yet | |
| GitHub | OAuth scopes for private repos, GitHub App permissions, webhook signature scheme, rate limits | not yet | |
| Cloudflare R2 | Presigned URL behavior, encryption at rest, lifecycle rules | not yet | |
| LangGraph | Current names and behavior of interrupt/resume, Postgres checkpointer, parallel `Send` | not yet | |
| LLM providers | Model identifiers, capabilities, rate limits, data retention and training terms | not yet | |
| Celery | Redis broker visibility-timeout semantics, current recommended settings | not yet | |

## 6. ADR template for future changes

```markdown
### ADR-0NN · Title
- **Status:** Proposed | Confirmed | Recommended | Deferred | Open | Superseded by ADR-0MM
- **Date / author:**
- **Context:**
- **Decision:**
- **Rationale:**
- **Alternatives considered:**
- **Trade-offs:**
- **Consequences:** (documents and code areas that must change)
- **Revisit when:**
```

Rules: a Confirmed decision changes only with explicit human approval. Superseded records stay in this file with a pointer to their replacement.
