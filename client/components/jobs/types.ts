import type { AnalysisJobResponse } from "@devmind/common/api";
import type { BadgeVariant } from "../ui/Badge";

export type JobStatus =
  | "queued"
  | "running"
  | "awaiting_approval"
  | "succeeded"
  | "partially_succeeded"
  | "failed"
  | "cancel_requested"
  | "cancelled"
  | "timed_out";

export interface JobEventItem {
  id: string;
  jobId: string;
  seq: number;
  kind: "milestone" | "progress" | "status" | "error" | "approval_request";
  message: string;
  data?: Record<string, unknown>;
  createdAt: string;
}

export interface JobApprovalInfo {
  actionTitle: string;
  actionDescription: string;
  impactScope: string;
  requestedAt: string;
}

export interface JobWithDetails extends AnalysisJobResponse {
  progressPct?: number;
  events?: JobEventItem[];
  approval?: JobApprovalInfo;
}

export interface JobFilterState {
  status: string; // 'all' | 'running' | 'awaiting_approval' | 'succeeded' | 'failed'
  type: string; // 'all' | 'security_review' | 'ask_project' | ...
  query: string;
}

export const INITIAL_JOB_FILTER_STATE: JobFilterState = {
  status: "all",
  type: "all",
  query: "",
};

export function getJobStatusBadgeVariant(status: string): BadgeVariant {
  switch (status.toLowerCase()) {
    case "running":
      return "ref";
    case "awaiting_approval":
      return "warn";
    case "succeeded":
      return "signal";
    case "partially_succeeded":
      return "warn";
    case "failed":
    case "timed_out":
      return "danger";
    case "cancel_requested":
    case "cancelled":
    case "queued":
    default:
      return "neutral";
  }
}

export function formatJobType(jobType: string): string {
  switch (jobType) {
    case "security_review":
      return "Security Review";
    case "ask_project":
      return "Ask Project (Agent)";
    case "code_review":
      return "Code Review";
    case "change_impact":
      return "Change Impact";
    case "pr_analysis":
      return "PR Analysis";
    case "ingest_project":
      return "Manifest Ingest";
    case "embed_chunks":
      return "Embed Chunks";
    case "doc_drift":
      return "Doc Drift";
    case "bug_match":
      return "Bug Memory Match";
    case "purge_project":
      return "Project Purge";
    default:
      return jobType
        .split("_")
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" ");
  }
}

export function formatDuration(startedAt?: string | null, finishedAt?: string | null): string {
  if (!startedAt) return "Not started";
  const start = new Date(startedAt).getTime();
  const end = finishedAt ? new Date(finishedAt).getTime() : Date.now();
  const diffSec = Math.max(0, Math.floor((end - start) / 1000));
  if (diffSec < 60) return `${diffSec}s`;
  const mins = Math.floor(diffSec / 60);
  const secs = diffSec % 60;
  return `${mins}m ${secs}s`;
}

export const SAMPLE_JOBS_LIST: JobWithDetails[] = [
  {
    id: "018f0a00-0000-7000-9000-000000000001",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    type: "security_review",
    status: "running",
    attempt: 1,
    max_attempts: 3,
    queue: "analysis",
    progressPct: 65,
    started_at: new Date(Date.now() - 45000).toISOString(),
    created_at: new Date(Date.now() - 50000).toISOString(),
    events: [
      {
        id: "evt-01",
        jobId: "018f0a00-0000-7000-9000-000000000001",
        seq: 1,
        kind: "milestone",
        message: "Job dispatched to Celery worker: analysis-pool-01",
        createdAt: new Date(Date.now() - 45000).toISOString(),
        data: { worker: "analysis-pool-01", queue: "analysis" },
      },
      {
        id: "evt-02",
        jobId: "018f0a00-0000-7000-9000-000000000001",
        seq: 2,
        kind: "milestone",
        message: "Resolved 42 files across Tier 1 AST and Tier 2 code relationships",
        createdAt: new Date(Date.now() - 35000).toISOString(),
        data: { files_count: 42, ast_nodes: 1250 },
      },
      {
        id: "evt-03",
        jobId: "018f0a00-0000-7000-9000-000000000001",
        seq: 3,
        kind: "progress",
        message: "Evaluating auth and permission guards with AuthCheck workflow node",
        createdAt: new Date(Date.now() - 15000).toISOString(),
        data: { evaluated_routes: 8, total_routes: 12, violations_found: 1 },
      },
      {
        id: "evt-04",
        jobId: "018f0a00-0000-7000-9000-000000000001",
        seq: 4,
        kind: "progress",
        message: "Building verification evidence bundle (E2 deterministic confirmation)",
        createdAt: new Date(Date.now() - 5000).toISOString(),
        data: { evidence_level: "E2", confirmed_findings: 1 },
      },
    ],
  },
  {
    id: "018f0a00-0000-7000-9000-000000000002",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    type: "code_review",
    status: "awaiting_approval",
    attempt: 1,
    max_attempts: 3,
    queue: "agent",
    progressPct: 80,
    started_at: new Date(Date.now() - 120000).toISOString(),
    created_at: new Date(Date.now() - 130000).toISOString(),
    approval: {
      actionTitle: "Apply Suggested Auth Middleware Fix",
      actionDescription:
        "CodeMate workflow paused before external side effect. Approval is requested to write patch file `server/app/api/admin.py` with declared permission guard.",
      impactScope: "1 file, 3 insertions (+@declare_permission, require_permission)",
      requestedAt: new Date(Date.now() - 30000).toISOString(),
    },
    events: [
      {
        id: "evt-11",
        jobId: "018f0a00-0000-7000-9000-000000000002",
        seq: 1,
        kind: "milestone",
        message: "CodeMate workflow initialized with checkpoint thread-018f0a",
        createdAt: new Date(Date.now() - 120000).toISOString(),
      },
      {
        id: "evt-12",
        jobId: "018f0a00-0000-7000-9000-000000000002",
        seq: 2,
        kind: "approval_request",
        message: "State interrupted at human-in-the-loop approval gate (ADR-006, docs/08 §11 S-09)",
        createdAt: new Date(Date.now() - 30000).toISOString(),
        data: { target_file: "server/app/api/admin.py", action: "write_patch" },
      },
    ],
  },
  {
    id: "018f0a00-0000-7000-9000-000000000003",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    type: "embed_chunks",
    status: "succeeded",
    attempt: 1,
    max_attempts: 3,
    queue: "embedding",
    progressPct: 100,
    started_at: new Date(Date.now() - 3600000).toISOString(),
    finished_at: new Date(Date.now() - 3570000).toISOString(),
    created_at: new Date(Date.now() - 3610000).toISOString(),
    result_ref: {
      chunks_embedded: 248,
      dimensions: 768,
      provider: "google_genai_embedding",
      duration_ms: 30000,
    },
    events: [
      {
        id: "evt-21",
        jobId: "018f0a00-0000-7000-9000-000000000003",
        seq: 1,
        kind: "milestone",
        message: "Embedded 248 chunks into pgvector successfully",
        createdAt: new Date(Date.now() - 3570000).toISOString(),
      },
    ],
  },
  {
    id: "018f0a00-0000-7000-9000-000000000004",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    type: "change_impact",
    status: "failed",
    attempt: 3,
    max_attempts: 3,
    queue: "analysis",
    started_at: new Date(Date.now() - 7200000).toISOString(),
    finished_at: new Date(Date.now() - 7180000).toISOString(),
    created_at: new Date(Date.now() - 7210000).toISOString(),
    error_code: "git.diff_timeout",
    error_detail: "Base git tree commit reference 'b418cd9' not resolvable in remote repository.",
    events: [
      {
        id: "evt-31",
        jobId: "018f0a00-0000-7000-9000-000000000004",
        seq: 1,
        kind: "error",
        message: "Failed after 3 attempts: git.diff_timeout",
        createdAt: new Date(Date.now() - 7180000).toISOString(),
      },
    ],
  },
  {
    id: "018f0a00-0000-7000-9000-000000000005",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    type: "ask_project",
    status: "cancelled",
    attempt: 1,
    max_attempts: 3,
    queue: "agent",
    started_at: new Date(Date.now() - 86400000).toISOString(),
    finished_at: new Date(Date.now() - 86390000).toISOString(),
    created_at: new Date(Date.now() - 86410000).toISOString(),
    error_code: "job.cancelled_by_user",
    error_detail: "Cancelled upon user request.",
    events: [
      {
        id: "evt-41",
        jobId: "018f0a00-0000-7000-9000-000000000005",
        seq: 1,
        kind: "status",
        message: "Job cancelled cooperatively",
        createdAt: new Date(Date.now() - 86390000).toISOString(),
      },
    ],
  },
];
