/**
 * Project Mentor and Project Evaluation UI types and sample data (docs/01 CAP-08, CAP-09, Screen S-17).
 */

import type {
  ProjectTaskResponse,
  ProjectTaskCreate,
  ProjectTaskUpdate,
  TaskDependencyResponse,
  TaskRecommendationResponse,
  ProjectEvaluationResponse,
} from "@devmind/common/api";

export type {
  ProjectTaskResponse,
  ProjectTaskCreate,
  ProjectTaskUpdate,
  TaskDependencyResponse,
  TaskRecommendationResponse,
  ProjectEvaluationResponse,
};

export const SAMPLE_TASKS: ProjectTaskResponse[] = [
  {
    id: "task-001",
    workspace_id: "ws-devmind",
    project_id: "proj-1",
    title: "Implement Clerk User Authentication & RBAC Guards",
    description:
      "Setup session middleware, AuthContext derivation, and role-based access checks across all tenant endpoints.",
    status: "completed",
    priority: "critical",
    source: "user",
    metadata: { module: "auth", estimate: "3d" },
    depends_on_ids: [],
    dependent_ids: ["task-002", "task-003"],
    created_at: new Date(Date.now() - 7 * 86400000).toISOString(),
    updated_at: new Date(Date.now() - 5 * 86400000).toISOString(),
  },
  {
    id: "task-002",
    workspace_id: "ws-devmind",
    project_id: "proj-1",
    title: "Enforce Workspace & Project Tenant Scoping on Repository Queries",
    description:
      "Wrap every SELECT, UPDATE, and DELETE query with workspace_id and project_id predicates to eliminate cross-tenant leakage.",
    status: "in_progress",
    priority: "critical",
    source: "finding",
    finding_id: "find-sec-01",
    metadata: { rule: "devmind.auth.tenant_isolation" },
    depends_on_ids: ["task-001"],
    dependent_ids: ["task-004"],
    created_at: new Date(Date.now() - 4 * 86400000).toISOString(),
    updated_at: new Date(Date.now() - 1 * 86400000).toISOString(),
  },
  {
    id: "task-003",
    workspace_id: "ws-devmind",
    project_id: "proj-1",
    title: "Implement Living Docs Route Drift Reconciler",
    description:
      "Detect discrepancies between OpenAPI endpoint declarations and tracked Markdown documentation references.",
    status: "open",
    priority: "high",
    source: "user",
    metadata: { module: "docs" },
    depends_on_ids: ["task-001"],
    dependent_ids: [],
    created_at: new Date(Date.now() - 3 * 86400000).toISOString(),
    updated_at: new Date(Date.now() - 3 * 86400000).toISOString(),
  },
  {
    id: "task-004",
    workspace_id: "ws-devmind",
    project_id: "proj-1",
    title: "Integrate CI Security Regression Suite & Automated Audit",
    description:
      "Run automated tests against multi-tenant boundary leakages and token validation fixtures on every PR.",
    status: "open",
    priority: "medium",
    source: "agent",
    metadata: { category: "testing" },
    depends_on_ids: ["task-002"],
    dependent_ids: [],
    created_at: new Date(Date.now() - 2 * 86400000).toISOString(),
    updated_at: new Date(Date.now() - 2 * 86400000).toISOString(),
  },
  {
    id: "task-005",
    workspace_id: "ws-devmind",
    project_id: "proj-1",
    title: "Fix Memory Leak in LangGraph Checkpointer Redis Adapter",
    description:
      "Ensure stale thread state keys expire after configured TTL (ADR-046 Free Profile compliance).",
    status: "open",
    priority: "high",
    source: "agent",
    metadata: { component: "orchestration" },
    depends_on_ids: [],
    dependent_ids: [],
    created_at: new Date(Date.now() - 1 * 86400000).toISOString(),
    updated_at: new Date(Date.now() - 1 * 86400000).toISOString(),
  },
];

export const SAMPLE_RECOMMENDATION: TaskRecommendationResponse = {
  recommended_task: SAMPLE_TASKS[1],
  rank: 1,
  score: 420.0,
  is_ready: true,
  downstream_impact_count: 1,
  reason: "Critical security prerequisite unblocking downstream CI regression test verification.",
  narrative:
    "Task 'Enforce Workspace & Project Tenant Scoping on Repository Queries' is ranked #1. Tackling tenant isolation guards first resolves high-severity security findings and unblocks downstream CI regression suite integration.",
  unblocked_count: 3,
  total_pending_tasks: 4,
};

export const SAMPLE_EVALUATION: ProjectEvaluationResponse = {
  id: "eval-sample-01",
  workspace_id: "ws-devmind",
  project_id: "proj-1",
  overall_score: 91.5,
  dimension_scores: {
    security: 95.0,
    code_quality: 92.0,
    testing: 88.0,
    documentation: 90.0,
    functionality: 95.0,
    architecture: 100.0,
  },
  verdict: "ready_with_warnings",
  blockers: [],
  warnings: [
    {
      id: "warn-01",
      dimension: "testing",
      title: "Playwright E2E suite skipped in fast verification mode",
      severity: "low",
      reason: "Run full suite with 'node scripts/test-all.mjs --full' prior to production deploy.",
    },
    {
      id: "warn-02",
      dimension: "documentation",
      title: "1 undocumented route detected in Living Docs",
      severity: "low",
      reason:
        "POST /api/v1/projects/{id}/evaluations/run does not have an explicit markdown link in docs/03.",
    },
  ],
  positive_indicators: [
    "Zero critical open security vulnerabilities detected",
    "Task dependency graph is strictly acyclic with 0 cycles",
    "All user-declared feature checklist milestones complete (High confidence)",
    "Living documentation is 98% synchronized with registered API endpoints",
    "Structured logging redacts all secrets and tokens automatically",
  ],
  rubric_version: "1.0",
  functionality_confidence: "high",
  narrative:
    "Project DevMind achieves an overall release readiness health score of 91.5 / 100 (Verdict: Ready with Warnings). Zero release blockers exist. Architecture and security dimensions maintain peak stability, with minor warnings on skipped E2E tests and Living Docs sync.",
  created_at: new Date(Date.now() - 3600000).toISOString(),
  updated_at: new Date(Date.now() - 3600000).toISOString(),
};
