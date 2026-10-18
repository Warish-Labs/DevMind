import type { FindingItem } from "@devmind/common/api";

export interface ScanRunItem {
  id: string;
  projectId: string;
  status: "completed" | "in_progress" | "failed";
  scanKind: "full" | "incremental";
  filesAnalyzed: number;
  totalFiles: number;
  durationMs: number;
  createdAt: string;
}

export interface ActivityJobItem {
  id: string;
  projectId: string;
  jobType: "manifest_sync" | "graph_build" | "embedding_sync" | "security_eval";
  status: "completed" | "running" | "failed";
  progressPct: number;
  createdAt: string;
}

export interface ProjectHealthStats {
  securityScore: number;
  securityGrade: string;
  analysisCoveragePct: number;
  totalFiles: number;
  analyzedFiles: number;
  tier1AstFiles: number;
  tier2GraphFiles: number;
  tier3SemanticsFiles: number;
}

export const SAMPLE_FINDINGS: FindingItem[] = [
  {
    id: "018f0a00-0000-7000-8000-000000001001",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    fingerprint: "fp_auth_missing_check_01",
    rule_id: "SEC-AUTH-001",
    source: "devmind_rule",
    category: "authorization",
    title: "Missing authorization check on administrative route",
    summary: "Route /api/v1/admin/users allows unauthenticated caller access without role check.",
    explanation:
      "Route handler /api/v1/admin/users does not require admin role or check permissions against caller's AuthContext.",
    severity: "high",
    confidence: "high",
    evidence_level: "E2",
    status: "open",
    primary_path: "server/app/api/admin.py",
    primary_start_line: 42,
    primary_end_line: 68,
    created_at: new Date(Date.now() - 3600000 * 4).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 4).toISOString(),
  },
  {
    id: "018f0a00-0000-7000-8000-000000001002",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    fingerprint: "fp_async_rejection_02",
    rule_id: "REL-ASYNC-003",
    source: "scanner",
    category: "reliability",
    title: "Unhandled promise rejection in motion stream handler",
    summary: "Async sequence does not catch rejection on cancelled animation frame.",
    explanation: "Animation loop cancels without rejecting awaiting promise chain.",
    severity: "high",
    confidence: "high",
    evidence_level: "E1",
    status: "open",
    primary_path: "client/lib/motion/sequence.ts",
    primary_start_line: 112,
    primary_end_line: 130,
    created_at: new Date(Date.now() - 3600000 * 12).toISOString(),
    updated_at: new Date(Date.now() - 3600000 * 12).toISOString(),
  },
  {
    id: "018f0a00-0000-7000-8000-000000001003",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    fingerprint: "fp_db_tenant_index_03",
    rule_id: "PERF-DB-005",
    source: "devmind_rule",
    category: "performance",
    title: "Query missing tenant composite index",
    summary: "Filtering by status without workspace_id composite index triggers sequential scan.",
    explanation:
      "PostgreSQL query optimizer performs sequential table scan on unindexed tenant column.",
    severity: "medium",
    confidence: "medium",
    evidence_level: "E1",
    status: "open",
    primary_path: "server/app/domain/brain/repository.py",
    primary_start_line: 88,
    primary_end_line: 105,
    created_at: new Date(Date.now() - 86400000 * 2).toISOString(),
    updated_at: new Date(Date.now() - 86400000 * 2).toISOString(),
  },
  {
    id: "018f0a00-0000-7000-8000-000000001004",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    fingerprint: "fp_html_target_blank_04",
    rule_id: "SEC-HTML-009",
    source: "scanner",
    category: "security",
    title: "External anchor missing noopener relationship",
    summary: "Anchor opening in new tab does not include rel='noopener noreferrer'.",
    explanation: "External link exposes window.opener reference to target origin.",
    severity: "low",
    confidence: "high",
    evidence_level: "E0",
    status: "open",
    primary_path: "client/components/layout/Header.tsx",
    primary_start_line: 64,
    primary_end_line: 72,
    created_at: new Date(Date.now() - 86400000 * 3).toISOString(),
    updated_at: new Date(Date.now() - 86400000 * 3).toISOString(),
  },
];

export const SAMPLE_HEALTH_STATS: ProjectHealthStats = {
  securityScore: 88,
  securityGrade: "B+",
  analysisCoveragePct: 94,
  totalFiles: 45,
  analyzedFiles: 42,
  tier1AstFiles: 42,
  tier2GraphFiles: 38,
  tier3SemanticsFiles: 36,
};

export const SAMPLE_SCANS: ScanRunItem[] = [
  {
    id: "scan_018f0a_001",
    projectId: "018f0a00-0000-7000-8000-000000000101",
    status: "completed",
    scanKind: "full",
    filesAnalyzed: 42,
    totalFiles: 45,
    durationMs: 1420,
    createdAt: new Date(Date.now() - 1000 * 60 * 14).toISOString(),
  },
  {
    id: "scan_018f0a_002",
    projectId: "018f0a00-0000-7000-8000-000000000101",
    status: "completed",
    scanKind: "incremental",
    filesAnalyzed: 6,
    totalFiles: 45,
    durationMs: 380,
    createdAt: new Date(Date.now() - 1000 * 60 * 95).toISOString(),
  },
];

export const SAMPLE_JOBS: ActivityJobItem[] = [
  {
    id: "job_018f0a_010",
    projectId: "018f0a00-0000-7000-8000-000000000101",
    jobType: "manifest_sync",
    status: "completed",
    progressPct: 100,
    createdAt: new Date(Date.now() - 1000 * 60 * 14).toISOString(),
  },
  {
    id: "job_018f0a_011",
    projectId: "018f0a00-0000-7000-8000-000000000101",
    jobType: "graph_build",
    status: "completed",
    progressPct: 100,
    createdAt: new Date(Date.now() - 1000 * 60 * 18).toISOString(),
  },
  {
    id: "job_018f0a_012",
    projectId: "018f0a00-0000-7000-8000-000000000101",
    jobType: "embedding_sync",
    status: "completed",
    progressPct: 100,
    createdAt: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
  },
];

/**
 * Deterministic ordering for "Highest-priority finding to fix"
 * ordered by severity (critical > high > medium > low > info),
 * then evidence level (E2 > E1 > E0).
 */
export function getHighestPriorityFinding(findings: FindingItem[]): FindingItem | null {
  if (!findings || findings.length === 0) return null;
  const severityRank: Record<string, number> = {
    critical: 4,
    high: 3,
    medium: 2,
    low: 1,
    info: 0,
  };
  const evidenceRank: Record<string, number> = {
    E2: 3,
    E1: 2,
    E0: 1,
  };

  return [...findings].sort((a, b) => {
    const sDiff = (severityRank[b.severity] || 0) - (severityRank[a.severity] || 0);
    if (sDiff !== 0) return sDiff;
    const eDiff = (evidenceRank[b.evidence_level] || 0) - (evidenceRank[a.evidence_level] || 0);
    return eDiff;
  })[0];
}
