import type { PullRequestSummary, PRAnalysisResponse } from "@devmind/common/api";
import type { BadgeVariant } from "../ui/Badge";

export interface ChecklistFindingItem {
  id: string;
  rule_id: string;
  title: string;
  category: "input_validation" | "error_handling" | "auth" | "testing" | "custom_rules" | string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  file_path: string;
  line_range: [number, number];
  evidence_level: "E0" | "E1" | "E2";
  explanation: string;
  suggested_fix?: string;
  status: "open" | "verified" | "dismissed";
}

export function getPRStatusBadgeVariant(state: string): BadgeVariant {
  switch (state.toLowerCase()) {
    case "open":
      return "signal";
    case "merged":
      return "ref";
    case "closed":
      return "neutral";
    default:
      return "neutral";
  }
}

export function getRiskLevelBadgeVariant(risk: string): BadgeVariant {
  switch (risk.toLowerCase()) {
    case "critical":
      return "danger";
    case "high":
      return "warn";
    case "medium":
      return "ref";
    case "low":
      return "signal";
    default:
      return "neutral";
  }
}

export function getSeverityBadgeVariant(severity: string): BadgeVariant {
  switch (severity.toLowerCase()) {
    case "critical":
      return "danger";
    case "high":
      return "warn";
    case "medium":
      return "ref";
    case "low":
    case "info":
      return "signal";
    default:
      return "neutral";
  }
}

// Sample fallback data for preview and offline resilience
export const SAMPLE_PULL_REQUESTS: PullRequestSummary[] = [
  {
    id: "pr-101",
    repository_id: "repo-devmind",
    number: 87,
    title: "feat(server): implement M11-05 PRAgent change-impact analysis and PR intelligence",
    author_login: "devmind-bot",
    state: "merged",
    head_sha: "0a5c79745e1289cf001b92019a930128495bcde1",
    base_sha: "3851e83100ac2e783abdf18901239014589df001",
    head_ref: "feature/m11-pr-agent",
    base_ref: "main",
    diff_url: "https://github.com/Warish-Labs/DevMind/pull/87.diff",
    merged_at: "2026-10-28T17:45:00Z",
    closed_at: null,
    created_at: "2026-10-28T14:30:00Z",
    updated_at: "2026-10-28T17:45:00Z",
  },
  {
    id: "pr-102",
    repository_id: "repo-devmind",
    number: 88,
    title: "fix(auth): enforce strict tenant scoping on webhook event replay",
    author_login: "alice-engineer",
    state: "open",
    head_sha: "a1c49028df1287900b129840291e0129a091cf78",
    base_sha: "0a5c79745e1289cf001b92019a930128495bcde1",
    head_ref: "fix/webhook-tenant-scoping",
    base_ref: "main",
    diff_url: "https://github.com/Warish-Labs/DevMind/pull/88.diff",
    merged_at: null,
    closed_at: null,
    created_at: "2026-10-29T09:15:00Z",
    updated_at: "2026-10-29T10:00:00Z",
  },
  {
    id: "pr-103",
    repository_id: "repo-devmind",
    number: 89,
    title: "refactor(client): modernize gutter navigation with icon micro-interactions",
    author_login: "bob-ui",
    state: "open",
    head_sha: "f901cb45701928400aa1892830192834019283a0",
    base_sha: "0a5c79745e1289cf001b92019a930128495bcde1",
    head_ref: "refactor/gutter-rail-polish",
    base_ref: "main",
    diff_url: "https://github.com/Warish-Labs/DevMind/pull/89.diff",
    merged_at: null,
    closed_at: null,
    created_at: "2026-10-30T11:00:00Z",
    updated_at: "2026-10-30T11:30:00Z",
  },
];

export const SAMPLE_PR_ANALYSIS: PRAnalysisResponse = {
  id: "pra-8801",
  workspace_id: "ws-default",
  project_id: "proj-sample",
  pull_request_id: "pr-102",
  head_sha: "a1c49028df1287900b129840291e0129a091cf78",
  job_id: "job-pr-88-analysis",
  risk_level: "high",
  summary: {
    purpose:
      "Enforces strict workspace tenant isolation during webhook delivery replay by checking signed tenant headers against AuthContext.",
    files_changed: [
      "server/app/domain/webhooks/github_webhook_service.py",
      "server/app/api/integrations.py",
      "server/tests/test_webhooks.py",
    ],
    affected_areas: [
      "Webhook Ingestion & Signature Verification",
      "Tenant Policy Evaluation",
      "API Integrations Router",
    ],
    risks: [
      "Alters tenant resolution order in webhook dispatcher.",
      "Requires explicit workspace_id header on replay simulation routes.",
    ],
    security_summary:
      "High positive security impact: eliminates tenant boundary ambiguity. Evidence verified with 4 automated test assertions.",
    testing_concerns: [
      "Verify cross-tenant replay attempts return 403 Forbidden with RFC 9457 problem detail.",
      "Check backward compatibility with legacy GitHub ping delivery events.",
    ],
    documentation_impact: "Update docs/03 §11 and docs/07 §6 with new replay auth requirements.",
    risk_level: "high",
  },
  impact: {
    changed_files: [
      "server/app/domain/webhooks/github_webhook_service.py",
      "server/app/api/integrations.py",
      "server/tests/test_webhooks.py",
    ],
    direct_symbols: [
      {
        name: "verify_and_replay_delivery",
        kind: "function",
        file_path: "server/app/domain/webhooks/github_webhook_service.py",
        symbol_key: "fn:verify_and_replay_delivery",
      },
      {
        name: "replay_webhook_event",
        kind: "function",
        file_path: "server/app/api/integrations.py",
        symbol_key: "route:replay_webhook_event",
      },
    ],
    affected_modules: ["server.app.domain.webhooks", "server.app.api.integrations"],
    affected_routes: [
      {
        path: "/api/v1/projects/{pid}/webhooks/replay",
        method: "POST",
        handler: "replay_webhook_event",
        file_path: "server/app/api/integrations.py",
      },
      {
        path: "/api/v1/webhooks/github",
        method: "POST",
        handler: "handle_github_event",
        file_path: "server/app/api/integrations.py",
      },
    ],
    affected_tests: [
      "server/tests/test_webhooks.py::test_replay_cross_tenant_rejected",
      "server/tests/test_webhooks.py::test_replay_valid_signature_succeeds",
    ],
    dependency_graph_nodes: [
      {
        id: "server/app/domain/webhooks/github_webhook_service.py:verify_and_replay_delivery",
        label: "verify_and_replay_delivery",
        type: "symbol",
        file_path: "server/app/domain/webhooks/github_webhook_service.py",
      },
      {
        id: "server/app/api/integrations.py:replay_webhook_event",
        label: "POST /api/v1/.../replay",
        type: "route",
        file_path: "server/app/api/integrations.py",
      },
      {
        id: "server/app/domain/webhooks/manager.py:dispatch_replay",
        label: "WebhookManager.dispatch_replay",
        type: "symbol",
        file_path: "server/app/domain/webhooks/manager.py",
      },
      {
        id: "server/tests/test_webhooks.py:test_replay_cross_tenant_rejected",
        label: "test_replay_cross_tenant_rejected",
        type: "test",
        file_path: "server/tests/test_webhooks.py",
      },
    ],
    dependency_graph_edges: [
      {
        from_node: "server/app/api/integrations.py:replay_webhook_event",
        to_node: "server/app/domain/webhooks/github_webhook_service.py:verify_and_replay_delivery",
        kind: "calls",
      },
      {
        from_node: "server/app/domain/webhooks/manager.py:dispatch_replay",
        to_node: "server/app/domain/webhooks/github_webhook_service.py:verify_and_replay_delivery",
        kind: "calls",
      },
      {
        from_node: "server/tests/test_webhooks.py:test_replay_cross_tenant_rejected",
        to_node: "server/app/api/integrations.py:replay_webhook_event",
        kind: "tests",
      },
    ],
    risk_level: "high",
    risk_reasons: [
      "Touches 2 authenticated API routes handling external inputs.",
      "High security sensitivity: alters tenant boundary verification.",
    ],
  },
  created_at: "2026-10-29T10:05:00Z",
  updated_at: "2026-10-29T10:05:00Z",
};

export const SAMPLE_CHECKLIST_FINDINGS: ChecklistFindingItem[] = [
  {
    id: "chk-001",
    rule_id: "sec-tenant-context-enforcement",
    title: "Explicit AuthContext validation required on replay dispatcher",
    category: "auth",
    severity: "high",
    file_path: "server/app/domain/webhooks/github_webhook_service.py",
    line_range: [142, 168],
    evidence_level: "E1",
    explanation:
      "verify_and_replay_delivery accepts an unverified workspace_id string parameter without validating it against the tenant token in AuthContext.",
    suggested_fix:
      "Pass `auth_ctx: AuthContext` directly to `verify_and_replay_delivery` and assert `auth_ctx.workspace_id == workspace_id`.",
    status: "verified",
  },
  {
    id: "chk-002",
    rule_id: "err-bare-except-forbidden",
    title: "Bare except clause detected in HMAC signature check",
    category: "error_handling",
    severity: "medium",
    file_path: "server/app/domain/webhooks/github_webhook_service.py",
    line_range: [180, 186],
    evidence_level: "E1",
    explanation:
      "Catching Exception broadly can suppress unexpected decoding errors without recording telemetry.",
    suggested_fix:
      "Catch specific `(ValueError, binascii.Error)` and log the failure code with structured context.",
    status: "open",
  },
  {
    id: "chk-003",
    rule_id: "test-coverage-mutating-routes",
    title: "Missing test for negative HMAC signature payload corruption",
    category: "testing",
    severity: "low",
    file_path: "server/tests/test_webhooks.py",
    line_range: [45, 75],
    evidence_level: "E0",
    explanation:
      "Existing suite tests valid payloads and missing signatures, but lacks tests for tampered payload bodies.",
    suggested_fix:
      "Add `test_replay_tampered_payload_rejected` asserting 401 Unauthorized status code.",
    status: "open",
  },
];
