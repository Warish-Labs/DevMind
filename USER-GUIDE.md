# DevMind · User Guide & Platform Walkthrough

Welcome to **DevMind** — the agentic software engineering platform built around a continuous, shared **Project Brain**.

DevMind connects your local development workflow in **VS Code** with a centralized, evidence-grounded intelligence platform on the **Web**, giving both human developers and autonomous AI agents a continuously synchronized mental model of your codebase.

---

## Table of Contents

1. [Core Principles & Architecture](#1-core-principles-architecture)
2. [Quickstart: Access & Authentication](#2-quickstart-access-authentication)
3. [Managing Workspaces & Projects](#3-managing-workspaces-projects)
4. [VS Code Extension Setup & Usage](#4-vs-code-extension-setup-usage)
5. [Local Scanning & Privacy-First Sync](#5-local-scanning-privacy-first-sync)
6. [Web Platform Capabilities](#6-web-platform-capabilities)
   - [Project Brain & Symbol Knowledge Graph](#61-project-brain-symbol-knowledge-graph)
   - [Project Mentor & Topological Task DAGs](#62-project-mentor-topological-task-dags)
   - [Living Documentation (DocsAlive)](#63-living-documentation-docsalive)
   - [Bug Memory & Resolution Retrieval](#64-bug-memory-resolution-retrieval)
   - [Deployment Diagnosis & Incident Triage](#65-deployment-diagnosis-incident-triage)
   - [PR Intelligence & Review Rules](#66-pr-intelligence-review-rules)
7. [Environment Variables & Configuration](#7-environment-variables-configuration)
8. [Troubleshooting & Frequently Asked Questions](#8-troubleshooting-frequently-asked-questions)

---

## 1. Core Principles & Architecture

DevMind is built upon four non-negotiable architectural foundations:

1. **Local-First & Zero Egress Without Consent (ADR-022, ADR-047)**:
   Your source code stays on your developer machine. The VS Code companion parses files locally using tree-sitter ASTs. No source code or chunk leaves your machine without an explicit, interactive **Consent Preview**.
2. **Continuous Shared Project Brain (ADR-001, ADR-002)**:
   Instead of re-reading raw repositories on every AI request, DevMind maintains a synchronized knowledge graph of symbols, call hierarchies, AST dependencies, and semantic embeddings in PostgreSQL + pgvector.
3. **Resolvable Evidence Standard (E0–E3)**:
   Every finding produced by DevMind must provide verifiable evidence:
   - `E0 · Syntactic`: AST pattern match (e.g. missing middleware check).
   - `E1 · Structural`: Call-graph / control-flow connection across files.
   - `E2 · Semantic / Invariant`: Grounded dynamic trace or model verification.
   - _(Never speculative or hallucinatory)._
4. **Zero Live Database Connections (ADR-034)**:
   DevMind statically discovers schemas, relationships, and models directly from source code and migrations (Prisma, SQLAlchemy, Alembic). It never opens live TCP connections to production databases.

---

## 2. Quickstart: Access & Authentication

### 2.1 Web Platform Access

- **Production URL**: [https://devmind.warishlabs.in](https://devmind.warishlabs.in)
- **Local Dev URL**: `http://localhost:3000`

### 2.2 Sign Up & Sign In with Clerk

1. Click **Sign In** or **Sign Up** in the top navigation bar.
2. Authenticate using your preferred Clerk provider:
   - **Google Workspace** / OAuth
   - **GitHub** (recommended for seamless PR analysis)
   - **Email Magic Link / Password**
3. Upon first sign-in, you are directed to `/onboarding` to initialize your primary workspace and developer profile.

> [!NOTE]
> **Developer Offline Bypass**: If evaluating in an air-gapped or local environment without Clerk credentials configured, DevMind automatically presents a fallback **Developer Access** form allowing instant local progression.

---

## 3. Managing Workspaces & Projects

### 3.1 Workspaces (Multi-Tenant Isolation)

All DevMind data is strictly isolated by `workspace_id`.

- Navigate to `/workspaces` to inspect your active workspaces.
- To create a new workspace: Click **Create Workspace**, provide a name and slug (e.g. `engineering-core`).
- Workspace roles follow role-based access control (RBAC): `Owner`, `Admin`, `Member`, `Viewer`.

### 3.2 Projects

A workspace contains one or more **Projects** (each corresponding to a code repository or microservice).

- Navigate to your workspace and select **Create Project**.
- Copy the generated **Project ID (UUIDv7)** — you will link your VS Code workspace to this Project ID.

---

## 4. VS Code Extension Setup & Usage

The DevMind Companion extension (`devmind-vscode`) brings local AST scanning, architectural views, and consented sync into your editor.

### 4.1 Installing the Extension Package (.vsix)

The extension package is generated in the repository under `extension/dist/devmind-vscode.vsix`.

**To install via command line:**

```bash
code --install-extension /path/to/DevMind/extension/dist/devmind-vscode.vsix
```

**To install via VS Code UI:**

1. Open VS Code.
2. Open the Extensions sidebar (`Ctrl+Shift+X` / `Cmd+Shift+X`).
3. Click the `...` (Views and More Actions) menu in the top right of the Extensions view.
4. Select **Install from VSIX...**.
5. Choose `extension/dist/devmind-vscode.vsix`.

### 4.2 Configuring Extension Settings

Open VS Code Settings (`Ctrl+,` or `Cmd+,`) and search for `DevMind`:

- `devmind.apiBaseUrl`: Base URL for the DevMind API (default: `https://api.devmind.warishlabs.in/api/v1` or `http://localhost:8000/api/v1` for local dev).
- `devmind.projectId`: Paste your Project UUID here.
- `devmind.syncMode`: Choose between `metadata_only` (default), `indexed`, or `disabled`.
- `devmind.fixtureMode`: Set to `true` if operating offline without a server.

---

## 5. Local Scanning & Privacy-First Sync

### 5.1 Scanning Your Workspace

1. Click the **DevMind** icon on the VS Code Activity Bar (left sidebar).
2. Click **Scan Workspace** (or run `Ctrl+Shift+P` → `DevMind: Scan Workspace`).
3. The local scanner parses your workspace using deterministic tree-sitter AST engines.
4. Detected architectural items appear across the sidebar views:
   - **Findings**: Code vulnerabilities, missing role checks (`devmind.authz.missing_role_check`), exposed secrets.
   - **Project Structure**: Discovered API routes, middleware chains, endpoints.
   - **Database (from files)**: Extracted ORM models and schema migrations.

### 5.2 Reviewing What Leaves Your Machine (Consent Ledger)

Before any metadata or chunk leaves your machine:

1. Run `DevMind: Review What Leaves Machine` from the Command Palette.
2. A security-isolated **Consent Preview Webview** opens showing:
   - Exact files and line ranges proposed for synchronization.
   - Total payload byte count.
   - Redaction checks (all tokens and credentials masked as `[REDACTED:type:hash8]`).
3. Click **Accept & Sync** to transmit consented data, or **Cancel** to abort.

---

## 6. Web Platform Capabilities

### 6.1 Project Brain & Symbol Knowledge Graph

- **Route**: `/projects/[projectId]/brain`
- Explore your codebase as a living knowledge graph.
- Inspect symbols (classes, functions, interfaces), caller-callee relationships, and semantic embeddings.
- Filter by file, directory strata, or component blast radius.

### 6.2 Project Mentor & Topological Task DAGs

- **Route**: `/projects/[projectId]/mentor`
- **Topological Task Sorting**: View work items organized via Kahn's algorithm DAG. Blocked tasks strictly follow unblocked blockers with zero circular dependency deadlocks.
- **Health Evaluations**: Generate release-readiness assessments across six dimensions:
  1. Functionality
  2. Code Quality
  3. Security Posture
  4. Test Coverage
  5. Living Documentation
  6. Architecture Adherence

### 6.3 Living Documentation (DocsAlive)

- **Route**: `/projects/[projectId]/documentation`
- Automatically compares actual code AST implementations against Markdown / OpenAPI documentation.
- Detects **Documentation Drift** (outdated parameters, renamed routes, missing docs).
- Generates one-click unified diff patches to sync documentation back to ground truth.

### 6.4 Bug Memory & Resolution Retrieval

- **Route**: `/projects/[projectId]/bugs`
- Deduplicates exceptions and runtime errors using canonical SHA-256 error signatures.
- When an engineer or CI hits an error, Bug Memory surfaces the exact verified code fix and root cause from historical incidents.

### 6.5 Deployment Diagnosis & Incident Triage

- **Route**: `/projects/[projectId]/deployments`
- Paste raw deployment and startup logs from Render, Vercel, or Docker.
- Automatically redacts sensitive tokens and detects:
  - Missing environment variables.
  - Database migration failures and connection timeouts.
  - Port binding mismatches and container OOM kills.
- Outputs probable cause classification and step-by-step remediation commands.

### 6.6 PR Intelligence & Review Rules

- **Route**: `/projects/[projectId]/prs`
- Connect GitHub repositories to automatically analyze incoming Pull Requests.
- Runs evidence-based security and architecture checks, posting actionable PR review comments grounded strictly in E0–E2 evidence.

---

## 7. Environment Variables & Configuration

Below is the reference matrix of environment variables:

| Component     | Variable                            | Purpose                               | Default / Example                          |
| ------------- | ----------------------------------- | ------------------------------------- | ------------------------------------------ |
| **Client**    | `NEXT_PUBLIC_API_BASE_URL`          | DevMind FastAPI API endpoint          | `https://api.devmind.warishlabs.in`        |
| **Client**    | `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk authentication frontend key     | `pk_live_...`                              |
| **Client**    | `NEXT_PUBLIC_SITE_URL`              | Canonical client URL                  | `https://devmind.warishlabs.in`            |
| **Server**    | `DEVMIND_DATABASE_URL`              | PostgreSQL connection with pgvector   | `postgresql+psycopg://...`                 |
| **Server**    | `DEVMIND_REDIS_URL`                 | Redis for Celery queues and caching   | `rediss://...`                             |
| **Server**    | `CLERK_SECRET_KEY`                  | Clerk backend JWT verification secret | `sk_live_...`                              |
| **Extension** | `DEVMIND_API_BASE_URL`              | Target server URL during build        | `https://api.devmind.warishlabs.in/api/v1` |

---

## 8. Troubleshooting & Frequently Asked Questions

### Q: Why do I see "Developer Access" instead of the Clerk sign-in card?

**A:** This occurs when `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is not present in the active environment. You can enter any developer email to proceed in offline mode, or provide your Clerk publishable key in `client/.env.local`.

### Q: Does the VS Code extension ever send my source code to third-party AI providers?

**A:** **Never.** Under ADR-022 and ADR-047, all parsing is local. Only consented manifests or indexed chunk hashes leave your machine, and only to your designated DevMind backend.

### Q: How do I link a new repository to an existing DevMind Project?

1. Open the project in the DevMind Web UI and copy its **Project ID**.
2. Open your repository folder in VS Code.
3. Run `DevMind: Link Workspace to Project` from the Command Palette (`Ctrl+Shift+P`).
4. Paste the Project ID. Subsequent scans and syncs will associate with that Project Brain.

### Q: How do I test the platform locally with zero external services?

DevMind includes complete mock adapters for offline development:

- Run `node scripts/test-all.mjs --fast` to execute the full end-to-end verification suite across client, server, extension, and common packages.
- Start the server with `DEVMIND_RUN_MODE=all` and client with `NEXT_PUBLIC_FIXTURE_MODE=true`.
