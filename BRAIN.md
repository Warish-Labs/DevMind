# BRAIN.md — DevMind Working Memory

> No secrets, tokens, source content or user data in this file. It is committed to git.

---

## 1. Current state

| Field | Value |
| **Branch** | `feature/m12-deploy-agent` |
| **Last commit** | `8d03a75` (`feat(server): implement M12-15 deployment diagnosis specialist agent, env checker, and REST API`) |
| **Release Tag** | `v0.1.0` (MVP Release Candidate) · Milestone 11 Complete · Milestone 12.1 Complete · Milestone 12.2 Complete · Milestone 12.3 In Progress |
| **Working tree** | Clean |
| **Open PR** | [#109](https://github.com/Warish-Labs/DevMind/pull/109) |
| **Last CI result** | `test-all --fast`: 13 passed, 0 failed, 1 skipped |
| **Date** | 2026-11-01 |

---

## 2. Next action (exact)

1. Review and merge PR for `feature/m12-deploy-agent` into `main`.
2. After PR is merged:
   - Switch to `main`, pull latest (`git pull --ff-only origin main`).
   - Delete branch `feature/m12-deploy-agent` locally and remotely on GitHub (`git push origin --delete feature/m12-deploy-agent`).
   - Create feature branch `feature/m12-deploy-ui` for task **M12-16**: Web screens for Deployment Diagnosis (log paste/upload with redaction preview, probable root causes, log line citations, incident history).

---

## 3. Waiting on owner

Review and merge PR #109 (`feature/m12-deploy-agent` → `main`) after CI passes.

---

## 4. Done log

### Orchestration & API — M12-15: Deployment Diagnosis Specialist Agent, Env Checker & REST API

- **Date**: 2026-11-01
- **Branch**: `feature/m12-deploy-agent`
- **What**:
  - Implemented environment variable name checker, past incident similarity search, DeployDoctor specialist agent (`DeployDoctorAgent`), deployment domain service, and REST API endpoints (CAP-07, docs/01 §4, docs/03 §11.1, docs/05 §6.9):
    - **Environment Variable Name Checker (`server/app/analysis/env_checker.py`)**:
      - Implemented `EnvVarChecker` with Levenshtein-based similarity scoring (cutoff default 0.70) against reference template variables (e.g. from `.env.example`).
      - Identifies missing required variables, suggests typo corrections for unrecognized variables, and flags unreferenced template variables.
      - Integrated regex-based pattern matching for referenced env vars.
      - Unit tests in `server/tests/test_env_var_checker.py` (5/5 tests passing).
      - Exported `EnvVarChecker` in `server/app/analysis/__init__.py`.
    - **Past Incident Similarity Search (`server/app/persistence/repositories/incident_repo.py`)**:
      - Added `search_similar_incidents()` supporting exact category match, query keyword token overlap scoring in summary/probable_cause, and occurrence weighting.
      - Preserves tenant isolation raising `ForbiddenError` on workspace mismatch.
      - Unit tests in `server/tests/test_incident_repo.py` (7/7 tests passing).
    - **Deployment Diagnosis LLM Task & Structured Schemas (`server/app/llm/`)**:
      - Added `DiagnosisHypothesis` and `DeploymentDiagnosisOutput` schemas to `server/app/llm/schemas.py` and registered in `SchemaRegistry`.
      - Added `deployment_diagnosis` task configuration to `server/configs/llm/tasks.yaml` with schema enforcement and temperature 0.1.
      - Created structured prompt template `server/app/llm/prompts/deployment_diagnosis/v1.md` with instructions on log citations, root cause ranking, and remediation steps.
    - **DeployDoctor Specialist Agent (`server/app/orchestration/deploy_doctor.py`)**:
      - Built `DeployDoctorAgent` and `run_deploy_doctor_specialist()` LangGraph-compatible stateful runner.
      - Performs deterministic pre-analysis: log parsing & redaction, environment variable checking against project template, and similar incident retrieval.
      - Invokes LLM gateway with structured output, falls back to deterministic rule-based diagnosis when LLM is unavailable or fails.
      - Persists diagnosed incidents automatically in `DeploymentIncidentRepository`.
      - Wired `deploy_doctor` specialist into `ManagerAgent` (`server/app/orchestration/manager.py`), including intent classification, node factories, conditional routing, and `RELEASED_SPECIALISTS`.
      - Unit tests in `server/tests/test_deploy_doctor.py` (5/5 tests passing).
    - **Deployment Domain Service & REST API (`server/app/domain/deployment/`, `server/app/api/deployment.py`)**:
      - Domain service `DeploymentService` wrapping incident listing, detail, resolution updates, and on-demand diagnosis execution.
      - FastAPI router `deployment_router` (`/api/v1/workspaces/{workspace_id}/projects/{project_id}/deployments/...`):
        - `POST /diagnose`: Diagnose deployment failure log (`analysis:create`).
        - `GET /incidents`: List deployment incidents with category/resolution filters (`project:read`).
        - `GET /incidents/{incident_id}`: Retrieve incident details (`project:read`).
        - `PATCH /incidents/{incident_id}`: Update incident resolution (`project:update`).
        - `DELETE /incidents/{incident_id}`: Delete incident (`project:delete`).
      - Registered router in `server/app/main.py`.
      - Declared permissions on every endpoint via `@declare_permission` and updated Table 11.1 in `docs/03-data-model-and-api.md`.
      - API unit tests in `server/tests/test_deployment_api.py` (4/4 tests passing).
    - **Verification**:
      - All 13 steps in `scripts/test-all.mjs --fast` passed.

### Analysis & Persistence — M12-14: Deployment Diagnosis Data Models, Migration, Log Parser, and Repository

- **Date**: 2026-11-01
- **Branch**: `feature/m12-deploy-core`
- **What**:
  - Implemented core data model, schema migrations, log parsing with deterministic pre-redaction, and persistence repository for Deployment Diagnosis (CAP-07, docs/01 §4, docs/03 §3.4, docs/07 §6):
    - **Persistence Model (`server/app/persistence/models/deployment.py`)**:
      - Defined `DeploymentIncident` mapping table `deployment_incidents` with UUIDv7 primary key, tenant scoping (`workspace_id`, `project_id`), deterministic incident `fingerprint`, `summary`, `probable_cause`, `resolution`, `error_signature`, `environment`, `service_name`, `failure_category`, `log_snippet` (sanitized up to 4000 chars), `occurrence_count`, `last_seen_at`, `resolved_at`, `resolved_by`, and extensible JSONB `metadata_`.
      - Exported `DeploymentIncident` in `server/app/persistence/models/__init__.py`.
    - **Alembic Migration (`server/alembic/versions/0018_deployment_incidents.py`)**:
      - Created revision `0018_deployment_incidents` down-revisioned to `0017_project_mentor_and_evaluations`.
      - Added table `deployment_incidents` with foreign keys on `workspaces` and `projects` (`ondelete="CASCADE"`), unique index on `(project_id, fingerprint)`, composite index on `(workspace_id, project_id)`, and filter index on `(project_id, failure_category)`.
      - Updated schema inventory and migration head assertions in `server/tests/test_migrations.py` and `server/tests/test_restore_drill.py`.
    - **Deterministic Log Parser & Redaction Pre-filter (`server/app/analysis/log_parser.py`)**:
      - Implemented `LogParser` with ANSI terminal escape stripping and deterministic server-side credential redaction (`RedactionService` integration, environment variable assignment masking, and PAT fallback regex).
      - Multi-category failure classification heuristics for `missing_env_var`, `database_migration_failed`, `dependency_mismatch`, `port_binding_failed`, `build_compilation_failed`, `timeout`, and `unhandled_exception`.
      - Extraction of referenced environment variable names and code stack trace frames with project code prioritization.
      - Canonical error signature normalization and SHA-256 fingerprint generation.
      - Exported `LogParser`, `LogFrame`, `ParsedDeploymentLog` in `server/app/analysis/__init__.py`.
    - **Persistence Repository (`server/app/persistence/repositories/incident_repo.py`)**:
      - Implemented `DeploymentIncidentRepository` inheriting `BaseRepository`.
      - Strict cross-workspace and cross-project isolation checks raising `ForbiddenError` when alien contexts are supplied.
      - Incident deduplication via fingerprint: recurring failures increment `occurrence_count` and refresh `last_seen_at` without duplication.
      - Methods: `record_incident()`, `get_incident()`, `get_by_fingerprint()`, `list_incidents()`, `update_resolution()`, `delete_incident()`.
      - Exported repository in `server/app/persistence/repositories/__init__.py`.
    - **Documentation (`docs/03-data-model-and-api.md`)**:
      - Updated Table 3.4 schema and constraint definitions for `deployment_incidents`.
    - **Test Coverage**:
      - `server/tests/test_log_parser.py`: 9 unit tests covering credentials redaction, Pydantic settings missing vars, Alembic migration failures, dependency mismatches, port binding conflicts, build compilation errors, timeouts, empty logs, and deterministic fingerprinting.
      - `server/tests/test_incident_repo.py`: 6 unit and tenant-isolation tests covering new incident upsert, recurring failure deduplication, retrieval by ID and fingerprint, cross-tenant rejection (`ForbiddenError`), filtering, resolution update, and deletion.
      - All 13 steps in `scripts/test-all.mjs --fast` passed.

### Documentation — M12-13: Milestone 12.2 Documentation Update & Operational Runbook

- **Date**: 2026-11-01
- **Branch**: `feature/m12-mentor-docs`
- **What**:
  - Implemented comprehensive operational runbook and documentation update for Milestone 12.2 (Project Mentor & Project Evaluation, CAP-08, CAP-09):
    - **Operational Runbook (`docs/runbooks/project-mentor-and-evaluation.md`)**:
      - Subsystem architecture overview: TaskDAG topological sorting, priority weighting, Kahn's algorithm, cycle prevention, ProjectMentor specialist agent; multidimensional scoring engine, OQ-18 functionality checklist audit, and release readiness verdicts.
      - Architecture diagrams in Mermaid for task dependency sorting and multidimensional health evaluation pipelines.
      - Data model and schema definitions for `project_tasks`, `project_task_dependencies`, and `project_evaluations`.
      - Operational procedures for dependency cycle triage and resolution, release blocker diagnosis, and triggering evaluations (CLI `eval:mentor`, REST API, and Web UI Screen S-17).
      - Structured logging, telemetry conventions, RFC 9457 error code troubleshooting table (`conflict.state`, `validation.failed`, `resource.not_found`, `auth.forbidden`, `llm.unavailable`).
      - Verification benchmarks table reflecting 100.0% composite score recorded baseline.
    - **Documentation Updates**:
      - `docs/03-data-model-and-api.md`: Updated Status and §11.1 endpoint families table with task backlog and evaluation REST endpoints.
      - `docs/09-testing-and-quality-strategy.md`: Registered Project Mentor & Health Evaluation evaluation baseline (M12-12) in §9 recorded baselines table and added `eval:mentor` to §13 commands table.
      - `docs/10-deployment-and-operations.md`: Added runbook cross-reference in §18 operational playbooks.
      - `docs/11-mvp-and-implementation-roadmap.md`: Updated roadmap status to Release 1.3 Complete, marked Milestone M12.2 as Complete with runbook link, and set M12.3 dependencies.
      - `PLAN.md`: Marked M12-13 `[x]` and expanded detailed task breakdown for M12.3 (Release 1.4: Deployment Diagnosis, M12-14 through M12-18).
    - **Verification**:
      - `node scripts/docs-links.mjs`: Scanned 64 Markdown files, validated 969 links & anchors, 40 Mermaid diagrams, 50 ADRs, and 18 OQs (clean pass).
      - Monorepo fast verification suite (`node scripts/test-all.mjs --fast` passing 13/13).

### Feature — M12-12: Mentor & Evaluation Benchmark Suite, Evaluators & E2E Tests

- **Date**: 2026-11-01
- **Branch**: `feature/m12-mentor-evals`
- **What**:
  - Implemented evaluation suite, benchmarks, and end-to-end integration tests for Project Mentor & Project Evaluation (CAP-08, CAP-09, [`docs/01`](docs/01-product-requirements.md) §8, [`docs/03`](docs/03-data-model-and-api.md) §3.6, §3.7, [`docs/05`](docs/05-agents-and-llm-workflows.md) §6.8):
    - **Benchmark Dataset (`evals/mentor/dataset.json`)**:
      - 7 realistic task recommendation benchmark test cases covering linear chains, multiple independent tasks, priority overrides, branching prerequisites, blocked tasks, fully unblocked sets, and cyclic dependency attempts.
      - 7 health evaluation benchmark test cases covering pristine MVP projects, critical security blockers, moderate velocity drift, multiple architectural blockers, missing checklist items, and low/high confidence levels.
    - **Benchmark Metrics (`evals/mentor/metrics.py`)**:
      - `TaskRecommendationMetrics`: Computes top-1 recommendation accuracy, Mean Reciprocal Rank (MRR), and ready-task execution alignment.
      - `ProjectEvaluationMetrics`: Computes release readiness verdict accuracy, blocker precision/recall/F1 score, and health dimension score MAE (Mean Absolute Error).
      - `MentorBenchmarkSummary`: Aggregates all recommendation and audit metrics into an overall composite benchmark score.
    - **Evaluation Harness Runner (`evals/mentor/harness.py`, `evals/mentor/__init__.py`)**:
      - Self-contained CLI runner evaluating TaskDAG topological ranking, cycle detection, and multidimensional health evaluations.
      - Recorded baseline in `evals/results/mentor/latest.json` (100.00% composite score: Top-1 Acc=100%, MRR=1.00, Verdict Acc=100%, Blocker F1=100%).
    - **Unit & E2E Integration Tests**:
      - `server/tests/test_mentor_eval.py`: 5 unit tests validating dataset loading, recommendation metrics, evaluation metrics, and harness runner execution.
      - `server/tests/test_mentor_e2e.py`: 3 comprehensive integration tests testing the complete HTTP API lifecycle (`/api/v1/projects/{project_id}/tasks`, `/recommend`, `/dependencies`, `/evaluations/run`, `/evaluations/latest`) and LangGraph specialist agent dispatch (`run_mentor_specialist`).
    - **Monorepo Integration**:
      - Added `eval:mentor` command to root `package.json` (`server/.venv/bin/python evals/mentor/harness.py`).
      - Verified full monorepo fast suite (`node scripts/test-all.mjs --fast` passing 13/13).

### Feature — M12-11: Web Screens for Project Mentor & Project Evaluation

- **Date**: 2026-10-31
- **Branch**: `feature/m12-mentor-ui`
- **What**:
  - Implemented Screen S-17 (Project Mentor & Health Evaluation) per [`docs/01`](docs/01-product-requirements.md) §8 (CAP-08, CAP-09), [`docs/08`](docs/08-ui-ux-design-specification.md), and [`docs/03`](docs/03-data-model-and-api.md) §3.6, §3.7:
    - **API Client Layer (`common/src/api/index.ts`)**:
      - Exported types `ProjectTaskResponse`, `ProjectTaskCreate`, `ProjectTaskUpdate`, `TaskDependencyCreate`, `TaskDependencyResponse`, `TaskRecommendationResponse`, `ProjectEvaluationResponse`, `ProjectEvaluationRunRequest`.
      - Added 12 typed methods to `DevMindApiClient` for task backlog CRUD, dependency graph manipulation, next-task recommendation queries, and evaluation triggers/lookups.
    - **Navigation & Command Palette**:
      - Added `MentorIcon` to `client/components/shell/icons.tsx`.
      - Added "Project Mentor & Health (S-17)" navigation link to `AppGutterRail.tsx` and quick jump to `CommandPalette.tsx`.
    - **Page Route (`client/app/projects/[projectId]/tasks/page.tsx`)**:
      - Implemented project tasks & evaluation route with clean async server loading and metadata.
    - **Mentor Components (`client/components/mentor/`)**:
      - `MentorPageClient.tsx`: Tabbed view (`Backlog & Recommendation`, `Dependency Graph (DAG)`, `Health Scorecard & Radar`, `Release Blockers`), quick action toolbar, stats counters, state management with API error resilience.
      - `MentorRecommendationSpotlight.tsx`: Hero card highlighting next unblocked priority task, mentor narrative, rank, impact count, and quick status actions.
      - `TaskBacklogTable.tsx`: Full backlog table with text search, status and priority filters, inline status toggles, link prerequisite modals, and deletion.
      - `TaskDAGViewer.tsx`: Topological graph visualizer rendering tasks grouped by execution tier/level, cycle detection status badges, and prerequisite relationship tags.
      - `HealthScorecardView.tsx`: Health audit view with overall score meter (/100), release-readiness verdict badge, mentor narrative box, and 6 dimension scorecards with progress bars and weights.
      - `BlockersAndWarningsList.tsx`: Dedicated tab for active release blockers, quality/documentation warnings, and positive health strengths.
      - `CreateTaskModal.tsx`: Accessible dialog for adding new backlog tasks with priority and optional prerequisite dependencies.
      - `LinkDependencyModal.tsx`: Modal for managing incoming prerequisite dependencies on tasks.
      - `TaskDetailModal.tsx`: Detailed drawer/dialog for editing title, description, priority, and viewing dependency lists.
    - **Tests & Verification**:
      - Authored `client/tests/mentor-ui.test.tsx` (7 Vitest tests covering rendering of recommendation spotlight, backlog table, DAG viewer, health scorecard, blockers list, and create modal).
      - Verified `pnpm --filter client build` (Turbopack static optimization + typecheck) passed cleanly.
      - Verified `pnpm --filter client test` (30 test files, 198 tests passed).
      - Verified `node scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped).

### Feature — M12-10: Project Mentor Specialist Agent, Routing, and REST Endpoints

- **Date**: 2026-10-31
- **Branch**: `feature/m12-mentor-agent`
- **What**:
  - Implemented M12-10 per [`docs/01`](docs/01-product-requirements.md) §8 (CAP-08, CAP-09), [`docs/03`](docs/03-data-model-and-api.md) §3.6, §3.7, and [`docs/05`](docs/05-agents-and-llm-workflows.md) §6.8:
    - **LLM Tasks & Prompts**:
      - Registered `mentor_recommendation` and `project_evaluation_narrative` in `server/configs/llm/tasks.yaml`.
      - Authored versioned prompt templates `server/app/llm/prompts/mentor_recommendation/v1.md` and `server/app/llm/prompts/project_evaluation_narrative/v1.md`.
      - Registered schemas `MentorRecommendationOutput` and `ProjectEvaluationNarrativeOutput` in `server/app/llm/schemas.py`.
    - **Specialist Agent (`server/app/orchestration/mentor.py`)**:
      - `ProjectMentorAgent`: Deterministic TaskDAG next-task recommendation unblocking analysis and multidimensional project health evaluations.
      - Implemented `run_mentor_specialist` node runner supporting `recommend` and `evaluate` actions within LangGraph workflows.
      - Fallback deterministic narratives when LLM gateway is offline or unavailable.
    - **Orchestration Integration (`server/app/orchestration/manager.py`)**:
      - Added `"mentor"` to `RELEASED_SPECIALISTS`.
      - Deterministic intent classification for job types (`task_recommendation`, `mentor`, `project_mentor`, `next_task`, `project_evaluation`, `release_readiness`) and user prompts.
      - Integrated `mentor_node_factory`, conditional edges, and join barrier in `build_agent_manager_graph`.
    - **Domain Service (`server/app/domain/mentor/service.py`)**:
      - `ProjectMentorService`: Full task CRUD, cycle-checked dependency linking, next task recommendations, on-demand evaluation execution, and scorecard retrieval.
    - **REST API Endpoints (`server/app/api/mentor.py`)**:
      - `GET /api/v1/projects/{project_id}/tasks` (`PERM_PROJECT_READ`)
      - `POST /api/v1/projects/{project_id}/tasks` (`PERM_PROJECT_UPDATE`)
      - `GET /api/v1/projects/{project_id}/tasks/recommend` (`PERM_PROJECT_READ`)
      - `GET /api/v1/projects/{project_id}/tasks/{task_id}` (`PERM_PROJECT_READ`)
      - `PATCH /api/v1/projects/{project_id}/tasks/{task_id}` (`PERM_PROJECT_UPDATE`)
      - `DELETE /api/v1/projects/{project_id}/tasks/{task_id}` (`PERM_PROJECT_UPDATE`)
      - `POST /api/v1/projects/{project_id}/tasks/{task_id}/dependencies` (`PERM_PROJECT_UPDATE`, returns 409 on cycle)
      - `DELETE /api/v1/projects/{project_id}/tasks/{task_id}/dependencies/{depends_on_task_id}` (`PERM_PROJECT_UPDATE`)
      - `GET /api/v1/projects/{project_id}/evaluations` (`PERM_PROJECT_READ`)
      - `POST /api/v1/projects/{project_id}/evaluations/run` (`PERM_ANALYSIS_CREATE`)
      - `GET /api/v1/projects/{project_id}/evaluations/latest` (`PERM_PROJECT_READ`)
      - `GET /api/v1/projects/{project_id}/evaluations/{evaluation_id}` (`PERM_PROJECT_READ`)
      - Mounted `mentor_router` on `/api/v1` in `server/app/main.py`.
    - **OpenAPI Schema & TypeScript Client**:
      - Exported OpenAPI schema (103 paths) and regenerated `@devmind/common` (`common/src/api/schema.d.ts`).
    - **Unit & Integration Tests**:
      - `server/tests/test_mentor_agent.py`: 5 tests covering empty backlog, DAG ranking with dependencies, LLM narrative generation, evaluation health scoring persistence, and specialist node execution.
      - `server/tests/test_mentor_api.py`: 3 tests covering task CRUD, next task recommendation, dependency cycle prevention (409 Conflict), and project evaluation lifecycle.
- **Verification**: `node scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped). Linting clean (`ruff check`). Formatting clean (`ruff format`). Import boundaries clean (7/7 contracts maintained). Pytest: 8/8 mentor tests passed, 17/17 DAG & scoring tests passed.

### Feature — M12-09: Evaluation Scoring Engine and Release Blockers Synthesis

- **Date**: 2026-10-31
- **Branch**: `feature/m12-eval-scoring`
- **PR**: [#102](https://github.com/Warish-Labs/DevMind/pull/102)
- **What**:
  - Implemented M12-09 per [`docs/01`](docs/01-product-requirements.md) §8 (CAP-09), [`docs/03`](docs/03-data-model-and-api.md) §3.7, and [`docs/12`](docs/12-architecture-decisions-and-open-questions.md) (OQ-18):
    - **Deterministic Scoring Engine (`server/app/analysis/eval_scoring.py`)**:
      - `ProjectEvaluationScorer`: Computes normalized rubric scores (0.0 to 100.0) across 6 weighted dimensions: Security (0.25), Code Quality (0.20), Testing (0.20), Documentation (0.15), Functionality (0.10), Architecture (0.10).
      - **Security Dimension**: Penalizes open/confirmed vulnerabilities (-35 for CRITICAL, -20 for HIGH, -10 for MEDIUM, -3 for LOW). Dismissed and fixed findings do not degrade score.
      - **Code Quality Dimension**: Evaluates review violations and recurring unresolved errors from Bug Memory (severe bugs >= 10 occurrences penalize quality and block release).
      - **Testing Dimension**: Evaluates CI pass rate, penalizing failed test suites (-25 per failed test) and flagging blockers for any failing test.
      - **Documentation Dimension**: Evaluates Living Docs drift status, penalizing active undocumented routes (-12) and ghost routes (-8).
      - **Functionality Dimension (OQ-18)**: Evaluates user-declared feature checklists; defaults with labeled `"low"` confidence when no declared checklist is available, and `"high"` confidence when declared, with incomplete critical features triggering blockers.
      - **Architecture Dimension**: Evaluates task dependency DAG health, detecting circular dependencies (-35 and blocker) and blocked backlog tasks.
      - **Release Readiness Verdict**: Deterministically classifies projects into `ready` (>= 85.0 with zero blockers), `ready_with_warnings` (70.0 - 85.0 or open warnings), or `not_ready` (< 70.0 or any critical blocker).
      - **Blockers & Indicators Synthesis**: Generates structured blocker diagnostics (`id`, `dimension`, `title`, `severity`, `detail`), warning notices, and positive health indicators.
    - **Unit Tests (`server/tests/test_eval_scoring.py`)**:
      - 9 comprehensive unit tests verifying clean project readiness, critical security blockers, dismissed/fixed finding immunity, severe recurring bug penalties, test failure blocking, documentation drift warnings, OQ-18 functionality confidence states, cyclic architecture blocker, and composite weighted score precision.
- **Verification**: `node scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped). Linting clean (`ruff check`). Formatting clean (`ruff format`). Import boundaries clean (7/7 contracts maintained). Pytest: 9/9 evaluation scoring tests passed (0 warnings).

### Feature — M12-08: Project Mentor & Evaluation Data Models, Migrations, Repositories, and DAG Sorter

- **Date**: 2026-10-31
- **Branch**: `feature/m12-mentor-core`
- **PR**: [#101](https://github.com/Warish-Labs/DevMind/pull/101)
- **What**:
  - Implemented M12-08 per [`docs/01`](docs/01-product-requirements.md) §8 (CAP-08, CAP-09), [`docs/03`](docs/03-data-model-and-api.md) §3.6, §3.7, and [`docs/11`](docs/11-mvp-and-implementation-roadmap.md) §6 (M12.2):
    - **Persistence Models (`server/app/persistence/models/mentor.py`)**:
      - `ProjectTask`: developer or agent work item with UUIDv7 PK, tenant scoping (`workspace_id`, `project_id`), status (`open`, `in_progress`, `blocked`, `completed`, `cancelled`), priority (`critical`, `high`, `medium`, `low`), source, linked finding ID, JSONB metadata, and self-referential many-to-many relationship (`dependencies` / `dependents`).
      - `TaskDependency`: explicit DAG edge table with composite PK (`task_id`, `depends_on_task_id`), cascade deletes, and reverse indexing.
      - `ProjectEvaluation`: release-readiness and multidimensional health evaluation with composite `overall_score`, JSONB `dimension_scores` (functionality, code_quality, security, testing, documentation, architecture), `verdict` (`ready`, `ready_with_warnings`, `not_ready`), `blockers`, `warnings`, `positive_indicators`, and snapshot/evaluator relationships.
      - Exported models via `app.persistence.models.__init__`.
    - **Alembic Migration (`server/alembic/versions/0017_project_mentor_and_evaluations.py`)**:
      - Authored schema migration introducing `project_tasks`, `task_dependencies`, and `project_evaluations` with UUIDv7 primary keys, tenant scoping, foreign keys with CASCADE/SET NULL, and performance indexes.
    - **Topological Task DAG Sorter (`server/app/analysis/task_dag.py`)**:
      - Deterministic topological dependency sorting via Kahn's algorithm.
      - Cycle prevention with `CyclicDependencyError` (detecting self-dependencies, direct 2-node cycles, and arbitrary multi-hop circular paths).
      - Transitive downstream impact counter calculating unblocking blast radius.
      - Priority- and readiness-aware task ranking: ready unblocked tasks strictly precede blocked tasks, with weighting across priority, finding severity, downstream impact bonus, and FIFO temporal tie-breaking.
    - **Repositories**:
      - `ProjectTaskRepository` (`server/app/persistence/repositories/project_task_repo.py`): Task CRUD, status/priority filtering, pre-commit cycle validation before edge insertion, and in-memory DAG loading.
      - `ProjectEvaluationRepository` (`server/app/persistence/repositories/project_eval_repo.py`): Persisting evaluations, latest evaluation retrieval by project, historical list pagination, and tenant isolation.
      - Re-exported via `app.persistence.repositories.__init__`.
    - **Comprehensive Test Suite**:
      - `server/tests/test_task_dag.py` (8 tests): linear sorting, diamond DAGs, self-dependency rejection, 2-node cycle rejection, multi-hop cycle rejection, ready vs blocked ranking, priority/severity weighting, completed task exclusion.
      - `server/tests/test_mentor_repo.py` (7 tests): task creation and retrieval with relationships, update/delete lifecycle, dependency cycle rejection, self-dependency rejection, task multi-tenant isolation, evaluation creation and latest retrieval, and evaluation cross-tenant isolation.
      - Updated `test_migrations.py` and `test_restore_drill.py` with the new migration head `0017_project_mentor_and_evaluations`.
- **Verification**: `node scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped). Linting clean (`ruff check`). Formatting clean (`ruff format`). Import boundaries clean (7/7 contracts maintained). Pytest: 15/15 mentor unit tests passed, 878 total server tests passed.

### Feature — M12-07: Milestone 12.1 Documentation Update and Operational Runbook

- **Date**: 2026-10-31
- **Branch**: `feature/m12-docs`
- **PR**: [#100](https://github.com/Warish-Labs/DevMind/pull/100)
- **What**:
  - Implemented M12-07 concluding Milestone 12.1 (Release 1.2: Bug Memory & Living Documentation):
    - **Operational Runbook**: Authored [`docs/runbooks/bug-memory-and-living-docs.md`](docs/runbooks/bug-memory-and-living-docs.md) covering subsystem architecture, normalization/deduplication data flow, state machine transitions, operational playbooks (high-volume error surges, documentation drift backlog triage, reversing erroneous doc patches, and multi-tenant isolation verification), and regression evaluation gates.
    - **Deployment & Operations**: Updated [`docs/10-deployment-and-operations.md`](docs/10-deployment-and-operations.md) §18 referencing the new operational runbook for Bug Memory deduplication surges and DocsAlive drift triage.
    - **Testing & Quality Strategy**: Updated [`docs/09-testing-and-quality-strategy.md`](docs/09-testing-and-quality-strategy.md) §9 with recorded evaluation baselines for Bug Memory and Living Docs (Composite Score: 1.0000, 100% Top-1, 100% Recall@3, MRR: 1.0000, 100% Patch Diff Validity). Added `npm run eval:bug-docs` and `npm run eval:pr` commands in §14.2.
    - **Roadmap & Milestones**: Updated [`docs/11-mvp-and-implementation-roadmap.md`](docs/11-mvp-and-implementation-roadmap.md) marking Release 1.2 (Milestone 12.1) complete and linking runbook.
    - **Roadmap Expansion**: Updated [`PLAN.md`](PLAN.md) marking M12.1 complete and expanding Milestone 12.2 (Release 1.3: Project Mentor & Project Evaluation, CAP-08, CAP-09) into tasks M12-08 through M12-13.
- **Verification**: `node scripts/docs-links.mjs` (All 61 Markdown files, 935 links/anchors, 39 Mermaid diagrams, 50 ADRs, 18 OQ references verified valid).

### Feature — M12-06: Integration Tests, Evaluation Benchmark Datasets, and Recorded Baselines for Bug Memory and Living Docs

- **Date**: 2026-10-31
- **Branch**: `feature/m12-bug-docs-evals`
- **PR**: [#99](https://github.com/Warish-Labs/DevMind/pull/99)
- **What**:
  - Implemented M12-06 per [`docs/01`](docs/01-product-requirements.md) §7 (CAP-03, CAP-04), [`docs/03`](docs/03-data-model-and-api.md) §3.4, §3.5, and [`docs/09`](docs/09-testing-and-quality-strategy.md) §9:
    - **Benchmark Dataset (`evals/bug_docs/dataset.json`)**: Curated 12 comprehensive benchmark cases:
      - 6 Bug Memory cases covering exact fingerprint deduplication, timeout trace normalization, TypeError with variable hex memory pointers, network connection trace extraction, validation error matching, and zero-match negative rejection.
      - 6 Living Documentation drift cases covering missing symbol detection, removed route detection, undocumented active route drift, stale document section drift, compound multi-drift extraction, and zero-drift negative baseline.
    - **Evaluation Metrics Module (`evals/bug_docs/metrics.py`)**: Authored metric calculations for Bug Memory (Top-1 accuracy, Recall@3, MRR, fingerprint deduplication accuracy, negative rejection rate) and Living Docs (drift candidate precision, recall, F1-score, patch diff validity).
    - **Benchmark Runner (`evals/bug_docs/harness.py`)**: Created end-to-end evaluation harness verifying normalization, retrieval, drift detection, and deterministic patch generation with baseline recording in `evals/results/bug_docs/latest.json`.
    - **Monorepo Package Scripts**: Added `"eval:bug-docs"` and `"eval:pr"` to `package.json`.
    - **Unit & Regression Tests (`server/tests/test_bug_docs_eval.py`)**: 5 unit tests validating dataset schema, bug case evaluation, drift evaluation, metric aggregations, and result serialization.
    - **E2E Integration Tests (`server/tests/test_e2e_bug_memory.py` & `server/tests/test_e2e_living_docs.py`)**:
      - `test_e2e_bug_memory_lifecycle`: full lifecycle from raw error trace -> normalization -> duplicate occurrence increment -> hybrid matching -> resolution attachment.
      - `test_e2e_bug_memory_multi_tenant_isolation`: verifies cross-workspace tenant boundaries return 404 NotFoundError.
      - `test_e2e_living_docs_lifecycle_and_approval_gate`: full lifecycle from document registration -> drift detection -> approval gate enforcement (409 Conflict when unapproved) -> rejection -> approval -> patch application.
      - `test_e2e_living_docs_multi_tenant_isolation`: verifies multi-tenant isolation returns 404 NotFoundError.
- **Verification**: `node scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped). `eval:bug-docs` (Composite 1.0, 100% Top-1, 100% Recall, 100% Patch Diff Validity). Linting clean (`ruff check`). Formatting clean (`ruff format`). Import boundaries clean (7/7 contracts maintained).

### Feature — M12-05: Web Screens for Bug Memory and Living Docs

- **Date**: 2026-10-31
- **Branch**: `feature/m12-bug-docs-ui`
- **PR**: [#98](https://github.com/Warish-Labs/DevMind/pull/98)
- **What**:
  - Implemented M12-05 per [`docs/01`](docs/01-product-requirements.md) §7 (CAP-03, CAP-04), [`docs/03`](docs/03-data-model-and-api.md) §3.4, §3.5, §11, and [`docs/08`](docs/08-ui-ux-design-specification.md) (Screen S-15 Bug Memory & Screen S-16 Living Docs):
    - **API Client Extensions**: Added typed methods in `common/src/api/index.ts` for Bug Memory (`listProjectBugs`, `createBug`, `matchSimilarBugs`, `getBugDetail`, `addBugResolution`) and Living Documentation (`listProjectDocs`, `registerProjectDoc`, `getProjectDoc`, `detectDocDrift`, `listProjectDriftItems`, `getDriftItem`, `approveDriftProposal`, `rejectDriftProposal`, `applyDriftPatch`).
    - **Navigation & Icons**: Added `BugIcon` and `BookOpenIcon` in `client/components/shell/icons.tsx`. Added S-15 `/projects/[projectId]/bugs` and S-16 `/projects/[projectId]/docs` to `client/components/shell/AppGutterRail.tsx` and quick commands in `client/components/shell/CommandPalette.tsx`.
    - **Bug Memory Web Screen (S-15)** (`client/app/projects/[projectId]/bugs/page.tsx` & `client/components/bugs/`):
      - `ErrorMatcherPanel.tsx`: Interactive error input, trace normalization, candidate search, AI explanation, past resolution steps, and files.
      - `BugsTable.tsx`: List of tracked bug records with filters, occurrence count badge, fingerprint hash, and actions ("Inspect", "+ Resolution").
      - `BugDetailModal.tsx`: Inspection modal displaying full error signature, fingerprint, raw error snippet, and historical resolutions.
      - `AddResolutionModal.tsx`: Submission modal for recording root cause, fix summary, and modified files.
      - `LogBugModal.tsx`: Modal for registering new recurring bug traces.
      - `BugsPageClient.tsx`: Root client page coordinating state, API fetching, and modals.
    - **Living Documentation & DocsAlive Web Screen (S-16)** (`client/app/projects/[projectId]/docs/page.tsx` & `client/components/living-docs/`):
      - `DriftItemsTable.tsx`: Review table with drift kind badges, status pills, and "Review Proposal" triggers.
      - `TrackedDocsTable.tsx`: Inventory of registered Markdown docs with hashes and "Inspect" triggers.
      - `PatchApprovalModal.tsx`: Human approval gate modal with color-coded unified diff viewer (`+` green, `-` red, `@@` ref), proposed markdown body preview, and approval gate controls (`status == "detected"` -> Approve/Reject; `status == "approved"` -> Apply Patch to Documentation).
      - `DocDetailModal.tsx`: Extracted route/code symbols inspection and snapshot viewer.
      - `RegisterDocModal.tsx`: Modal for registering Markdown files.
      - `LivingDocsPageClient.tsx`: Root client coordinating tabs ("Drift Review & Patch Proposals" vs "Tracked Documentation Files"), drift detection trigger, and modals.
    - **Comprehensive Test Coverage**:
      - `client/tests/bugs-ui.test.tsx` (6 tests).
      - `client/tests/living-docs-ui.test.tsx` (7 tests).
- **Verification**: `node scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped). Client Vitest 29/29 files passed, 191/191 tests passed. Root & client TypeScript clean (0 errors).

### Feature — M12-04: DocsAlive Specialist Agent, Patch Proposal Generator, and Human Approval Gates

- **Date**: 2026-10-31
- **Branch**: `feature/m12-docs-alive-agent`
- **PR**: [#97](https://github.com/Warish-Labs/DevMind/pull/97)
- **What**:
  - Implemented M12-04 per [`docs/01`](docs/01-product-requirements.md) §7 (CAP-04), [`docs/03`](docs/03-data-model-and-api.md) §3.5, §11.2, and [`docs/05`](docs/05-agents-and-llm-workflows.md) §6.7:
    - **LLM Configuration & Prompts**: Registered `doc_patch_proposal` task in `server/configs/llm/tasks.yaml`, registered `DocPatchProposal` Pydantic model in `server/app/llm/schemas.py`, and authored prompt template in `server/app/llm/prompts/doc_patch_proposal/v1.md`.
    - **DocsAlive Specialist Agent**: Implemented `DocsAliveAgent` in `server/app/orchestration/docsalive.py` providing deterministic patch synthesis via `difflib.unified_diff`, LLM generation with fallback, approval gating (`status == "approved"`), rejection, and patch application (`apply_patch`).
    - **Agent Manager Integration**: Registered `docsalive` in `RELEASED_SPECIALISTS`, integrated intent classification and LangGraph workflow routing in `server/app/orchestration/manager.py`.
    - **Domain Service & Schemas**: Implemented `LivingDocService` in `server/app/domain/living_docs/service.py` with multi-tenant scoping, Markdown registration, drift detection, proposal retrieval, approval, rejection, and patch application.
    - **REST API Endpoints**: Created `server/app/api/living_docs.py` exposing:
      - `GET /api/v1/projects/{project_id}/docs`
      - `POST /api/v1/projects/{project_id}/docs`
      - `POST /api/v1/projects/{project_id}/docs/detect-drift`
      - `GET /api/v1/projects/{project_id}/docs/drift`
      - `GET /api/v1/projects/{project_id}/docs/{doc_id}`
      - `GET /api/v1/docs/drift/{drift_id}`
      - `POST /api/v1/docs/drift/{drift_id}/approve`
      - `POST /api/v1/docs/drift/{drift_id}/reject`
      - `POST /api/v1/docs/drift/{drift_id}/apply`
        Updated `server/app/main.py` and exported OpenAPI schema to `common/openapi.json` (94 paths) and generated TypeScript types.
    - **Test Coverage**: Added `server/tests/test_docsalive_agent.py` (5 tests) and `server/tests/test_living_docs_api.py` (5 tests) covering deterministic diffs, LLM patch synthesis, approval/rejection lifecycle, 409 conflict when applying unapproved patches, and cross-workspace multi-tenant isolation.
- **Verification**: `node scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped). Linting clean (`ruff check`). Formatting clean (`ruff format`). Import boundaries clean (7/7 contracts maintained).

### Feature — M12-03: Living Documentation Schema, Migration, Doc Parser, and Symbol Drift Detector

- **Date**: 2026-10-31
- **Branch**: `feature/m12-living-docs-core`
- **PR**: [#96](https://github.com/Warish-Labs/DevMind/pull/96)
- **What**:
  - Implemented M12-03 per [`docs/01`](docs/01-product-requirements.md) §7 (CAP-04), [`docs/03`](docs/03-data-model-and-api.md) §3.5, §11.2, and [`docs/05`](docs/05-agents-and-llm-workflows.md) §6.7:
    - **Alembic Migration**: Authored `server/alembic/versions/0016_living_documentation.py` introducing `documentation_records` and `doc_drift_items` with UUIDv7 primary keys, tenant scoping (`workspace_id`, `project_id`), JSONB payload fields, and foreign key cascades.
    - **Persistence Models**: Added `DocumentationRecord` and `DocDriftItem` in `server/app/persistence/models/living_documentation.py` exported through `models/__init__.py`.
    - **Deterministic Doc Parser**: Created `server/app/analysis/doc_parser.py` extracting headings, doc sections, HTTP route specifications (`METHOD /path`), and code symbols (`function`, `class`, `interface`, `def`) with code block awareness.
    - **Deterministic Drift Detector**: Authored `server/app/analysis/doc_drift_detector.py` analyzing documentation against actual codebase symbols, OpenAPI/REST routes, and config keys to pinpoint missing symbols, removed routes, or signature drift without LLM invocations.
    - **Repository Layer**: Added `LivingDocRepository` in `server/app/persistence/repositories/living_doc_repo.py` supporting document indexing, drift item tracking, filtering by drift type and status (`detected`, `approved`, `rejected`, `applied`), and status mutations.
    - **Test Coverage**: Added `server/tests/test_living_docs.py` (5 tests covering Markdown sectioning, route/symbol extraction, drift detection, and repository CRUD). Updated `test_migrations.py` and `test_restore_drill.py` to assert head revision `0016_living_documentation` and tables `documentation_records`, `doc_drift_items`.
- **Verification**: `node scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped). Linting clean (`ruff check server`). Formatting clean (`ruff format server`). Import boundaries clean (7/7 contracts maintained).

### Feature — M12-02: Bug Memory Hybrid Similarity Search, Specialist Agent, and REST Endpoints

- **Date**: 2026-10-31
- **Branch**: `feature/m12-bug-memory-agent`
- **PR**: [#95](https://github.com/Warish-Labs/DevMind/pull/95)
- **What**:
  - Implemented M12-02 per [`docs/01`](docs/01-product-requirements.md) §7 (CAP-03), [`docs/03`](docs/03-data-model-and-api.md) §3.4, §11.1, and [`docs/05`](docs/05-agents-and-llm-workflows.md) §6.6:
    - **Hybrid Similarity Search**: Added `search_similar_bugs` in `BugRecordRepository` combining exact SHA-256 fingerprint matching (score 1.0), token Jaccard overlap on error signatures, titles, and summaries, and module hint priority scoring.
    - **LLM Task & Prompt**: Added `bug_similarity_explanation` task in `server/configs/llm/tasks.yaml`, registered `BugSimilarityExplanation` schema in `server/app/llm/schemas.py`, and authored prompt template in `server/app/llm/prompts/bug_similarity_explanation/v1.md`.
    - **Specialist Agent**: Authored `BugMemoryAgent` in `server/app/orchestration/bug_memory.py` coordinating normalization, candidate search, AI similarity comparison, historical resolution derivation, and resolution proposal formulation. Added `bugmemory` to `RELEASED_SPECIALISTS` in Agent Manager.
    - **Domain Service & Schemas**: Authored `BugMemoryService` in `server/app/domain/bug_memory/service.py` with full CRUD, occurrence incrementing, resolution management, and tenant scoping. Authored request/response schemas in `server/app/domain/bug_memory/schemas.py`.
    - **REST API Endpoints**: Created `server/app/api/bug_memory.py` exposing:
      - `GET /api/v1/projects/{project_id}/bugs`
      - `POST /api/v1/projects/{project_id}/bugs`
      - `POST /api/v1/projects/{project_id}/bugs/match`
      - `GET /api/v1/bugs/{bug_id}`
      - `POST /api/v1/bugs/{bug_id}/resolutions`
        Included router in `server/app/main.py`. Exported updated OpenAPI schema to `common/openapi.json`.
    - **Test Coverage**: Added `server/tests/test_bug_memory_agent.py` (5 tests) and `server/tests/test_bug_memory_api.py` (5 tests) verifying exact matching, fuzzy fallback, LLM comparison synthesis, zero-match behavior, resolution proposals, API endpoints, and cross-workspace multi-tenant isolation.
- **Verification**: `node scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped). Linting 100% clean (`ruff check`). Formatting 100% clean (`ruff format`). Import boundaries clean (7/7 contracts maintained).

### Feature — M12-01: Bug Memory Foundation, Schema, Migration, and Error Normalizer

- **Date**: 2026-10-31
- **Branch**: `feature/m12-bug-memory-core`
- **PR**: [#94](https://github.com/Warish-Labs/DevMind/pull/94)
- **What**:
  - Implemented M12-01 per [`docs/01`](docs/01-product-requirements.md) §7 (CAP-03), [`docs/03`](docs/03-data-model-and-api.md) §3.4, and [`docs/05`](docs/05-agents-and-llm-workflows.md) §6.6:
    - **Alembic Migration**: Authored `server/alembic/versions/0015_bug_memory.py` adding `bug_records` and `bug_resolutions` tables with UUIDv7 primary keys, tenant constraints (`workspace_id`, `project_id`), fingerprint indexes, and cascading foreign keys.
    - **Persistence Models**: Added `BugRecord` and `BugResolution` in `server/app/persistence/models/bug_memory.py`, registered in `models/__init__.py`.
    - **Deterministic Error Normalizer**: Authored `ErrorNormalizer` in `server/app/analysis/error_normalizer.py` extracting canonical signatures, normalized module hints, and SHA-256 fingerprints while stripping ephemeral memory addresses, timestamps, UUIDs, and absolute paths for Python and JavaScript/TypeScript stack traces.
    - **Repository Layer**: Authored `BugRecordRepository` in `server/app/persistence/repositories/bug_record_repo.py` supporting `record_bug` with duplicate detection and occurrence counter increment, `add_resolution`, fingerprint lookup, and multi-tenant scoping.
    - **Testing**: Added `server/tests/test_bug_memory.py` (11 unit/isolation tests), updated `server/tests/test_migrations.py` and `server/tests/test_restore_drill.py` verifying Alembic head `0015_bug_memory` and database table inventory.
- **Verification**: `node scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped). Linting 100% clean (`ruff check`). Import boundaries clean (7/7 contracts maintained).

### Feature — M11-09: Milestone 11 Documentation Update and Operational Runbook

- **Date**: 2026-10-31
- **Branch**: `feature/m11-docs`
- **What**:
  - Implemented M11-09 per [`docs/01`](docs/01-product-requirements.md) §9 (CAP-05, CAP-06), [`docs/10`](docs/10-deployment-and-operations.md) §11, §18, and [`docs/11`](docs/11-mvp-and-implementation-roadmap.md) M11-09:
    - **Operational Runbook**: Authored [`docs/runbooks/github-integration-and-pr-intelligence.md`](docs/runbooks/github-integration-and-pr-intelligence.md) covering:
      - GitHub OAuth App setup & repository binding.
      - Webhook ingestion architecture (`/api/v1/webhooks/github`) with HMAC-SHA256 signature verification & delivery deduplication.
      - Webhook secret rotation procedure and zero-downtime rolling restart.
      - GitHub OAuth client secret rotation procedure.
      - Webhook delivery failure triage & manual replay (via GitHub UI and CLI/curl).
      - GitHub API rate limit mitigation and AST caching.
      - Emergency kill switch activation (`DEVMIND_KILL_WEBHOOKS=true`).
      - Resend transactional email domain verification (`warishlabs.in`), free tier quota management (3,000/mo, 100/day per ADR-046), and offline mock fallback.
      - Stale invitation cleanup queries and immutable structured audit log events (`workspace.invitation.*`, `pr.analysis.*`, `pr.comment.approved`).
    - **Automated Runbook Testing**: Updated [`server/tests/test_operational_runbooks.py`](server/tests/test_operational_runbooks.py) to validate `github-integration-and-pr-intelligence.md` inventory presence, required procedural sections, and security invariants (6/6 tests passing).
    - **Governing Documentation Updates**:
      - [`docs/00-documentation-index.md`](docs/00-documentation-index.md): Updated status to reflect Milestone 11 as fully implemented, tested, and validated.
      - [`docs/01-product-requirements.md`](docs/01-product-requirements.md): Marked CAP-05 (Code Review Intelligence) and CAP-06 (Pull Request Intelligence) as implemented in M11 with test and eval citations; noted human approval gate enforcement for PR comments (ADR-015).
      - [`docs/03-data-model-and-api.md`](docs/03-data-model-and-api.md): Updated schema tables (`workspace_invitations`, `review_rules`, `github_credentials`, `github_repository_bindings`, `pull_requests`, `pr_analyses`) to M11 implementation status; documented review rules and GitHub/PR API endpoints.
      - [`docs/05-agents-and-llm-workflows.md`](docs/05-agents-and-llm-workflows.md): Updated status to include M11 agents; expanded §6.4 (ReviewBuddy) and §6.5 (PRAgent) detailing diff parsing, checklist rule engine, change-impact blast radius traversal, and human approval gates.
      - [`docs/07-security-privacy-and-threat-model.md`](docs/07-security-privacy-and-threat-model.md): Updated status with GitHub envelope encryption, webhook signature verification, Resend token hashing, and test citations.
      - [`docs/09-testing-and-quality-strategy.md`](docs/09-testing-and-quality-strategy.md): Updated status; added PR Intelligence & ReviewBuddy Evaluation benchmark results (Composite Score: 1.0000); documented E2E-9 multi-agent integration test.
      - [`docs/10-deployment-and-operations.md`](docs/10-deployment-and-operations.md): Updated status; added `DEVMIND_EMAIL_FROM` and `DEVMIND_APP_BASE_URL` environment variables; linked operational runbook.
      - [`docs/11-mvp-and-implementation-roadmap.md`](docs/11-mvp-and-implementation-roadmap.md): Updated status to Release 1.1 Complete; marked all 10 M11 tasks as completed with evidence links.
      - [`server/.env.example`](server/.env.example): Added `DEVMIND_EMAIL_FROM` and `DEVMIND_APP_BASE_URL`.
      - [`PLAN.md`](PLAN.md): Marked M11-09 as completed `[x]`.
    - **Verification**:
      - `npm run docs:audit`: 889 links & anchors, 37 Mermaid diagrams, 50 ADRs, 18 OQ references, 10 brand assets valid.
      - `pytest server/tests/test_operational_runbooks.py`: 6 passed.
- **Branch**: `feature/m11-tests-evals`
- **What**:
  - Implemented M11-08 per [`docs/01`](docs/01-product-requirements.md) CAP-05, CAP-06, [`docs/09`](docs/09-testing-and-quality-strategy.md) §9, §14 (E2E-9), and [`docs/11`](docs/11-mvp-and-implementation-roadmap.md) M11-08:
    - **Webhook Replay Fixtures & Delivery Idempotency**:
      - Authored [`server/tests/test_webhook_replay.py`](server/tests/test_webhook_replay.py) (6 tests) covering full GitHub event lifecycle:
        - `ping` event deduplication and `pong` response.
        - PR lifecycle state transitions (`opened` -> `synchronize` updating head SHA -> `closed` with timestamps).
        - `push` commit counting and ref tracking.
        - `installation` and `installation_repositories` additions/removals.
        - Security tampering rejection (tampered payload HMAC mismatch returning 401).
        - Malformed JSON body validation rejection (400/422).
    - **E2E Integration Testing (E2E-9)**:
      - Authored [`server/tests/test_e2e_pr_intelligence.py`](server/tests/test_e2e_pr_intelligence.py) (4 tests) covering:
        - Full multi-agent PR intelligence flow: Webhook PR ingest -> PR mirroring -> PRAgent change-impact analysis -> ReviewBuddy checklist engine -> PRSummary and ChangeImpactReport synthesis -> persistence.
        - Cross-tenant isolation rejection (Tenant B actor querying Tenant A PR rejected with `NotFoundError`).
        - Human-in-the-loop approval gate enforcement (PR comment posting gated behind explicit human approval per ADR-015 and docs/01 §15).
        - GitHub OAuth token revocation/outage resilience (graceful handling without server crash).
    - **Evaluation Benchmark Suite**:
      - Created `evals/pr_intelligence/` suite with:
        - [`evals/pr_intelligence/dataset.json`](evals/pr_intelligence/dataset.json): 5 change-impact cases (critical auth, migration addition, docs-only, webhook router, formatter utility) and 5 ReviewBuddy cases (unvalidated inputs, bare excepts, missing auth, custom forbidden patterns, 100% compliant route).
        - [`evals/pr_intelligence/metrics.py`](evals/pr_intelligence/metrics.py): quantitative precision, recall, F1, risk accuracy, false positive rate, and composite scoring.
        - [`evals/pr_intelligence/harness.py`](evals/pr_intelligence/harness.py): benchmark runner and results persistence to [`evals/results/pr_intelligence/latest.json`](evals/results/pr_intelligence/latest.json).
        - [`server/tests/test_pr_eval.py`](server/tests/test_pr_eval.py) (5 tests): benchmark schema integrity, case execution, and baseline quality gates (Change-Impact: 100%, ReviewBuddy: 100% precision/recall, 0.00% FP rate, 100% composite score).
    - **Engine Bug Fixes & Refinements**:
      - Fixed `PRAgentService.analyze_pull_request` diff fetch accessing non-existent `repo_binding.workspace_id` (corrected to `project.workspace_id`).
      - Enhanced `parse_unified_diff` in `server/app/analysis/review_buddy.py` to parse patch diffs formatted with standard `--- / +++` headers without requiring leading `diff --git`.
    - **Verification**:
      - 15/15 M11-08 tests passed in pytest.
      - 812/812 total server tests passed.
      - `node scripts/test-all.mjs --fast`: 13 passed, 0 failed, 1 skipped.
      - `npm run docs:audit`: 849 links, 37 Mermaid diagrams valid.

### Feature — M11-07: Workspace Invitations via Resend, Token Verification, Acceptance, and Audit Logging

- **Date**: 2026-10-31
- **Branch**: `feature/m11-invitations-audit`
- **What**:
  - Implemented M11-07 per [`docs/01`](docs/01-product-requirements.md) FR-PLT-05, [`docs/03`](docs/03-data-model-and-api.md) §3.1, §3.5, §11.1, [`docs/07`](docs/07-security-privacy-and-threat-model.md) §6, [`docs/10`](docs/10-deployment-and-operations.md) §11, and [`docs/12`](docs/12-architecture-decisions-and-open-questions.md) ADR-014:
    - **Confirmed ADR-014**: Documented adoption of Resend transactional email (free tier, 3,000/mo) on `warishlabs.in` with SHA-256 token hashing and immutable audit logging.
    - **Database Migration**: Created [`server/alembic/versions/0014_workspace_invitations.py`](server/alembic/versions/0014_workspace_invitations.py) introducing `workspace_invitations` table with role check constraint (`admin`, `member`, `viewer`), unique `token_hash`, and cascade constraints.
    - **Persistence Model**: Authored [`server/app/persistence/models/workspace_invitation.py`](server/app/persistence/models/workspace_invitation.py) (`WorkspaceInvitation`) and exported in [`server/app/persistence/models/__init__.py`](server/app/persistence/models/__init__.py).
    - **Repository Layer**: Authored [`server/app/persistence/repositories/workspace_invitation_repo.py`](server/app/persistence/repositories/workspace_invitation_repo.py) (`WorkspaceInvitationRepository`) providing tenant isolation, active invitation lookup by email, token hash lookup, acceptance marking, and deletion.
    - **Resend Client**: Authored [`server/app/domain/email/resend_client.py`](server/app/domain/email/resend_client.py) (`ResendEmailClient`) implementing async email dispatch with clean HTML/text invitation templates and simulated offline mock fallback.
    - **Domain Service**: Authored [`server/app/domain/workspaces/invitation_service.py`](server/app/domain/workspaces/invitation_service.py) (`WorkspaceInvitationService`) implementing cryptographically secure 32-byte URL-safe token generation, SHA-256 hashing, 7-day expiration, conflict detection, public token verification preview, authenticated acceptance with `WorkspaceMembership` creation, and audit logging (`workspace.invitation.created`, `workspace.invitation.revoked`, `workspace.invitation.accepted`).
    - **REST API Endpoints**:
      - `GET /api/v1/workspaces/{id}/invitations` (`PERM_WORKSPACE_READ`)
      - `POST /api/v1/workspaces/{id}/invitations` (`PERM_MEMBERS_MANAGE_WORKSPACE`)
      - `DELETE /api/v1/workspaces/{id}/invitations/{invitation_id}` (`PERM_MEMBERS_MANAGE_WORKSPACE`)
      - `GET /api/v1/invitations/verify` (`PERMISSION_PUBLIC`)
      - `POST /api/v1/invitations/accept` (`PERMISSION_AUTHENTICATED`)
    - **API Client Extensions**: Authored [`common/src/api/index.ts`](common/src/api/index.ts) models (`WorkspaceInvitationItem`, `CreateInvitationRequest`, `CreateInvitationResponse`, `VerifyInvitationResponse`, `AcceptInvitationRequest`, `AcceptInvitationResponse`) and methods on `DevMindApiClient`.
    - **Web UI**:
      - Authored [`client/components/workspaces/WorkspaceMembersManager.tsx`](client/components/workspaces/WorkspaceMembersManager.tsx) for managing workspace members, viewing pending invitations, copying links, revoking invites, and opening the "Invite Member" dialog.
      - Integrated "Members & Invites" tab into [`client/components/settings/ProjectSettingsClient.tsx`](client/components/settings/ProjectSettingsClient.tsx).
      - Authored dedicated page [`client/app/workspaces/[workspaceId]/settings/page.tsx`](client/app/workspaces/[workspaceId]/settings/page.tsx).
      - Authored accept page [`client/app/invitations/accept/page.tsx`](client/app/invitations/accept/page.tsx) and [`client/components/invitations/AcceptInvitationClient.tsx`](client/components/invitations/AcceptInvitationClient.tsx).
    - **Tests & Verification**:
      - Authored [`server/tests/test_workspace_invitations.py`](server/tests/test_workspace_invitations.py) (9 tests covering mock dispatch, lifecycle, conflicts, expired tokens, RBAC, API endpoints).
      - Authored [`client/tests/workspace-invitations-ui.test.tsx`](client/tests/workspace-invitations-ui.test.tsx) (3 tests covering members manager, pending invites, and accept invitation client).
      - Verified `test-all --fast`: 13 passed, 0 failed, 1 skipped.
      - Verified `npm run docs:audit`: 0 broken links.

### Feature — M11-06: Pull Request Web Screens (List, Overview, Change-Impact Graph, Checklist Triage)

- **Date**: 2026-10-30
- **Branch**: `feature/m11-pr-ui`
- **What**:
  - Implemented M11-06 per [`docs/01`](docs/01-product-requirements.md) §9 (CAP-06), [`docs/02`](docs/02-system-architecture.md) §10, [`docs/03`](docs/03-data-model-and-api.md) §3.5 and §11.1, [`docs/08`](docs/08-ui-ux-design-specification.md) (Screen S-14):
    - **API Client Extensions**: Authored Pull Request and PR Analysis methods and models in [`common/src/api/index.ts`](common/src/api/index.ts) (`listProjectPullRequests`, `syncProjectPullRequests`, `getPullRequest`, `analyzePullRequest`, `getLatestPullRequestAnalysis`, `listPullRequestAnalyses`, `listProjectReviewRules`, `PullRequestSummary`, `ChangeImpactReport`, `PRAnalysisResponse`, `ReviewRuleResponse`). Built and verified with `pnpm --filter common test` (8/8 passed).
    - **App Shell & Navigation**:
      - Added `GitPullRequestIcon` in [`client/components/shell/icons.tsx`](client/components/shell/icons.tsx).
      - Added "Pull Requests & Impact (S-14)" navigation item in [`client/components/shell/AppGutterRail.tsx`](client/components/shell/AppGutterRail.tsx).
      - Added section breadcrumbs and mobile menu entry in [`client/components/shell/AppTopBar.tsx`](client/components/shell/AppTopBar.tsx).
      - Added quick navigation entry in [`client/components/shell/CommandPalette.tsx`](client/components/shell/CommandPalette.tsx).
    - **Pull Request List Views**:
      - Authored [`client/components/pull-requests/PullRequestsTable.tsx`](client/components/pull-requests/PullRequestsTable.tsx) showing PR number, title, branches, status badge, author avatar/initials, head commit SHA, and inspect action.
      - Authored [`client/components/pull-requests/PullRequestsPageClient.tsx`](client/components/pull-requests/PullRequestsPageClient.tsx) with live GitHub sync button, state filtering (All, Open, Merged, Closed), text query search, and error banners.
      - Authored route [`client/app/projects/[projectId]/pull-requests/page.tsx`](client/app/projects/[projectId]/pull-requests/page.tsx).
    - **Pull Request Detail & Intelligence Views**:
      - Authored [`client/components/pull-requests/PRSummaryPanel.tsx`](client/components/pull-requests/PRSummaryPanel.tsx) rendering PRAgent executive summary, risk badge, security assessment, testing concerns, affected areas, and changed files.
      - Authored [`client/components/pull-requests/ChangeImpactGraph.tsx`](client/components/pull-requests/ChangeImpactGraph.tsx) displaying blast radius metrics, node filtering (symbols, routes, tests, modules), and graph relationship inspection.
      - Authored [`client/components/pull-requests/ChecklistTriageTab.tsx`](client/components/pull-requests/ChecklistTriageTab.tsx) displaying ReviewBuddy checklist findings grouped by category, evidence levels (E1), and inline verify/dismiss triage actions.
      - Authored [`client/components/pull-requests/PullRequestDetailClient.tsx`](client/components/pull-requests/PullRequestDetailClient.tsx) coordinating PR overview, change impact, review checklist tabs, and the "Trigger PRAgent" action.
      - Authored route [`client/app/projects/[projectId]/pull-requests/[prId]/page.tsx`](client/app/projects/[projectId]/pull-requests/[prId]/page.tsx).
    - **Tests & Verification**:
      - Authored [`client/tests/pull-requests-ui.test.tsx`](client/tests/pull-requests-ui.test.tsx) with 8 component and integration tests.
      - Verified `pnpm --filter client test`: 26 test files passed, 175 tests passed.
      - Verified `node scripts/test-all.mjs --fast`: 13 passed, 0 failed, 1 skipped.
      - Verified `npm run docs:audit`: 0 broken links.

### Feature — M11-05: PRAgent Change-Impact Analysis, Subgraph Traversal, and PR Intelligence

- **Date**: 2026-10-28
- **Branch**: `feature/m11-pr-agent`
- **What**:
  - Implemented M11-05 per [`docs/01`](docs/01-product-requirements.md) §9 (CAP-06), [`docs/02`](docs/02-system-architecture.md) §10, [`docs/03`](docs/03-data-model-and-api.md) §3.5 and §11.1, [`docs/05`](docs/05-agents-and-llm-workflows.md) §6.5:
    - **Database Migration**: Created [`server/alembic/versions/0013_pr_analyses.py`](server/alembic/versions/0013_pr_analyses.py) adding `pr_analyses` table with foreign keys to `workspaces`, `projects`, `pull_requests`, and `analysis_jobs`, with unique constraint on `(pull_request_id, head_sha, job_id)`.
    - **Persistence Model**: Authored [`server/app/persistence/models/pr_analysis.py`](server/app/persistence/models/pr_analysis.py) (`PRAnalysis`) and exported in [`server/app/persistence/models/__init__.py`](server/app/persistence/models/__init__.py).
    - **Repository Layer**: Authored [`server/app/persistence/repositories/pr_analysis_repo.py`](server/app/persistence/repositories/pr_analysis_repo.py) (`PRAnalysisRepository`) providing tenant isolation, CRUD, latest analysis lookup, and historical listing.
    - **Change-Impact Analysis Engine**: Authored [`server/app/analysis/change_impact.py`](server/app/analysis/change_impact.py) (`ChangeImpactAnalyzer`) traversing direct symbols, callers, importers, affected routes, affected tests, and building dependency graph nodes/edges with categorical risk assessment (`low`, `medium`, `high`, `critical`). Exported in [`server/app/analysis/__init__.py`](server/app/analysis/__init__.py).
    - **PRAgent Specialist**: Authored [`server/app/orchestration/pragent.py`](server/app/orchestration/pragent.py) (`PRAgent`, `PRAgentState`, `run_pragent_specialist`) integrating change impact traversal, ReviewBuddy diff evaluation, evidence verification (E1), PR summary synthesis, and gated GitHub comment proposals. Registered `pragent` in `RELEASED_SPECIALISTS`, intent classifier, and graph workflow in [`server/app/orchestration/manager.py`](server/app/orchestration/manager.py).
    - **Domain Service & Schemas**: Authored [`server/app/domain/pr_agent/schemas.py`](server/app/domain/pr_agent/schemas.py) and [`server/app/domain/pr_agent/service.py`](server/app/domain/pr_agent/service.py).
    - **REST API Endpoints**: Registered `POST /api/v1/pull-requests/{id}/analyze`, `GET /api/v1/pull-requests/{id}/analyses/latest`, and `GET /api/v1/pull-requests/{id}/analyses` with RBAC permissions (`analysis:create`, `project:read`) in [`server/app/api/integrations.py`](server/app/api/integrations.py).
    - **Tests & Verification**: Authored [`server/tests/test_pr_agent.py`](server/tests/test_pr_agent.py) with 11 tests; verified 13 passed in `test-all --fast` (0 lint errors, 0 broken import boundaries, 46 targeted tests passing).

### Feature — M11-04: Review Rules Schema, Migration, and ReviewBuddy Checklist Engine

- **Date**: 2026-10-28
- **Branch**: `feature/m11-review-rules`
- **What**:
  - Implemented M11-04 per [`docs/01`](docs/01-product-requirements.md) §9 (CAP-05, CAP-06), [`docs/03`](docs/03-data-model-and-api.md) §3.5 and §11.1, [`docs/05`](docs/05-agents-and-llm-workflows.md) §2.3 and §3, [`docs/07`](docs/07-security-privacy-and-threat-model.md) §6:
    - **Database Migration**: Created [`server/alembic/versions/0012_review_rules.py`](server/alembic/versions/0012_review_rules.py) adding `review_rules` table with tenant columns (`workspace_id`, `project_id`), category and severity check constraints, and unique rule index `(project_id, rule_id)`.
    - **Persistence Model**: Authored [`server/app/persistence/models/review_rules.py`](server/app/persistence/models/review_rules.py) and exported in [`server/app/persistence/models/__init__.py`](server/app/persistence/models/__init__.py).
    - **Repository Layer**: Authored [`server/app/persistence/repositories/review_rule_repo.py`](server/app/persistence/repositories/review_rule_repo.py) providing tenant isolation, CRUD operations, default built-in rule seeding (`seed_default_rules`), and deletion restrictions on built-ins.
    - **In-Repo Rules Parser**: Authored [`server/app/domain/review/parser.py`](server/app/domain/review/parser.py) supporting `.devmind/rules.yaml` parsing with strict Pydantic validation.
    - **ReviewBuddy Analyzer Engine**: Authored [`server/app/analysis/review_buddy.py`](server/app/analysis/review_buddy.py) implementing deterministic rule evaluation, unified diff hunk line scoping, and built-in detectors (input validation, bare excepts, mutating route permissions, test coverage, and regex patterns).
    - **Domain Service & API Endpoints**:
      - Authored [`server/app/domain/review/service.py`](server/app/domain/review/service.py) coordinating rule persistence and diff evaluation.
      - Authored [`server/app/api/review_rules.py`](server/app/api/review_rules.py) mounted under `/api/v1/projects/{pid}/review-rules` with RBAC permissions (`project:read`, `project:update`).
    - **LangGraph Specialist Integration**:
      - Authored [`server/app/orchestration/reviewbuddy.py`](server/app/orchestration/reviewbuddy.py) integrating ReviewBuddy with evidence verification (E0/E1).
      - Registered `reviewbuddy` in `RELEASED_SPECIALISTS`, `classify_intent_rule_based`, `route_specialists`, and the state graph in [`server/app/orchestration/manager.py`](server/app/orchestration/manager.py).
    - **Tests & Verification**:
      - Authored [`server/tests/test_review_rules.py`](server/tests/test_review_rules.py) with 14 unit and integration tests.
      - Updated `test_agent_manager.py` fanout assertions.
      - Verified: 13 passed in `test-all --fast`, 0 lint errors, 0 import boundary breaches.

### Feature — M11-03: GitHub Repository Ingestion, Webhook Receiver, and PR Mirroring

- **Date**: 2026-10-27
- **Branch**: `feature/m11-webhooks-ingest`
- **What**:
  - Implemented M11-03 per [`docs/01`](docs/01-product-requirements.md) §9 (CAP-05, CAP-06), [`docs/03`](docs/03-data-model-and-api.md) §3.5 and §11.1, [`docs/07`](docs/07-security-privacy-and-threat-model.md) §6, [`docs/10`](docs/10-deployment-and-operations.md) §11.1, and [`docs/12`](docs/12-architecture-decisions-and-open-questions.md) (ADR-015):
    - **Database Migration**: Created [`server/alembic/versions/0011_github_repositories_and_prs.py`](server/alembic/versions/0011_github_repositories_and_prs.py) adding `github_repositories` and `pull_requests` tables, indexed on `workspace_id`, `project_id`, `full_name`, and `number`.
    - **Persistence Models**: Added `GitHubRepositoryBinding` and `PullRequest` in [`server/app/persistence/models/github.py`](server/app/persistence/models/github.py) and exported in [`server/app/persistence/models/__init__.py`](server/app/persistence/models/__init__.py).
    - **Repository Layer**: Extended [`server/app/persistence/repositories/github_repo.py`](server/app/persistence/repositories/github_repo.py) with `link_repository`, `get_repository_by_project`, `get_repository_by_full_name`, `unlink_repository`, `upsert_pull_request`, `get_pull_request`, and `list_pull_requests`.
    - **Ingestion & Webhook Services**:
      - Authored [`server/app/domain/integrations/github_ingest_service.py`](server/app/domain/integrations/github_ingest_service.py) supporting repository linking/unlinking, PR listing, PR detail retrieval, and manual live sync from GitHub REST API.
      - Updated [`server/app/domain/webhooks/github_webhook_service.py`](server/app/domain/webhooks/github_webhook_service.py) to automatically ingest and mirror incoming `pull_request` webhook payloads into PostgreSQL with robust error handling and delivery deduplication.
    - **API Routes**:
      - Registered routes in [`server/app/api/integrations.py`](server/app/api/integrations.py) and mounted in [`server/app/main.py`](server/app/main.py):
        - `POST /api/v1/projects/{pid}/github/link`
        - `DELETE /api/v1/projects/{pid}/github/unlink`
        - `GET /api/v1/projects/{pid}/github/repository`
        - `GET /api/v1/projects/{pid}/pull-requests`
        - `POST /api/v1/projects/{pid}/pull-requests/sync`
        - `GET /api/v1/pull-requests/{id}`
      - Declared required permissions (`PERM_INTEGRATIONS_MANAGE` and `PERM_INTEGRATIONS_READ`) on all routes.
    - **Tests & Migration Parity**:
      - Authored [`server/tests/test_github_ingest.py`](server/tests/test_github_ingest.py) (8 tests passing).
      - Updated `server/tests/test_github_webhook.py` with mock session injection (5 tests passing).
      - Updated head revisions in `test_migrations.py`, `test_restore_drill.py`, `test_health.py`, and `test_staging_promotion.py`.
  - Validated full test suite via `scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped) and `npm run docs:audit` (0 broken links, 0 ADR/OQ errors).

### Feature — M11-02: GitHub OAuth Linking, Encrypted Credential Repository, and Token Management

- **Date**: 2026-10-27
- **Branch**: `feature/m11-oauth-tokens`
- **What**:
  - Implemented M11-02 per [`docs/03`](docs/03-data-model-and-api.md) §3.5 and §11.1, [`docs/07`](docs/07-security-privacy-and-threat-model.md) §6, [`docs/10`](docs/10-deployment-and-operations.md) §11.1, and [`docs/12`](docs/12-architecture-decisions-and-open-questions.md) (ADR-015):
    - Extended [`server/app/persistence/repositories/github_repo.py`](server/app/persistence/repositories/github_repo.py):
      - Added `get_connection_by_id` with strict workspace tenancy scoping (preventing cross-tenant IDOR).
      - Added `get_decrypted_token` for authenticated and authorized operations, securely retrieving and decrypting AES-256-GCM credential envelopes without ever logging or exposing plaintext secrets.
      - Added `rotate_credential` enabling zero-downtime key rotation: decrypts legacy envelopes encrypted under secondary keys and re-encrypts under the current primary key (`v1:0:`).
    - Enhanced [`server/app/domain/integrations/github_oauth_service.py`](server/app/domain/integrations/github_oauth_service.py):
      - Integrated audit event logging for all sensitive credential lifecycle transitions via `AuditEventRepository` (`integration.github.connected`, `integration.github.revoked`, `integration.github.rotated`).
      - Added `get_connection_status` evaluating active, degraded, revoked, expired, and unlinked states with resolution hints and analysis readiness.
      - Added `rotate_connection_credential` wrapper with audit event emission.
    - Updated [`server/app/api/integrations.py`](server/app/api/integrations.py) and [`docs/03-data-model-and-api.md`](docs/03-data-model-and-api.md) §11.1:
      - Added `GET /api/v1/workspaces/{wid}/integrations/github/status` returning `GitHubConnectionStatusSummary`.
      - Added `POST /api/v1/workspaces/{wid}/integrations/github/rotate` triggering credential re-encryption.
      - Enforced `@declare_permission(PERM_INTEGRATIONS_MANAGE)` on all routes.
    - Created unit, isolation, key rotation, and API integration tests in [`server/tests/test_github_token_management.py`](server/tests/test_github_token_management.py) (8 tests passing; 46 total tests across crypto, github, and route permissions suites).
  - Validated full test suite via `scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped) and `npm run docs:audit` (0 broken links, 0 ADR/OQ errors).

### Feature — M11-01: GitHub Permissions Review, Encrypted Token Storage Spec, and ADR-015 Update

- **Date**: 2026-10-27
- **Branch**: `feature/m11-permissions-adr15`
- **What**:
  - Implemented M11-01 per [`docs/01`](docs/01-product-requirements.md) §9 (CAP-05, CAP-06), [`docs/07`](docs/07-security-privacy-and-threat-model.md) §6, [`docs/10`](docs/10-deployment-and-operations.md) §11.1, and [`docs/11`](docs/11-mvp-and-implementation-roadmap.md) §M11:
    - Updated [`docs/12-architecture-decisions-and-open-questions.md`](docs/12-architecture-decisions-and-open-questions.md) confirming ADR-015 and resolving OQ-11:
      - Established the dual-tier integration architecture: Tier 1 GitHub OAuth for developer identity linking (`read:user`, `user:email`), Tier 2 GitHub App installation for granular repository permissions (`pull_requests:read`, `contents:read`, `metadata:read`) and webhook events.
      - Mandated AES-256-GCM envelope encryption (`DEVMIND_ENCRYPTION_KEYS`) for stored installation and user credentials in Neon, with multi-key rotation and zero plaintext secrets in logs, database dumps, or API errors.
      - Defined HMAC-SHA256 signature verification (`X-Hub-Signature-256`) and 24-hour LRU delivery deduplication for webhook events.
      - Documented permission degradation protocol and RFC 9457 error classification (`integration.github.permission_denied`, `integration.github.token_revoked`, `integration.github.rate_limited`).
      - Confirmed strict prohibition of unapproved external side effects (automated PR commenting or auto-merging strictly forbidden; human approval gate enforced).
    - Updated [`docs/03-data-model-and-api.md`](docs/03-data-model-and-api.md) §10.1 adding stable error codes for GitHub permission denied, token revoked, signature invalid, and rate limited.
    - Implemented [`server/app/domain/integrations/github_permissions.py`](server/app/domain/integrations/github_permissions.py) defining permission matrices, forbidden scopes rejection, degradation evaluator, human approval gate checker, and RFC 9457 error mapping.
    - Enhanced [`server/app/domain/webhooks/github_webhook_service.py`](server/app/domain/webhooks/github_webhook_service.py) with lifecycle handlers for `installation` and `installation_repositories` events.
    - Created comprehensive contract test suite [`server/tests/test_github_permissions_contract.py`](server/tests/test_github_permissions_contract.py) covering 18 test cases (36 total tests across crypto and github suites).
  - Validated full test suite via `scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped) and `npm run docs:audit` (0 broken links, 0 ADR/OQ errors).

### Feature — M13-06: MVP Release Checklist, Release Notes, and Known Limitations Ledger

- **Date**: 2026-10-27
- **Branch**: `feature/m13-release-checklist`
- **What**:
  - Implemented the official MVP Release Checklist, launch protocol, release notes, and known limitations ledger per [`docs/01`](docs/01-product-requirements.md) §17, [`docs/09`](docs/09-testing-and-quality-strategy.md) §15, [`docs/10`](docs/10-deployment-and-operations.md) §17, and [`docs/11`](docs/11-mvp-and-implementation-roadmap.md) §M13:
    - Authored [`docs/runbooks/release-checklist.md`](docs/runbooks/release-checklist.md) establishing the 7-phase pre-flight, cloud topology, distribution, smoke test, and rollback procedure for v0.1.0.
    - Updated repository root [`CHANGELOG.md`](CHANGELOG.md) documenting `[0.1.0] - 2026-10-27` release with all core functional pillars (CAP-01 Project Brain, CAP-02 SecuritySentinel, Web application shell, VS Code companion extension, FastAPI/Celery backend, test runners).
    - Recorded the official **Known Limitations Ledger** (Language Tiers 1 vs 2, zero live DB connections per ADR-034, no in-extension AI chat, evidence grounding tiers E0–E3, and free-tier sleep behavior).
    - Added automated unit tests in [`client/tests/release-checklist.test.ts`](client/tests/release-checklist.test.ts) (3 tests passing).
  - Validated full test suite via `scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped).

### Feature — M13-05: Documentation Consistency, Broken Link, and Brand Audit

- **Date**: 2026-10-27
- **Branch**: `feature/m13-docs-audit`
- **What**:
  - Executed complete documentation and brand audit across `docs/00` through `docs/13`, `brand/BRAND-GUIDE.md`, and repository root markdown files:
    - Updated status headers in `AGENTS.md` and `docs/00` through `docs/12` to accurately reflect the completed and tested state of the MVP release (Milestones M1–M10, M13) while retaining post-MVP specifications for M11–M12 per [`docs/00`](docs/00-documentation-index.md) §7.
    - Enhanced `scripts/docs-links.mjs` into a comprehensive documentation auditor:
      - Validated all 724 relative links and anchor fragments across 56 Markdown files (0 broken).
      - Validated all 36 Mermaid diagram code blocks across all documents for supported diagram types (`flowchart`, `graph`, `sequenceDiagram`, `stateDiagram-v2`, `erDiagram`), balanced quote delimiters, and quoted parentheses in node brackets (0 syntax issues).
      - Verified that all 50 ADR citations across all documentation files match defined records in [`docs/12`](docs/12-architecture-decisions-and-open-questions.md).
      - Verified that all 18 Open Question citations (`OQ-01` to `OQ-18`) match defined records in [`docs/12`](docs/12-architecture-decisions-and-open-questions.md).
      - Verified critical brand identity assets inventory against `brand/BRAND-GUIDE.md` §7.
    - Added `"docs:audit": "node scripts/docs-links.mjs"` script target to root [`package.json`](package.json).
  - Validated full test suite via `scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped).

### Feature — M13-04: Extension Packaging & Marketplace Release Readiness

- **Date**: 2026-10-25
- **Branch**: `feature/m13-extension-packaging`
- **What**:
  - Prepared the VS Code companion extension for Visual Studio Marketplace and Open VSX release readiness per [`docs/06`](docs/06-vscode-extension-and-local-scanning.md) §18:
    - Added complete marketplace manifest metadata in [`extension/package.json`](extension/package.json) (`homepage`, `bugs`, `qna`, `keywords`, and gallery categorization).
    - Added dedicated pre-release packaging target script (`package:pre-release`) running `vsce package --pre-release --no-dependencies --out dist/devmind-vscode-pre-release.vsix`.
    - Created [`extension/CHANGELOG.md`](extension/CHANGELOG.md) adhering to Semantic Versioning and documenting v0.1.0 through v0.1.2 releases with full Known Limitations Ledger (Language tiers 1 & 2, zero live DB connections per ADR-034, and no in-extension AI chat).
    - Standardized license references to MIT in [`extension/README.md`](extension/README.md) and [`extension/package.json`](extension/package.json).
    - Expanded automated test coverage in [`extension/tests/quality.test.ts`](extension/tests/quality.test.ts) (80 passed across 15 test files).
    - Packaged and verified both stable (`dist/devmind-vscode.vsix`, 55.77 KB) and pre-release (`dist/devmind-vscode-pre-release.vsix`, 55.78 KB) bundles with zero dependencies.
  - Validated full test suite via `scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped).

### Feature — M13-03: Authenticated App Shell & Screen States Review

- **Date**: 2026-10-25
- **Branch**: `feature/m13-app-shell-polish`
- **What**:
  - Audited authenticated app shell and screen states across screens S-02 through S-12 per `docs/08` §10 and §11:
    - Verified desktop 56px gutter rail ([`AppGutterRail`](client/components/shell/AppGutterRail.tsx)), top bar ([`AppTopBar`](client/components/shell/AppTopBar.tsx)), status bar ([`AppStatusBar`](client/components/shell/AppStatusBar.tsx)), and global Cmd+K palette ([`CommandPalette`](client/components/shell/CommandPalette.tsx)).
    - S-03: Verified Project selection empty state ("Create your first project" with VS Code companion connect deep link).
    - S-05: Verified Project Brain explorer empty file selection state and `metadata_only` mode banner with source text redaction (ADR-034) and consent action.
    - S-06: Verified AI project conversation empty citations panel, clickable inline citations `[1]`, execution trace lines, and distinct insufficient evidence banner styling with suggested next steps.
    - S-07: Verified findings table empty states distinguishing unanalyzed projects ("Project not analyzed yet") from clean projects ("No security findings detected") and filtered results.
    - S-08: Verified finding detail triage modal with strict maintainer permission gate (disabled with error notice when not maintainer; enabled when maintainer).
    - S-09: Verified background jobs table empty state and floating job tray.
    - S-10: Added loading skeleton verification for [`ProjectSettingsLoading`](client/app/projects/[projectId]/settings/loading.tsx).
    - Expanded automated test coverage in [`client/tests/a11y-empty-error-loading.test.tsx`](client/tests/a11y-empty-error-loading.test.tsx) (12 passed).
  - Validated full test suite via `scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped).

### Feature — M13-02: Motion Polish, Custom Cursor & Keyboard Accessibility Pass

- **Date**: 2026-10-25
- **Branch**: `feature/m13-motion-a11y`
- **What**:
  - Audited motion tokens (`dur1` through `durStory`, `easeOut`, `easeIn`, `easeMove`) and smoothing math (`dampLerp`) in [`client/lib/motion/`](client/lib/motion/):
    - Verified magnetic attraction offset capping strictly `<= 8px` and RAF loop auto-pause after 1s of pointer inactivity to conserve GPU/CPU cycles.
    - Verified `@media (prefers-reduced-motion: reduce)` global overrides in [`client/app/tokens.css`](client/app/tokens.css) resetting animation/transition durations to 0.01ms.
    - Verified [`SequenceRunner`](client/lib/motion/sequence.ts) immediate execution bypass under reduced motion.
    - Verified WCAG 2.2 focus appearance ring (`2px solid var(--ref)` with `2px` offset) on interactive controls ([`Button`](client/components/ui/Button.tsx), [`Dialog`](client/components/ui/Dialog.tsx), [`CommandPalette`](client/components/shell/CommandPalette.tsx), [`Header`](client/components/layout/Header.tsx)).
    - Expanded automated test coverage in [`client/tests/cursor-motion.test.ts`](client/tests/cursor-motion.test.ts) (15 passed in 0.38s).
  - Validated full test suite via `scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped).

### Feature — M13-01: Public Homepage & Navigation Audit

- **Date**: 2026-10-25
- **Branch**: `feature/m13-homepage-audit`
- **What**:
  - Audited all 8 public homepage sections and the hero Trace component against `docs/08` §8 and §9:
    - Verified synchronization with single sources of truth in `common/data/` (`rule-catalog.json`, `release-status.json`, `privacy-ledger.json`, `capabilities.json`, `walkthrough.json`).
    - Verified all 8 section anchors (`#section-01` to `#section-08` and `#walkthrough`), brand logo, and header/footer navigation links.
    - Updated the Architecture Decision Record claim on `/early-access` from 47 to 49 to match ADR-001 through ADR-049 in [`docs/12-architecture-decisions-and-open-questions.md`](docs/12-architecture-decisions-and-open-questions.md).
    - Expanded [`client/tests/content-integrity.test.ts`](client/tests/content-integrity.test.ts) with automated tests verifying the exact ADR count matches `docs/12` and all 8 homepage section components are rendered in sequence.
  - Verified Next.js production build (`next build`) generating 14 static and 12 dynamic routes without error.
  - Ran full test suite via `scripts/test-all.mjs --fast` (13 passed, 0 failed, 1 skipped).

### Feature — M10-10: Staging Promotion Rehearsal & Release Verification

- **Date**: 2026-10-25
- **Branch**: `feature/m10-staging-rehearsal`
- **What**:
  - Authored and verified complete staging promotion protocol, pre-promotion smoke rehearsal, and rollback playbooks per docs/10 §2, §17, §22, docs/09 §15, ADR-046, and AGENTS.md:
    - **Staging Promotion Runbook** ([`docs/runbooks/staging-promotion.md`](docs/runbooks/staging-promotion.md)):
      - Documented the immutable container image promotion workflow (`DEVMIND_BUILD_SHA`).
      - Staging vs Production environment parity matrix under ADR-046 free-profile topology.
      - 5-phase promotion rehearsal lifecycle: (1) Build & Tag Image, (2) Deploy & Migrate Staging, (3) Automated Smoke Harness, (4) Human Approval Decision Gate (G1–G6 Quality Gates), (5) Production Zero-Downtime Rollout.
      - Emergency Rollback Rehearsal: Application code rollback, kill switch isolation, and Neon PITR database branch restoration.
    - **Automated Verification Suite** ([`server/tests/test_staging_promotion.py`](server/tests/test_staging_promotion.py)):
      - Validated runbook lifecycle completeness, rollback strategies, and G1–G6 Quality Gates.
      - Validated `Settings` behavior under staging (`DEVMIND_ENV=staging`, `is_production=False`) and production.
      - Verified `/readyz` probe contract under healthy dependencies and graceful degradation.
      - Tested synthetic staging smoke workflow: prompt template rendering, delimiter escaping, and structured schema conformance.
      - Validated backward-compatible Alembic migration expand-contract invariants for zero-downtime rollback safety (5 passed in 0.71s).
    - **Documentation & Cross-Links**:
      - Updated cross-links in [`docs/10-deployment-and-operations.md`](docs/10-deployment-and-operations.md) §17 and [`docs/runbooks/deploy-render-vercel.md`](docs/runbooks/deploy-render-vercel.md).
      - Verified documentation links across all 55 Markdown files via `scripts/docs-links.mjs` (720 links checked, 0 broken).

### Feature — M10-09: Threat-Model Review and Residual Risk Ledger Update

- **Date**: 2026-10-25
- **Branch**: `feature/m10-threat-model`
- **What**:
  - Completed comprehensive threat model audit and residual risk ledger update per docs/07 §17, §18, §20, docs/09 §11, and docs/11 M10-09:
    - **Threat Model Matrix Audit** ([`docs/07-security-privacy-and-threat-model.md`](docs/07-security-privacy-and-threat-model.md) §18):
      - Reviewed all 24 cataloged threats (T-01 through T-24) against implementation milestones, automated tests, and architectural boundaries.
      - Added explicit `Verification Evidence` column mapping each threat to its automated test suite (e.g. T-01 to `test_authz_matrix.py`, T-02 to `test_extension_auth.py`, T-03 to `test_injection_abuse.py` and 55-vector corpus, T-04 to `test_redaction.py`, T-08 to `test_queue_drills.py`).
      - Updated incident response playbooks section with direct links to [`docs/runbooks/incident-response.md`](docs/runbooks/incident-response.md), [`docs/runbooks/disaster-recovery.md`](docs/runbooks/disaster-recovery.md), and [`docs/runbooks/database-restore.md`](docs/runbooks/database-restore.md).
    - **Residual Risk Ledger** ([`docs/07-security-privacy-and-threat-model.md`](docs/07-security-privacy-and-threat-model.md) §20):
      - Expanded the summary into a structured, active **DevMind Residual Risk Ledger** covering the six principal residual risks:
        - `RR-01` (T-19): AI Provider Data Handling & Model Training Risk.
        - `RR-02` (T-04): Novel or Unrecognized Secret Formats escaping entropy/regex.
        - `RR-03` (T-03): Subtle Prompt-Induced Misleading Explanations.
        - `RR-04` (T-11): GitHub OAuth Scope Breadth on Private Repositories.
        - `RR-05` (T-01): Cross-Tenant Authorization Drift on Additive Endpoints.
        - `RR-06` (T-18): Provider Backup Retention Window Persistence.
      - Cataloged inherent severity, verified mitigations, accepted risk posture, ownership, review frequency, and kill switch safeguards for each risk.
    - **Automated Verification Suite** ([`server/tests/test_threat_model.py`](server/tests/test_threat_model.py)):
      - Automated pytest suite verifying catalog completeness (all 24 threats T-01 to T-24), verification evidence file existence (15+ test files verified), residual risk ledger completeness (RR-01 to RR-06), and playbook cross-links (4 passed in 0.08s).
      - Verified documentation links across all 54 Markdown files via `scripts/docs-links.mjs` (699 links checked, 0 broken).

### Feature — M10-08: Operational Runbooks and Disaster Recovery Playbooks

- **Date**: 2026-10-25
- **Branch**: `feature/m10-runbooks`
- **What**:
  - Authored and verified complete operational runbooks and playbooks per docs/10 §11, §16, §18, §21, §22, docs/07 §12, §17, and ADR-046:
    - **Incident Diagnosis & Response Playbooks** ([`docs/runbooks/incident-response.md`](docs/runbooks/incident-response.md)):
      - Standardized 4-tier incident severity matrix (SEV-1 to SEV-4) with response time objectives.
      - Core diagnostic and step-by-step remediation playbooks for all 5 failure modes:
        - Playbook 1: Worker stall, backpressure, and stranded task reaping (`sweep_stranded_jobs`).
        - Playbook 2: Retrieval degradation, provider rate-limit backpressure, pgvector vacuum/reindex, and keyword fallback.
        - Playbook 3: Real-time SSE disconnects, 15s keep-alive verification, and HTTP long-polling fallback.
        - Playbook 4: Cross-tenant isolation suspicion, emergency write freeze, and forensic log preservation.
        - Playbook 5: Duplicate task execution, atomic claim locks (`SKIP LOCKED`), and visibility timeout handling.
      - Subsystem kill switch catalog: `DEVMIND_KILL_INDEXING`, `DEVMIND_KILL_LLM`, `DEVMIND_KILL_EMBED`, `DEVMIND_KILL_WEBHOOKS`, `DEVMIND_PAUSE_QUEUES`.
    - **Disaster Recovery & Business Continuity** ([`docs/runbooks/disaster-recovery.md`](docs/runbooks/disaster-recovery.md)):
      - Scenario 1: Regional and host infrastructure outage (multi-AZ Paxos storage, secondary Render Blueprint deployment, Vercel edge CDN reroute).
      - Scenario 2: Corrupted or incompatible embedding space (pgvector index drop, batch re-embedding pipeline).
      - Scenario 3: Accidental destructive migration and database loss (Neon Point-In-Time Restore to branch, RTO < 5m, RPO window).
      - Scenario 4: Critical secret and token compromise (zero-downtime envelope encryption dual-key rollover, Clerk session revocation).
    - **Free-Tier Operations & Resource Quotas** ([`docs/runbooks/free-tier-operations.md`](docs/runbooks/free-tier-operations.md)):
      - Operational guidelines and mitigations under ADR-046 free-profile topology.
      - Render 15-minute idle spin-down, 50s-90s cold start tolerance, and 512 MB RAM ceiling (batch chunking $< 25$ MB).
      - Neon 5-minute auto-suspend, `pool_pre_ping=True`, and 512 MB storage quota.
      - Upstash Redis 10,000 cmd/day ceiling, daily consumption budget (~5,580 cmds/day), in-memory rate-limiter fallback, and SSE polling fallback.
    - **Automated Verification Suite** ([`server/tests/test_operational_runbooks.py`](server/tests/test_operational_runbooks.py)):
      - Automated pytest suite validating runbook file inventory, all 5 failure playbooks, 5 kill switches consistency with code and settings, disaster scenarios, and free quota alignment (5 passed in 0.10s).
      - Verified markdown documentation links and anchors across all 54 files via `scripts/docs-links.mjs` (661 links checked, 0 broken).

### Feature — M10-07: Prompt-Injection Corpus Expansion and Abuse Tests

- **Date**: 2026-10-25
- **Branch**: `feature/m10-injection-expansion`
- **What**:
  - Implemented prompt-injection corpus expansion, adversarial abuse test suite, and heuristic defense hardening per docs/05 §14, docs/07 §8, §10, §15, and docs/09 §12:
    - **Corpus Expansion** ([`evals/injection/corpus.json`](evals/injection/corpus.json)):
      - Expanded corpus from 25 to 55 test cases (45 adversarial injection vectors, 10 benign controls).
      - Added attack classes: BiDi directional control smuggling (`\u202e`), ChatML / Llama special token injection (`<|im_start|>`, `<<SYS>>`), fabricated closing tag collisions, unregistered tool invocations (`execute_bash`, `deploy`, `delete_all_data`), deep path traversals, multi-hop RAG retrieval poisoning, finding suppression gaslighting, base64/URL obfuscation, and oversized payload DoS.
    - **Prompt Loader Hardening** ([`server/app/llm/prompt_loader.py`](server/app/llm/prompt_loader.py)):
      - Enhanced `_INJECTION_PATTERNS` to detect BiDi control characters, special chat formatting tokens, finding suppression phrases, and cross-tenant exfiltration instructions.
      - Hardened `escape_untrusted_content` to neutralize ChatML tokens (`[sanitized_token]`), strip BiDi directional overrides (`[\u202a-\u202e\u2066-\u2069]`), and enforce `</untrusted_data>` delimiter neutralization.
    - **Harness & Benchmark Run** ([`evals/injection/harness.py`](evals/injection/harness.py)):
      - Enhanced comment normalization across multi-line payloads in AST checks.
      - Executed evaluation harness across all 55 cases: **100% pass rate** (55/55 passed; 0 failed).
      - Delimiter Integrity: 1.0000, Tool Containment: 1.0000, Finding Protection: 1.0000, Cross-Tenant Isolation: 1.0000, Schema Conformance: 1.0000.
    - **Abuse Test Suite** ([`server/tests/test_injection_abuse.py`](server/tests/test_injection_abuse.py)):
      - Automated 10 dedicated abuse tests validating delimiter breakout escaping, special token sanitization, BiDi override removal, forbidden tool containment, path traversal boundary quarantine, finding non-suppression, and 50KB+ oversized payload resilience.
    - **Documentation**:
      - Updated [`docs/09-testing-and-quality-strategy.md`](docs/09-testing-and-quality-strategy.md) §9 evaluation ledger with expanded corpus metrics.
      - Automated test suite: [`server/tests/test_injection_abuse.py`](server/tests/test_injection_abuse.py) (10 passed in 1.04s).
      - Architecture boundaries verified: `lint-imports` (7 kept, 0 broken).

---

## 4. Done log

### Feature — M10-06: Database Restore Drill & Runbook

- **Date**: 2026-10-25
- **Branch**: `feature/m10-restore-drill`
- **What**:
  - Implemented database point-in-time restore (PITR) verification, disaster recovery drills, and operational runbook per docs/10 §16, §21, §22, and ADR-046:
    - **Schema Inventory & Table Integrity Drill** ([`server/tests/test_restore_drill.py`](server/tests/test_restore_drill.py)):
      - Validated all 29 core database tables declared in `Base.metadata` matching Alembic migrations.
      - Confirmed each table has defined primary keys, foreign keys, indexes, and constraints.
      - Confirmed Alembic script directory has exactly 1 head revision (`0010_retention_policies`).
    - **Point-In-Time Snapshot & Restore Simulation** ([`server/tests/test_restore_drill.py`](server/tests/test_restore_drill.py)):
      - Simulated point-in-time snapshot and restore of tenant records (workspaces, projects, audit events).
      - Verified primary key integrity, foreign key relationship consistency, cross-tenant isolation (0 records returned for alien tenants), and cascading deletes (`ON DELETE CASCADE`).
    - **Post-Restore Reconciliation & Job Sweep** ([`server/tests/test_restore_drill.py`](server/tests/test_restore_drill.py)):
      - Simulated restoring a database containing in-flight jobs from 15 minutes prior.
      - Verified that `reap_stale_jobs` detects dead worker heartbeat timeouts and safely requeues running jobs back to `queued`.
      - Verified that `sweep_stranded_jobs` discovers all stranded jobs and prepares them for Celery re-dispatch.
    - **Connection Pool Switchover & Reconnection** ([`server/tests/test_restore_drill.py`](server/tests/test_restore_drill.py)):
      - Tested `close_db_engine()` cleanly disposing existing engine pools.
      - Tested clean initialization of new async connection pool pointing to the recovery database endpoint without connection leaks.
    - **Operational Runbook** ([`docs/runbooks/database-restore.md`](docs/runbooks/database-restore.md)):
      - Documented complete 5-phase procedure for Neon PITR branch creation, schema verification, application connection string update, and post-restore reconciliation sweep.
      - Documented RTO target (< 5 min; local schema & seed replay measured < 3.0s) and RPO window.
      - Updated [`docs/10-deployment-and-operations.md`](docs/10-deployment-and-operations.md) §21 table.
    - **Automated Verification**:
      - Automated test suite: [`server/tests/test_restore_drill.py`](server/tests/test_restore_drill.py) (5 passed in 0.82s).
      - Architecture boundaries verified: `lint-imports` (7 kept, 0 broken).

---

## 4. Done log

### Feature — M10-05: Queue Soak and Redis Failure Drills

- **Date**: 2026-10-25
- **Branch**: `feature/m10-queue-drills`
- **What**:
  - Implemented comprehensive queue soak benchmarks, disaster recovery drills, and Redis failure tests per docs/02 §10, §11, docs/10 §9, §14, §16, §18, and ADR-046:
    - **Redis Outage & Graceful Degradation Drill** ([`server/tests/test_queue_drills.py`](server/tests/test_queue_drills.py)):
      - Validated Rate Limiter fallback: `RateLimitMiddleware` seamlessly degrades to an in-memory sliding window when Redis raises `ConnectionError`, enforcing rate limits without failing client requests with 500 errors.
      - Validated SSE Event Stream resilience: `JobLifecycleService.stream_job_events` catches Redis Pub/Sub disconnections and gracefully falls back to database polling for terminal state transitions.
      - Validated Heartbeat resilience: Worker and Celery Beat scheduler synchronous heartbeats log warnings and gracefully continue without crashing when Redis is unreachable.
      - Validated Alert evaluation resilience: `evaluate_system_alerts` handles broker connection errors gracefully and emits operational alerts.
    - **Redis Crash & Queue Rebuild Drill (Reconstructibility from PostgreSQL)** ([`server/tests/test_queue_drills.py`](server/tests/test_queue_drills.py)):
      - Simulated total Redis wipe with in-flight tasks in PostgreSQL (`queued` and abandoned `running` jobs).
      - Verified that `reap_stale_jobs` detects dead worker heartbeat timeouts and safely requeues jobs back to `queued`.
      - Verified that `sweep_stranded_jobs` sweeps all stranded jobs from PostgreSQL and re-enqueues them to Celery.
      - Verified atomic compare-and-set claim prevents duplicate execution on redundant deliveries.
    - **Worker Termination Mid-Task & Retry Handling** ([`server/tests/test_queue_drills.py`](server/tests/test_queue_drills.py)):
      - Verified Celery reliability configuration: `task_acks_late=True`, `task_reject_on_worker_lost=True`, `visibility_timeout >= 3600`.
      - Tested dead-worker lease expiration: jobs repeatedly abandoned reach `max_attempts` and transition cleanly to `failed` with error code `DEAD_WORKER_HEARTBEAT_TIMEOUT`.
    - **Queue Soak & Backpressure Drill** ([`server/tests/test_queue_drills.py`](server/tests/test_queue_drills.py)):
      - Verified multi-queue routing rules across partitions (`default`, `ingest`, `embed`, `analysis`).
      - Verified queue depth monitoring: depth > 50 messages triggers `queue_depth_exceeded` warning alert, and clears when drained.
    - **Automated Verification**:
      - Automated test suite: [`server/tests/test_queue_drills.py`](server/tests/test_queue_drills.py) (9 passed in 0.77s).
      - Architecture boundaries verified: `lint-imports` (7 kept, 0 broken).

---

## 4. Done log

### Feature — M10-04: Free-Profile Load, Concurrency, and Capacity Tests

- **Date**: 2026-10-25
- **Branch**: `feature/m10-load-tests`
- **What**:
  - Implemented comprehensive free-profile load, concurrency, memory profiling, and capacity benchmarks per docs/10 §15, §21, §22, ADR-046, and ADR-047:
    - **Neon Connection Concurrency & Pool Resilience** ([`server/tests/test_capacity.py`](server/tests/test_capacity.py)):
      - Verified SQLAlchemy async engine pool configuration: `pool_size=5`, `max_overflow=5`, `pool_recycle=1800`, `pool_pre_ping=True`.
      - Executed burst concurrent session acquisition tests (25 simultaneous sessions) verifying zero connection leaks, clean context manager exit, and graceful pool reclamation.
      - Tested pool pre-ping resilience against simulated serverless compute suspension / transient socket resets, confirming automatic connection refresh without failing caller operations.
    - **SSE Event Streaming Concurrency & Disconnect Lifecycle** ([`server/tests/test_capacity.py`](server/tests/test_capacity.py)):
      - Simulated 20 concurrent SSE subscriber streams consuming real-time broadcast milestone events over Redis pub/sub.
      - Tested clean client disconnection lifecycle: verified that terminating SSE generator invokes `pubsub.unsubscribe()` and `pubsub.aclose()`, eliminating dangling subscriptions or memory leaks.
      - Tested keepalive ping frame efficiency: verified ping payload is <= 30 bytes (< 10 KB/hour total idle network bandwidth per connection).
    - **Ingestion & AST Chunking Memory Profiling** ([`server/tests/test_capacity.py`](server/tests/test_capacity.py)):
      - Benchmarked `CodeAwareChunker.chunk_file` and redaction scanning on representative synthetic multi-language codebase (100 Python, 50 TypeScript, 25 Markdown files; 3,500+ lines).
      - Profiled peak memory allocations via `tracemalloc`: measured < 25 MB allocation delta during chunking.
      - Proved combined container resident set size (RSS: base ~90MB + Celery solo ~80MB + chunking ~25MB = ~195MB) remains comfortably below 250 MB, well within Render Free's 512 MB ceiling (target < 350 MB).
    - **Upstash Redis Daily Command Budget Simulation** ([`server/tests/test_capacity.py`](server/tests/test_capacity.py)):
      - Built precise Redis command accounting model for all background workers, scheduler beats, rate limiter queries, and alert evaluations.
      - Proved Scenario A (Realistic Developer Day with Render Free sleep tolerance): ~5,580 commands/day, providing 44% headroom below Upstash's 10,000 commands/day cap.
      - Proved Scenario B (Stress 24-hour continuous non-sleeping baseline): 5,760 commands/day, leaving 4,240 commands for jobs and queries within the 10,000 cap.
    - **Documentation**:
      - Updated [`docs/10-deployment-and-operations.md`](docs/10-deployment-and-operations.md) §21 table with validated empirical measurements and thresholds.
      - Automated test suite: [`server/tests/test_capacity.py`](server/tests/test_capacity.py) (9 passed in 1.01s).
      - Architecture boundaries verified: `lint-imports` (7 kept, 0 broken).

### Feature — M10-03: Alerting Thresholds, Health Checks, and Kill Switches

- **Date**: 2026-10-25
- **Branch**: `feature/m10-alerts`
- **What**:
  - Implemented comprehensive operational alerting thresholds, enhanced health & readiness probes, worker/scheduler heartbeat tracking, and centralized administrative kill switches per docs/07 §12, docs/10 §11, §12, §14, §15, §18, ADR-046, and ADR-047:
    - **Centralized Subsystem Kill Switches** ([`server/app/core/kill_switches.py`](server/app/core/kill_switches.py)):
      - Built operational flag controllers for 5 critical subsystems: `indexing`, `llm`, `embed`, `webhooks`, and `pause_queues`.
      - Added dynamic in-memory override controls (`set_dynamic_kill_switch`, `reset_dynamic_kill_switches`) for operational drills and automated testing.
      - Integrated FastAPI route dependency (`require_kill_switch_inactive`) and core check (`check_kill_switch`) raising `FeatureDisabledError` (RFC 9457 Problem Details HTTP 503, `code: "feature.disabled"`).
      - Wired kill switch enforcement directly into:
        - `server/app/api/webhooks.py`: router dependency blocks external webhooks when `kill_webhooks=True`.
        - `server/app/api/extension.py`: `post_snippets` blocks snippet intake when `kill_indexing=True`.
        - `server/app/llm/router.py`: `generate` and `stream_generate` block LLM invocations when `kill_llm=True`.
        - `server/app/domain/brain/embedding_service.py`: `process_embed_chunks` blocks vector generation when `kill_embed=True`.
        - `server/app/workers/celery_app.py`: `enqueuer_sweep` and `process_job` defer processing and return paused status when `pause_queues=True`.
    - **Worker & Scheduler Heartbeat Tracking** ([`server/app/core/heartbeat.py`](server/app/core/heartbeat.py)):
      - Implemented Redis-backed heartbeat recording with configurable TTLs for Celery background workers (`WorkerHeartbeat` with worker ID, hostname, pid, serviced queues) and Celery Beat scheduler (`SchedulerHeartbeat`).
      - Built liveness evaluators (`check_worker_liveness`, `check_scheduler_liveness`) detecting stale heartbeats against `alert_max_heartbeat_stale_seconds` (default 120s) and worker drop.
      - Added Celery Beat periodic task (`devmind.scheduler_heartbeat`) every 30s and worker heartbeat tasks.
    - **Operational Alert Evaluator** ([`server/app/core/alerts.py`](server/app/core/alerts.py)):
      - Built non-blocking operational evaluator (`evaluate_system_alerts`) monitoring 6 health dimensions:
        1. Queue depth per queue (`default`, `ingest`, `embed`, `analysis`) against `alert_max_queue_depth` (default 500).
        2. Oldest message age against `alert_max_queue_age_seconds` (default 300s).
        3. Stale worker heartbeats and worker drop against `alert_max_heartbeat_stale_seconds` (default 120s).
        4. Stale Celery Beat scheduler heartbeats.
        5. Active kill switch notifications (`INFO` / `WARNING`).
        6. Error rate percentages from in-memory telemetry snapshots against `alert_max_error_rate_percent` (default 5.0%).
      - Guaranteed zero secrets, tokens, or source code in alert payloads (ADR-047).
    - **Enhanced Health & Readiness Probes** ([`server/app/api/health.py`](server/app/api/health.py)):
      - Updated `/health` and `/healthz` liveness probes to return process status and build SHA (`DEVMIND_BUILD_SHA`).
      - Enhanced `/readyz` to verify PostgreSQL connectivity, Redis connectivity, and Alembic migration status against expected heads (`check_migrations_at_head` in [`database.py`](server/app/persistence/database.py)) while reporting active kill switches and alert counts.
      - Added `/readyz/alerts` operational endpoint returning structured `SystemAlertsResponse`.
    - **Configuration & Documentation Updates**:
      - Updated `Settings` in [`server/app/core/settings.py`](server/app/core/settings.py) and [`server/.env.example`](server/.env.example) with kill switch flags, alerting thresholds, and `DEVMIND_BUILD_SHA`.
    - **Automated Verification**:
      - Added [`server/tests/test_alerts.py`](server/tests/test_alerts.py) with 15 unit and integration tests covering kill switch enforcement, heartbeat recording/expiration, alert threshold triggers, and zero-secret guarantees.
      - Updated [`server/tests/test_health.py`](server/tests/test_health.py) and [`server/tests/test_authz_matrix.py`](server/tests/test_authz_matrix.py).
      - Verified `test-all.mjs --fast`: 13 passed, 0 failed, 1 skipped (all 701 server tests passed).

### Feature — M10-02: Observability Stack & OpenTelemetry Traces

- **Date**: 2026-10-19
- **Branch**: `feature/m10-observability`
- **What**:
  - Implemented comprehensive OpenTelemetry tracing, metrics instrumentation, structured log correlation, and error reporting across the API, background workers, and LLM gateway per docs/02 §12, docs/10 §13, docs/11 §M10, ADR-030, ADR-046, and ADR-047:
    - **OpenTelemetry Core Infrastructure** ([`server/app/core/telemetry.py`](server/app/core/telemetry.py)):
      - Built `init_telemetry` configuring `TracerProvider` and `MeterProvider` with configurable exporter modes (`memory` for testing/diagnostics, `console` for Render log stream).
      - Added `TelemetryMiddleware` for FastAPI requests automatically extracting route templates, HTTP methods, status codes, and request correlation IDs into server spans while populating `X-Trace-ID` response headers.
      - Implemented strict attribute payload sanitization (`sanitize_span_attributes`): guarantees forbidden keys (`prompt`, `completion`, `code`, `source`, `raw_payload`, `password`, `secret`, `token`, `cookie`, `jwt`) are dropped and sensitive values are redacted with `redact_sensitive_text` (Rule 5 & ADR-047).
      - Built in-memory metric reader with standard instruments: `devmind_http_requests_total`, `devmind_http_request_duration_seconds`, `devmind_worker_jobs_total`, `devmind_worker_job_duration_seconds`, `devmind_llm_requests_total`, `devmind_llm_tokens_total`, `devmind_llm_latency_seconds`, and `devmind_queue_depth`.
    - **Structured Log Correlation** ([`server/app/core/logging.py`](server/app/core/logging.py)):
      - Enhanced `JSONFormatter` to inspect active OpenTelemetry spans and automatically inject W3C standard 32-hex `trace_id` and 16-hex `span_id` into all structured log entries.
      - Added `actor_id_ctx` context variable alongside `request_id_ctx`, `job_id_ctx`, `workspace_id_ctx`, and `project_id_ctx`.
      - Preserved pytest `LogCaptureHandler` instances during log initialization for robust test isolation.
    - **LLM Gateway & Background Worker Telemetry** ([`server/app/llm/router.py`](server/app/llm/router.py), [`server/app/workers/celery_app.py`](server/app/workers/celery_app.py)):
      - Instrumented LLM generation requests with `devmind.llm.generate` spans and recorded `record_llm_call` token consumption and latency metrics without emitting prompts or completions.
      - Instrumented Celery `process_job` background task with `devmind.worker.process_job` spans, execution duration histograms, and outcome metrics.
    - **Free-Tier Error Reporting Fallback (OQ-15)** ([`server/app/core/error_reporting.py`](server/app/core/error_reporting.py), [`server/app/core/errors.py`](server/app/core/errors.py)):
      - Built `report_exception` with payload scrubbing (stripping headers, request bodies, prompt/source text).
      - Fallback to local structured JSON logging when `DEVMIND_SENTRY_DSN` is absent (100% free profile compliant, ADR-046).
      - Wired `unhandled_exception_handler` in `errors.py` to `report_exception`.
    - **Automated Verification**:
      - Added [`server/tests/test_telemetry.py`](server/tests/test_telemetry.py) covering span creation, attribute redaction, trace correlation in JSON logs, middleware metrics, worker metrics, LLM metrics, and error fallback.
      - 665 server tests passed in 89s.
      - Layer import boundary check (`lint-imports`): 7 kept, 0 broken.
      - `node scripts/test-all.mjs --fast`: all 13 checks passed.

### Feature — M10-01: Complete Authorization and Tenant Isolation Test Suite across All Routes

- **Date**: 2026-10-19
- **Branch**: `feature/m10-authz-suite`
- **What**:
  - Implemented comprehensive Quality Gate G3 test suite enforcing tenant isolation, authorization, and scheme separation across all API endpoints, repositories, and workflows per docs/09 §6, docs/03 §4 & §13, docs/07 §3, ADR-010, ADR-012, and ADR-047:
    - **FastAPI Route Registry Discovery & Validation** ([`server/app/domain/auth/policy.py`](server/app/domain/auth/policy.py), [`server/tests/test_route_permissions.py`](server/tests/test_route_permissions.py)):
      - Implemented `extract_api_routes(app_routes)` recursively inspecting nested routers and `_IncludedRouter` mounts.
      - Updated `find_undeclared_routes` to scan the full route tree (75 endpoints).
      - Added assertion in `test_all_api_routes_declare_permission` verifying >= 70 routes are inspected and zero routes lack declared permissions.
    - **Security & Authorization Hardening** ([`server/app/api/integrations.py`](server/app/api/integrations.py)):
      - Fixed missing permission enforcement on `GET /api/v1/workspaces/{wid}/integrations/github` and `DELETE /api/v1/workspaces/{wid}/integrations/github` by binding `require_permission(PERM_INTEGRATIONS_MANAGE)` dependency.
    - **Scheme Separation Suite** ([`server/tests/test_authz_matrix.py`](server/tests/test_authz_matrix.py)):
      - Asserted browser API routes (`/api/v1/...`) strictly reject DevMind extension tokens (`Bearer dme_at_...`) with RFC 9457 `401 Unauthorized` (`auth.unauthenticated`).
      - Asserted extension routes (`/api/v1/ext/...`) strictly reject Clerk browser JWT tokens with `401 Unauthorized`.
      - Asserted extension routes reject unauthenticated requests with `401 Unauthorized`.
    - **Cross-Tenant & Role Permission Matrix** ([`server/tests/test_authz_matrix.py`](server/tests/test_authz_matrix.py)):
      - Parameterized 54 distinct resource endpoint variations covering Workspaces, Members, Projects, Analyses, Retention, Brain (Snapshots, Symbols, Graph, Files, Search), Findings, Consents, Jobs, and Extension Sync.
      - Asserted anonymous calls return `401 Unauthorized`.
      - Asserted cross-tenant access attempts (Workspace B user accessing Workspace A resource) return `403 Forbidden` (`auth.forbidden`).
      - Asserted insufficient role attempts (Workspace Viewer attempting admin mutations, Project Contributor attempting delete/purge) return `403 Forbidden`.
    - **Repository Layer Context Enforcement** ([`server/tests/test_authz_matrix.py`](server/tests/test_authz_matrix.py), [`server/app/persistence/repositories/`](server/app/persistence/repositories/)):
      - Verified `BaseRepository._validate_context(None)` and `_validate_context("invalid")` raises `TypeError` across all 10 repositories (`UserRepository`, `WorkspaceRepository`, `ProjectRepository`, `BrainRepository`, `AuditEventRepository`, `UsageRecordRepository`, `ExtensionRepository`, `RetentionRepository`, `ConsentRepository`, `GitHubRepository`).
      - Exported `ConsentRepository` and `RetentionRepository` cleanly in repositories module.
    - **Cross-Tenant Zero-Hit & Consent Enforcement Tests**:
      - Verified project access boundary raises `PermissionError` on alien project access and vector/keyword queries strictly bind `project_id`.
      - Verified snippet upload without active consent returns RFC 9457 `403 Forbidden` (`consent.required`).
      - Verified cross-tenant job detail and SSE event streaming access rejection (`403 Forbidden`).
      - Verified extension access token expiry/revocation and replay detection.
      - Verified audit event metadata zero-leak invariant (no source code, prompts, completions, or raw secrets).
    - **Test Isolation Hardening** ([`server/tests/test_rate_limit.py`](server/tests/test_rate_limit.py)):
      - Added autouse `reset_rate_limit_windows` fixture and isolated `redis_key_prefix` to prevent rate limit test cross-contamination.
    - **Automated Verification**:
      - `tests/test_authz_matrix.py`: 169 passed in 58s.
      - Full test suite: 657 server tests passed.
      - Layer import boundary check (`lint-imports`): 7 kept, 0 broken.
      - Next.js production build passes with 25 routes compiled.
      - Master `node scripts/test-all.mjs --fast`: 13 passed, 0 failed, 1 skipped.

### Feature — M9-07: Extension Sync Log and History Store

- **Date**: 2026-10-19
- **Branch**: `feature/m9-extension-sync-log`
- **What**:
  - Implemented append-only local synchronization audit logging and UI history inspection per docs/06 §9, §11.3, §13, and ADR-047:
    - **Local Sync Log Store (`SyncLogStore`)** ([`extension/src/scanner/syncLog.ts`](extension/src/scanner/syncLog.ts)):
      - Built `SyncLogStore` storing sync events strictly outside the repository in `storageDirectory/sync-log.json` (honoring Rule 5 and ADR-047 public repo zero-leak invariants).
      - Tracks per-event execution status (`success`, `failed`, `stale_base_recovered`, `offline_queued`), file counts, version counts, symbol & edge counts, finding counts, duration ms, receipt hash, and errors.
      - Implements FIFO capping to 100 entries, with `record()`, `getRecent()`, `getAll()`, `getLastSync()`, and `clear()`.
    - **Sync Client Integration (`SyncClient`)** ([`extension/src/services/syncClient.ts`](extension/src/services/syncClient.ts)):
      - Integrated `syncLogStore` into `SyncOptions` and `SyncResult`.
      - Measures precise sync duration in milliseconds.
      - Automatically logs both successful sync executions (with receipt hash) and failures (unauthenticated or network/server errors).
    - **VS Code Extension UI (`SyncViewProvider` & Commands)** ([`extension/src/views/syncView.ts`](extension/src/views/syncView.ts), [`extension/src/extension.ts`](extension/src/extension.ts), [`extension/package.json`](extension/package.json)):
      - Enhanced `SyncReceiptTreeItem` to dynamically show actual latest receipt hash, timestamp, and status.
      - Added collapsible `SyncHistoryGroupTreeItem` rendering itemized `SyncLogEntryTreeItem` events with status badges (`✓`, `↺`, `✗`), file/symbol summary chips, and rich hover tooltips.
      - Registered `devmind.showSyncLog`: Displays complete formatted audit log in a dedicated VS Code OutputChannel (`DevMind: Sync Log`).
      - Registered `devmind.clearSyncLog`: Clears local sync history outside the repo and notifies the user.
    - **Automated Verification**:
      - Added `extension/tests/sync-log.test.ts` (8 tests passing).
      - Full extension test suite: 15 test files, 78 passed.
      - Extension packaged cleanly (`devmind-vscode.vsix`).
      - Next.js production build passes (25 routes).
      - `node scripts/test-all.mjs --fast` passes all 13 checks.

### Feature — M9-06: Workspace and Project Audit Endpoints & Governance UI

- **Date**: 2026-10-19
- **Branch**: `feature/m9-audit-endpoints`
- **What**:
  - Implemented immutable audit event logging, REST API endpoints, and frontend governance UI per docs/03 §3.5 & §11.1, docs/07 §16, and docs/08 (Screens S-10, S-12):
    - **Persistence & Repository (`AuditEventRepository`)** ([`server/app/persistence/repositories/audit_repo.py`](server/app/persistence/repositories/audit_repo.py)):
      - Enhanced `AuditEventRepository` with tenant-isolated filtering methods:
        - `list_for_workspace` and `count_for_workspace` filtering by `action`, `target_kind`, `target_id`, `actor_id`, with limit/offset pagination.
        - `list_for_project` and `count_for_project` filtering by project identifier either directly on `target_id` or inside `metadata_json->>'project_id'`.
    - **Domain Layer (`AuditService`)** ([`server/app/domain/audit/service.py`](server/app/domain/audit/service.py)):
      - Built `AuditService` with tenant verification (`ForbiddenError` on cross-tenant workspace or cross-tenant project access).
      - Added audit event logging on sensitive workspace and project operations:
        - Membership changes: `membership.added`, `membership.updated`, `membership.removed`.
        - Workspace updates: `workspace.updated`.
        - Project creation and deletion: `project.created`, `project.deleted`.
    - **REST API Endpoints & Schemas** ([`server/app/api/audit.py`](server/app/api/audit.py), [`server/app/api/schemas.py`](server/app/api/schemas.py)):
      - Added `AuditEventItem` Pydantic schema mapping `metadata_json` to `metadata` attribute.
      - Added `GET /api/v1/workspaces/{workspace_id}/audit-events` guarded by `PERM_AUDIT_READ` (requires workspace admin/owner).
      - Added `GET /api/v1/projects/{pid}/audit-events` guarded by `PERM_PROJECT_READ`.
      - Mounted routers in `server/app/main.py`.
    - **Common Client API (`@devmind/common`)** ([`common/src/api/index.ts`](common/src/api/index.ts)):
      - Exported `AuditEventItem` and `ListAuditEventsParams`.
      - Added `getWorkspaceAuditEvents(workspaceId, params)` and `getProjectAuditEvents(projectId, params)` to `DevMindApiClient`.
      - Built and verified `@devmind/common`.
    - **Frontend UI & Governance Integration** ([`client/components/audit/`](client/components/audit/)):
      - Built `AuditLogViewer` supporting action filtering, status-colored chips (`danger`, `signal`, `ref`, `neutral`), UTC timestamp formatting, actor/target display, hashed IP chips, and expandable metadata JSON drawer.
      - Built `AuditLogModal` dialog container.
      - Integrated "Audit Events →" modal trigger into Screen S-12 `UsageDashboard` ([`client/components/usage/UsageDashboard.tsx`](client/components/usage/UsageDashboard.tsx)).
      - Added "Audit Trail (docs/07 §16)" tab to Screen S-10 Project Settings ([`client/components/settings/ProjectSettingsClient.tsx`](client/components/settings/ProjectSettingsClient.tsx)).
    - **Automated Verification**:
      - Added `server/tests/test_audit_api.py` (6 tests passing, including cross-tenant isolation and permission checks).
      - Verified route permissions (`server/tests/test_route_permissions.py`) and layer import boundaries (`lint-imports`).
      - Added `client/tests/audit-events.test.tsx` (6 tests passing).
      - Full client test suite: 24 test files, 154 tests passing.
      - TypeScript check on client and root passes with 0 errors.
      - `node scripts/test-all.mjs --fast` passes all 13 checks.
      - Next.js production build passes with 25 routes compiled.

### Feature — M9-05: Snapshot History and Diff Viewer

- **Date**: 2026-10-19
- **Branch**: `feature/m9-snapshot-history`
- **What**:
  - Implemented Snapshot History and Point-in-time Diff Viewer UI and common API client methods per docs/03 §3.2 & §7, docs/08 (Screen S-05), and docs/11 (M9-05):
    - **Common Client API (`@devmind/common`)** ([`common/src/api/index.ts`](common/src/api/index.ts)):
      - Exported `CreateSnapshotRequest`, `SnapshotDiffItem`, and `SnapshotDiffResponse` schema types.
      - Added `createSnapshot(projectId, data)` executing `POST /api/v1/projects/{pid}/brain/snapshots`.
      - Added `compareSnapshots(projectId, snapshotId, targetSnapshotId?)` executing `GET /api/v1/projects/{pid}/brain/snapshots/{sid}/diff`.
      - Rebuilt and verified `@devmind/common`.
    - **Snapshot History Modal & Diff Viewer Component** ([`client/components/brain/SnapshotHistoryModal.tsx`](client/components/brain/SnapshotHistoryModal.tsx)):
      - Built multi-tab modal dialog (`history`, `diff`, `capture` tabs):
        - **Timeline Tab**: Lists historical and current snapshots with origin kind badge (`scan`, `commit`, `manual`), created timestamp, file count, active state badge, and quick actions to run diff comparison or switch active Brain Explorer snapshot.
        - **Diff & Comparison Tab**: Allows selecting a Base Snapshot and Target Snapshot (or against "Current Active Project State"). Displays 4 summary metric counters (`+Added`, `-Removed`, `~Modified`, `=Unchanged`) and an itemized difference list with status chips, file paths, and truncated SHA-256 content hash transitions (`base_hash -> target_hash`), with status filtering and file path search input.
        - **Capture Snapshot Tab**: Dedicated form to capture immediate immutable point-in-time project snapshot with kind (`manual` / `scan` / `commit`), optional reference SHA / tag, and human label.
    - **Brain Explorer Integration** ([`client/components/brain/BrainHeader.tsx`](client/components/brain/BrainHeader.tsx), [`client/components/brain/BrainExplorer.tsx`](client/components/brain/BrainExplorer.tsx)):
      - Added "History & Diffs" button next to snapshot selector in `BrainHeader`.
      - Integrated `SnapshotHistoryModal` with state management into `BrainExplorer`.
    - **Automated Verification**:
      - Added `client/tests/snapshot-history.test.tsx` (5 tests passing).
      - Full client test suite passes: 23 test files, 148 passed.
      - Server snapshot tests pass: `tests/test_snapshots.py` (8 passed).
      - Next.js production build passes with 25 routes compiled.
      - `node scripts/test-all.mjs --fast` passes all 13 checks.

### Feature — M9-04: Retention Windows and Scheduler Cleanup

- **Date**: 2026-10-19
- **Branch**: `feature/m9-retention-windows`
- **What**:
  - Implemented configurable retention windows, ADR-026 interim defaults, periodic scheduler sweeps, and Screen S-10 retention UI per docs/03 §3.1, docs/07 §9, docs/08 (Screen S-10), and docs/10 §9:
    - **Database & Migration (`RetentionPolicy`, `0010_retention_policies`)** ([`server/app/persistence/models/retention.py`](server/app/persistence/models/retention.py), [`server/alembic/versions/0010_retention_policies.py`](server/alembic/versions/0010_retention_policies.py)):
      - Created `retention_policies` table scoped to `workspace_id` with optional `project_id` override, category `kind`, and `days` (with `CheckConstraint("days >= 1")` and unique constraint `(workspace_id, project_id, kind)`).
      - Exported in `server/app/persistence/models/__init__.py`.
    - **Persistence Layer (`RetentionRepository` & `BrainRepository`)** ([`server/app/persistence/repositories/`](server/app/persistence/repositories/)):
      - Implemented `RetentionRepository` managing workspace and project retention policies with `AuthContext` tenancy verification.
      - Added `sweep_project_retention(ctx, project_id, cutoffs)` to `BrainRepository`:
        - Deletes expired `JobEvent` records older than cutoff.
        - Nulls out expired evidence snippet text in `FindingEvidence` older than cutoff.
        - Deletes stale non-current `FileVersion` records and unlinks associated `CodeChunk` and `ChunkEmbedding` rows older than snapshot retention cutoff.
        - Deletes expired `AgentRun` records and associated LangGraph checkpoints older than cutoff.
    - **Domain Layer (`RetentionService`)** ([`server/app/domain/retention/retention_service.py`](server/app/domain/retention/retention_service.py)):
      - Implemented ADR-026 interim retention defaults (`job_events: 30d`, `snapshots: 90d`, `ephemeral_snippets: 7d`, `checkpoints: 30d`, `idempotency_keys: 1d`, `audit_events: 365d`).
      - Implemented `get_workspace_retention`, `update_workspace_retention`, `get_project_retention`, `update_project_retention`, `reset_project_retention`, and `execute_retention_sweep`.
      - Emits immutable `AuditEvent` on updates, overrides, resets, and completed sweeps (`action="retention.sweep_completed"`).
    - **Scheduler Worker (`server/app/workers/scheduler.py`)** ([`server/app/workers/scheduler.py`](server/app/workers/scheduler.py)):
      - Added `run_retention_sweep_job()` using explicit `SystemContext(reason="scheduled_retention_sweep")`.
      - Added `periodic_sweep_worker` running automated sweeps periodically with graceful cancellation handling.
    - **REST API Routes & Schemas** ([`server/app/api/retention.py`](server/app/api/retention.py), [`server/app/api/schemas.py`](server/app/api/schemas.py)):
      - Added workspace routes `GET/PUT /api/v1/workspaces/{wid}/retention` guarded by `@declare_permission(PERM_WORKSPACE_READ/PERM_WORKSPACE_MANAGE)`.
      - Added project routes `GET/PUT/DELETE /api/v1/projects/{pid}/retention` and `POST /api/v1/projects/{pid}/retention/sweep` guarded by `@declare_permission(PERM_PROJECT_READ/PERM_PROJECT_UPDATE)`.
      - Mounted in `server/app/main.py`.
    - **Common Client (`@devmind/common`)** ([`common/src/api/index.ts`](common/src/api/index.ts)):
      - Added TypeScript interfaces: `RetentionPolicyItem`, `EffectiveRetentionCategory`, `EffectiveRetentionSummary`, `UpdateRetentionPolicyRequest`, `RetentionSweepReport`.
      - Added client methods: `getWorkspaceRetention`, `updateWorkspaceRetention`, `getProjectRetention`, `updateProjectRetention`, `resetProjectRetention`, `triggerProjectRetentionSweep`.
    - **Frontend UI (Screen S-10 Retention Tab)** ([`client/components/settings/`](client/components/settings/)):
      - Created [`RetentionPolicyManager.tsx`](client/components/settings/RetentionPolicyManager.tsx) displaying category cards, days, status badges (Default vs Override), days edit dialog, provider backup retention disclosure (ADR-026 & docs/03 §8), and a "Run Retention Sweep Now" button with immediate swept counts report.
      - Integrated into [`ProjectSettingsClient.tsx`](client/components/settings/ProjectSettingsClient.tsx).
    - **Automated Verification**:
      - Added `server/tests/test_retention.py` (8 tests passing).
      - Added `client/tests/retention-policy.test.tsx` (2 tests, 143 total client tests passing).
      - Updated `server/tests/test_migrations.py` verifying head `0010_retention_policies`.
      - Next.js production build passes (25 routes).
      - Full `node scripts/test-all.mjs --fast` passes all 13 checks.

### Feature — M9-03: Purge Jobs and Verification Counts

- **Date**: 2026-10-19
- **Branch**: `feature/m9-purge-verification`
- **What**:
  - Implemented multi-store project data purging, cryptographic verification report generation, and Danger Zone UI per ADR-047, docs/03 §10, docs/07 §7, and docs/08 (Screen S-10):
    - **Persistence Layer (`BrainRepository`)** ([`server/app/persistence/repositories/brain_repo.py`](server/app/persistence/repositories/brain_repo.py)):
      - Implemented `purge_project_data(self, ctx, project_id, scope="all") -> dict[str, Any]` executing coordinated per-store purges:
        - PostgreSQL: Deletes `ChunkEmbedding`, `CodeChunk`, redaction/evidence snippets in `FindingEvidence.snippet_text`, and `JobEvent` records scoped to `project_id`.
        - Redis: Scan-and-delete pattern for temporary project cache keys `*{project_id}*`.
        - LangGraph checkpoints: Purges thread state/checkpoints matching `devmind:{project_id}:%`.
        - Returns structured store counts: `{ postgres: {...}, redis: {...}, checkpoints: {...} }`.
    - **Domain Layer (`ProjectService`)** ([`server/app/domain/projects/service.py`](server/app/domain/projects/service.py)):
      - Implemented `purge_project_data(self, ctx, project_id, scope="all", confirmation_slug=None)`:
        - Validates typed confirmation slug against target project slug to prevent accidental deletion.
        - Executes multi-store purge via `BrainRepository`.
        - Automatically resets project `sync_mode` to `metadata_only`.
        - Generates deterministic SHA-256 cryptographic `verification_hash` over sorted canonical payload without sensitive code snippets per ADR-047.
        - Emits immutable `AuditEvent` (`action="project.data_purged"`).
        - Returns `DeletionVerificationReport`.
    - **REST API Route & Schemas** ([`server/app/api/projects.py`](server/app/api/projects.py), [`server/app/api/schemas.py`](server/app/api/schemas.py)):
      - Added `PurgeProjectDataRequest` and `DeletionVerificationReport` schemas.
      - Mounted `POST /api/v1/projects/{pid}/purge` protected by `@declare_permission(PERM_PROJECT_DELETE)` with RFC 9457 error handling.
    - **Common API Client** ([`common/src/api/index.ts`](common/src/api/index.ts)):
      - Added TypeScript interfaces `PurgeProjectDataRequest` and `DeletionVerificationReport`.
      - Implemented `DevMindApiClient.purgeProjectData(projectId, data)`.
    - **Frontend UI (Screen S-10 Danger Zone)** ([`client/components/settings/`](client/components/settings/)):
      - Created [`ProjectPurgeManager.tsx`](client/components/settings/ProjectPurgeManager.tsx): dialog with typed confirmation slug, irreversible purge warning, per-store breakdown table (chunks, embeddings, evidence snippets, checkpoints, cache entries), and verification hash badge with copy button.
      - Integrated into [`ProjectSettingsClient.tsx`](client/components/settings/ProjectSettingsClient.tsx) Danger Zone.
    - **Automated Verification**:
      - Added `client/tests/project-purge.test.tsx` (2 tests, 141 total client tests passing).
      - Added `test_project_purge_forbidden_without_delete_role` and `test_project_service_purge_project_data_and_verification_report` in `server/tests/test_projects_api.py`.
      - Next.js production build passes (25 routes).
      - Full `node scripts/test-all.mjs --fast` passes all 13 checks.

### Feature — M9-02: Consent Revoke Flow & Dependent Data Purge

- **Date**: 2026-10-18
- **Branch**: `feature/m9-consent-revoke`
- **What**:
  - Implemented source-transmission consent revocation, dependent data purge execution, and audit logging per ADR-047, docs/07 §7, and docs/11:
    - **Domain Layer (`ConsentService`)** ([`server/app/domain/consent/consent_service.py`](server/app/domain/consent/consent_service.py)):
      - In `revoke_consent`: Sets `revoked_at` timestamp immediately; validates if revoked consent covers `cloud_index` scope. If no active `cloud_index` consent remains for the project, immediately triggers irreversible purge of all vector embeddings and code chunk texts via `BrainRepository.purge_project_chunks(ctx, project_id)` and downgrades project `sync_mode` to `metadata_only`.
      - Emits immutable `AuditEvent` (`action="consent.revoked"`) in `AuditEventRepository` recording actor ID, target consent ID, scope, authorized providers, and exact `purged_counts` without raw source content per ADR-047.
      - In `create_consent`: Emits immutable `AuditEvent` (`action="consent.granted"`).
      - Updated `ConsentItem` model to return `purged_counts`, `sync_mode_updated`, and `new_sync_mode`.
    - **REST API Route** ([`server/app/api/consents.py`](server/app/api/consents.py)):
      - Added `POST /api/v1/projects/{pid}/consents/{cid}/revoke` route alias alongside `DELETE /api/v1/projects/{pid}/consents/{cid}` with `@declare_permission(PERM_CONSENT_MANAGE)`.
    - **Common API Client** ([`common/src/api/index.ts`](common/src/api/index.ts)):
      - Added TypeScript interfaces: `ConsentItem`, `ConsentListResponse`, `CreateConsentRequest`.
      - Added `listProjectConsents`, `createProjectConsent`, and `revokeProjectConsent` to `DevMindApiClient`.
    - **Frontend UI (Screen S-10 / S-11)** ([`client/components/settings/`](client/components/settings/)):
      - Created [`ConsentManager.tsx`](client/components/settings/ConsentManager.tsx): displays active and historical consent grants, scope badges, policy versions, authorized providers, data categories, grant dates, and a modal for granting new transmission consent.
      - Added Revoke confirmation dialog with plain-language before/after consequence explanation and warning that revoking `cloud_index` permanently purges stored embeddings/chunks and switches to `metadata_only`.
      - Integrated `Consent Records (docs/07 §7)` tab into [`ProjectSettingsClient.tsx`](client/components/settings/ProjectSettingsClient.tsx).
    - **Automated Verification**:
      - Added `client/tests/consent-manager.test.tsx` (2 tests, 139 total client tests passing).
      - Added `test_consent_service_revoke_cloud_index_triggers_purge_and_audit` in `server/tests/test_consent.py` (5 passed).
      - Next.js production build passes (25 routes).
      - Master `test-all --fast` passed all 13 checks.

### Feature — M9-01: Sync-Mode Transitions & Purge Consequences API & UI

- **Date**: 2026-10-18
- **Branch**: `feature/m9-sync-mode`
- **What**:
  - Implemented synchronization mode switching with explicit consequence execution and audit tracking per ADR-022, ADR-047, and Screen S-10:
    - **Persistence Layer** ([`server/app/persistence/repositories/brain_repo.py`](server/app/persistence/repositories/brain_repo.py)):
      - Added `purge_project_chunks(self, ctx, project_id) -> dict[str, int]`: securely purges `ChunkEmbedding` vectors and `CodeChunk` records with exact per-store counts.
    - **Domain Service** ([`server/app/domain/projects/service.py`](server/app/domain/projects/service.py)):
      - Added `update_sync_mode(self, ctx, project_id, new_sync_mode)`: validates transition, executes irreversible cloud purge when transitioning `indexed` -> `metadata_only`, updates project record, and emits immutable `AuditEvent` (`action="project.sync_mode_updated"`, metadata recording exact purge counts without raw source content per ADR-047).
      - Updated `update_project` to enforce the same purge consequence and audit recording on general project patch.
    - **REST API Route & Schemas** ([`server/app/api/projects.py`](server/app/api/projects.py), [`server/app/api/schemas.py`](server/app/api/schemas.py)):
      - Added `PATCH /api/v1/projects/{pid}/sync-mode` with `@declare_permission(PERM_PROJECT_UPDATE)` and RFC 9457 error handling.
      - Defined `UpdateSyncModeRequest` and `SyncModeTransitionResponse` schemas.
    - **API Client** ([`common/src/api/index.ts`](common/src/api/index.ts), [`common/src/index.ts`](common/src/index.ts)):
      - Added `updateProjectSyncMode(projectId, syncMode)` method to `DevMindApiClient`.
      - Exported `* from "./api/index.js"` from root `@devmind/common`.
    - **Frontend UI (Screen S-10)** ([`client/components/settings/`](client/components/settings/)):
      - `SyncModeManager.tsx`: ADR-022 comparison diptych (`metadata_only` vs `indexed`), Active Mode badges, confirmation dialog with consequence warnings, and post-transition purge counts notification.
      - `ProjectSettingsClient.tsx`: Project settings container with breadcrumbs, section tabs (Sync Modes, Retention Windows, Danger Zone), and Return to Overview navigation.
      - Added routes [`client/app/projects/[projectId]/settings/page.tsx`](client/app/projects/[projectId]/settings/page.tsx) and [`client/app/projects/[projectId]/settings/loading.tsx`](client/app/projects/[projectId]/settings/loading.tsx).
    - **Automated Verification**:
      - Added `client/tests/sync-mode-settings.test.tsx` (6 unit tests, 137 total passing).
      - Added `test_project_service_sync_mode_transition_and_purge` and auth checks in `server/tests/test_projects_api.py`.
      - Production build passes (25 routes: 14 static, 11 dynamic).
      - Full `test-all --fast` passed all 13 checks.

### Feature — M8-10: Empty, Error, Loading States, Accessibility Audit, and Keyboard Navigation Pass

- **Date**: 2026-10-18
- **Branch**: `feature/m8-a11y-polish`
- **What**:
  - Implemented comprehensive screen polish, state management, and WCAG 2.2 AA accessibility across all MVP screens S-02..S-12:
    - **EmptyState Component** ([`client/components/ui/EmptyState.tsx`](client/components/ui/EmptyState.tsx)):
      - Clean non-illustrative indicator glyph, semantic heading, single sentence explanation, primary action button/link, secondary action, and optional link to docs per docs/08 §6 and §16.
    - **ErrorState & RFC 9457 Error Boundaries** ([`client/components/ui/ErrorState.tsx`](client/components/ui/ErrorState.tsx)):
      - Formats RFC 9457 Problem Details (`application/problem+json`) with standard error codes (e.g. `devmind.client.runtime_error`, `devmind.authz.permission_denied`).
      - Displays `request_id`, error code, user-friendly cause, next action, retry action callback, and return to overview link per docs/08 §15.
      - Implemented App Router route error boundaries:
        - [`client/app/error.tsx`](client/app/error.tsx) (application runtime error boundary)
        - [`client/app/global-error.tsx`](client/app/global-error.tsx) (critical root layout error boundary)
        - [`client/app/projects/error.tsx`](client/app/projects/error.tsx) (projects directory error boundary)
        - [`client/app/projects/[projectId]/error.tsx`](client/app/projects/[projectId]/error.tsx) (project-scoped error boundary)
    - **Route Loading Skeletons (`loading.tsx`)**:
      - Implemented Suspense-based route loading states across all routes matching layout:
        - [`client/app/loading.tsx`](client/app/loading.tsx) (global loading)
        - [`client/app/projects/loading.tsx`](client/app/projects/loading.tsx) (projects catalog S-03)
        - [`client/app/projects/[projectId]/loading.tsx`](client/app/projects/[projectId]/loading.tsx) (project overview S-04)
        - [`client/app/projects/[projectId]/findings/loading.tsx`](client/app/projects/[projectId]/findings/loading.tsx) (findings index S-07)
        - [`client/app/projects/[projectId]/findings/[findingId]/loading.tsx`](client/app/projects/[projectId]/findings/[findingId]/loading.tsx) (finding detail S-08)
        - [`client/app/projects/[projectId]/brain/loading.tsx`](client/app/projects/[projectId]/brain/loading.tsx) (brain explorer S-05)
        - [`client/app/projects/[projectId]/chat/loading.tsx`](client/app/projects/[projectId]/chat/loading.tsx) (conversation S-06)
        - [`client/app/projects/[projectId]/jobs/loading.tsx`](client/app/projects/[projectId]/jobs/loading.tsx) (job center S-09)
        - [`client/app/projects/[projectId]/usage/loading.tsx`](client/app/projects/[projectId]/usage/loading.tsx) (usage & quotas S-12)
        - [`client/app/workspaces/loading.tsx`](client/app/workspaces/loading.tsx) (workspaces S-03)
      - All skeletons marked with `role="status"` and accessible screen reader text (`sr-only`), disabling animation under `prefers-reduced-motion: reduce`.
    - **Accessibility & Keyboard Navigation Audit (WCAG 2.2 AA)**:
      - Resolved duplicate `<main>` landmark violation by adjusting `AppShell` (`#app-main` with `role="region" aria-label="Application content"`), leaving RootLayout `<main id="main-content">` as sole top-level landmark.
      - Added `scope="col"` to all table headers in FindingsTable, JobsTable, ExtensionDevicesPane, and UsageBreakdownPane.
      - Added accessible tablist and tab semantics (`role="tablist"`, `role="tab"`, `aria-selected`) to mobile tabs in BrainExplorer.
      - Added accessible ordered step list semantics (`role="list"`, `aria-current="step"`) to onboarding progress bar.
      - Verified keyboard focus rings (`focus-visible:ring-2 focus-visible:ring-[var(--ref)]`) across interactive controls.
    - **Unit Tests**:
      - Added 7 tests in [`client/tests/a11y-empty-error-loading.test.tsx`](client/tests/a11y-empty-error-loading.test.tsx) covering EmptyState, ErrorState, error boundaries, skeleton accessibility, and AppShell landmark hierarchy.
      - Client test suite total increased to 131 tests across 18 test files (all 131 passing).
      - Full test suite: 13 passed, 0 failed, 1 skipped. Production Next.js build passes cleanly.

### Feature — M8-09: Usage Dashboard, Quotas, and Extension Devices (Screen S-12)

- **Date**: 2026-10-18
- **Branch**: `feature/m8-usage-ui`
- **What**:
  - Implemented Workspace Usage Dashboard & Extension Devices Manager per `docs/08 §11 S-12 & S-11`:
    - **API & Domain Layer** ([`common/src/api/index.ts`](common/src/api/index.ts)):
      - Exported types `QuotaItem`, `TaskUsageBreakdown`, `ProjectUsageBreakdown`, `WorkspaceUsageSummary`, `ExtensionDeviceItem`, `RevokeDeviceResponse`.
      - Added methods to `DevMindApiClient`: `getWorkspaceUsage`, `listExtensionDevices`, and `revokeExtensionDevice`.
    - **Quota Overview & Thresholds** ([`client/components/usage/QuotaOverview.tsx`](client/components/usage/QuotaOverview.tsx)):
      - Summary cards: Inference Metering (tokens), Analysis Workflows (jobs), Extension Devices, and Free Profile Limits (ADR-046).
      - Visual quota progress bars with color-coded threshold states: Normal (<80%, `var(--signal)`), Warning (80-95%, amber), and Danger/Exceeded (≥95%, red).
      - Accessible ARIA progressbars (`aria-valuenow`, `aria-valuemax`).
    - **Token Accounting Breakdown** ([`client/components/usage/UsageBreakdownPane.tsx`](client/components/usage/UsageBreakdownPane.tsx)):
      - Tabs toggling between "By Agent Task" (`security_scan`, `ast_indexing`, `conversation_reasoning`, `evidence_verification`, `symbol_resolution`) and "By Project".
      - Tabular mono formatting of prompt tokens, completion tokens, total tokens, job count, and percentage bars.
      - Search/filter input for task and project names.
      - Strict privacy disclosure: zero retention of raw prompts, completions, code snippets, or secrets per ADR-047 / docs/07 §15.
    - **Authorized Extension Devices** ([`client/components/usage/ExtensionDevicesPane.tsx`](client/components/usage/ExtensionDevicesPane.tsx)):
      - Registered VS Code extension devices table: device name, platform OS (`Linux`, `macOS`, `Windows`), extension version, VS Code version, last heartbeat, and status badge (`ACTIVE`, `IDLE`, `REVOKED`).
      - "Revoke Access" action button with confirmation dialog invalidating tokens per ADR-012.
      - "Connect Device" instructions modal explaining the local command `DevMind: Connect to Web Workspace` and consented sync protocol.
    - **Master Dashboard Container** ([`client/components/usage/UsageDashboard.tsx`](client/components/usage/UsageDashboard.tsx)):
      - Breadcrumbs, billing period indicator ("October 2026"), and link to audit events (`/jobs`).
    - **Routes & Shell Navigation**:
      - Added routes [`client/app/projects/[projectId]/usage/page.tsx`](client/app/projects/[projectId]/usage/page.tsx) and [`client/app/workspaces/[workspaceId]/usage/page.tsx`](client/app/workspaces/[workspaceId]/usage/page.tsx).
      - Added `Usage & Quotas (S-12)` nav item with `UsageIcon` to [`client/components/shell/AppGutterRail.tsx`](client/components/shell/AppGutterRail.tsx).
    - **Vercel Monorepo Build Fix**:
      - Resolved Vercel error `[NEXT_OUTPUT_DIR_MISSING] The Next.js output directory client/.next was not found at /vercel/path0/client/client/.next`.
      - Updated `vercel.json` and added `client/vercel.json` without hardcoded subpath `outputDirectory`, allowing Vercel's Next.js framework preset to automatically resolve `.next` from the project root.
    - **Automated Verification**:
      - Added 7 unit tests in [`client/tests/usage-ui.test.tsx`](client/tests/usage-ui.test.tsx) verifying quota rendering, threshold badges, task/project tab switching, search filtering, device revocation, and dashboard hierarchy.
      - All 17 client test files pass (124/124 tests).
      - All 13 monorepo checks pass in `node scripts/test-all.mjs --fast`.
      - Next.js production build succeeds packaging all 24 routes (14 static, 10 dynamic).
    - **API Client Extensions** ([`common/src/api/client.ts`](common/src/api/client.ts)):
      - Exported types `SnapshotItem`, `SnapshotDetail`, `CodeSymbolItem`, `BrainFileItem`, `BrainFileDetail`, `GraphResponse`, `BrainSummaryResponse`.
      - Added methods to `DevMindApiClient`: `listSnapshots`, `getSnapshotDetail`, `listBrainFiles`, `getBrainFileDetail`, `listSymbols`, `getBrainGraph`, and `getBrainSummary`.
    - **Header & Snapshot Controls** ([`client/components/brain/BrainHeader.tsx`](client/components/brain/BrainHeader.tsx)):
      - Snapshot selector dropdown clearly marking `(current)` and badging `[stale]` snapshots.
      - Hybrid search input for searching symbols or file paths (`POST /brain/search`).
      - Mode indicator (`Indexed Mode` vs `Metadata-Only Mode`) and "Enable Indexed Mode" action button.
    - **File Tree Left Pane** ([`client/components/brain/FileTreePane.tsx`](client/components/brain/FileTreePane.tsx)):
      - Interactive recursive directory tree with folder expand/collapse.
      - Badges for language tier (`tier1`), findings count (`!1`), and stale flags.
    - **Code & Symbol Center Pane** ([`client/components/brain/CodeSymbolPane.tsx`](client/components/brain/CodeSymbolPane.tsx)):
      - File metadata header: path, line counts, SHA-256 content hash, and copy path action.
      - Symbol quick-jump chips (`function`, `class`, `route`).
      - **Metadata-Only Mode State**: renders explicit warning banner ("Metadata-Only Mode: Source Text Redacted") explaining that source code text is not stored without consent per ADR-034/docs/08 §11, and renders extracted AST symbols list without raw source.
      - **Indexed Mode State**: code viewer with numbered lines and hover highlights.
    - **Relationships & Findings Right Pane** ([`client/components/brain/RelationshipsPane.tsx`](client/components/brain/RelationshipsPane.tsx)):
      - Relationships tab: incoming and outgoing symbol edges (`calls`, `imports`, `extends`, `guards`) with direction indicators and "Expand Graph" action (`GET /brain/graph`).
      - Findings tab: list of security findings mapped to this file with severity pills, E-level badges, and deep link to Finding Detail (`/projects/{pid}/findings/{id}`).
    - **Full Brain Explorer Container & Route** ([`client/components/brain/BrainExplorer.tsx`](client/components/brain/BrainExplorer.tsx), [`client/app/projects/[projectId]/brain/page.tsx`](client/app/projects/[projectId]/brain/page.tsx)):
      - Three-column layout on desktop; responsive tabs on mobile (`Files`, `Code & Symbols`, `Graph & Findings`).
      - Added route at `/projects/[projectId]/brain`.
    - **Unit Tests** ([`client/tests/brain-explorer.test.tsx`](client/tests/brain-explorer.test.tsx)):
      - Added 8 unit tests covering all components, three-pane layout, metadata-only mode, and snapshot selectors. All 16 client test files pass (115/115 tests).
  - **CI Workflow Hardening** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)):
    - Re-enabled automatic CI runs on pull requests and pushes to `main`.
    - Configured fast, robust, self-contained `ci-fast` and `ci-gate` jobs executing the canonical 13-check suite with zero external secrets or GitHub environment variables required.

### Feature — M8-07: Conversation Interface with Citations and Insufficient Evidence Banner (Screen S-06)

- **Date**: 2026-10-18
- **Branch**: `feature/m8-conversation-ui`
- **What**:
  - Implemented AI project conversation interface, AST citation references, agent execution trace, and insufficient evidence banner per `docs/08 §11 S-06`:
    - **Components & Types** ([`client/components/chat/types.ts`](client/components/chat/types.ts)):
      - Defined `CitationItem`, `ChatMessage`, starter queries, and sample conversation data.
    - **Citations Panel (Screen S-06 right drawer/aside)** ([`client/components/chat/CitationsPanel.tsx`](client/components/chat/CitationsPanel.tsx)):
      - AST-verified badge, file path with line numbers (`L28-L45`), symbol name tag, code snippet preview box, copy reference button, and deep link to Brain Explorer (`/projects/{pid}/brain?file=...`).
    - **Message Items & Inline Citations** ([`client/components/chat/ChatMessageItem.tsx`](client/components/chat/ChatMessageItem.tsx)):
      - User messages styled with right-aligned bubble and timestamp.
      - Assistant messages featuring DevMind avatar, collapsible Agent Execution Trace showing AST search and verification steps, markdown rendering with clickable inline citation badges `[1]`, `[2]`, copy markdown action, and timestamp.
      - **Insufficient Evidence Banner**: distinct amber/warning card with explicit reason explaining missing evidence, and structured list of actionable suggested next steps per `docs/08 §11 S-06`.
    - **Chat Composer** ([`client/components/chat/ChatComposer.tsx`](client/components/chat/ChatComposer.tsx)):
      - Auto-resizing textarea with Enter to submit, Shift+Enter for newlines, suggested starter queries chips, AST Grounded indicator, and Ask Project / Stop Generation controls.
    - **Full Conversation Container** ([`client/components/chat/ConversationView.tsx`](client/components/chat/ConversationView.tsx)):
      - Coordinates message scroll, citations panel drawer toggle, starter queries chips, export conversation as Markdown file, clear conversation, error banners for quota exceeded (`/projects/{pid}/usage` deep link) and metadata-only mode.
      - Integrates with `apiClient.createAnalysisJob(projectId, { type: "ask_project", params: { query } })` and SSE streaming with fallback simulation.
    - **Route & Tests**:
      - Added route at [`client/app/projects/[projectId]/chat/page.tsx`](client/app/projects/[projectId]/chat/page.tsx).
      - Added 8 unit tests in [`client/tests/conversation-ui.test.tsx`](client/tests/conversation-ui.test.tsx). All 15 client test files passed (107/107 tests).

### Feature — M8-06: Job Center and SSE Streaming Event Client with Fallback (Screen S-09)

- **Date**: 2026-10-18
- **Branch**: `feature/m8-jobs-sse`
- **What**:
  - Implemented background job center, live Server-Sent Events (SSE) streaming client, polling fallback, human-in-the-loop approval gate card, and floating job tray per `docs/08 §11 S-09`:
    - **OpenAPI Schema & Client Generation** ([`common/src/api/client.ts`](common/src/api/client.ts)):
      - Regenerated OpenAPI schema with `pnpm gen:api` exporting `AnalysisJobResponse`, `AnalysisJobCreatedResponse`, and `CreateAnalysisRequest`.
      - Added `listProjectJobs`, `getJob`, `cancelJob`, and `createAnalysisJob` methods to `DevMindApiClient`.
    - **SSE Event Streaming Hook with Fallback** ([`client/components/jobs/useJobEvents.ts`](client/components/jobs/useJobEvents.ts)):
      - Subscribes to `/api/v1/jobs/{id}/events` via `EventSource` (RFC 8895) for real-time progress and milestone updates.
      - Automatically falls back to polling via `apiClient.getJob(id)` on connection drops or unsupported clients.
      - Automatically detects terminal states (`succeeded`, `failed`, `cancelled`, `timed_out`) and closes event stream cleanly.
    - **Job Center Table (Screen S-09 list)** ([`client/components/jobs/JobsTable.tsx`](client/components/jobs/JobsTable.tsx)):
      - Table layout with status filter pills (`All`, `Running / Queued`, `Awaiting Approval`, `Succeeded`, `Failed`), job type dropdown, search query, progress bars, attempt counts, duration formatting, and quick cancel actions.
      - Empty state handling and mobile collapsed cards.
    - **Job Detail View (Screen S-09 detail)** ([`client/components/jobs/JobDetailView.tsx`](client/components/jobs/JobDetailView.tsx)):
      - Live progress bar, connection status chip (`Live SSE Stream` / `Polling Fallback`).
      - Human Approval Gate prompt card when status is `awaiting_approval` stating exactly what action will be taken, declared impact scope, and "Approve and Proceed" / "Reject & Cancel" actions per `docs/08 §11 S-09` and ADR-006.
      - Milestone events log with sequence numbers, timestamps, and expandable structured metadata.
      - Execution failure diagnostics card for failed jobs.
    - **Floating Job Tray** ([`client/components/jobs/FloatingJobTray.tsx`](client/components/jobs/FloatingJobTray.tsx)):
      - Global floating drawer in bottom-right corner summarizing active jobs across any page per `docs/08 §11 S-09`.
      - Highlights amber when human approval is required; expands to reveal active jobs with direct links.
    - **Next.js App Router Routes**:
      - Added `client/app/projects/[projectId]/jobs/page.tsx` (Screen S-09 list).
      - Added `client/app/projects/[projectId]/jobs/[jobId]/page.tsx` (Screen S-09 detail).
    - **Comprehensive Unit Tests** ([`client/tests/jobs-ui.test.tsx`](client/tests/jobs-ui.test.tsx)):
      - Added 9 unit tests verifying table rendering, empty states, detail view with live stream, approval card with declared impact scope, failure diagnostics, floating tray, and duration/type formatters.

### Feature — M8-05: Findings List and Detail Views with Evidence Transitions (Screens S-07, S-08)

- **Date**: 2026-10-18
- **Branch**: `feature/m8-findings-ui`
- **What**:
  - Implemented dense findings table and evidence-first detail views conforming to `docs/08 §11 S-07, S-08` and `docs/03 §5.1`:
    - **API Client Extensions** ([`common/src/api/client.ts`](common/src/api/client.ts)):
      - Re-exported `FindingEvidenceItem`, `FindingStatusHistoryItem`, and `FindingStatusTransitionRequest`.
      - Added `listFindings`, `getFindingDetail`, and `transitionFindingStatus` methods to `DevMindApiClient`.
    - **Dense Findings Table (Screen S-07)** ([`client/components/findings/FindingsTable.tsx`](client/components/findings/FindingsTable.tsx)):
      - Multi-column dense layout with Severity, Evidence level (`E0`, `E1`, `E2`), Rule ID + Title, Location (`primary_path#L{line}`), Status badge, and Quick row actions (`Ack`, `Progress`, `Triage`, `Resolve`, `Re-verify`, `Reopen`).
      - Filter bar with Status pills showing counts (`All`, `Open / Acknowledged`, `In Progress`, `Resolved`, `Dismissed / Triaged`, `Stale`), Severity dropdown, Category dropdown, Evidence Level dropdown, and text search query.
      - Distinguishes empty states: "No findings detected" vs "Project not analyzed yet" with coverage prompt.
      - Responsive 2-line cards on mobile viewports per `docs/08 §11 S-07`.
    - **Finding Triage Modal** ([`client/components/findings/FindingTriageModal.tsx`](client/components/findings/FindingTriageModal.tsx)):
      - Accessible modal dialog for triaging findings to `dismissed` or `accepted_risk`.
      - Reason code dropdown for dismissal (`false_positive`, `not_applicable`, `duplicate`, `other`) and rationale textarea.
      - Enforces maintainer permission rule (`docs/08 §11 S-07`): disables confirm button with warning if caller lacks maintainer role.
      - Displays explicit notice regarding immutable recording to `finding_status_history` and tenant audit events.
    - **Finding Detail View (Screen S-08)** ([`client/components/findings/FindingDetail.tsx`](client/components/findings/FindingDetail.tsx)):
      - Evidence-first hierarchy: title & status, severity/confidence/evidence strip, "What and where" code excerpt with highlighted target lines, "Why it matters" explanation, machine-checkable evidence list with source tags (`structural_check`, `retrieved_context`, `rule_hit`), suggested remediation ("Review and apply yourself", no auto-apply), and status history audit timeline.
      - Prominent stale finding banner with "Re-verify finding" action when `status === 'stale'` per `docs/08 §11 S-08`.
      - Code Excerpt component ([`client/components/findings/CodeExcerpt.tsx`](client/components/findings/CodeExcerpt.tsx)) with dark editor container, line numbers, and copy reference button.
    - **Next.js App Router Pages**:
      - Added `client/app/projects/[projectId]/findings/page.tsx` (Screen S-07).
      - Added `client/app/projects/[projectId]/findings/[findingId]/page.tsx` (Screen S-08).
    - **Comprehensive Tests** ([`client/tests/findings-ui.test.tsx`](client/tests/findings-ui.test.tsx)):
      - Added 8 unit tests verifying S-07 table filtering, empty states, mobile collapse, triage modal permissions, code excerpt line highlighting, evidence-first hierarchy, suggested remediation label, and stale finding banner.

- **Date**: 2026-10-18
- **Branch**: `feature/m8-project-overview`
- **What**:
  - Implemented Project Overview dashboard answering the five core vision questions conforming to `docs/08 §11 S-04`:
    - **Overview Types & Deterministic Ordering** ([`client/components/overview/types.ts`](client/components/overview/types.ts)):
      - Defined data shapes for scan runs, background jobs, project health statistics, and findings.
      - Implemented `getHighestPriorityFinding(findings)` providing deterministic ordering by severity (`critical` > `high` > `medium` > `low`), then evidence level (`E2` > `E1` > `E0`).
    - **Question 5 · Is the Project Healthy?** ([`client/components/overview/CoverageHealthStrip.tsx`](client/components/overview/CoverageHealthStrip.tsx)):
      - Top strip displaying Security score (`88 / 100`, Grade B+) and Analysis coverage (`94%`, 42 of 45 files analyzed) in mono typography.
      - Explicitly marks unassessed categories (Reliability, Performance, Documentation) as `Not assessed` with release roadmap targets per `docs/08 §11 S-04`.
    - **Question 4 · What Should I Do Next?** ([`client/components/overview/NextActionBand.tsx`](client/components/overview/NextActionBand.tsx)):
      - Full-width band highlighting the highest-priority finding to fix with severity, evidence level (`E0`-`E2`), file location with line numbers, summary, and "Review Finding" CTA.
      - Labeled `rule-based until Project Mentor ships (1.3)` per spec.
      - Handled clean zero-findings state with "Ask Project Brain" CTA.
    - **Questions 2 & 3 · What Is Broken? & What Is Risky?** ([`client/components/overview/FindingsPanel.tsx`](client/components/overview/FindingsPanel.tsx)):
      - Severity count metrics cards (Critical, High, Medium, Low) and Bug Memory release label (`ships in 1.2`).
      - Risky findings list with evidence level badges, confidence, file references, and direct link to findings view.
      - Handled independent loading skeleton and error retry states.
    - **Question 1 · What Is Happening?** ([`client/components/overview/ActivityPanel.tsx`](client/components/overview/ActivityPanel.tsx)):
      - Recent scans list (Full & Incremental scans) with duration and file counts.
      - Background job center summary with status badges.
      - Last sync timestamp and sync mode badge (`indexed` vs `metadata_only`).
      - Handled independent loading skeleton and error retry states.
    - **Master Dashboard & Page Route** ([`client/components/overview/ProjectOverview.tsx`](client/components/overview/ProjectOverview.tsx) & [`client/app/projects/[projectId]/page.tsx`](client/app/projects/[projectId]/page.tsx)):
      - Assembled responsive layout with next-action band first on mobile, top strip, and 2-column grid (7 cols findings, 5 cols activity) on desktop.
    - **Unit Tests** ([`client/tests/project-overview.test.tsx`](client/tests/project-overview.test.tsx)):
      - 9 Vitest tests covering master dashboard, CoverageHealthStrip (Q5), NextActionBand deterministic ordering (Q4), FindingsPanel (Q2 & Q3), ActivityPanel (Q1), loading skeletons, and error retry states.
  - Verified with `pnpm --filter client test`: all 12 test files passed (82/82 tests).
  - Verified with `node scripts/test-all.mjs --fast`: 13/13 checks passed.
  - Verified with `node scripts/docs-links.mjs`: 50 files, 466 links valid.

### Feature — M8-03: App Shell, Navigation, and Workspace/Project Selection (Screen S-03)

- **Date**: 2026-10-18
- **Branch**: `feature/m8-app-shell`
- **What**:
  - Implemented application shell, global navigation, and Screen S-03 conforming to `docs/08 §10` and `docs/08 §11 S-03`:
    - **Application Context** ([`client/context/AppContext.tsx`](client/context/AppContext.tsx)):
      - Manages active workspace, active project, list of workspaces and projects, sync mode (`metadata_only` vs `indexed`), scan status, active jobs count, command palette toggle, and mobile navigation state.
      - Implements project creation via `apiClient.createProject` with fallback for offline/preview environments.
    - **SVG Icon Library** ([`client/components/shell/icons.tsx`](client/components/shell/icons.tsx)):
      - Accessible SVG icons for Overview, Brain, Chat, Findings, Jobs, Settings, Search, Plus, Folder, ChevronDown, Check, ExternalLink, and Close.
    - **Gutter Rail** ([`client/components/shell/AppGutterRail.tsx`](client/components/shell/AppGutterRail.tsx)):
      - Desktop 56px left navigation rail (`w-14`, `lg:flex`) with active workspace monogram trigger, project section links with accessible tooltips, and bottom account & documentation links.
    - **Top Bar** ([`client/components/shell/AppTopBar.tsx`](client/components/shell/AppTopBar.tsx)):
      - Breadcrumb trail (Workspace / Project / Active section), Command Palette trigger button (`⌘K` shortcut badge), Job tray status indicator, user avatar, and mobile navigation drawer.
    - **Bottom Status Bar** ([`client/components/shell/AppStatusBar.tsx`](client/components/shell/AppStatusBar.tsx)):
      - Fixed 28px bottom status bar displaying local scan status, sync mode badge with plain-language tooltip, job queue count, and VS Code extension companion status.
    - **Command Palette** ([`client/components/shell/CommandPalette.tsx`](client/components/shell/CommandPalette.tsx)):
      - Accessible modal dialog triggered by `Cmd+K` / `Ctrl+K` with real-time fuzzy search across Navigation targets, Projects, and quick Actions (Trigger Scan, Toggle Sync Mode, Connect VS Code).
    - **Workspace & Project Switcher** ([`client/components/shell/WorkspaceProjectSwitcher.tsx`](client/components/shell/WorkspaceProjectSwitcher.tsx)):
      - Accessible dropdown popover allowing seamless context switching across isolated workspaces and projects.
    - **Screen S-03 Project Index** ([`client/components/projects/ProjectIndex.tsx`](client/components/projects/ProjectIndex.tsx) & [`client/app/projects/page.tsx`](client/app/projects/page.tsx)):
      - Workspace header with VS Code extension connect deep-link (`vscode://devmind.devmind-vscode/connect`) and New Project action.
      - Project index table (desktop $\ge$ 1024px) with Project (name, slug, language), Source, Sync Mode, Last Scan, Open Findings by severity breakdown (Critical, High, Medium, Low), and Open actions.
      - Responsive stacked cards layout for mobile ($<$ 1024px).
      - Interactive search filter and sync mode filter tabs (`All`, `Indexed`, `Metadata only`).
      - Empty state card ("Create your first project") with VS Code extension connection instructions.
      - Accessible New Project modal dialog ([`client/components/projects/CreateProjectDialog.tsx`](client/components/projects/CreateProjectDialog.tsx)).
    - **Marketing Layout Isolation** ([`client/components/layout/Header.tsx`](client/components/layout/Header.tsx), [`Footer.tsx`](client/components/layout/Footer.tsx), [`GutterRail.tsx`](client/components/layout/GutterRail.tsx)):
      - Suppressed marketing headers and footers on app routes (`/projects*`, `/workspaces*`) to ensure the App Shell has full viewport control.
    - **Unit Tests** ([`client/tests/app-shell.test.tsx`](client/tests/app-shell.test.tsx)):
      - 8 Vitest tests covering AppShell composition, GutterRail, TopBar, StatusBar, WorkspaceProjectSwitcher, CommandPalette, Screen S-03 ProjectIndex table, and CreateProjectDialog.
  - Verified with `pnpm --filter client test`: all 11 test files passed (73/73 tests).
  - Verified with `node scripts/test-all.mjs --fast`: 13/13 checks passed.
  - Verified with `node scripts/docs-links.mjs`: 50 files, 452 links valid.

### Feature — M8-02: Authentication and Onboarding (Screen S-02)

- **Date**: 2026-10-18
- **Branch**: `feature/m8-auth-onboarding`
- **What**:
  - Implemented authentication routes and onboarding wizard conforming to `docs/08 §11 S-02`:
    - **Clerk Themed Appearance** ([`client/components/auth/clerk-theme.ts`](client/components/auth/clerk-theme.ts)):
      - Mapped Clerk appearance variables strictly to DevMind CSS custom properties (`var(--signal)`, `var(--bg-1)`, `var(--fg-0)`, `var(--bg-2)`, `var(--radius-control)`).
    - **Sign In Route** ([`client/app/sign-in/[[...sign-in]]/page.tsx`](client/app/sign-in/[[...sign-in]]/page.tsx)):
      - Dedicated route embedding Clerk's `<SignIn />` component with fallback developer sign-in card when Clerk keys are unconfigured in local development.
    - **Sign Up Route** ([`client/app/sign-up/[[...sign-up]]/page.tsx`](client/app/sign-up/[[...sign-up]]/page.tsx)):
      - Dedicated route embedding Clerk's `<SignUp />` component with developer registration card fallback.
    - **Screen S-02 Onboarding Wizard** ([`client/app/onboarding/page.tsx`](client/app/onboarding/page.tsx)):
      - 3-step progress rail:
        1. Workspace creation / selection with tenant partition guarantee.
        2. Project source connection (VS Code extension deep link `vscode://devmind.devmind-vscode/connect` vs manual registration).
        3. Synchronization mode selection (`metadata_only` vs `indexed`) with plain-language privacy disclosure and required consent acknowledgement.
    - **Unit Tests** ([`client/tests/auth-onboarding.test.tsx`](client/tests/auth-onboarding.test.tsx)):
      - 5 Vitest tests covering token mappings, SignIn/SignUp branding, and S-02 step rail.
  - Verified with `pnpm --filter client test`: 65 client tests pass.
  - Verified with `node scripts/test-all.mjs --fast`: all 13 checks pass.

### Feature — M8-01: Tokens and Base UI Components

- **Date**: 2026-10-18
- **Branch**: `feature/m8-components`
- **What**:
  - Implemented design system base components conforming to `docs/08 §3-§7`:
    - **Button** ([`client/components/ui/Button.tsx`](client/components/ui/Button.tsx)):
      - Variants: `primary` (`--signal`), `secondary` (`--line-3`), `tertiary`, `destructive` (`--danger`).
      - Sizes: `sm` (32px), `default` (36px), `lg` (44px min touch target).
      - Loading spinner, disabled state, left/right icons, ref forwarding.
    - **Badge** ([`client/components/ui/Badge.tsx`](client/components/ui/Badge.tsx)):
      - Semantic encoding (glyphs: `●`, `✓`, `▲`, `✕`, `◆`) ensuring color is never used alone (`docs/08 §3.4`).
      - Native support for evidence levels (`E0`, `E1`, `E2`), mono formatting for IDs and counts.
    - **Card** ([`client/components/ui/Card.tsx`](client/components/ui/Card.tsx)):
      - Subcomponents: `CardHeader`, `CardTitle`, `CardDescription`, `CardContent`, `CardFooter`.
      - Layered surfaces (`--bg-1`, `--bg-2`), 1px hairline border (`--line-1`), 6px panel radius (`--radius-panel`).
    - **Input** ([`client/components/ui/Input.tsx`](client/components/ui/Input.tsx)):
      - `--bg-2` fill, `--line-3` border, `--radius-control` (4px).
      - Accessible label with `htmlFor`, helper text, inline error with glyph (`✕`) and `role="alert"`.
    - **Skeleton** ([`client/components/ui/Skeleton.tsx`](client/components/ui/Skeleton.tsx)):
      - Layout-matched placeholder, `--bg-2`, static under `prefers-reduced-motion: reduce`.
    - **Dialog** ([`client/components/ui/Dialog.tsx`](client/components/ui/Dialog.tsx)):
      - Modal overlay, soft shadow, `--radius-panel` (6px), Esc key dismissal, focus trap, accessible title and description.
    - **Tabs** ([`client/components/ui/Tabs.tsx`](client/components/ui/Tabs.tsx)):
      - Accessible `Tabs`, `TabList`, `TabTrigger`, `TabContent`. Active tab indicated by 2px `--signal` underline.
    - **Tooltip** ([`client/components/ui/Tooltip.tsx`](client/components/ui/Tooltip.tsx)):
      - 160ms delay, Esc dismissal, visible on both hover and focus.
    - **Barrel Export** ([`client/components/ui/index.ts`](client/components/ui/index.ts)):
      - Central export of all UI primitives.
    - **Unit Tests** ([`client/tests/ui-components.test.tsx`](client/tests/ui-components.test.tsx)):
      - 14 Vitest tests covering all components, variants, accessibility attributes, and error states.
  - Verified with `pnpm --filter client test`: 60 client tests pass.
  - Verified with `node scripts/test-all.mjs --fast`: all 13 checks pass.

### Feature — M7-10: Injection Corpus Run Against Graph Workflows

- **Date**: 2026-10-18
- **Branch**: `feature/m7-injection-run`
- **What**:
  - Implemented graph prompt-injection benchmark harness, test suite, and baselines per `docs/09 §12`, `docs/05 §14`, and `docs/09 §9`:
    - **Prompt Loader Enhancement** ([`server/app/llm/prompt_loader.py`](server/app/llm/prompt_loader.py)):
      - Added `render(task, variables, version)` method to `PromptLoader` delegating to `PromptTemplate.render`, maintaining strict `<untrusted_data>` escaping and delimiter sanitization.
    - **Evaluation Metrics & Runner** ([`evals/injection/metrics.py`](evals/injection/metrics.py), [`evals/injection/harness.py`](evals/injection/harness.py)):
      - Built `GraphInjectionHarness` executing all 25 vectors in `evals/injection/corpus.json` across:
        1. Prompt delimiter escaping & system boundary persistence on all 4 agent tasks (`agent_manager_routing`, `code_answer`, `security_explanation`, `final_synthesis`).
        2. Tool least-privilege & malicious hijack containment (`AgentToolSet` allowlist enforcement, forbidden tool rejection, path traversal containment).
        3. Structured-output schema conformance under adversarial payloads (`AgentPlan`, `FindingExplanation`, `SynthesizedAnswer`).
        4. Deterministic finding non-suppression under code comment injection (`SEC-001` preserved on unauthenticated routes).
        5. Cross-tenant isolation under prompt injection (`AuthContext` tenant boundary enforcement).
      - Achieved 100.00% pass rate across all 25 corpus items (Delimiter Integrity: 1.0, Tool Containment: 1.0, Finding Protection: 1.0, Cross-Tenant Isolation: 1.0, Schema Conformance: 1.0).
      - Saved baseline to `evals/results/injection/latest.json`.
    - **Documentation Baseline** ([`docs/09-testing-and-quality-strategy.md`](docs/09-testing-and-quality-strategy.md)):
      - Updated §9 tracked baselines table with `Graph Prompt-Injection Defense (M7-10)` metrics.
    - **Unit Tests** ([`server/tests/test_agent_injection.py`](server/tests/test_agent_injection.py)):
      - Added 7 unit tests verifying all 6 non-negotiable assertions from `docs/09 §12`. All pass in 0.60s.
  - Verified with `node scripts/test-all.mjs --fast`: all 13 checks pass, 470 server tests pass, 46 client tests pass. Milestone M7 is 100% complete.

### Feature — M7-09: Evaluation Sets with Baselines (Answer-Quality, Faithfulness)

- **Date**: 2026-10-18
- **Branch**: `feature/m7-eval-baselines`
- **What**:
  - Implemented evaluation corpus, automated evaluator metrics, benchmark harness, and documentation baseline per `docs/09 §9`, `docs/05 §7`, `docs/05 §14`, and `docs/09 §10`:
    - **Dataset** ([`evals/agents/dataset.json`](evals/agents/dataset.json)):
      - Golden test corpus containing 7 CodeMate Q&A questions (5 grounded across fixture and server files + 2 out-of-scope/insufficient evidence negative controls) and 8 AuthCheck security review cases (covering compliant routes, tampered hash rejection, line range boundary violations, unresolved callee E2 to E1 downgrade, language discipline enforcement, and secret redaction).
    - **Metrics Module** ([`evals/agents/metrics.py`](evals/agents/metrics.py)):
      - Defined Pydantic models for `AnswerQualityMetrics`, `FaithfulnessMetrics`, and `AgentBenchmarkSummary`.
      - Computes citation precision, citation recall, symbol coverage, insufficient evidence accuracy, route confirmation accuracy, evidence grounding accuracy, finding downgrade fidelity, and language discipline adherence.
    - **Benchmark Harness** ([`evals/agents/harness.py`](evals/agents/harness.py)):
      - Built `AgentEvaluationHarness` executing real evaluation across citation verification (`CitationVerifier.verify_batch`), AST structural route analysis, and finding verification (`EvidenceVerifier.verify_draft_finding`).
      - Records benchmark results to `evals/results/agents/latest.json` and timestamped JSON files.
      - Achieved baseline scores: Answer Quality 0.9600, Faithfulness 1.0000, Composite Score 0.9840 (exceeds min tolerance 0.8500).
    - **Documentation Baseline** ([`docs/09-testing-and-quality-strategy.md`](docs/09-testing-and-quality-strategy.md)):
      - Updated §9 tracked baselines table with `Agent Workflows: Answer Quality & Faithfulness (M7)` metrics.
    - **Unit Tests** ([`server/tests/test_agent_eval.py`](server/tests/test_agent_eval.py)):
      - Added 5 unit tests validating dataset schema, CodeMate verification, AuthCheck verification vectors, metric calculation, and full harness execution. All pass in 0.18s.
  - Verified with `node scripts/test-all.mjs --fast`: all 13 checks pass, 463 server tests pass, 46 client tests pass.

### Feature — M7-08: Job Integration (ask_project, security_review) and SSE Event Streaming

- **Date**: 2026-10-18
- **Branch**: `feature/m7-agent-jobs`
- **What**:
  - Implemented analysis job lifecycle, Celery background worker orchestration, and Server-Sent Events (SSE) streaming per `docs/03 §5.2`, `docs/03 §12.2`, `docs/05 §4`, and `docs/02 §8.2`:
    - **Persistence & Repository** ([`server/app/persistence/repositories/brain_repo.py`](server/app/persistence/repositories/brain_repo.py)):
      - Added `get_job_by_id`, `list_jobs` (with status filtering and pagination), and `get_job_events` query methods enforcing `AuthContext` tenancy.
    - **Domain Service** ([`server/app/domain/jobs/service.py`](server/app/domain/jobs/service.py)):
      - Added `create_analysis_job` with idempotency validation and async enqueuer hook.
      - Added `get_job_by_id`, `list_project_jobs`, and cooperative `request_job_cancellation`.
      - Added `publish_job_event` persisting structured milestone events to `job_events` table and broadcasting real-time JSON payloads to Redis Pub/Sub channels (`{prefix}job_events:{job_id}`).
      - Implemented `stream_job_events` async SSE generator with past event replay (`since_seq`), Redis pub/sub live consumption, periodic heartbeat pings (`: ping`), and terminal event handling.
      - Decoupled worker enqueueing via `register_job_enqueuer` / `get_job_enqueuer` ensuring `domain` never imports `workers`.
    - **API Endpoints & Schemas** ([`server/app/api/jobs.py`](server/app/api/jobs.py), [`server/app/api/schemas.py`](server/app/api/schemas.py)):
      - Added `POST /api/v1/projects/{pid}/analyses` (202 Accepted with links to status and events), `GET /api/v1/projects/{pid}/jobs`.
      - Added `GET /api/v1/jobs/{id}`, `POST /api/v1/jobs/{id}/cancel`, and `GET /api/v1/jobs/{id}/events` (`text/event-stream`).
      - Mounted routers under `/api/v1` in [`server/app/main.py`](server/app/main.py) and declared route permissions (`PERM_ANALYSIS_CREATE`, `PERM_PROJECT_READ`).
    - **Worker Integration** ([`server/app/workers/celery_app.py`](server/app/workers/celery_app.py)):
      - Wired `AgentManager` execution into `devmind.process_job` for `ask_project` and `security_review`.
      - Emitted intake, progress, and finding persistence milestones with token usage and cost accounting.
      - Batch-upserted verified findings from AuthCheck workflows directly into the `findings` table.
      - Registered Celery task dispatcher with domain service.
  - Authored comprehensive test suite in [`server/tests/test_agent_jobs.py`](server/tests/test_agent_jobs.py) covering API creation, 403 authorization guards, listing, details, cancellation, SSE stream formatting, and Celery worker agent workflow execution. All 8 tests pass; full test-all passes (13 passed, 458 server tests pass).

- **Date**: 2026-10-18
- **Branch**: `feature/m7-evidence-verifier`
- **What**:
  - Implemented the deterministic evidence and citation verification engine in [`server/app/analysis/evidence_verifier.py`](server/app/analysis/evidence_verifier.py) per `docs/05 §7`, `docs/03 §3.4`, and `docs/03 §12.1`:
    - Full implementation of all 7 mandatory verification checks:
      1. Snapshot presence and version check ensuring cited file path exists in snapshot and matches expected version ID.
      2. Line range integrity validating positive start line, non-inverted range, and file length boundary checks.
      3. Snippet hash confirmation computing normalized SHA-256 digest of cited line slices and rejecting tampered evidence.
      4. Rule ID registry checking built-in DevMind rules and approved scanner prefixes (`bandit.*`, `semgrep.*`, `trivy.*`, `gitleaks.*`, `eslint.*`, `ruff.*`, `devmind.*`) with dynamic registration support.
      5. Structural claim verification cross-referencing route authorization findings against `RouteGuardAnalyzer` evaluations and rejecting false claims on protected/exempt routes.
      6. Evidence level verification downgrading E2 findings with unresolved callees or dynamic dependencies in `analysis_scope` to E1; downgrading disallowed E3 exploitability claims in v1 (ADR-041); sanitizing exploitability language (`vulnerable`, `exploitable`) for E0/E1 findings per `AGENTS.md §5.7`.
      7. Secret detection and redaction identifying private keys, API tokens (Anthropic, OpenAI, Stripe, GitHub, GitLab, Slack, AWS), and database connection credentials, redacting them to `[REDACTED:<type>:<hash8>]`.
    - Implemented `CitationVerifier` for structured and inline markdown citations (`[source: path:line-line]`, `[file]`, `[symbol]`, `[chunk_id]`), computing grounding ratios and identifying hallucinated references.
    - Exported models and utilities in [`server/app/analysis/__init__.py`](server/app/analysis/__init__.py).
    - Integrated `EvidenceVerifier` into AuthCheck's `verify_evidence_node` in [`server/app/orchestration/authcheck.py`](server/app/orchestration/authcheck.py) to filter, sanitize, and record dropped/downgraded findings.
  - Authored 14 unit tests in [`server/tests/test_evidence_verifier.py`](server/tests/test_evidence_verifier.py) covering rule registry, file/version checks, line bounds, snippet hashing, structural claims, E2/E3 downgrades, secret redaction, and citation verification. All 13 test-all checks pass (450 server tests pass).

### Feature — M7-06: AuthCheck Workflow Nodes and Evidence-Constrained Explanation

- **Date**: 2026-10-18
- **Branch**: `feature/m7-authcheck`
- **What**:
  - Implemented the AuthCheck specialist workflow subgraph in [`server/app/orchestration/authcheck.py`](server/app/orchestration/authcheck.py) per `docs/05 §6.3`:
    - Route analysis node (`analyze_routes_node_factory`) executing `RouteGuardAnalyzer` for deterministic route enumeration, guard chain resolution, and E2/E1 draft finding emission.
    - Security explanation node (`explain_findings_node_factory`) rendering versioned `security_explanation` v1 prompt and parsing `FindingExplanation` structured output for risks and remediation diffs with evidence constraint enforcement.
    - Evidence verification and synthesis node (`verify_evidence_node` / `finalize_authcheck_node`) formatting structured security summaries with endpoints discovered, protected, missing auth/authz, public exempt, and unsupported frameworks notice.
    - Exported `AuthCheckAgent`, `build_authcheck_graph`, and `run_authcheck_specialist` in [`server/app/orchestration/__init__.py`](server/app/orchestration/__init__.py).
  - Integrated AuthCheck specialist execution into `AgentManager` in [`server/app/orchestration/manager.py`](server/app/orchestration/manager.py) with parallel execution support.
  - Added clean LangGraph reducer returns across specialist nodes in [`server/app/orchestration/codemate.py`](server/app/orchestration/codemate.py) and [`server/app/orchestration/state.py`](server/app/orchestration/state.py) to prevent duplicate accumulation during parallel fan-out.
  - Authored 9 unit tests in [`server/tests/test_authcheck.py`](server/tests/test_authcheck.py) covering route analysis, prompt rendering, structured explanation parsing, E2 verification fallback, unsupported framework notices, and specialist integration. All 13 test-all checks pass (440 server tests pass).

### Feature — M7-05: Guard Resolution and Structural Route Check (E2 Deterministic Confirmation)

- **Date**: 2026-10-18
- **Branch**: `feature/m7-guard-resolution`
- **What**:
  - Implemented deterministic route enumeration, guard resolution, and E2 verification in [`server/app/analysis/guard_resolution.py`](server/app/analysis/guard_resolution.py) per `docs/05 §6.3`, `docs/03 §3.2`, and `docs/03 §12.1`:
    - Framework detection supporting FastAPI, Express, and Next.js (route handlers and server actions), recording any unsupported frameworks as `not_analyzed` (never reported as "safe").
    - Route enumeration discovering endpoints from `defines_route` edges, `route_handler`, and `server_action` symbols.
    - Guard chain resolution traversing `guarded_by` and `calls` relationships (middleware, dependencies, decorators, inline checks) with cycle prevention and depth tracking.
    - Deterministic route sensitivity classification (public, authenticated, sensitive/admin) with customizable `ProjectSecurityConfig`.
    - Deterministic E2 confirmation when guard chain is fully resolved within `analysis_scope` (`"handler and N resolved callees; 0 unresolved dependencies"`) emitting `devmind.authz.missing_role_check` or `devmind.authn.unprotected_route`.
    - E1 fallback when call-path resolution is incomplete due to dynamic dependencies or unanalyzed external calls.
  - Exported analysis models and `RouteGuardAnalyzer` in [`server/app/analysis/__init__.py`](server/app/analysis/__init__.py).
  - Authored 11 unit tests in [`server/tests/test_guard_resolution.py`](server/tests/test_guard_resolution.py) covering framework detection, sensitivity classification, route enumeration, E2 missing authn/authz confirmation, E1 fallback on incomplete paths, protected and public exemptions, unsupported framework handling, and repository database integration. All 13 test-all checks pass (427 server tests pass).

### Feature — M7-04: CodeMate Workflow Nodes and Citation Validation

- **Date**: 2026-10-18
- **Branch**: `feature/m7-codemate`
- **What**:
  - Implemented the canonical CodeMate workflow subgraph in [`server/app/orchestration/codemate.py`](server/app/orchestration/codemate.py) per `docs/05 §4` and `docs/05 §6.1`:
    - Context retrieval node (`retrieve_context_node_factory`) running hybrid retrieval search via `search_brain`.
    - Insufficient context fallback node (`insufficient_context_node`) producing explicit `SynthesizedAnswer` explanations when no context packs match.
    - Grounded generation node (`generate_answer_node_factory`) rendering versioned `codemate_generate` prompt and streaming synthesis with strict citation syntax `[source: <target>]`.
    - Deterministic citation verification (`validate_citations` / `validate_citations_node`) validating provenance against ContextPack reference docs, symbol keys, exact file paths, and overlapping line ranges `[path:start-end]`.
    - Single-retry regeneration node (`regenerate_answer_node_factory`) instructing LLM to regenerate removing or fixing ungrounded citations when hallucination is detected.
    - Final answer extraction node (`finalize_node`) producing verified `SynthesizedAnswer` state.
  - Wired CodeMate specialist execution directly into `AgentManager`'s `codemate_node_factory` in [`server/app/orchestration/manager.py`](server/app/orchestration/manager.py).
  - Exported CodeMate components in [`server/app/orchestration/__init__.py`](server/app/orchestration/__init__.py).
  - Authored 7 unit tests in [`server/tests/test_codemate.py`](server/tests/test_codemate.py) covering citation parsing, line range overlap math, insufficient context fallback, grounded generation, regeneration on hallucinated citations, and specialist integration. All 13 test-all checks pass (416 server tests pass).

### Feature — M7-03: Agent Manager Graph and Plan Execution Routing

- **Date**: 2026-10-18
- **Branch**: `feature/m7-manager-routing`
- **What**:
  - Implemented the canonical Agent Manager LangGraph workflow in [`server/app/orchestration/manager.py`](server/app/orchestration/manager.py) per `docs/05 §2` and `docs/05 §4.1`:
    - Deterministic intent classification (`classify_intent_deterministically`) mapping explicit job types (`ask_project`, `security_review`, `comprehensive_review`) and keyword signals directly to specialist plans, bypassing the LLM route for speed and zero cost.
    - LLM routing fallback (`classify_intent_with_llm`) rendering versioned prompt `agent_manager_routing` (v1) and validating output against `AgentPlan` schema, filtering to allowlisted MVP specialists (`codemate`, `authcheck`).
    - Specialist fan-out executing CodeMate and AuthCheck in parallel branches with concurrent state reducer `merge_specialist_tasks`.
    - Join barrier, deterministic evidence verifier, and multi-specialist synthesis.
    - Human approval gate interrupting execution before external side-effects with checkpointer resume support.
  - Added `merge_specialist_tasks` reducer to `RunState.plan` in [`server/app/orchestration/state.py`](server/app/orchestration/state.py).
  - Exported `AgentManager`, `build_agent_manager_graph`, `classify_intent_deterministically`, and `RELEASED_SPECIALISTS` in [`server/app/orchestration/__init__.py`](server/app/orchestration/__init__.py).
  - Authored 10 unit tests in [`server/tests/test_agent_manager.py`](server/tests/test_agent_manager.py) covering deterministic routing, LLM schema parsing and fallback, parallel fan-out, approval gate interrupt/resume, and streaming. All 13 test-all checks pass (409 server tests pass).

### Feature — M7-02: Tools with Scoped Access (search_brain, get_symbol, get_file_range, get_relationships)

- **Date**: 2026-10-18
- **Branch**: `feature/m7-agent-tools`
- **What**:
  - Implemented scoped retrieval and analysis tools in [`server/app/orchestration/tools.py`](server/app/orchestration/tools.py) adhering strictly to `docs/05 §9` tool execution boundaries:
    - Closed allowlisted set: read-only by default, tenant-isolated via `AuthContext`, no code execution.
    - `search_brain`: hybrid retrieval over Project Brain returning bounded items and `CitationRef` structures without exposing raw unconsented code.
    - `get_symbol`: symbol declaration lookup by name and optional path filter, extracting qualified signatures, framework tags, and line ranges.
    - `get_file_range`: line-bounded file slice reader strictly clamped to max 200 lines, reconstructing line text from current version code chunks.
    - `get_relationships`: architectural call graph, import edge, and route guard inspector supporting incoming, outgoing, and bidirectional traversal.
    - `AgentToolSet` wrapper and `create_agent_tools` factory generating LangChain `StructuredTool` instances and LLM gateway `ToolDefinition`s.
    - Audit logging records tool name, counts, and durations without leaking raw queries or source code.
  - Exported all tools and input schemas in [`server/app/orchestration/__init__.py`](server/app/orchestration/__init__.py).
  - Authored 13 unit tests in [`server/tests/test_agent_tools.py`](server/tests/test_agent_tools.py) verifying success paths, cross-tenant isolation, line range clamping, symbol filtering, LangChain tool invocations, and tool definition schemas. All 13 test-all checks pass (399 server tests pass).

### Feature — M7-01: LangGraph State Schema and Checkpointer

- **Date**: 2026-10-18
- **Branch**: `feature/m7-state-checkpointer`
- **What**:
  - Implemented LangGraph state schema and reducers in [`server/app/orchestration/state.py`](server/app/orchestration/state.py) (docs/05 §4.2):
    - `RunState`: TypedDict holding references and small structured values, never code bodies, keeping checkpoints small and free of source code.
    - Reducer `append_items` for `drafts`, `context_refs`, and `errors`.
    - Reducer `merge_usage_totals` accumulating tokens and cost units across parallel nodes.
    - Structured state types: `RequestState`, `IntentState`, `SpecialistTask`, `CitationRef`, `DraftFinding`, `VerifiedFinding`, `Hypothesis`, `Proposal`, `ApprovalState`, `NodeError`, `BudgetState`, and `UsageTotals`.
    - Factory function `create_initial_run_state`.
  - Implemented checkpointer factory and thread identification in [`server/app/orchestration/checkpointer.py`](server/app/orchestration/checkpointer.py) (ADR-006, ADR-037, OQ-12):
    - `format_thread_id` and `parse_thread_id` enforcing canonical `devmind:<project_id>:<run_id>` format.
    - `CheckpointerFactory` supporting `InMemorySaver` for testing/local execution and `PostgresSaver`/`AsyncPostgresSaver` in schema `langgraph` with worker direct connection fallback (OQ-12).
  - Added `AgentRun` model in [`server/app/persistence/models/brain.py`](server/app/persistence/models/brain.py) and created Alembic migration `0009_agent_runs.py` (docs/03 §3.3).
  - Authored 9 unit and integration tests in [`server/tests/test_agent_state.py`](server/tests/test_agent_state.py) verifying state graph execution, state reducers, checkpointing, and human approval interrupt/resume. All 13 suite checks pass.

### Feature — M6-11: LLM Evaluation Benchmark Harness and Prompt Injection Test Corpus

- **Date**: 2026-10-18
- **Branch**: `feature/m6-llm-eval`
- **What**:
  - Authored comprehensive prompt injection attack corpus in [`evals/injection/corpus.json`](evals/injection/corpus.json) covering all required vectors (docs/07 §8, docs/09 §12):
    - Vectors: `code_comment`, `readme_docs`, `file_path`, `commit_pr`, `logs`, `retrieved_context`, `encoded_obfuscated`, `tag_breakout`, `role_hijack`, `jailbreak_persona`, and benign controls.
    - Exported dataset path loader in [`evals/injection/__init__.py`](evals/injection/__init__.py).
  - Built LLM evaluation benchmark harness and metrics in [`evals/llm/`](evals/llm/) (docs/05 §16, docs/09 §12):
    - [`evals/llm/metrics.py`](evals/llm/metrics.py): `InjectionEvaluationMetrics` (delimiter integrity rate, precision, recall, F1 score), `SchemaEvaluationMetrics` (validity rate, one-shot repair rate), and `LLMBenchmarkSummary`.
    - [`evals/llm/harness.py`](evals/llm/harness.py): Benchmark runner validating delimiter encapsulation, tag neutralization, signal detection accuracy, and structured output schema conformance; writes structured results to `evals/results/llm/latest.json`.
    - Added `"eval:llm"` npm script in [`package.json`](package.json).
  - Enhanced prompt injection detection regex patterns in [`server/app/llm/prompt_loader.py`](server/app/llm/prompt_loader.py) and added convenience properties to `PromptTemplate`, `ValidationResult`, and `SchemaRegistry`.
  - Authored 7 comprehensive unit and integration tests in [`server/tests/test_llm_eval.py`](server/tests/test_llm_eval.py).
  - Verified 100% delimiter integrity, 100% detector precision, 100% detector recall (1.0000 F1), and 87.5% schema validity rate. All 13 suite checks pass.

### Feature — M6-10: Versioned Prompt Template Loader with Untrusted Context Escaping

- **Date**: 2026-10-18
- **Branch**: `feature/m6-prompt-loader`
- **What**:
  - Implemented versioned prompt template parser and loader in [`server/app/llm/prompt_loader.py`](server/app/llm/prompt_loader.py) (docs/05 §8, docs/07 §8, ADR-028):
    - `PromptFrontMatter`: Validates front matter metadata via Pydantic (`task`, `version`, `input_variables`, `untrusted_variables`, `output_schema`, `required_capabilities`, `description`).
    - `PromptTemplate`: Manages system prompt template, user prompt template, variable validation, and deterministic substitution (`{var}` and `{{var}}`).
    - `escape_untrusted_content`: Encapsulates untrusted inputs inside `<untrusted_data name="...">...</untrusted_data>` blocks and neutralizes closing tag sequences `</untrusted_data>` to prevent prompt breakout.
    - `detect_injection_signals`: Regex-based heuristic detector auditing instruction override, role hijack, and secret exfiltration attempts, populating `injection_signals` in `RenderedPrompt`.
    - `PromptLoader`: Directory-based cached template loader resolving `prompts/<task>/v<version>.md`.
  - Added canonical versioned prompt templates in `server/app/llm/prompts/`:
    - `agent_manager_routing/v1.md` (AgentPlan)
    - `code_answer/v1.md` (untrusted repo code, diffs, query)
    - `security_explanation/v1.md` (FindingExplanation)
    - `final_synthesis/v1.md` (SynthesizedAnswer)
    - `query_rewrite/v1.md` (RewrittenQuery)
  - Exported loader and helpers in [`server/app/llm/__init__.py`](server/app/llm/__init__.py).
  - Authored 15 unit tests in [`server/tests/test_llm_prompts.py`](server/tests/test_llm_prompts.py). All 13 suite checks pass.

### Feature — M6-09: Structured-Output Schema Repair and Validation Layer

- **Date**: 2026-10-18
- **Branch**: `feature/m6-output-repair`
- **What**:
  - Implemented canonical task Pydantic schemas in [`server/app/llm/schemas.py`](server/app/llm/schemas.py) (docs/05 §10, §11):
    - `AgentPlan` (task: `agent_manager_routing`), `FindingExplanation` (task: `security_explanation`), `SynthesizedAnswer` (task: `final_synthesis`), `RewrittenQuery` (task: `query_rewrite`).
    - Implemented `SchemaRegistry` and default global instance for resolving schemas by name and generating `StructuredOutputSpec` with JSON Schema dictionary definitions.
  - Implemented extraction, validation, and repair engine in [`server/app/llm/repair.py`](server/app/llm/repair.py) (docs/05 §10, ADR-027):
    - `extract_json_candidate`: Strips markdown code blocks (` ```json ... ``` ` or ` ``` ... ``` `) and isolates JSON objects/arrays from surrounding text.
    - `clean_json_string`: Cleans common syntax anomalies such as trailing commas before closing braces/brackets.
    - `StructuredOutputRepairer`: Validates JSON against registered Pydantic models with detailed field-level error messages.
    - Implemented `attempt_repair`: Generates a targeted correction conversation with validation errors and executes exactly ONE repair attempt at temperature 0.0 with the same model/adapter.
  - Integrated into [`server/app/llm/router.py`](server/app/llm/router.py):
    - Automatic `output_schema` resolution from `tasks.yaml` when not explicitly provided on request.
    - Model capability mode adaptation (`native`, `json_mode`, or `prompt_only`).
    - Automatic validation and one-shot repair upon syntax or schema invalid output.
    - Non-bypassable failure: if repair attempt fails, raises `LLMInvalidOutputError` (`llm.invalid_output`) without attempting fallback models (ADR-027).
  - Added 13 unit and integration tests in [`server/tests/test_llm_output_repair.py`](server/tests/test_llm_output_repair.py). All 74 LLM tests, 2 boundary tests, and 355 server tests pass.

### Feature — M6-08: LLM Usage Recording, Cost Accounting, and Persistence

- **Date**: 2026-10-17
- **Branch**: `feature/m6-usage-records`
- **What**:
  - Implemented `calculate_cost_units` in [`server/app/llm/usage.py`](server/app/llm/usage.py) (docs/05 §13):
    - Computes integer cost accounting units from input/output tokens and `price_units` configuration from `models.yaml`.
  - Implemented `LLMUsageRecorder` in [`server/app/llm/usage.py`](server/app/llm/usage.py) (docs/05 §13, docs/03 §3.5):
    - In-memory audit trail with `RecordedUsage` model (UUIDv7, tenant scoping, outcome, latency, token counts).
    - Decoupled asynchronous `UsageSink` protocol preserving architectural layer boundary (`app.llm` never imports `app.persistence` per docs/02 §4.1).
  - Implemented `create_database_usage_sink` in [`server/app/persistence/repositories/usage_repo.py`](server/app/persistence/repositories/usage_repo.py):
    - Async sink adapter persisting usage records via `UsageRecordRepository` under `SystemContext(reason="llm_inference_usage_recording")`.
  - Integrated usage recording into [`server/app/llm/router.py`](server/app/llm/router.py):
    - Calls recorded on generation success, content refusal (`LLMRefusalError`), timeout (`LLMTimeoutError`), provider errors, and streaming completion.
  - Added 10 unit and integration tests in [`server/tests/test_llm_usage_records.py`](server/tests/test_llm_usage_records.py). All 61 LLM tests and 342 server tests pass.

### Feature — M6-07: LLM Quotas, Concurrency Semaphores, and Rate Limiting

- **Date**: 2026-10-17
- **Branch**: `feature/m6-llm-quotas`
- **What**:
  - Implemented `LLMConcurrencyManager` in [`server/app/llm/quotas.py`](server/app/llm/quotas.py) (docs/05 §13):
    - Provider-level concurrency semaphores based on `concurrency.max_in_flight` from `providers.yaml`.
    - Tenant-level concurrency caps (`max_workspace_concurrency`) preventing one workspace from monopolizing workers.
  - Implemented `LLMRateLimiter` in [`server/app/llm/quotas.py`](server/app/llm/quotas.py) (docs/05 §13):
    - Sliding-window rate limiter per provider (e.g. Gemini 15 RPM, Groq 30 RPM) backed by Redis sorted sets with in-memory fallback.
    - Dynamic backoff penalty tracking upon receiving upstream HTTP 429 (`Retry-After`).
  - Implemented `LLMQuotaEnforcer` in [`server/app/llm/quotas.py`](server/app/llm/quotas.py) (docs/05 §13, ADR-046):
    - Pre-call context length verification against `model_entry.limits.max_input_tokens`.
    - Pre-call task budget verification against `task_entry.budget.max_input_tokens`.
    - Monthly workspace token quota enforcement (`monthly_token_allowance_per_workspace`).
  - Integrated into [`server/app/llm/router.py`](server/app/llm/router.py):
    - Automatic fallback when primary provider is rate-limited or context ceiling is exceeded.
    - Token usage deduction towards tenant allowances upon generation completion.
  - Added 10 unit tests in [`server/tests/test_llm_quotas.py`](server/tests/test_llm_quotas.py). All 51 LLM tests and 332 server tests pass.

### Fix — Client Footer Tech Stack & Cloud / Host Mentions Cleanup

- **Date**: 2026-10-17
- **Branch**: `main` (commit `9e57aec`)
- **What**:
  - Removed "Render + Neon Free Profile" and "Next.js · FastAPI · PostgreSQL · Redis" from [`client/components/layout/Footer.tsx`](client/components/layout/Footer.tsx).
  - Replaced with clean "Operational · System Active" status indicator and "Continuous Project Brain" tag.
  - All 46 client tests pass.

### Feature — M6-06: LLM Gateway Router with Fallbacks and Privacy Guard

- **Date**: 2026-10-17
- **Branch**: `feature/m6-gateway-router`
- **What**:
  - Implemented `LLMGatewayRouter` in [`server/app/llm/router.py`](server/app/llm/router.py) (docs/05 §11.6, §12, ADR-027, ADR-047):
    - Candidate resolution mapping `tasks.yaml` primary model and fallbacks to `models.yaml` and `providers.yaml`.
    - Capability matching filter (tool calling, structured output mode, streaming).
    - Status deprecation filter (`status != "deprecated"`).
    - Environment enablement filter (`provider.environments`).
    - Customer source code privacy guard (ADR-047: excludes providers where `source_code_allowed=False` or `terms_reviewed=False` in staging/production when `may_contain_source=True`).
    - Non-streaming execution (`generate`) with automated fallback across eligible candidates on transient errors (`LLMTimeoutError`, `LLMRateLimitError`, `LLMProviderError`, `LLMUnavailableError`).
    - Strict non-bypass on safety refusal (`LLMRefusalError`) and invalid structured output (`LLMInvalidOutputError`): immediately re-raises without attempting fallbacks per ADR-027.
    - Streaming execution (`stream_generate`) with fallback on initial connect failure, while preserving safety and aborting without fallback once tokens have begun streaming to client.
    - Adapter caching and test override registration (`register_adapter_override`).
  - Added 19 comprehensive unit tests in [`server/tests/test_llm_router.py`](server/tests/test_llm_router.py).
  - All 13 checks pass in `node scripts/test-all.mjs --fast` (322 server tests pass).

### Feature — M6-05 & Extension Production Package v0.1.2 Rebuild

- **Date**: 2026-10-17
- **Branch**: `main`
- **What**:
  - **VS Code Extension Production Rebuild (v0.1.2)**:
    - Bumped extension version to `0.1.2` in `extension/package.json` and updated `tests/quality.test.ts`.
    - Enforced production configuration defaults in `extension/package.json`:
      - `devmind.apiBaseUrl`: `"https://api.devmind.warishlabs.in/api/v1"`
      - `devmind.fixtureMode`: `false`
    - Hardened `SettingsService` ([`extension/src/services/settings.ts`](extension/src/services/settings.ts)) so production builds strictly prioritize `https://api.devmind.warishlabs.in/api/v1` and disable fixture mode even if legacy `localhost` defaults existed in workspace settings.
    - Rebuilt and packaged `dist/devmind-vscode.vsix` (version `0.1.2`, 51.99 KB, 9 clean files, no secrets or environment files included).
  - **Milestone M6-05: OpenAI-Compatible LLM Adapter**:
    - Implemented `OpenAICompatibleAdapter(LLMAdapter)` in `server/app/llm/adapters/openai_compatible.py` targeting standard `/chat/completions` REST endpoints.
    - Compatible with Groq (free tier: 30 RPM), OpenAI, Together, Mistral, and local Ollama.
    - Supports native `json_schema` response_format, tool/function calling, SSE token streaming, and full RFC 9457 exception mapping (`LLMRateLimitError`, `LLMProviderError`, `LLMTimeoutError`, `LLMRefusalError`).
    - Registered as `"openai_compatible"`, `"openai"`, and `"groq"` in the adapter registry.
    - Added 10 unit tests in `server/tests/test_openai_compatible_adapter.py`. Server test suite expanded to 303 passing tests. All 13 test-all fast suite checks pass.

### Feature — M6-04: Google Gemini Generation Adapter (Official REST/SDK Protocol)

- **Date**: 2026-10-17
- **Branch**: `feature/m6-gemini-adapter`
- **What**:
  - Implemented `GoogleGeminiAdapter(LLMAdapter)` in `server/app/llm/adapters/google_genai.py` connecting to Google's official Gemini Generative Language API (v1beta):
    - Default model `gemini-1.5-flash` with support for `gemini-1.5-pro` and `gemini-2.0-flash`.
    - Key resolution supporting `GEMINI_API_KEY` and `DEVMIND_LLM_PRIMARY_API_KEY` with Google AI Studio free tier limits.
    - Unified request mapping: system instructions (`systemInstruction`), messages (`contents` with `user` and `model` roles), generation options (`temperature`, `maxOutputTokens`, `topP`, `stopSequences`).
    - Native structured JSON output configuration with `responseMimeType: "application/json"` and `responseSchema`.
    - Function calling / tool translation (`functionDeclarations`) and tool execution constraints (`AUTO`, `ANY`, `NONE`).
    - SSE streaming via `streamGenerateContent?alt=sse` yielding incremental `LLMStreamChunk` deltas.
    - Complete RFC 9457 error translation: HTTP 429 / `RESOURCE_EXHAUSTED` with `retry-after` hint $\rightarrow$ `LLMRateLimitError`, HTTP 401/403 $\rightarrow$ `LLMError(llm.authentication_error)`, HTTP 400 $\rightarrow$ `LLMInvalidOutputError`, HTTP 5xx $\rightarrow$ `LLMProviderError`, timeouts $\rightarrow$ `LLMTimeoutError`, safety blocks $\rightarrow$ `LLMRefusalError`.
    - Data policy enforcement: `source_code_allowed=False` by default (ADR-046/ADR-047 privacy preservation on free tier).
    - Registered as `"google"` and `"gemini"` in adapter factory registry.
  - Added 12 unit tests in `server/tests/test_gemini_adapter.py` verifying generation, structured output, tool calls, SSE streaming, safety blocks, and error mappings.
  - Server test suite expanded to 293 passing tests. All 13 checks pass in `node scripts/test-all.mjs --fast`.

### Fix — Turnstile Refresh Loop Elimination & Strict Button Lock When Unverified

- **Date**: 2026-10-17
- **Branch**: `main`
- **What**:
  - Eliminated Cloudflare Turnstile infinite iframe reload loop by configuring explicit `retry: "never"`, `refresh-expired: "manual"`, and `refresh-timeout: "never"` on the Turnstile widget render parameters.
  - Added `getResolvedSiteKey()` with domain inspection that routes localhost, LAN IP addresses, and `*.vercel.app` preview deployments to Cloudflare's official dummy test sitekey `1x00000000000000000000AA`, avoiding domain-mismatch (e.g. error 110200) loops when a production-only sitekey is configured.
  - Render widget strictly once per container lifecycle (`renderAttemptedRef`), avoiding duplicate iframes.
  - Locked the submit button completely when unverified across both `EarlyAccessForm` and `contact/page.tsx`:
    - Native `disabled` and `aria-disabled="true"`
    - `pointer-events-none select-none cursor-not-allowed` (physically impossible to click in browser)
    - `tabIndex={-1}` to prevent keyboard activation
    - Explicit label `Verification Required` / `Security Verification Required to Send`
    - Removed `onClick` handler when unverified so no click actions or error popups fire.
  - Verified with 46 client vitest tests passing and all 13 test-all fast suite checks passing. Committed and pushed to `origin/main`.

### Feature — M6-03: Gateway YAML Config Loaders with Pydantic Validation

- **Date**: 2026-10-17
- **Branch**: `main`
- **What**: Implemented versioned YAML configuration files and validation engine for the LLM Gateway (docs/05 §11, M6-03):
  - Created configuration schemas: `server/configs/llm/providers.yaml`, `models.yaml`, and `tasks.yaml`.
  - Implemented `server/app/llm/config.py` with strict Pydantic schemas (`extra="forbid"`): `ProvidersConfig`, `ModelsConfig`, `TasksConfig`, and `GatewayConfig`.
  - Implemented referential integrity checks (model $\rightarrow$ provider, task $\rightarrow$ model, fallback $\rightarrow$ model).
  - Implemented capability constraint validation (tool calling, structured output, streaming) matching tasks against model capabilities.
  - Implemented source-code privacy guard: tasks with `may_contain_source=True` cannot route to providers where `source_code_allowed=False` or `terms_reviewed=False` in staging/production.
  - Implemented placeholder rejection (`.invalid`, `REPLACE_*`, missing token limits) and missing secret environment variable checks for staging and production.
  - Added deterministic SHA-256 `config_hash` computation across configuration files for reproducible run auditing.
  - Added 11 unit tests in `server/tests/test_llm_config.py`. Server test suite grew to 281 passing tests.

### Feature — M6-02: Fake LLM Provider Adapter with Scripted Responses and Fault Injection

- **Date**: 2026-10-17
- **Branch**: `main`
- **What**: Implemented deterministic `FakeLLMAdapter` and fault injection engine for test environments (docs/05 §11.1, §12, §15, M6-02):
  - Created `FakeFaultInjection` model in `server/app/llm/adapters/fake.py` supporting simulated timeouts, rate limits (HTTP 429), provider 5xx errors, content refusals, malformed JSON outputs, and partial stream connection aborts.
  - Implemented `FakeLLMAdapter` supporting FIFO queue scripted responses, task-specific response mappings, synthesized schema-compliant structured outputs, tool call generation, and word-by-word streaming with token usage statistics.
  - Registered `fake` provider in the adapter registry (`register_adapter("fake", FakeLLMAdapter)`).
  - Added 12 unit tests in `server/tests/test_fake_adapter.py` verifying all generation modes, streaming, fault injections, and registry factory creation.

### Fix — Turnstile Refresh Loop, Unverified Submit Button Guard, and Website GitHub Removal

- **Date**: 2026-10-17
- **Branch**: `main`
- **What**: Resolved Cloudflare Turnstile refresh loop, prevented unverified form submissions, and removed GitHub repository links from website:
  - **Turnstile Refresh Loop**: In `client/components/turnstile/TurnstileWidget.tsx`, stored `onVerify`, `onError`, `onExpire` callbacks in `useRef` and added a single-render guard on `widgetIdRef.current` to prevent widget teardown/reconstruction loops caused by parent re-renders when typing into inputs.
  - **Form Submit Button Guards**: Updated `EarlyAccessForm.tsx` and `contact/page.tsx` submit buttons to `disabled={submitting || !turnstileToken}` with `disabled:opacity-40 disabled:cursor-not-allowed` and dynamic status labels (`"Verify to Join"` / `"Verify Security Challenge to Send →"`).
  - **Website GitHub Links Removal**: Removed GitHub repository links and promotion buttons from `Section08CTA.tsx`, `Footer.tsx`, `Section07PrivacyLedger.tsx`, `early-access/page.tsx`, and `contact/page.tsx`, redirecting users to the official VS Code Extension on Marketplace and internal policy pages. Preserved README links intact.

### Feature — M6-01: LLM Provider Adapter Interfaces, Capabilities, and Common Models

- **Date**: 2026-10-17
- **Branch**: `main`
- **What**: Implemented base LLM provider adapter interfaces, capability flags, unified request/response types, and exception hierarchy (docs/05 §11-§12, M6-01):
  - Created `server/app/llm/exceptions.py` with RFC 9457-aligned exception hierarchy: `LLMError`, `LLMTimeoutError`, `LLMRateLimitError`, `LLMProviderError`, `LLMInvalidOutputError`, `LLMUnavailableError`, `LLMRefusalError`, `LLMQuotaExceededError`, `LLMPermissionError`, `LLMContextLengthExceededError`.
  - Created `server/app/llm/models.py` with standard models: `ChatMessage`, `MessageRole`, `FunctionCall`, `ToolCall`, `FunctionDefinition`, `ToolDefinition`, `StructuredOutputSpec`, `LLMGenerationOptions`, `TokenUsage`, `LLMGenerationRequest`, `LLMGenerationResponse`, `LLMStreamChunk`, `ModelCapabilities`, `ProviderDataPolicy`.
  - Created `server/app/llm/adapter.py` defining base `LLMAdapter` abstract class with `generate()`, `stream_generate()`, `validate_request_capabilities()`, and `validate_data_policy()` guards.
  - Created `server/app/llm/registry.py` providing adapter registration and factory mechanisms.
  - Exported all classes and types in `server/app/llm/__init__.py`.
  - Added 11 unit tests in `server/tests/test_llm_gateway.py` verifying model validation, capability enforcement, data policy privacy guards, streaming, exceptions, and registry operations. All 258 server tests pass.

### Feature — M5-11: Failure-State Behavior: Embedding Provider Outage Degradation

- **Date**: 2026-10-17
- **Branch**: `main`
- **What**: Implemented graceful degradation for hybrid retrieval when the embedding provider or vector store experiences an outage (docs/04 §16):
  - Updated `BrainSearchResponse` schema with `degraded: bool` (default `False`) and `degraded_reason: str | None`.
  - In `RetrievalService.search()`, safely caught provider exceptions or missing active spaces; set `is_degraded = True` with descriptive diagnosis without raising HTTP 500.
  - Degraded gracefully to RRF fusion across available `keyword` and `symbol` channels, preserving search continuity.
  - Regulated `_retrieve_vectors()` to raise explicit runtime errors on provider network failures or empty responses so the orchestrator can catch and flag degradation cleanly.
  - Synchronized OpenAPI spec (`common/openapi.json`) and TypeScript client types (`schema.d.ts`).
  - Added unit tests in `server/tests/test_hybrid_retrieval.py` verifying degradation behavior and ensuring all 247 server tests pass.

### Feature — M5-10: Record Retrieval Baselines in docs/09 §9

- **Date**: 2026-10-17
- **Branch**: `main`
- **What**: Recorded first empirical retrieval benchmark baselines into `docs/09-testing-and-quality-strategy.md` §9 and established regression gates:
  - Recorded benchmark results from `evals/results/retrieval/latest.json` under commit `3b381fb`.
  - Documented baseline metrics across 12 labeled queries:
    - Fused RRF: Recall@5: `0.5544`, MRR: `0.9375`, nDCG@5: `0.7377`.
    - Fused RRF + 1-hop expansion: Recall@5: `0.5775`, MRR: `0.9375`, nDCG@5: `0.7658`.
    - Ablation comparison: Fused RRF outperforming keyword (`0.6803`), vector (`0.6779`), and symbol (`0.4209`).
  - Defined regression gate tolerance: maximum allowed drop in overall nDCG@5 is $\le 0.02$.

### Feature — M5-09: Retrieval Evaluation Harness and Benchmark Dataset

- **Date**: 2026-10-17
- **Branch**: `main`
- **What**: Implemented deterministic retrieval evaluation harness and labeled benchmark dataset:
  - **Benchmark Dataset (`evals/retrieval/dataset.json`)**:
    - 12 labeled queries across 4 categories: `identifier` (exact/trigram), `concept` (natural language), `flow` (relationship/callee tracing), and `no_answer` (negative controls).
    - Graded relevance scores (relevance 2 for primary definitions/routes, 1 for callers/dependencies).
  - **Metrics Computation Engine (`evals/retrieval/metrics.py`)**:
    - Implemented Recall@k, Mean Reciprocal Rank (MRR), Normalized Discounted Cumulative Gain (nDCG@k), and No-Answer accuracy.
    - Added category-level and overall aggregation helper `aggregate_query_metrics()`.
  - **Evaluation Harness & Runner (`evals/retrieval/harness.py`)**:
    - Created `InMemoryFixtureRetriever` indexing the fixture codebases (`fastapi-admin`, `express-admin`).
    - Implemented ablation runner comparing: `symbol_only`, `keyword_only`, `vector_only`, `fused` (RRF), and `fused_expanded` (RRF + 1-hop expansion).
    - Demonstrated empirical advantage of hybrid RRF (nDCG@5: `0.7377` fused vs `0.6803` keyword vs `0.6779` vector vs `0.4209` symbol; expansion further improves to `0.7658`).
    - Added timestamped and `latest.json` result persistence under `evals/results/retrieval/`.
    - Added `pnpm eval:retrieval` command to root `package.json`.
  - **Test Suite (`server/tests/test_retrieval_eval.py`)**:
    - Added 8 unit tests validating metric edge cases, dataset schema, fixture retriever, and benchmark execution.
    - Verified all 245 server tests pass.

### Feature — Extension v0.1.1 Rebuild & Packaging with Embedded Environment

- **Date**: 2026-10-17
- **Branch**: `main`
- **What**: Bumped VS Code extension version to `0.1.1`, injected production environment defaults, and packaged artifact:
  - Bumped version in `extension/package.json` to `0.1.1`.
  - Updated `extension/src/services/syncClient.ts` `X-DevMind-Client` header to `extension/0.1.1`.
  - Updated `extension/tests/quality.test.ts` to assert version `0.1.1` and tolerate fresh package states.
  - Executed production esbuild build with `https://api.devmind.warishlabs.in/api/v1` and `fixtureMode: false` inlined.
  - Packaged `extension/dist/devmind-vscode.vsix` (9 files, 51.93 KB) and verified inlined bundle inside VSIX.
  - Verified all 70 extension vitest tests pass.

### Feature — M5-08: Hybrid Retrieval with Fusion and Context-Pack Builder

- **Date**: 2026-10-17
- **Branch**: `main`
- **What**: Implemented multi-channel hybrid retrieval, Reciprocal Rank Fusion (RRF), 1-hop relationship expansion, token-bounded context-pack assembly, and `POST /api/v1/projects/{pid}/brain/search`:
  - **Retrieval Configuration (`server/configs/retrieval.yaml`)**:
    - Default fusion hyperparameters: $k = 60$, equal channel weights ($w_{\text{symbol}} = 1.0$, $w_{\text{keyword}} = 1.0$, $w_{\text{vector}} = 1.0$).
    - Configurable token budget ($2000$ tokens default, capped at $8192$), max results per channel ($20$).
  - **BrainRepository Multi-Channel Retrieval**:
    - Added `search_symbols()` using exact case-insensitive match and `pg_trgm` similarity ranking.
    - Added `get_relationships_for_symbols()` querying 1-hop caller/callee/definition graph edges.
    - Updated `search_chunks_text()` and `search_chunks_vector()` with eager loading (`joinedload`) of parent `ProjectFile` records.
  - **RetrievalService & RRF Fusion (`server/app/domain/brain/retrieval_service.py`)**:
    - Implemented multi-channel retrieval orchestrator querying symbol name, full-text tsvector keyword, and pgvector cosine similarity.
    - Canonicalized chunk-to-symbol identity mapping and computed RRF scores: $\text{RRF}(d) = \sum_{c \in C} \frac{w_c}{k + \text{rank}_c(d)}$.
    - Relationship graph 1-hop expansion: dynamically resolved related symbol definitions and callers/callees.
    - Assembled markdown Context Pack with strict token budget enforcement, code fence language deduction, and provenance citations (`path`, `line_range`, `symbol_key`).
  - **API Endpoint & OpenAPI Spec (`server/app/api/brain.py`)**:
    - Mounted `POST /api/v1/projects/{pid}/brain/search` guarded by `@declare_permission(PERM_BRAIN_READ)`.
    - Regenerated OpenAPI spec (48 endpoints) and synchronized `@devmind/common` SDK TypeScript types (`schema.d.ts`).
  - **Automated Verification**:
    - Added comprehensive unit and integration test suite (`server/tests/test_hybrid_retrieval.py`, 5 tests).
    - Verified all 237 server tests pass (`pytest`), 0 lint warnings (`ruff`), and clean 13/13 passes in fast runner (`node scripts/test-all.mjs --fast`).

### Feature — Neon Migration, Local Separation & Production Extension Packaging

- **Date**: 2026-10-17
- **Branch**: `main`
- **What**: Executed production Neon database migrations, maintained strict local development environment separation, packaged the production VS Code extension with verified embedded environment variables, and added direct Vercel deployment automation:
  - **Neon PostgreSQL Migration**:
    - Acquired PostgreSQL advisory lock `0x444D5F4D49475231` on Neon.
    - Executed all 8 pending Alembic revisions sequentially (`0001_initial_tenancy` through `0008_github_connections`).
    - Successfully created all 28 production tables (including `chunk_embeddings` with `pgvector` HNSW index and `code_chunks` with `pg_trgm` GIN index).
    - Executed idempotent reference data seed provisioning the default active embedding space (`fake-embed-v1`, 64-dim).
    - Verified final Neon schema revision at `0008_github_connections`.
  - **Local Development Configuration**:
    - Kept `server/.env.local` completely isolated from `server/.env.production`.
    - Tested local database connectivity (`localhost:5433/devmind`); ping `SELECT 1` verified successful.
  - **VS Code Extension Production Packaging**:
    - Updated `extension/.env.production` with `DEVMIND_API_BASE_URL=https://api.devmind.warishlabs.in/api/v1` and `DEVMIND_FIXTURE_MODE_DEFAULT=false`.
    - Updated `extension/esbuild.mjs` to dynamically load `.env.production` in production mode and prevent localhost URLs from being packaged.
    - Packaged `extension/dist/devmind-vscode.vsix` (9 files, 51.93 KB) with embedded production defaults verified by direct unzipping.
    - Verified zero private secrets or environment files in the VSIX bundle.
  - **Vercel Deployment Automation & Guide**:
    - Added `"deploy:client"` (`npx --yes vercel deploy client --prod`) and `"deploy:client:preview"` (`npx --yes vercel deploy client`) to root `package.json`.
    - Updated `DEPLOYMENT_GUIDE.md` Section 14 with direct CLI commands, linking procedures, and full dashboard settings.
  - **Verification**: Fast test runner passed 13/13 checks (server 232/236, client 45/45, extension 70/70).

### Feature — Official VS Code Extension Marketplace Promotion

- **Date**: 2026-10-17
- **Branch**: `main`
- **What**: Updated DevMind web platform, documentation, and extension assets to promote the official Visual Studio Marketplace release:
  - **Official Marketplace URL**: `https://marketplace.visualstudio.com/items?itemName=WarishLabs.devmind-vscode`
  - **Installation Command**: `ext install WarishLabs.devmind-vscode` (or `code --install-extension WarishLabs.devmind-vscode`).
  - **Web Platform Updates (`client/`)**:
    - **Header (`Header.tsx`)**: Added `VS Code Extension ↗` action link navigating to Marketplace listing.
    - **Hero (`Hero.tsx`)**: Replaced placeholder chip with prominent `Install VS Code Extension ↗` CTA button with active status pulse.
    - **Architecture Diptych (`Section06Diptych.tsx`)**: Added Marketplace link in companion header and `ext install WarishLabs.devmind-vscode` prompt.
    - **Primary CTA (`Section08CTA.tsx`)**: Added `Install VS Code Extension ↗` button in primary conversion row.
    - **Footer (`Footer.tsx`)**: Added `VS Code Extension (Marketplace) ↗` link under Open Engine & Specs.
    - **Early Access Page (`early-access/page.tsx`)**: Added dedicated companion installation card with one-click copyable install command and direct marketplace link.
  - **Documentation & Metadata Updates**:
    - **`README.md`**: Added official Visual Studio Marketplace badge, direct installation instructions with CLI/GUI options in Section 11, and updated Roadmap table status.
    - **`extension/README.md`**: Added Marketplace version badge and quick installation guide.
    - **`docs/SETUP-GUIDE.md` & `docs/runbooks/release-extension.md`**: Updated publisher ID to `WarishLabs` and listed the official Marketplace item URL.
  - **Verification**: 13/13 passing in fast runner, 45/45 client tests, 70/70 extension tests, 232 server tests, and clean 12/12 Next.js Turbopack build.

### Feature — Mid-Build Deployment Readiness & Production Preparation

- **Date**: 2026-10-17
- **Branch**: `main`
- **What**: Prepared repository for zero-downtime, free-tier production deployment across Render (backend Docker), Vercel (Next.js client), Upstash Redis, Neon Postgres, and VS Code Extension:
  - **Docker & Render Standardization**:
    - Created multi-stage `server/Dockerfile` with Python 3.12, dynamic `PORT` binding (`os.getenv("PORT", "8000")`), and container health check probe.
    - Added `server/.dockerignore` excluding `.venv`, `.env*`, and caches.
    - Updated `render.yaml` to Docker runtime with free instance type, removed Render Redis, configured Upstash Redis env var.
    - Built and verified local Docker image `devmind-server:test` with active health probes (`/health`, `/healthz`).
  - **Upstash Redis Integration**:
    - Added `UPSTASH_REDIS_URL` and `REDIS_URL` aliases in `server/app/core/settings.py` alongside `DEVMIND_REDIS_URL`.
    - Added fast-fail validator rejecting Upstash HTTP REST URLs and requiring TLS Redis protocol URI (`rediss://default:...@...upstash.io:6379`).
  - **Health Probes & Throttled Homepage Ping**:
    - Mounted `GET /health` alongside `GET /healthz` verifying database connectivity with `SELECT 1` ping.
    - Added client-side throttled health check (`client/lib/health/health-check.ts` and `HomepageHealthTrigger.tsx`) executing at most once per hour per browser without blocking rendering.
  - **Database Migration & Reference Data Seed**:
    - Implemented `server/app/core/bootstrap.py` for automated Alembic migrations and idempotent reference data seed (`text-embedding-3-small` embedding space).
    - Added `pnpm db:migrate` and `pnpm db:seed` root package scripts.
  - **Extension Build Standardization**:
    - Configured `extension/esbuild.mjs` build-time injection targeting `https://api.devmind.warishlabs.in/api/v1` and `fixtureMode: false`.
  - **Environment Audit & Verification**:
    - Created `scripts/validate-env.mjs` secret-safe environment validator.
    - Completely updated `DEPLOYMENT_GUIDE.md` with 20-point production deployment manual.
    - Marked Cloudflare R2 as Deferred / Not used by MVP.
    - All tests green: 13 passed in `test-all --fast` (server 232/236, client 45/45, extension 70/70).

### Feature — Cloudflare Turnstile Verification End-to-End

- **Date**: 2026-10-17
- **Branch**: `main`
- **What**: Integrated Cloudflare Turnstile across frontend and backend without silent bypass:
  - **Frontend (`client/`)**:
    - Created `TurnstileWidget` (`client/components/turnstile/TurnstileWidget.tsx`) with dynamic Turnstile script loading, theme detection, token callbacks, error/expiry handling, and fallback test mode.
    - Integrated widget into `EarlyAccessForm` and `/contact` page.
    - Unit tests (`client/tests/turnstile.test.ts`) covering widget rendering, reset, error handling, and form submission.
  - **Backend (`server/`)**:
    - Added `TurnstileVerifier` & `verify_turnstile_token` dependency (`server/app/core/turnstile.py`) supporting official Cloudflare Siteverify API with test secret fallback for local testing.
    - Added RFC 9457 `TurnstileError` in `server/app/core/errors.py`.
    - Added public endpoints `POST /api/v1/public/waitlist` and `POST /api/v1/public/contact` in `server/app/api/public.py`.
    - Unit and integration tests (`server/tests/test_turnstile.py`) covering valid tokens, invalid/expired/missing tokens, upstream timeout/failure handling, and route protection.

### Feature — GitHub OAuth Authorization & Webhook Receiver

- **Date**: 2026-10-17
- **Branch**: `main`
- **What**: Implemented secure GitHub OAuth authorization flow, account linking, encrypted credential storage, and webhook receiver:
  - **Envelope Encryption (`server/app/core/crypto.py`)**:
    - AES-256-GCM envelope encryption with multi-key rotation fallback (`v1:0:nonce_b64:ct_b64`).
    - Unit tests in `server/tests/test_crypto.py`.
  - **Database Migration (`server/alembic/versions/0008_github_connections.py`)**:
    - Table `github_connections` with composite unique constraint `(workspace_id, external_account, kind)`.
    - Models and repository in `app/persistence/models/github.py` and `app/persistence/repositories/github_repo.py`.
  - **Domain Service (`server/app/domain/integrations/github_oauth_service.py`)**:
    - HMAC-SHA256 signed `state` parameter with 10-minute expiry to prevent CSRF.
    - Open-redirect protection validating destination URL scheme/host against frontend allowlist.
    - Code exchange with GitHub OAuth, authenticated `/user` profile fetch, and AES-256-GCM token encryption before database write.
    - Safe workspace connection listing and revocation methods.
  - **Webhook Receiver (`server/app/domain/webhooks/github_webhook_service.py`)**:
    - HMAC-SHA256 verification of `X-Hub-Signature-256` using `settings.github_webhook_secret`.
    - In-memory LRU deduplication on `X-GitHub-Delivery`.
    - Handler for `ping`, `pull_request`, and `push` events.
  - **API Endpoints (`server/app/api/integrations.py` & `server/app/api/webhooks.py`)**:
    - `GET /api/v1/integrations/github/authorize` (302 to GitHub).
    - `GET /api/v1/integrations/github/callback` (302 to frontend).
    - `GET /api/v1/workspaces/{wid}/integrations/github` and `DELETE /api/v1/workspaces/{wid}/integrations/github`.
    - `POST /api/v1/webhooks/github`.
  - **Tests**:
    - `server/tests/test_github_oauth.py` (8 tests) and `server/tests/test_github_webhook.py` (5 tests).
    - Boundary checks and migration head assertions updated and passing.

### M5-07 — Chunk Embeddings with pgvector and Per-Space HNSW Vector Index

- **Date**: 2026-10-17
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented pgvector vector persistence, per-space HNSW vector index migration, SQLAlchemy vector custom type, brain repository vector operations, and embedding persistence service per `docs/03 §3.2` and `docs/04 §9`:
  - **Custom SQLAlchemy Type** (`server/app/persistence/models/vector.py`):
    - Created `PGVector(UserDefinedType)` with comparator factory supporting cosine distance (`<=>`), Euclidean L2 distance (`<->`), and inner product (`<#>`).
    - Handled string parsing/formatting `[x,y,z]` and raw tuple/list conversion cleanly.
  - **Alembic Migration** (`server/alembic/versions/0007_chunk_embeddings.py`):
    - Table `chunk_embeddings` with composite primary key `(chunk_id, space_id)`.
    - Tenant isolation columns: `workspace_id` (FK to `workspaces.id` CASCADE), `project_id` (FK to `projects.id` CASCADE).
    - FK `chunk_id` to `code_chunks.id` (CASCADE), FK `space_id` to `embedding_spaces.id` (CASCADE).
    - `embedding` column typed `vector(64)` matching the default embedding space dimension.
    - HNSW vector index: `CREATE INDEX ix_chunk_embeddings_hnsw ON chunk_embeddings USING hnsw (embedding vector_cosine_ops)`.
    - Tenant and project indexes: `ix_chunk_embeddings_project_space` on `(project_id, space_id)`.
  - **SQLAlchemy Persistence Model** (`server/app/persistence/models/brain.py`):
    - Defined `ChunkEmbedding` class with composite PK, relationships to `CodeChunk` and `EmbeddingSpace`.
    - Exported in `server/app/persistence/models/__init__.py`.
  - **Repository & Domain Updates** (`BrainRepository`, `EmbeddingService`):
    - `save_chunk_embeddings`: Stores bulk chunk vectors for active embedding spaces.
    - `search_chunks_vector`: Cosine distance similarity query with tenant safety filters.
    - `get_unembedded_chunks`: Outer joins with `ChunkEmbedding` on `chunk_id` and `space_id` to return only un-embedded chunks.
    - `EmbeddingService.process_embed_chunks`: Automatically saves generated vectors to `chunk_embeddings`.
  - **Unit & Integration Tests**:
    - `server/tests/test_vector_index.py` (6 tests passing): Type serialization, model mapping, vector persistence, cosine similarity search, un-embedded outer join, and cross-tenant access rejection.
    - Updated `server/tests/test_migrations.py` (verified head `0007_chunk_embeddings`).
    - Updated `server/tests/test_brain_models.py` with `ChunkEmbedding` assertions.
    - All 199 server tests passing.

### M5-06 — Embedding Gateway Slice: Adapter Interface, Embedding Spaces, and embed_chunks Job

- **Date**: 2026-10-17
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented the standalone embedding gateway, deterministic zero-cost adapter, embedding spaces schema, repository methods, and worker job processor per `docs/04 §10`, `docs/05 §5`, and `docs/03 §3.2`:
  - **Alembic Migration** (`server/alembic/versions/0006_embedding_spaces.py`):
    - Table `embedding_spaces` with UUIDv7 PK, `provider_id`, `model_id`, `dimension`, `status` (`building`, `active`, `deprecated`), `config_hash`.
    - Unique constraint on `(provider_id, model_id, dimension)`.
    - Check constraint on valid statuses and `dimension > 0`.
    - Index on `status` and `(provider_id, model_id)`.
  - **SQLAlchemy Persistence Model** (`server/app/persistence/models/brain.py`):
    - Defined `EmbeddingSpace` class and exported in `server/app/persistence/models/__init__.py`.
  - **Embedding Gateway & Adapter Layer** (`server/app/llm/embedding_adapter.py`):
    - Abstract interface `EmbeddingAdapter` declaring `provider_id`, `model_id`, `dimension`, and `embed(texts, input_type)`.
    - Deterministic `FakeEmbeddingAdapter` deriving unit-normalized L2 vectors from SHA-256 hash seeds without external networks, API keys, or financial cost (strictly adhering to ADR-046 Free Tiers).
    - Factory `get_embedding_adapter(provider_id, model_id, dimension)`.
  - **Repository & Domain Service** (`BrainRepository`, `EmbeddingService` in `server/app/domain/brain/embedding_service.py`):
    - `get_active_embedding_space`, `create_embedding_space`, `set_active_embedding_space`, `get_unembedded_chunks`.
    - `EmbeddingService.process_embed_chunks`: Batches un-embedded chunks, runs embedding generation, tracks token counts, and reports execution statistics.
  - **Worker Job Dispatch** (`server/app/workers/celery_app.py`):
    - Wired `embed_chunks` job execution path into Celery worker lifecycle.
  - **Unit & Integration Tests**:
    - `server/tests/test_embedding_gateway.py` (7 tests passing): Determinism, unit normalization, document/query separation, batching, space lifecycle, zero-chunk handling, and tenant isolation.
    - Updated `server/tests/test_migrations.py` (verified head `0006_embedding_spaces`).
    - Updated `server/tests/test_brain_models.py` with `EmbeddingSpace` assertions.

### M5-05 — Chunk Storage, tsvector Full-Text, and Trigram Indices

- **Date**: 2026-10-17
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented `code_chunks` persistence, Alembic schema migration, full-text tsvector/trigram indices, and repository operations per `docs/03 §3.2` and `docs/04 §4`:
  - **Alembic Migration** (`server/alembic/versions/0005_code_chunks.py`):
    - Created table `code_chunks` with UUIDv7 PK, tenant FKs (`workspace_id`, `project_id` ON DELETE CASCADE), `file_version_id` (ON DELETE CASCADE), and nullable `symbol_id` (ON DELETE SET NULL).
    - Unique constraint `uq_code_chunks_version_lines_hash` on `(file_version_id, start_line, end_line, content_hash)`.
    - Check constraints for line ranges (`start_line >= 1 AND end_line >= start_line`) and symbol kinds (`module_prelude`, `function`, `class`, `statement`, `heading`, `window`).
    - Full-text search index: `CREATE INDEX ix_code_chunks_search_tsvector ON code_chunks USING gin (to_tsvector('english', search_text))`.
    - Trigram index: `CREATE EXTENSION IF NOT EXISTS pg_trgm;` and `CREATE INDEX ix_code_chunks_search_trgm ON code_chunks USING gin (search_text gin_trgm_ops)`.
    - Partial index for current chunks: `ix_code_chunks_project_current` on `(project_id, is_current)`.
    - Rollback downgrade with index drops.
  - **SQLAlchemy Persistence Model** (`server/app/persistence/models/brain.py`):
    - Defined `CodeChunk` mapped class with composite indexes, foreign keys, and relationships to `Workspace`, `Project`, `FileVersion`, and `CodeSymbol`.
    - Exported in `server/app/persistence/models/__init__.py`.
  - **BrainRepository Operations** (`server/app/persistence/repositories/brain_repo.py`):
    - `create_chunks`: Validates workspace tenant access and batch-inserts chunks.
    - `list_chunks`: Filters by project, file_version_id, and current status with pagination.
    - `search_chunks_text`: Case-insensitive and substring/tsvector matching on search_text scoped to current chunks.
    - `mark_symbols_non_current_for_versions`: Transactionally invalidates previous chunks (`is_current=False`) when file versions are superseded.
    - `get_brain_summary_stats`: Aggregates active chunk count (`total_chunks`).
  - **Unit and Integration Tests**:
    - `server/tests/test_chunk_storage.py` (7 tests passing): Model validation, batch insertion, querying, text search, version invalidation, and cross-tenant access rejection (`PermissionError`).
    - `server/tests/test_migrations.py` updated and passing (verified head `0005_code_chunks`).
    - `server/tests/test_brain_models.py` updated with `CodeChunk` assertions.

### M5-04 — Code-Aware Chunker per Language (TypeScript/JavaScript, Python, Markdown)

- **Date**: 2026-10-17
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented language-aware chunking pipeline in `server/app/domain/brain/chunker.py` conforming to `docs/04 §4` and `docs/03 §3.2`:
  - **Python AST Chunker** (`PythonChunker`):
    - Parses Python source using stdlib `ast`, extracting module preludes (docstrings, imports), top-level and nested functions, classes, decorated definitions, and statement groups.
    - Captures precise 1-indexed line ranges (`start_line`, `end_line`).
    - Graceful fallback to window chunker on syntax errors.
  - **TypeScript / JavaScript Semantic Chunker** (`TypeScriptChunker`):
    - Block-aware chunker tracking exports, functions, classes, interfaces, type aliases, and route handlers (`app.get`, `router.post`).
    - Respects brace nesting levels for accurate symbol boundary extraction.
  - **Markdown Chunker** (`MarkdownChunker`):
    - Heading-aware section chunker (`#`, `##`, `###`) grouping headings with their section bodies.
  - **Fallback Sliding-Window Chunker** (`FallbackLineChunker`):
    - Sliding line window with overlap (default 60 lines, 15 overlap) for general text, config files, and Tier 2/3 documents.
  - **Unified Dispatcher & Metadata Enrichment** (`CodeAwareChunker`):
    - Contextual header attachment (`// File: {path}` or `# File: {path}`) into `search_text` for BM25/vector retrieval context.
    - Redaction integration via `RedactionService.redact` ensuring zero unredacted secrets in chunk storage.
    - Deterministic SHA-256 chunk content hashing (`sha256:...`) and token estimation (~4 chars/token).
  - **Unit Tests** (`server/tests/test_chunker.py`):
    - 9 comprehensive tests verifying Python AST chunking, TypeScript symbol extraction, Markdown sections, window chunking, line range validity, deterministic content hashing, and redaction integration.

### M5-03 — Redaction Pipeline: Extension Client + Server-Side Redaction Re-check

- **Date**: 2026-10-17
- **Branch**: `main` (direct main workflow per owner instruction)
- **What**: Implemented the dual-layer secret detection and deterministic redaction pipeline across VS Code extension and FastAPI backend per `docs/07 §6` and `docs/03 §12.4`:
  - **Deterministic Token Hasher & Placeholder Format** (`[REDACTED:<type>:<hash8>]`):
    - Parity: 8-character SHA-256 token digest matches identically between Node.js (`crypto`) and Python (`hashlib`) without revealing raw secret values.
    - Enables cross-component repeat correlation without leaking sensitive content.
  - **Extension Client-Side Redaction Engine** (`extension/src/scanner/redaction.ts`):
    - Regex patterns for API keys (Stripe, Anthropic, OpenAI, GitHub PAT, AWS Access Key ID), private keys (blocks and single-line headers), webhook secrets (Svix/Clerk), JWT tokens, Bearer tokens, connection strings with embedded credentials, and high-entropy secret assignments.
    - Idempotent and fail-closed: preserves already-redacted text without double-masking; raises error on failure.
    - 6 unit tests in `extension/tests/redaction.test.ts` (all 14 test files / 70 tests pass).
  - **Server-Side Redaction Engine & Client Re-Check Service** (`server/app/domain/brain/redaction_service.py`):
    - Independent detection engine matching client regexes and token hashing.
    - `RedactionService.recheck_client_redaction`: Defense-in-depth re-scan catching secrets missed by client, masking them, and incrementing `total_redaction_count`.
    - `is_excluded_credential_path`: Guards `.env*`, `*.pem`, `*.key`, `id_rsa*`, `credentials*.json`, `*.kdbx`, `*.pfx`, `*.p12` as path-only.
  - **Consented Snippet Upload REST Endpoint** (`server/app/api/extension.py`):
    - `POST /api/v1/ext/projects/{pid}/snippets` (@declare_permission(PERM_PROJECT_SYNC)).
    - Enforces mandatory `Idempotency-Key` header via `IdempotencyMiddleware`.
    - Verifies active, non-revoked consent for `snippet_transmission` via `ConsentService.verify_consent` (raises `403 consent.required`).
    - Rejects excluded credential paths with `422 validation.failed` (credential files are path-only).
    - Validates line ranges (`start_line <= end_line`, `start_line >= 1`) and size limit (<= 2MB).
    - Runs server-side redaction re-check, computes deterministic `receipt_hash`, and returns `201 Created` with receipt item metadata (zero unconsented code in database).
  - **OpenAPI Schema & Client Generation**:
    - Re-exported OpenAPI schema (40 paths) to `common/openapi.json`.
    - Regenerated TypeScript types via `pnpm gen:api`.
  - **Unit & Integration Test Suite** (`server/tests/test_redaction.py`):
    - 12 comprehensive unit and endpoint tests covering API keys, private keys, bearer tokens, connection strings, repeats, idempotency, parity, re-check, credential guards, idempotency enforcement, and tenant isolation.
    - Full server pytest suite: 170 passed, 0 failed, 4 skipped.
    - Full monorepo fast suite: 13 passed, 0 failed, 1 skipped.

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
