# 13 · Glossary and Domain Terminology

**Purpose.** One definition per term, used identically in every document, API field, table and UI string. If a term here conflicts with another document, this glossary wins and the other document is a bug.

Related: [index](00-documentation-index.md) · [decisions](12-architecture-decisions-and-open-questions.md).

---

## 1. Core product terms

| Term | Definition |
|---|---|
| **DevMind** | The agentic AI software engineering system: a website, a VS Code extension and a backend that share one understanding of a software project. |
| **Project** | A software codebase registered in DevMind. Belongs to exactly one workspace. |
| **Workspace** | DevMind's tenant boundary: a set of users and projects. Not the same as a *local workspace*. |
| **Local workspace** | A folder opened in VS Code. A project may have several local workspace registrations (several machines or clones). |
| **Project Brain** | The structured, version-aware, continuously updated understanding of a project, made of eight related stores (see [04](04-project-brain-and-rag.md) §2). It is **not** one large prompt and not a pile of raw files. |
| **Agent Manager** | The orchestration entry point that classifies a request, selects specialist agents, runs them, verifies evidence, and merges results into one answer. |
| **Specialist agent** | A workflow dedicated to one capability (for example AuthCheck). Reads from and writes back to the Project Brain through restricted tools. |
| **Capability** | One of the nine original product capabilities, `CAP-01` to `CAP-09`. |
| **Lifecycle** | Understand, build, review, secure, fix, document, deploy, evaluate, improve, then repeat. |

## 2. Agents and codenames

Codenames marked ✱ come from the source vision document. The others are design recommendations.

| Capability | Specialist agent |
|---|---|
| CAP-01 Code Intelligence | CodeMate |
| CAP-02 Security Intelligence | AuthCheck ✱ |
| CAP-03 Bug Memory | BugMemory |
| CAP-04 Living Documentation | DocsAlive ✱ |
| CAP-05 Code Review Intelligence | ReviewBuddy ✱ |
| CAP-06 Pull Request Intelligence | PRAgent ✱ |
| CAP-07 Deployment Diagnosis | DeployDoctor ✱ |
| CAP-08 Project Mentor | ProjectMentor ✱ |
| CAP-09 Project Evaluation | ProjectEvaluator |

## 3. Knowledge and retrieval terms

| Term | Definition |
|---|---|
| **Local manifest** | The extension's on-disk record of each scanned file: relative path, size, content hash, language, last scan, local findings. Lives outside the repository. |
| **Local scan state** | The extension's progress and cache data (what was scanned, with which rules version). |
| **Cloud synchronization** | Transfer from the extension to the backend of metadata and, when consented, snippets. Always incremental and user-visible. |
| **Sync mode** | Per-project setting: `metadata_only` or `indexed`. |
| **File version** | An immutable record of a file's content at a given hash. The current version of a file is the one pointed to by the file record. |
| **Project snapshot** | A named set of (path → file version) pairs, usually tied to a commit or a scan run. Distinguishes *current state* from *history*. |
| **Code chunk** | A contiguous piece of a file version prepared for search and embedding, usually one symbol. |
| **Code symbol** | A named program element (function, class, method, route handler, model, constant) with file, line range and signature. |
| **Code relationship** | A directed, typed edge between symbols or files: `imports`, `calls`, `defines_route`, `guarded_by`, `reads_model`, `tests`, `documents`. |
| **Code index** | The searchable store of chunks, symbols and relationships. Distinct from the vector embeddings and distinct from the relationship graph. |
| **Vector embedding** | A numeric vector for a chunk or query, produced by a hosted embedding model, stored in pgvector. |
| **Embedding space** | One (provider, model, dimension) combination. Vectors from different spaces are never compared. |
| **Hybrid retrieval** | Combining keyword search, vector similarity, metadata filters, symbol lookup and relationship expansion, then fusing and ranking. |
| **Context pack** | The budgeted, attributed set of chunks, symbols, findings and history given to an LLM for one task. |
| **Citation** | A reference to evidence: project, file version, path, line range and content hash. |
| **Stale** | Derived data (a finding, a documentation drift item, a chunk, an embedding) whose source file version is no longer current. |

## 4. Findings and quality terms

| Term | Definition |
|---|---|
| **Finding** | A reportable issue with a location, explanation, severity, evidence level, confidence and remediation status. |
| **Evidence** | Machine-checkable support for a finding: citations plus the deterministic result or scanner rule that produced it. |
| **Evidence level** | E0 suspected (reasoning only) · E1 pattern match (deterministic rule hit) · E2 structurally verified (static analysis confirms the condition in the code) · E3 reproduced (dynamically demonstrated; post-MVP and only with explicit approval). |
| **Severity** | `critical`, `high`, `medium`, `low`, `info`. Impact if the finding is real. |
| **Confidence** | `low`, `medium`, `high`. How sure the system is the finding is real. Independent of severity. |
| **Verified finding** | A finding at E2 or higher. "Verified" never means exploit-proven unless E3. |
| **Possible finding** | A finding at E1 whose condition cannot be fully confirmed statically. Labelled as possible in every interface. |
| **Remediation status** | Lifecycle state: `open`, `acknowledged`, `in_progress`, `fix_proposed`, `resolved`, `dismissed`, `accepted_risk`, `stale`, `reopened`. |
| **Authentication** | Establishing who the caller is. |
| **Authorization** | Deciding whether that caller may perform this action on this resource. Always separate from authentication. |
| **Bug memory** | Structured records of resolved issues (error signature, cause, fix, files) matched against new errors. |
| **Bug record** | One entry in bug memory. Has a fingerprint and one or more resolutions. |
| **Change-impact analysis** | Determining what other symbols, routes, tests, documents and deployments a change can affect, using code relationships and history. |
| **Documentation drift** | A mismatch between current code and current documentation. |
| **Project health** | A rubric-based multi-dimension score. Not an industry benchmark. |
| **Release readiness** | A rule-based verdict (`ready`, `ready_with_warnings`, `not_ready`) with listed reasons. |

## 5. Execution terms

| Term | Definition |
|---|---|
| **Scan run** | One pass of file discovery and deterministic analysis over a local workspace or a cloud-fetched repository. Recorded in `scan_runs`. |
| **Analysis job** | One asynchronous unit of backend work (`analysis_jobs`): ingestion, embedding, or an agent workflow. Has the job status enumeration in [03](03-data-model-and-api.md) §6. |
| **Agent run** | One execution of a LangGraph workflow for a job, with its prompt versions, model choices and checkpoints. |
| **Checkpoint** | A saved LangGraph state allowing a workflow to resume after interruption. |
| **Approval gate** | A workflow pause (`awaiting_approval`) that requires a human decision before a sensitive step. |
| **Idempotency key** | A client-supplied value ensuring a repeated request creates one resource. |
| **Task** (LLM) | A named unit of model work (for example `security_explanation`) that maps to a model through routing configuration. Not a project task. |
| **Project task** | A work item in a project (`project_tasks`) used by ProjectMentor. |
| **Model routing** | Mapping each LLM task to a primary model and fallbacks through configuration. |
| **Model registry** | The validated catalog of models and their declared capabilities. |
| **Provider adapter** | The code that translates between DevMind's internal LLM interface and one provider's API. |
| **LLM gateway** | The only module agents use to call a model. Applies routing, limits, retries, normalization, accounting. |
| **Consent record** | An auditable grant by a user permitting specified data categories to be sent to specified providers for a project. |
| **Redaction** | Replacing detected secrets or excluded content with placeholders before any transmission, log or storage. |

## 6. Roles and permission terms

| Term | Definition |
|---|---|
| **Workspace role** | `owner`, `admin`, `member`, `viewer`. |
| **Project role** | `maintainer`, `contributor`, `viewer`; used for private projects. |
| **AuthContext** | The server-side object carrying verified identity, memberships and effective permissions for a request. Required by every repository function. |
| **Browser-facing API** | Endpoints under `/api/v1/` used by the website with a Clerk session token. |
| **Extension-facing API** | Endpoints under `/api/v1/ext/` used by the extension with an extension token. |

## 7. Documentation status terms

| Term | Definition |
|---|---|
| **Confirmed / Recommended / Deferred / Open** | Decision statuses; see [12](12-architecture-decisions-and-open-questions.md) §1. |
| **MVP** | The first release defined in [01](01-product-requirements.md) §14. |
| **Specification** | A written plan. Not evidence that anything is implemented or tested. |
