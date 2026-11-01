# Project Mentor and Health Evaluation Operational Runbook

> **Governing documents:** [docs/01 §8 (CAP-08, CAP-09)](../01-product-requirements.md) · [docs/03 §3.6, §3.7, §11](../03-data-model-and-api.md) · [docs/05 §6.8](../05-agents-and-llm-workflows.md) · [docs/07 §3, §10, §15](../07-security-privacy-and-threat-model.md) · [docs/08 §Screen S-17](../08-ui-ux-design-specification.md) · [docs/09 §9](../09-testing-and-quality-strategy.md#9-retrieval-and-answer-quality-evaluation-baselines) · [docs/10 §11, §18](../10-deployment-and-operations.md) · [ADR-006 (LangGraph Orchestration)](../12-architecture-decisions-and-open-questions.md#adr-006-langgraph-for-agents-services-for-everything-else) · [ADR-046 (Free-Only)](../12-architecture-decisions-and-open-questions.md#adr-046-free-only-constraint-and-free-deployment-profile) · [ADR-047 (Public Repo)](../12-architecture-decisions-and-open-questions.md#adr-047-repository-ownership-and-visibility) · [OQ-18 (Functionality Dimension Checklist)](../12-architecture-decisions-and-open-questions.md#4-open-questions).
> **Non-negotiable security:** Never store customer source code or unredacted secrets in task metadata or evaluation logs. All queries scoped strictly by `workspace_id` and `project_id`. Cyclic dependency injection is rejected deterministically with RFC 9457 `409 ConflictError`.

---

## 1. Subsystem overview

Release 1.3 introduces two collaborative decision-support capabilities designed to guide engineering teams toward release readiness and prevent uncoordinated development bottlenecks:

1. **Project Mentor (CAP-08):** A dependency-aware task backlog and execution order optimizer:
   - **Topological DAG Sorting (`TaskDAG`):** Represents project tasks and prerequisite dependencies as a Directed Acyclic Graph. Uses a modified Kahn's algorithm that accounts for task priority (`critical`=4.0, `high`=3.0, `medium`=2.0, `low`=1.0) and downstream unblocking impact count.
   - **Prerequisite Enforcement:** Tasks with incomplete dependencies are tagged as blocked; unblocked tasks (`is_ready == True`) are prioritized for immediate execution.
   - **Cycle Prevention:** Adding a dependency that would induce a cycle is detected ahead of database persistence and rejected with HTTP 409 (`code: "conflict.state"`).
   - **Specialist Agent (`ProjectMentorAgent`):** Analyzes the current backlog state to synthesize actionable, human-readable rationales highlighting why a specific task should be tackled next.
2. **Project Evaluation & Health Scorecards (CAP-09):** Multidimensional repository health evaluation and release-readiness verdict synthesis:
   - **Deterministic Scoring Engine (`compute_health_scorecard`):** Evaluates repository health across five core dimensions: Quality (weight 0.25), Security (weight 0.30), Architecture (weight 0.20), Velocity (weight 0.15), and Documentation (weight 0.10).
   - **Functionality Confidence & Blockers (OQ-18):** Audits declared feature checklists. Missing critical checklist items immediately escalate to release blockers. Projects with empty checklists report `low` functionality confidence.
   - **Release-Readiness Verdict (`evaluate_release_readiness`):** Produces a categorical verdict:
     - `ready`: Overall score ≥ 80, zero critical/high security blockers, zero unhandled architecture cycles, and high functionality confidence.
     - `warning`: Overall score between 60 and 79 with non-critical warnings.
     - `blocked`: Presence of any critical release blocker, active cyclic dependencies, or overall score < 60.
   - **Specialist Narrative Generator:** Formulates structured summaries articulating health strengths, active blockers, and high-impact remediation recommendations (with deterministic fallback when LLM gateway is offline).

---

## 2. Architecture and data flow

```mermaid
flowchart TD
    subgraph ProjectMentor["Project Mentor (CAP-08)"]
        TaskIn[Task Backlog Items] --> DAG[TaskDAG Sorter]
        DepIn[Dependency Links] --> CycleCheck{Cycle Check}
        CycleCheck -->|Cycle Detected| Err409[HTTP 409 Conflict]
        CycleCheck -->|Valid DAG| DAG
        DAG --> Rank[Topological & Priority Ranking]
        Rank --> NextTask[Next Unblocked Recommendation]
        NextTask --> AgentMentor[ProjectMentor Specialist Agent]
        AgentMentor --> RecOut[Task Recommendation Narrative]
    end

    subgraph ProjectEvaluation["Project Health Evaluation (CAP-09)"]
        Findings[Security & Quality Findings] --> EvalEngine[Deterministic Scoring Engine]
        AST[Code & Module Graph Metrics] --> EvalEngine
        Docs[Living Docs & Drift Items] --> EvalEngine
        OQ18[Declared Feature Checklist] --> EvalEngine
        EvalEngine --> Scorecard[Multidimensional Scorecard 0-100]
        EvalEngine --> Verdict[Release Verdict: ready | warning | blocked]
        Scorecard --> AgentNarrative[Evaluation Narrative Specialist]
        Verdict --> AgentNarrative
        AgentNarrative --> DB_Eval[("project_evaluations")]
    end
```

---

## 3. Data model and schema definitions

### 3.1 Project Tasks (`project_tasks`)

- **Table:** `project_tasks`
- **Columns:**
  - `id`: `UUID` (UUIDv7 primary key).
  - `workspace_id`: `UUID` (tenant workspace foreign key).
  - `project_id`: `UUID` (project foreign key).
  - `title`: `String(255)` task summary.
  - `description`: `Text` detailed scope or acceptance criteria (redacted).
  - `status`: `String(32)` (`pending`, `in_progress`, `completed`, `blocked`).
  - `priority`: `String(32)` (`low`, `medium`, `high`, `critical`).
  - `metadata_`: `JSONB` schemaless task attributes (source, tags, labels).
  - `created_at`, `updated_at`: `timestamptz` UTC.

### 3.2 Task Dependencies (`project_task_dependencies`)

- **Table:** `project_task_dependencies`
- **Columns:**
  - `project_id`: `UUID` (project foreign key).
  - `task_id`: `UUID` (task depending on prerequisite).
  - `depends_on_task_id`: `UUID` (prerequisite task).
  - `created_at`: `timestamptz` UTC.
  - **Constraints:** Composite primary key `(project_id, task_id, depends_on_task_id)`. Self-dependency check `task_id != depends_on_task_id`. Cascade deletion when either task is deleted.

### 3.3 Project Evaluations (`project_evaluations`)

- **Table:** `project_evaluations`
- **Columns:**
  - `id`: `UUID` (UUIDv7 primary key).
  - `workspace_id`: `UUID` (tenant workspace foreign key).
  - `project_id`: `UUID` (project foreign key).
  - `overall_score`: `Float` composite health score (0.0 to 100.0).
  - `verdict`: `String(32)` (`ready`, `warning`, `blocked`).
  - `functionality_confidence`: `String(32)` (`high`, `medium`, `low`).
  - `quality_score`, `security_score`, `architecture_score`, `velocity_score`, `documentation_score`: `Float` (0.0 to 100.0).
  - `blockers`: `JSONB` array of critical blockers barring release.
  - `warnings`: `JSONB` array of non-blocking health risks.
  - `strengths`: `JSONB` array of positive architectural and quality accomplishments.
  - `narrative`: `Text` synthesis and recommendations.
  - `created_at`: `timestamptz` UTC.

---

## 4. Operational procedures

### 4.1 Dependency cycle triage and resolution

When an API client attempts to link a dependency that would induce a cycle, the system aborts the mutation:

1. **Symptom:** Client receives `HTTP 409 Conflict` with `code: "conflict.state"` and message `"Adding this dependency would create a cycle: [...]"`.
2. **Identification:**
   - Review the cycle path reported in the RFC 9457 problem detail.
   - Inspect the task chain in the Task DAG Visualizer on web screen S-17 (`/projects/{projectId}/tasks`).
3. **Resolution:**
   - Remove the conflicting prerequisite or decompose compound tasks into smaller atomic stages.
   - If a circular link was added accidentally, delete the prerequisite via `DELETE /api/v1/projects/{projectId}/tasks/{taskId}/dependencies/{dependsOnId}`.

### 4.2 Interpreting and remediating release blockers

A verdict of `blocked` indicates that the project does not meet safety or stability criteria for production:

1. **Security Blockers (`E2`/`E3` Findings):**
   - Active critical/high security vulnerabilities (e.g., missing authentication on mutating routes, SQL injection, hard-coded credentials).
   - **Action:** Remediate finding in code or review with security maintainer.
2. **Topological Blockers (Cyclic Tasks):**
   - Cyclic dependency chains preventing completion of planned features.
   - **Action:** Break the cycle in the backlog DAG.
3. **Functionality Gaps (OQ-18):**
   - Declared checklists with missing critical verification items.
   - **Action:** Update feature status in the project checklist or complete the required acceptance verification.

### 4.3 Triggering on-demand project evaluations

Evaluations can be triggered manually or via continuous delivery pipelines:

1. **CLI Evaluation Harness:**
   ```bash
   npm run eval:mentor
   ```
   Executes the benchmark suite against synthetic edge-case fixtures and outputs composite scoring metrics.
2. **REST API Trigger:**
   ```bash
   curl -X POST "https://<api-host>/api/v1/projects/<project_id>/evaluations/run" \
     -H "Authorization: Bearer <clerk_token>" \
     -H "Content-Type: application/json" \
     -d '{"checklist": [{"title": "Authz enforcement", "is_critical": true, "is_verified": true}]}'
   ```
3. **Web Interface (Screen S-17):**
   - Navigate to `/projects/{projectId}/tasks`.
   - Select the **Health Scorecard & Radar** tab.
   - Click **Run Health Evaluation Audit** in the action bar.

---

## 5. Telemetry, logging & error codes

### 5.1 Logging conventions

All logging in the mentor and evaluation subsystem adheres strictly to ADR-047 and ADR-046:

- Structured JSON logs include `request_id`, `project_id`, `task_id`, `evaluation_id`, and `duration_ms`.
- **Never log:** Task descriptions containing private code or unredacted tokens, completion prompts, or raw customer data.
- **Always log:** Scorecard dimension values, verdict strings, blocker counts, and cycle paths.

### 5.2 Error code catalog

| HTTP Status | Error Code | Description | Troubleshooting Step |
|---|---|---|---|
| `400 Bad Request` | `validation.failed` | Invalid task status or priority string | Ensure priority is one of `[low, medium, high, critical]` and status is `[pending, in_progress, completed, blocked]`. |
| `404 Not Found` | `resource.not_found` | Task or evaluation ID not found | Verify task belongs to current `workspace_id` and `project_id`. |
| `409 Conflict` | `conflict.state` | Cyclic dependency detected | Inspect dependency path in error details; remove circular edge. |
| `403 Forbidden` | `auth.forbidden` | Insufficient project permissions | User requires `PERM_PROJECT_UPDATE` for mutating backlog tasks and `PERM_ANALYSIS_CREATE` for running health evaluations. |
| `503 Service Unavailable` | `llm.unavailable` | LLM provider gateway unavailable | System automatically falls back to deterministic rule-based narratives. Inspect provider API quotas if persistent. |

---

## 6. Verification and baseline benchmarks

The mentor and evaluation subsystem is continuously regression-tested against recorded baselines:

| Benchmark Metric | Target Baseline | Recorded Baseline (M12-12) |
|---|---|---|
| Top-1 Recommendation Accuracy | ≥ 90.0% | **100.0%** |
| Mean Reciprocal Rank (MRR) | ≥ 0.90 | **1.0000** |
| Ready-Task Execution Alignment | 100.0% | **100.0%** |
| Release Verdict Accuracy | ≥ 95.0% | **100.0%** |
| Blocker Precision / Recall / F1 | ≥ 95.0% | **100.0% / 100.0% / 100.0%** |
| Health Score Mean Absolute Error (MAE) | ≤ 5.0 pts | **2.70 pts** |
| Composite Benchmark Score | ≥ 90.0% | **100.0%** |

Full benchmark test data and evaluation fixtures are maintained under `evals/mentor/` with latest run results committed at `evals/results/mentor/latest.json`.
