# Runbook: Academic Demonstration & Viva Presentation Guide

> **Governing documents:** [docs/source/DevMind_Project_Document.md](../source/DevMind_Project_Document.md) · [docs/01 §4, §17](../01-product-requirements.md) · [docs/02 §4](../02-system-architecture.md) · [docs/05 §6](../05-agents-and-llm-workflows.md) · [docs/07 §6, §15](../07-security-privacy-and-threat-model.md) · [docs/08](../08-ui-ux-design-specification.md) · [docs/09 §9, §15](../09-testing-and-quality-strategy.md) · [docs/10 §22](../10-deployment-and-operations.md) · [docs/11 §3](../11-mvp-and-implementation-roadmap.md) · [docs/12](../12-architecture-decisions-and-open-questions.md).
> **Target Audience:** Project Supervisor, External Examiners, Viva Panel, and Technical Evaluators.
> **Demonstration Duration:** 15–20 minutes (Walkthrough + Q&A).

---

## 1. Executive Summary & The Viva Pitch

### 1.1 In One Sentence (The Core Thesis)
> *"DevMind is an agentic AI software engineering platform that maintains a continuous, shared understanding of a software project across its entire lifecycle — connecting code intelligence, security analysis, bug recurrence memory, living documentation, pull request reviews, deployment failure diagnosis, development task prioritization, and release-readiness auditing into one unified Project Brain rather than disconnected tools."*

### 1.2 The Fundamental Research Problem
Software engineering is rarely slowed down by the speed of typing code. It slows down because projects generate hundreds of **interconnected problems** across architecture, security, past bugs, documentation, reviews, and deployment that current tooling treats as **isolated, fragmented silos**.

- A change to an authorization middleware affects:
  1. API endpoint security (CAP-02).
  2. Pull request blast radius and review risk (CAP-05, CAP-06).
  3. OpenAPI / Markdown documentation accuracy (CAP-04).
  4. Runtime deployment environment variable requirements (CAP-07).
  5. Backlog task prerequisites and release readiness (CAP-08, CAP-09).

DevMind eliminates this fragmentation by anchoring specialized, least-privilege AI agents around a **single source of truth: the Project Brain**.

---

## 2. System Architecture: The Unified Project Brain

```mermaid
flowchart TD
    subgraph Brain["Project Brain Core Model (PostgreSQL + pgvector)"]
        AST[Tree-sitter AST & Symbol Graph]
        VecStore[Hybrid Retrieval: Dense Vectors + Sparse BM25 + Graph 1-Hop]
        HistoryStore[Incident & Bug Memory Records]
        TaskGraph[Topological Task DAG]
    end

    subgraph Agents["Specialist Agent Layer (LangGraph + Deterministic Heuristics)"]
        CodeMate[CodeMate: Code Intelligence CAP-01]
        AuthCheck[AuthCheck: Security Intelligence CAP-02]
        BugMem[BugMemory: Bug Recurrence Memory CAP-03]
        DocsAlive[DocsAlive: Living Documentation CAP-04]
        PRAgent[PRAgent: Change-Impact Analysis CAP-06]
        ReviewBuddy[ReviewBuddy: Checklist Review CAP-05]
        DeployDoc[DeployDoctor: Deployment Diagnosis CAP-07]
        Mentor[ProjectMentor: Task DAG Ordering CAP-08]
        EvalAgent[ProjectEvaluation: Multidimensional Health CAP-09]
    end

    subgraph Boundaries["Human-in-the-Loop & Security Boundaries"]
        ClientWeb["Next.js App Shell (Screens S-01 to S-18)"]
        Extension["Privacy-First VS Code Companion (E0/E1 Local)"]
        ApprovalGate{"Human Approval Gates (ADR-015, ADR-034)"}
    end

    Brain <--> Agents
    Agents --> ApprovalGate
    ApprovalGate --> ClientWeb
    Extension -->|Consented Snippets & Metadata| Brain
```

---

## 3. The 15-Minute Live Demonstration Script

### Act 1: Code & Security Intelligence (Minutes 00:00 – 04:00)
- **Target Capabilities:** CAP-01 (Code Intelligence) & CAP-02 (Security Intelligence).
- **Screens:** VS Code Extension & Web App Screen S-04 (`/projects/[pid]/brain`), Screen S-05 (`/projects/[pid]/findings`).
- **Demonstration Steps:**
  1. Open VS Code with `devmind-vscode`. Run local AST scan. Point out that the extension performs local static pattern matching (`E0/E1`) without live database access or LLM invocation (ADR-034).
  2. Open the web app shell. Navigate to **Project Brain**. Demonstrate the interactive module/symbol graph showing callers, callees, and dependencies rendered with zero latency from the PostgreSQL relational graph.
  3. Navigate to **Security Findings**. Demonstrate an AuthCheck finding:
     - Point out the exact evidence level (`E2` verified by AST structural flow).
     - Contrast DevMind's concrete finding ("`/api/v1/projects/{pid}/members` lacks `@declare_permission(PERM_PROJECT_UPDATE)`") against generic chatbot hallucinations ("You might have auth issues").
  4. Show the **Human Approval Gate**: Mark finding as `confirmed`. Note that state transitions are enforced by strict state machines ([docs/03 §5.1](../03-data-model-and-api.md)).

### Act 2: PR Intelligence & ReviewBuddy (Minutes 04:00 – 08:00)
- **Target Capabilities:** CAP-05 (Code Review Intelligence) & CAP-06 (Pull Request Intelligence).
- **Screens:** Web App Screen S-13 (`/projects/[pid]/pull-requests`), Screen S-14 (`/projects/[pid]/pull-requests/[prId]`).
- **Demonstration Steps:**
  1. Open a simulated GitHub Pull Request. Show that the GitHub App webhook ingested the PR with HMAC SHA-256 signature verification and idempotent replay deduplication.
  2. Highlight the **Change-Impact Analysis Graph**:
     - Demonstrate how PRAgent traversed the Project Brain graph to calculate the exact blast radius.
     - Show that changing a central database model flagged 4 downstream API routers and 2 Celery workers as affected areas.
  3. Demonstrate **ReviewBuddy Review Rules**:
     - Display the custom rules checklist (Input Validation, Error Handling, Permission Checks, Unit Tests).
     - Show located line citations where input validation was omitted in the diff.

### Act 3: Bug Memory & Living Docs (Minutes 08:00 – 11:00)
- **Target Capabilities:** CAP-03 (Bug Memory) & CAP-04 (Living Documentation).
- **Screens:** Web App Screen S-15 (`/projects/[pid]/bugs`), Screen S-16 (`/projects/[pid]/docs-drift`).
- **Demonstration Steps:**
  1. Open **Bug Memory**. Paste a recurring crash error traceback containing a memory pointer address (`at 0x7ffd98b0`).
  2. Demonstrate how `BugNormalizer` strips ephemeral memory addresses and timestamps to compute a canonical SHA-256 fingerprint.
  3. Show hybrid similarity matching: DevMind locates a past bug resolved 3 months earlier, displaying the previous root cause and fix summary.
  4. Switch to **Living Documentation**. Show a seeded documentation drift item ("Endpoint `/api/v1/projects/{pid}/tasks` was added in code but omitted from `docs/03-data-model-and-api.md`").
  5. Click **View Proposed Patch Diff**. Emphasize the Human-in-the-Loop constraint: DocsAlive drafts the unified diff, but never silently auto-commits to git.

### Act 4: Project Mentor & Health Evaluation (Minutes 11:00 – 14:00)
- **Target Capabilities:** CAP-08 (Project Mentor) & CAP-09 (Project Evaluation).
- **Screens:** Web App Screen S-17 (`/projects/[pid]/mentor`).
- **Demonstration Steps:**
  1. Open **Project Mentor**. Show the Task Backlog dependency visualizer.
  2. Demonstrate **Topological DAG Ordering**:
     - Show how Kahn's algorithm ranks unblocked tasks based on priority and downstream unblocking count.
     - Attempt to create a circular prerequisite dependency (`Task A -> Task B -> Task A`). Show that the server deterministically intercepts and rejects the cycle with HTTP 409 `ConflictError`.
  3. Switch to **Project Evaluation**:
     - Display the 5-dimensional health scorecard (Quality: 0.25, Security: 0.30, Architecture: 0.20, Velocity: 0.15, Documentation: 0.10).
     - Display the categorical **Release-Readiness Verdict** (`ready`, `warning`, `blocked`) and show the explicit release blocker items preventing deployment.

### Act 5: Deployment Diagnosis (Minutes 14:00 – 17:00)
- **Target Capabilities:** CAP-07 (Deployment Diagnosis).
- **Screens:** Web App Screen S-18 (`/projects/[pid]/deployments`).
- **Demonstration Steps:**
  1. In the **Log Diagnosis Form**, paste a raw production crash log containing ANSI escape codes and unredacted PostgreSQL database credentials (`postgresql://postgres:SuperSecretPassword123@neon.tech:5432/devmind`).
  2. Point out the **Client-Side Redaction Preview**: The sensitive connection string is masked in real-time before sending.
  3. Submit the log. Point out server-side results:
     - `LogParser` stripped ANSI codes and masked credentials with SHA-256 hashes (`redaction_count >= 1`).
     - Correct category classified: `missing_env_var`.
     - 1-based primary log line citation pinpointed.
     - `EnvVarChecker` detected that `DATABASE_URL` was missing from the deployment platform configuration.
     - Historical incident resolution suggested from past incidents.

---

## 4. Key Architectural Differentiators (Why DevMind is Novel)

When examiners ask what distinguishes DevMind from commercial products like GitHub Copilot, Cursor, or Snyk:

| Aspect | Generic AI Coding Assistant | DevMind Architecture |
|---|---|---|
| **Context Model** | Ephemeral, prompt-scoped buffer (current file or open tabs). | **Persistent, compounding Project Brain** stored in relational tables and vector embeddings. |
| **Lifecycle Scope** | Focused exclusively on code generation at typing time. | **Full Software Lifecycle**: Development -> Security -> Review -> Documentation -> Backlog -> Deployment. |
| **Past Incident Recall** | Zero memory of past bugs in the project. | **Bug Memory & DeployDoctor Incident Ledger** with normalized canonical fingerprints. |
| **Security Governance** | Unchecked generative code suggestions. | **Deterministic Evidence Tiers (`E0`–`E2`)**, AST dataflow analysis, and explicit Human Approval Gates. |
| **Dependency Governance** | Suggests arbitrary changes without prerequisite context. | **Topological DAG Backlog Ordering** with cycle prevention. |
| **Privacy & Zero Cost** | Cloud uploads with proprietary subscription fees. | **Privacy-first companion** (no silent uploads, zero live DB connections) running on **100% Free Tiers** (ADR-046). |

---

## 5. Defense Against Examiner Technical Questions

### Q1: "How do you prevent LLM hallucinations from corrupting the Project Brain or misleading developers?"
> **Answer:** *"DevMind follows a 'Deterministic Before Generative' principle. Core analysis is performed by deterministic code: Tree-sitter for AST parsing, Dijkstra/Kahn algorithms for DAG dependency resolution, Levenshtein/SequenceMatcher for typo detection, and regex parsers for error normalization. LLMs are only invoked at the final synthesis layer, where they are strictly constrained by structured Pydantic output schemas (`extra='forbid'`) and required to cite concrete log lines or AST symbol keys. If citations fail to resolve to real file versions, the evidence verifier downgrades or rejects the output. Furthermore, side effects (merges, PR comments, doc commits) are strictly blocked behind Human Approval Gates."*

### Q2: "How does the system scale within the strict Free Tier constraint (ADR-046)?"
> **Answer:** *"DevMind was engineered from day one to operate cleanly on Render's 512 MB RAM free tier and Neon's 0.5 Compute Unit free tier. In production, we use a modular monolith (`DEVMIND_RUN_MODE=all`) where FastAPI and embedded Celery workers share a single container process. Embeddings use lightweight pooling, background tasks use Upstash Redis with bounded queue lengths, and database queries use strict pagination, composite indexes on tenant columns, and connection pooling through PgBouncer."*

### Q3: "How do you guarantee multi-tenant security and prevent prompt injection attacks?"
> **Answer:** *"Every tenant query is strictly scoped by `workspace_id` and `project_id` via our `AuthContext` policy service; missing scopes fail at both the route registry and repository layer. Repository code is treated as untrusted input. We enforce strict delimiter encapsulation in prompt templates, strip terminal ANSI codes, and validate prompts against our 55-vector adversarial injection benchmark suite (`evals/injection/`), which achieves a 100% block rate against delimiter collision, tool escalation, and indirect injection."*

### Q4: "What evidence proves your 9 capabilities actually work rather than just look good in the UI?"
> **Answer:** *"Per rule §1 of our testing strategy ('A claim needs a measurement'), every capability is guarded by automated benchmark evaluation suites with recorded baselines in `docs/09 §9`:
> - Retrieval & Fusion: 0.7658 nDCG@5.
> - Agent Faithfulness: 1.0000 Grounding Ratio, 0.0 Hallucination Rate.
> - Prompt Injection Defense: 100% pass rate (55/55 vectors).
> - PR Intelligence: 100% risk classification, 100% ReviewBuddy F1.
> - Bug Memory & Living Docs: 100% Top-1 match, 100% drift detection F1.
> - Project Mentor & Health Evaluation: 100% DAG ordering, 100% release verdict accuracy.
> - Deployment Diagnosis: 100% secret redaction, 100% category classification, 100% env var F1.
> All benchmarks run via deterministic harnesses (`npm run eval:*`) and are verified by our 13-suite monorepo runner (`test-all.mjs`)."*

---

## 6. Pre-Viva Verification Checklist

Run this command sequence 30 minutes before the presentation to ensure complete system health:

```bash
# 1. Run full fast verification test suite (all 13 steps must pass)
node scripts/test-all.mjs --fast

# 2. Verify all evaluation benchmark baselines
npm run eval:pr
npm run eval:bug-docs
npm run eval:mentor
npm run eval:deploy

# 3. Verify database migrations are aligned with head
cd server && uv run alembic current

# 4. Verify client build compiles cleanly without warnings
pnpm --filter devmind-client build
```
