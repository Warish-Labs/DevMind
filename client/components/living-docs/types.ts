import type {
  DocRecordResponse,
  DocRecordDetailResponse,
  DocDriftItemResponse,
  PatchProposalResponse,
  DocRecordCreate,
  DocDriftDetectRequest,
  DocDriftDetectResponse,
  DriftActionResponse,
  DriftApprovalRequest,
} from "@devmind/common/api";

export type {
  DocRecordResponse,
  DocRecordDetailResponse,
  DocDriftItemResponse,
  PatchProposalResponse,
  DocRecordCreate,
  DocDriftDetectRequest,
  DocDriftDetectResponse,
  DriftActionResponse,
  DriftApprovalRequest,
};

export function getDriftStatusBadgeVariant(
  status: string
): "signal" | "warn" | "neutral" | "danger" {
  switch (status.toLowerCase()) {
    case "applied":
      return "signal";
    case "approved":
      return "neutral";
    case "detected":
      return "warn";
    case "rejected":
      return "danger";
    default:
      return "neutral";
  }
}

export function getDriftKindBadgeVariant(kind: string): "danger" | "warn" | "neutral" {
  switch (kind.toLowerCase()) {
    case "removed_route":
      return "danger";
    case "undocumented_route":
      return "warn";
    default:
      return "neutral";
  }
}

export const SAMPLE_DOCS: DocRecordResponse[] = [
  {
    id: "018f0a00-aaaa-7000-8000-000000000001",
    workspace_id: "018f0a00-0000-7000-8000-000000000001",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    file_id: null,
    path: "docs/03-data-model-and-api.md",
    title: "Data Model & API Specification",
    kind: "api",
    current_version_hash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    last_parsed_at: "2026-10-31T09:00:00Z",
    created_at: "2026-10-25T10:00:00Z",
    updated_at: "2026-10-31T09:00:00Z",
  },
  {
    id: "018f0a00-bbbb-7000-8000-000000000002",
    workspace_id: "018f0a00-0000-7000-8000-000000000001",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    file_id: null,
    path: "README.md",
    title: "Project Readme",
    kind: "readme",
    current_version_hash: "a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0",
    last_parsed_at: "2026-10-30T18:00:00Z",
    created_at: "2026-10-15T12:00:00Z",
    updated_at: "2026-10-30T18:00:00Z",
  },
  {
    id: "018f0a00-cccc-7000-8000-000000000003",
    workspace_id: "018f0a00-0000-7000-8000-000000000001",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    file_id: null,
    path: "docs/02-system-architecture.md",
    title: "System Architecture",
    kind: "architecture",
    current_version_hash: "9876543210abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    last_parsed_at: "2026-10-31T08:00:00Z",
    created_at: "2026-10-18T14:00:00Z",
    updated_at: "2026-10-31T08:00:00Z",
  },
];

export const SAMPLE_DRIFT_ITEMS: DocDriftItemResponse[] = [
  {
    id: "018f0a00-dddd-7000-8000-000000000001",
    workspace_id: "018f0a00-0000-7000-8000-000000000001",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    documentation_record_id: "018f0a00-aaaa-7000-8000-000000000001",
    kind: "undocumented_route",
    target_symbol_key: null,
    target_route_path: "POST /api/v1/projects/{project_id}/bugs/match",
    explanation:
      "Active FastAPI endpoint POST /api/v1/projects/{project_id}/bugs/match exists in code but is missing from docs/03-data-model-and-api.md.",
    status: "detected",
    proposal: {
      summary: "Add specification for POST /api/v1/projects/{project_id}/bugs/match endpoint",
      drift_kind: "undocumented_route",
      target_section: "§11.1 Bug Memory Endpoints",
      proposed_content: `### 11.1.3 \`POST /api/v1/projects/{project_id}/bugs/match\`

Matches an incoming error trace against historical bug records using deterministic fingerprinting and hybrid similarity.

- **Permission**: \`analysis:create\`
- **Request Body**: \`BugMatchRequest\` (\`raw_error\`, \`module_hint\`, \`limit\`)
- **Response**: \`BugMatchResponse\` with match candidates and BugMemory intelligence comparison.
`,
      diff_content: `--- a/docs/03-data-model-and-api.md
+++ b/docs/03-data-model-and-api.md
@@ -450,6 +450,14 @@
 
+### 11.1.3 \`POST /api/v1/projects/{project_id}/bugs/match\`
+
+Matches an incoming error trace against historical bug records using deterministic fingerprinting and hybrid similarity.
+
+- **Permission**: \`analysis:create\`
+- **Request Body**: \`BugMatchRequest\` (\`raw_error\`, \`module_hint\`, \`limit\`)
+- **Response**: \`BugMatchResponse\` with match candidates and BugMemory intelligence comparison.
+
 ### 11.2 Living Documentation Endpoints
`,
      gated: true,
      confidence: 0.95,
      notes: [
        "Inferred route signature from FastAPI route decorator in server/app/api/bug_memory.py",
      ],
      decided_by: null,
      decided_at: null,
      rejection_reason: null,
      applied_at: null,
    },
    created_at: "2026-10-31T09:05:00Z",
    updated_at: "2026-10-31T09:05:00Z",
  },
  {
    id: "018f0a00-eeee-7000-8000-000000000002",
    workspace_id: "018f0a00-0000-7000-8000-000000000001",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    documentation_record_id: "018f0a00-aaaa-7000-8000-000000000001",
    kind: "removed_route",
    target_symbol_key: null,
    target_route_path: "DELETE /api/v1/projects/{project_id}/docs/all",
    explanation:
      "Documented route DELETE /api/v1/projects/{project_id}/docs/all is no longer defined in codebase routers.",
    status: "approved",
    proposal: {
      summary: "Remove obsolete route documentation DELETE /api/v1/projects/{project_id}/docs/all",
      drift_kind: "removed_route",
      target_section: "§11.2 Living Documentation Endpoints",
      proposed_content: "",
      diff_content: `--- a/docs/03-data-model-and-api.md
+++ b/docs/03-data-model-and-api.md
@@ -480,8 +480,0 @@
-### 11.2.9 \`DELETE /api/v1/projects/{project_id}/docs/all\`
-
-Bulk deletes all documentation records for project.
`,
      gated: true,
      confidence: 0.9,
      notes: ["Route was deprecated and removed in M12-03"],
      decided_by: "lead_architect",
      decided_at: "2026-10-31T09:30:00Z",
      rejection_reason: null,
      applied_at: null,
    },
    created_at: "2026-10-31T09:05:00Z",
    updated_at: "2026-10-31T09:30:00Z",
  },
];

export const SAMPLE_DOC_DETAIL: DocRecordDetailResponse = {
  ...SAMPLE_DOCS[0],
  content_snapshot: `# Data Model and API Specification

## 11.1 Bug Memory Endpoints

### 11.1.1 \`GET /api/v1/projects/{project_id}/bugs\`
List tracked bug records.

### 11.1.2 \`POST /api/v1/projects/{project_id}/bugs\`
Create a bug record.
`,
  extracted_symbols: [
    { type: "route", method: "GET", path: "/api/v1/projects/{project_id}/bugs", line: 5 },
    { type: "route", method: "POST", path: "/api/v1/projects/{project_id}/bugs", line: 8 },
    { type: "symbol", name: "BugRecord", line: 12 },
    { type: "symbol", name: "BugMemoryService", line: 15 },
  ],
  drift_item_count: 2,
};
