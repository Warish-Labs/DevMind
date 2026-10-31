import type {
  BugRecordResponse,
  BugRecordDetailResponse,
  BugResolutionResponse,
  BugMatchResponse,
  BugMatchCandidateResponse,
  BugRecordCreate,
  BugResolutionCreate,
} from "@devmind/common/api";

export type {
  BugRecordResponse,
  BugRecordDetailResponse,
  BugResolutionResponse,
  BugMatchResponse,
  BugMatchCandidateResponse,
  BugRecordCreate,
  BugResolutionCreate,
};

export function getConfidenceBadgeVariant(label: string): "signal" | "warn" | "danger" | "neutral" {
  switch (label.toLowerCase()) {
    case "high":
      return "signal";
    case "medium":
      return "warn";
    case "low":
      return "danger";
    default:
      return "neutral";
  }
}

export function getMatchTypeBadgeVariant(type: string): "signal" | "warn" | "neutral" {
  switch (type.toLowerCase()) {
    case "exact_fingerprint":
      return "signal";
    case "fuzzy_signature":
      return "warn";
    default:
      return "neutral";
  }
}

export const SAMPLE_BUGS: BugRecordResponse[] = [
  {
    id: "018f0a00-1111-7000-8000-000000000001",
    workspace_id: "018f0a00-0000-7000-8000-000000000001",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    fingerprint: "a9f8b4c2d1e03857192837465019283746501928374650192837465019283746",
    error_signature: "NotFoundError: Project not found in tenant scope",
    title: "Project cross-tenant scoping lookup failure",
    summary: "Repository query returned None when attempting cross-workspace project access",
    module_hint: "app.persistence.repositories.project_repo",
    occurrence_count: 7,
    resolutions_count: 1,
    first_seen_at: "2026-10-28T09:15:00Z",
    last_seen_at: "2026-10-31T08:30:00Z",
    created_at: "2026-10-28T09:15:00Z",
    updated_at: "2026-10-31T08:30:00Z",
  },
  {
    id: "018f0a00-2222-7000-8000-000000000002",
    workspace_id: "018f0a00-0000-7000-8000-000000000001",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    fingerprint: "b1c2d3e4f5a60123456789abcdef0123456789abcdef0123456789abcdef0123",
    error_signature: "AttributeError: 'ParsedDocument' object has no attribute 'extracted_symbols'",
    title: "Attribute mismatch on Markdown extracted entities serialization",
    summary:
      "Parser method rename from extracted_symbols to referenced_symbols caused serialisation error",
    module_hint: "app.analysis.doc_parser",
    occurrence_count: 3,
    resolutions_count: 1,
    first_seen_at: "2026-10-30T14:22:00Z",
    last_seen_at: "2026-10-31T09:10:00Z",
    created_at: "2026-10-30T14:22:00Z",
    updated_at: "2026-10-31T09:10:00Z",
  },
  {
    id: "018f0a00-3333-7000-8000-000000000003",
    workspace_id: "018f0a00-0000-7000-8000-000000000001",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    fingerprint: "c3d4e5f6a7b890123456789abcdef0123456789abcdef0123456789abcdef0123",
    error_signature: "SystemContext missing required argument 'reason'",
    title: "Specialist agent orchestration SystemContext instantiation error",
    summary: "Audit policy requires an explicit reason parameter when elevating to SystemContext",
    module_hint: "app.orchestration.docsalive",
    occurrence_count: 2,
    resolutions_count: 0,
    first_seen_at: "2026-10-31T08:15:00Z",
    last_seen_at: "2026-10-31T08:20:00Z",
    created_at: "2026-10-31T08:15:00Z",
    updated_at: "2026-10-31T08:20:00Z",
  },
];

export const SAMPLE_BUG_DETAIL: BugRecordDetailResponse = {
  ...SAMPLE_BUGS[0],
  raw_error: `Traceback (most recent call last):
  File "server/app/domain/living_docs/service.py", line 159, in register_document
    project = await self.project_repo.get_by_id(ctx, project_id)
NotFoundError: Project 018f0a00-0000-7000-8000-000000000101 not found in tenant scope`,
  resolutions: [
    {
      id: "018f0a00-9999-7000-8000-000000000001",
      bug_record_id: "018f0a00-1111-7000-8000-000000000001",
      cause:
        "ProjectRepository.get_by_id expected single Project returned from result.scalars().first() scoped to caller workspace.",
      fix_summary:
        "Updated ProjectRepository query helper to handle scalar_one_or_none and properly map tenant error codes to RFC 9457 ProblemDetails.",
      files: [
        {
          path: "server/app/persistence/repositories/project_repo.py",
          lines: "35-42",
        },
      ],
      finding_id: null,
      resolved_by: "system_admin",
      created_at: "2026-10-29T11:00:00Z",
      updated_at: "2026-10-29T11:00:00Z",
    },
  ],
};

export const SAMPLE_MATCH_RESULT: BugMatchResponse = {
  matched: true,
  normalized_error: {
    exception_type: "NotFoundError",
    clean_message: "Project not found in tenant scope",
    fingerprint: "a9f8b4c2d1e03857192837465019283746501928374650192837465019283746",
    normalized_signature: "NotFoundError: Project not found in tenant scope",
    module_hint: "app.persistence.repositories.project_repo",
  },
  candidates: [
    {
      bug: {
        ...SAMPLE_BUGS[0],
        raw_error: null,
        resolutions: [],
      },
      score: 1.0,
      match_type: "exact_fingerprint",
    },
  ],
  explanation:
    "Identical error signature and normalized stack trace previously occurred in `project_repo.py`. The historical fix updated tenant-scoped queries with scalar_one_or_none and validated AuthContext boundaries.",
  confidence_label: "high",
  recommended_fix:
    "Inspect the caller AuthContext and ensure repository queries filter strictly by workspace_id and project_id.",
};
