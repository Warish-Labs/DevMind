import type { FindingItem, FindingDetailItem } from "@devmind/common/api";
import type { BadgeVariant } from "../ui/Badge";

export interface FindingFilterState {
  status: string; // 'all' | 'open' | 'acknowledged' | 'in_progress' | 'resolved' | 'dismissed' | 'accepted_risk' | 'stale'
  severity: string; // 'all' | 'critical' | 'high' | 'medium' | 'low' | 'info'
  category: string; // 'all' | 'authorization' | 'authentication' | 'secret_exposure' | ...
  evidenceLevel: string; // 'all' | 'E2' | 'E1' | 'E0'
  query: string;
}

export const INITIAL_FILTER_STATE: FindingFilterState = {
  status: "all",
  severity: "all",
  category: "all",
  evidenceLevel: "all",
  query: "",
};

export function getSeverityBadgeVariant(severity: string): BadgeVariant {
  switch (severity.toLowerCase()) {
    case "critical":
    case "high":
      return "danger";
    case "medium":
      return "warn";
    case "low":
      return "ref";
    case "info":
    default:
      return "neutral";
  }
}

export function getStatusBadgeVariant(status: string): BadgeVariant {
  switch (status.toLowerCase()) {
    case "open":
      return "warn";
    case "acknowledged":
      return "ref";
    case "in_progress":
      return "signal";
    case "resolved":
      return "signal";
    case "dismissed":
    case "accepted_risk":
      return "neutral";
    case "stale":
      return "danger";
    default:
      return "neutral";
  }
}

export const SAMPLE_FINDING_DETAILS: Record<string, FindingDetailItem> = {
  "018f0a00-0000-7000-8000-000000001001": {
    id: "018f0a00-0000-7000-8000-000000001001",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    fingerprint: "fp_auth_missing_check_01",
    rule_id: "SEC-AUTH-001",
    source: "devmind_rule",
    category: "authorization",
    title: "Missing authorization check on administrative route",
    summary: "Route /api/v1/admin/users allows unauthenticated caller access without role check.",
    explanation:
      "Route handler /api/v1/admin/users in `server/app/api/admin.py` handles user modification but does not depend on `require_permission(PERM_ADMIN_ACCESS)` or verify caller's AuthContext against required workspace role. An authenticated non-admin caller or unauthenticated request could invoke administrative operations.",
    severity: "critical",
    confidence: "high",
    evidence_level: "E2",
    status: "open",
    primary_path: "server/app/api/admin.py",
    primary_start_line: 42,
    primary_end_line: 56,
    suggested_fix: {
      summary: "Add require_permission dependency and AuthContext parameter",
      remediation_steps: [
        "Import `PERM_ADMIN_ACCESS` and `require_permission` from `app.domain.auth`.",
        "Add `@declare_permission(PERM_ADMIN_ACCESS)` to declare required scope in OpenAPI docs.",
        "Inject `ctx: AuthContext = Depends(require_permission(PERM_ADMIN_ACCESS))` into the route signature.",
      ],
      code_suggestion: `@@ -42,6 +42,8 @@
 @router.get("/users", response_model=list[UserResponse])
+@declare_permission(PERM_ADMIN_ACCESS)
 async def list_admin_users(
+    ctx: AuthContext = Depends(require_permission(PERM_ADMIN_ACCESS)),
     session: AsyncSession = Depends(get_db_session),
 ) -> list[UserResponse]:`,
    },
    created_at: "2026-10-18T10:00:00Z",
    updated_at: "2026-10-18T10:00:00Z",
    evidence: [
      {
        id: "ev-018f0a00-0000-7000-8000-000000000001",
        finding_id: "018f0a00-0000-7000-8000-000000001001",
        path: "server/app/api/admin.py",
        start_line: 42,
        end_line: 56,
        snippet_hash: "sha256:4a8b79e19d67e6c1e34",
        role: "structural_check",
        is_current: true,
        created_at: "2026-10-18T10:00:00Z",
        detail: {
          check_type: "ast_visitor_missing_guard",
          ast_node: "AsyncFunctionDef:list_admin_users",
          missing_decorator: "@declare_permission",
          missing_dependency: "require_permission(PERM_ADMIN_ACCESS)",
        },
      },
      {
        id: "ev-018f0a00-0000-7000-8000-000000000002",
        finding_id: "018f0a00-0000-7000-8000-000000001001",
        path: "server/app/domain/auth/permissions.py",
        start_line: 18,
        end_line: 25,
        snippet_hash: "sha256:8f2a1b9c7d6e4a3b1c2",
        role: "retrieved_context",
        is_current: true,
        created_at: "2026-10-18T10:00:00Z",
        detail: {
          matched_symbol: "PERM_ADMIN_ACCESS",
          permission_doc: "Grants full administrative privileges across tenant resources",
        },
      },
    ],
    history: [
      {
        id: "hist-01",
        finding_id: "018f0a00-0000-7000-8000-000000001001",
        from_status: "detected",
        to_status: "open",
        actor_kind: "system",
        actor_id: "scanner_ast_v1",
        reason: "Initial AST static check detection during full scan",
        created_at: "2026-10-18T10:00:00Z",
      },
    ],
  },
  "018f0a00-0000-7000-8000-000000001002": {
    id: "018f0a00-0000-7000-8000-000000001002",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    fingerprint: "fp_async_rejection_02",
    rule_id: "REL-ASYNC-003",
    source: "scanner",
    category: "reliability",
    title: "Unhandled promise rejection in motion stream handler",
    summary: "Async sequence does not catch rejection on cancelled animation frame.",
    explanation:
      "The motion animation loop in `client/lib/motion/sequence.ts` binds to `requestAnimationFrame` without wrapping internal async ticks in a try/catch or registering a `.catch()` on the rejected sequence promise. When the component unmounts mid-animation, an unhandled promise rejection error bubbles to the global window listener.",
    severity: "high",
    confidence: "high",
    evidence_level: "E1",
    status: "in_progress",
    primary_path: "client/lib/motion/sequence.ts",
    primary_start_line: 112,
    primary_end_line: 128,
    suggested_fix: {
      summary: "Add AbortSignal check and try/catch around animation step promise",
      remediation_steps: [
        "Check `signal.aborted` before advancing keyframe tick.",
        "Catch cancelled animation errors and gracefully resolve with `cancelled: true`.",
      ],
      code_suggestion: `@@ -112,6 +112,10 @@
-    await stepAnimation(frame);
+    try {
+      await stepAnimation(frame, { signal });
+    } catch (err) {
+      if (signal.aborted) return;
+      throw err;
+    }`,
    },
    created_at: "2026-10-18T08:30:00Z",
    updated_at: "2026-10-18T12:00:00Z",
    evidence: [
      {
        id: "ev-018f0a00-0000-7000-8000-000000000003",
        finding_id: "018f0a00-0000-7000-8000-000000001002",
        path: "client/lib/motion/sequence.ts",
        start_line: 112,
        end_line: 128,
        snippet_hash: "sha256:7b9c1d2e3f4a5b6c7d8",
        role: "rule_hit",
        is_current: true,
        created_at: "2026-10-18T08:30:00Z",
        detail: {
          rule: "REL-ASYNC-003",
          pattern: "await stepAnimation without catch block",
        },
      },
    ],
    history: [
      {
        id: "hist-02",
        finding_id: "018f0a00-0000-7000-8000-000000001002",
        from_status: "open",
        to_status: "in_progress",
        actor_kind: "user",
        actor_id: "usr_lead_developer",
        reason: "Investigating motion cleanup on page unmount",
        created_at: "2026-10-18T12:00:00Z",
      },
      {
        id: "hist-02b",
        finding_id: "018f0a00-0000-7000-8000-000000001002",
        from_status: "detected",
        to_status: "open",
        actor_kind: "system",
        actor_id: "scanner_ast_v1",
        reason: "Detected in incremental scan run #4",
        created_at: "2026-10-18T08:30:00Z",
      },
    ],
  },
  "018f0a00-0000-7000-8000-000000001003": {
    id: "018f0a00-0000-7000-8000-000000001003",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    fingerprint: "fp_db_tenant_index_03",
    rule_id: "PERF-DB-005",
    source: "devmind_rule",
    category: "performance",
    title: "Query missing tenant composite index",
    summary: "Filtering by status without workspace_id composite index triggers sequential scan.",
    explanation:
      "The repository query in `server/app/domain/brain/repository.py` filters by `status` and `project_id` without leveraging the composite index `(workspace_id, project_id, status)`. Under multi-tenant loads, Postgres will trigger table scans.",
    severity: "medium",
    confidence: "medium",
    evidence_level: "E1",
    status: "acknowledged",
    primary_path: "server/app/domain/brain/repository.py",
    primary_start_line: 88,
    primary_end_line: 104,
    suggested_fix: {
      summary: "Add compound index or include workspace_id in where clause",
      remediation_steps: [
        "Review Alembic migration for composite index definition.",
        "Ensure query explicitly binds `workspace_id` to hit index `ix_findings_tenant_status`.",
      ],
      code_suggestion: `@@ -88,4 +88,5 @@
-    query = select(FindingModel).where(FindingModel.status == status)
+    query = select(FindingModel).where(FindingModel.workspace_id == ctx.workspace_id, FindingModel.status == status)`,
    },
    created_at: "2026-10-17T14:15:00Z",
    updated_at: "2026-10-18T09:00:00Z",
    evidence: [
      {
        id: "ev-018f0a00-0000-7000-8000-000000000004",
        finding_id: "018f0a00-0000-7000-8000-000000001003",
        path: "server/app/domain/brain/repository.py",
        start_line: 88,
        end_line: 104,
        snippet_hash: "sha256:1a2b3c4d5e6f7a8b9c0",
        role: "structural_check",
        is_current: true,
        created_at: "2026-10-17T14:15:00Z",
        detail: {
          table: "findings",
          missing_index_columns: ["workspace_id", "status"],
        },
      },
    ],
    history: [
      {
        id: "hist-03",
        finding_id: "018f0a00-0000-7000-8000-000000001003",
        from_status: "open",
        to_status: "acknowledged",
        actor_kind: "user",
        actor_id: "usr_db_admin",
        reason: "Acknowledged; scheduled for migration sprint",
        created_at: "2026-10-18T09:00:00Z",
      },
    ],
  },
  "018f0a00-0000-7000-8000-000000001004": {
    id: "018f0a00-0000-7000-8000-000000001004",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    fingerprint: "fp_html_target_blank_04",
    rule_id: "SEC-WEB-012",
    source: "scanner",
    category: "input_validation",
    title: "Reverse tabnabbing risk on external documentation link",
    summary: "External hyperlink with target='_blank' lacks rel='noopener noreferrer'.",
    explanation:
      "In `client/components/health/StatusStrip.tsx`, an external documentation link opens in a new tab without `rel='noopener noreferrer'`. Older browser rendering engines allow the target page to manipulate `window.opener`.",
    severity: "low",
    confidence: "high",
    evidence_level: "E0",
    status: "resolved",
    primary_path: "client/components/health/StatusStrip.tsx",
    primary_start_line: 45,
    primary_end_line: 49,
    suggested_fix: {
      summary: "Add rel='noopener noreferrer' attribute to external <a> tags",
      remediation_steps: ["Include `rel='noopener noreferrer'` on all external anchor elements."],
      code_suggestion: `@@ -45,3 +45,3 @@
-<a href="https://docs.devmind.dev" target="_blank">
+<a href="https://docs.devmind.dev" target="_blank" rel="noopener noreferrer">`,
    },
    created_at: "2026-10-16T11:00:00Z",
    updated_at: "2026-10-17T16:30:00Z",
    evidence: [
      {
        id: "ev-018f0a00-0000-7000-8000-000000000005",
        finding_id: "018f0a00-0000-7000-8000-000000001004",
        path: "client/components/health/StatusStrip.tsx",
        start_line: 45,
        end_line: 49,
        snippet_hash: "sha256:3d4e5f6a7b8c9d0e1f2",
        role: "rule_hit",
        is_current: true,
        created_at: "2026-10-16T11:00:00Z",
        detail: {
          tag: "a",
          target: "_blank",
          rel: null,
        },
      },
    ],
    history: [
      {
        id: "hist-04",
        finding_id: "018f0a00-0000-7000-8000-000000001004",
        from_status: "in_progress",
        to_status: "resolved",
        actor_kind: "user",
        actor_id: "usr_fe_eng",
        reason: "Added rel='noopener noreferrer' in commit ab3f12",
        created_at: "2026-10-17T16:30:00Z",
      },
    ],
  },
  "018f0a00-0000-7000-8000-000000001005": {
    id: "018f0a00-0000-7000-8000-000000001005",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    fingerprint: "fp_auth_jwt_expire_05",
    rule_id: "SEC-AUTH-008",
    source: "devmind_rule",
    category: "authentication",
    title: "JWT token validation lacks maximum clock skew tolerance",
    summary:
      "JWT decode method does not specify leeway parameter, leading to token validation drift.",
    explanation:
      "In `server/app/core/auth_context.py`, the token decoder relies on default timestamp comparisons without configuring bounded clock skew leeway. In multi-region deployments, minor NTP drift can lead to spurious 401s.",
    severity: "low",
    confidence: "medium",
    evidence_level: "E1",
    status: "dismissed",
    status_reason: "false_positive: Clock drift handled upstream at reverse proxy ingress.",
    primary_path: "server/app/core/auth_context.py",
    primary_start_line: 62,
    primary_end_line: 74,
    created_at: "2026-10-15T09:00:00Z",
    updated_at: "2026-10-16T10:00:00Z",
    evidence: [
      {
        id: "ev-018f0a00-0000-7000-8000-000000000006",
        finding_id: "018f0a00-0000-7000-8000-000000001005",
        path: "server/app/core/auth_context.py",
        start_line: 62,
        end_line: 74,
        snippet_hash: "sha256:9a8b7c6d5e4f3a2b1c0",
        role: "rule_hit",
        is_current: true,
        created_at: "2026-10-15T09:00:00Z",
        detail: {
          function: "decode_jwt_token",
          missing_param: "leeway",
        },
      },
    ],
    history: [
      {
        id: "hist-05",
        finding_id: "018f0a00-0000-7000-8000-000000001005",
        from_status: "open",
        to_status: "dismissed",
        actor_kind: "user",
        actor_id: "usr_sec_lead",
        reason: "false_positive: Clock drift handled upstream at reverse proxy ingress.",
        created_at: "2026-10-16T10:00:00Z",
      },
    ],
  },
  "018f0a00-0000-7000-8000-000000001006": {
    id: "018f0a00-0000-7000-8000-000000001006",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    fingerprint: "fp_secret_hardcoded_06",
    rule_id: "SEC-LEAK-002",
    source: "devmind_rule",
    category: "secret_exposure",
    title: "Potentially hardcoded API key placeholder in test fixture",
    summary: "Test fixture mock contains high-entropy string resembling private provider token.",
    explanation:
      "In `server/tests/fixtures/tokens.py`, test data contains a token formatted like a live API key. Although marked for testing, committing high-entropy tokens to version control risks tripping automated secret scanners or leaking live credentials if copied.",
    severity: "high",
    confidence: "high",
    evidence_level: "E2",
    status: "stale",
    status_reason: "Evidence file changed in recent commit 4c8d559; re-verification needed.",
    primary_path: "server/tests/fixtures/tokens.py",
    primary_start_line: 15,
    primary_end_line: 22,
    created_at: "2026-10-14T18:00:00Z",
    updated_at: "2026-10-18T07:00:00Z",
    evidence: [
      {
        id: "ev-018f0a00-0000-7000-8000-000000000007",
        finding_id: "018f0a00-0000-7000-8000-000000001006",
        path: "server/tests/fixtures/tokens.py",
        start_line: 15,
        end_line: 22,
        snippet_hash: "sha256:2f3e4d5c6b7a8f9e0a1",
        role: "rule_hit",
        is_current: false,
        created_at: "2026-10-14T18:00:00Z",
        detail: {
          entropy_score: 4.82,
          pattern: "provider_key_regex",
          note: "File content modified since last scan. Hash mismatch.",
        },
      },
    ],
    history: [
      {
        id: "hist-06",
        finding_id: "018f0a00-0000-7000-8000-000000001006",
        from_status: "open",
        to_status: "stale",
        actor_kind: "system",
        actor_id: "scan_watcher",
        reason: "Evidence file server/tests/fixtures/tokens.py modified in commit 4c8d559",
        created_at: "2026-10-18T07:00:00Z",
      },
    ],
  },
};

export const SAMPLE_FINDINGS_LIST: FindingItem[] = Object.values(SAMPLE_FINDING_DETAILS).map(
  (d) => ({
    id: d.id,
    project_id: d.project_id,
    fingerprint: d.fingerprint,
    rule_id: d.rule_id,
    source: d.source,
    category: d.category,
    title: d.title,
    summary: d.summary,
    explanation: d.explanation,
    severity: d.severity,
    confidence: d.confidence,
    evidence_level: d.evidence_level,
    status: d.status,
    primary_path: d.primary_path,
    primary_start_line: d.primary_start_line,
    primary_end_line: d.primary_end_line,
    suggested_fix: d.suggested_fix,
    status_reason: d.status_reason,
    created_at: d.created_at,
    updated_at: d.updated_at,
  })
);

export const SAMPLE_CODE_SNIPPETS: Record<string, { code: string; startLine: number }> = {
  "server/app/api/admin.py": {
    startLine: 38,
    code: `@router.get(
    "/users",
    response_model=list[UserResponse],
    summary="List administrative users",
)
async def list_admin_users(
    session: AsyncSession = Depends(get_db_session),
) -> list[UserResponse]:
    """Retrieve all users without checking caller authorization."""
    stmt = select(UserModel).order_by(UserModel.created_at.desc())
    result = await session.execute(stmt)
    return [UserResponse.model_validate(u) for u in result.scalars().all()]`,
  },
  "client/lib/motion/sequence.ts": {
    startLine: 108,
    code: `export async function runSequence(keyframes: Keyframe[]): Promise<void> {
  for (const frame of keyframes) {
    // Unhandled promise rejection if cancelled without catch
    await stepAnimation(frame);
    await delay(frame.duration);
  }
}`,
  },
  "server/app/domain/brain/repository.py": {
    startLine: 85,
    code: `async def list_findings_by_status(
    session: AsyncSession,
    status: str,
) -> list[FindingModel]:
    # Missing tenant composite index scan
    stmt = select(FindingModel).where(FindingModel.status == status)
    result = await session.execute(stmt)
    return list(result.scalars().all())`,
  },
  "client/components/health/StatusStrip.tsx": {
    startLine: 43,
    code: `export function DocsLink() {
  return (
    <a href="https://docs.devmind.dev" target="_blank" className="text-ref hover:underline">
      View DevMind Documentation
    </a>
  );
}`,
  },
  "server/app/core/auth_context.py": {
    startLine: 60,
    code: `def decode_jwt_token(token: str, secret: str) -> dict[str, Any]:
    # Lacks leeway parameter for clock skew tolerance
    payload = jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        options={"verify_exp": True},
    )
    return payload`,
  },
  "server/tests/fixtures/tokens.py": {
    startLine: 12,
    code: `# Test mock fixtures
TEST_GITHUB_PAT = "ghp_MockSecretTokenValueForTestHarness1234567890"
TEST_API_KEY = "dm_live_mock_super_secret_payload_key_value_here"
TEST_SIGNING_SECRET = "sec_018f0a00_mock_signing_key"`,
  },
};
