import type {
  DeploymentDiagnosisRequest,
  DeploymentDiagnosisResponse,
  DeploymentIncidentListResponse,
  DeploymentIncidentResponse,
  DeploymentResolutionUpdate,
  DiagnosisHypothesis,
  EnvVarCheckResultSchema,
  SimilarIncidentMatch,
} from "@devmind/common/api";

export type {
  DeploymentDiagnosisRequest,
  DeploymentDiagnosisResponse,
  DeploymentIncidentListResponse,
  DeploymentIncidentResponse,
  DeploymentResolutionUpdate,
  DiagnosisHypothesis,
  EnvVarCheckResultSchema,
  SimilarIncidentMatch,
};

export function getCategoryBadgeVariant(
  category: string
): "signal" | "warn" | "danger" | "neutral" {
  switch (category.toLowerCase()) {
    case "database_migration_failed":
    case "unhandled_exception":
      return "danger";
    case "missing_env_var":
    case "port_binding_failed":
      return "warn";
    case "build_compilation_failed":
    case "dependency_mismatch":
      return "warn";
    case "timeout":
      return "neutral";
    default:
      return "neutral";
  }
}

export function formatCategoryLabel(category: string): string {
  switch (category) {
    case "missing_env_var":
      return "Missing Environment Variable";
    case "database_migration_failed":
      return "Database Migration Failed";
    case "dependency_mismatch":
      return "Dependency Mismatch";
    case "port_binding_failed":
      return "Port Binding Conflict";
    case "build_compilation_failed":
      return "Build / Compilation Failed";
    case "timeout":
      return "Service Startup Timeout";
    case "unhandled_exception":
      return "Unhandled Runtime Exception";
    default:
      return category.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }
}

export function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

export const SAMPLE_LOG_SNIPPET = `[2026-11-01 14:02:11] INFO: Starting DevMind API Gateway v0.1.0 on port 8000
[2026-11-01 14:02:12] ERROR: pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
[2026-11-01 14:02:12]   DATABASE_URL
[2026-11-01 14:02:12]     Field required [type=missing, input_value={}, input_type=dict]
[2026-11-01 14:02:12]   File "/app/server/app/core/config.py", line 42, in get_settings
[2026-11-01 14:02:12]     return Settings()
[2026-11-01 14:02:13] CRITICAL: Container failed to start. Exiting with code 1.`;

export const SAMPLE_DIAGNOSIS_RESPONSE: DeploymentDiagnosisResponse = {
  incident_id: "0192e4a1-0000-7000-8000-000000000001",
  is_new_incident: true,
  fingerprint: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  failure_category: "missing_env_var",
  confidence: 0.95,
  summary:
    "Application failed to boot because required environment variable DATABASE_URL is missing",
  probable_cause:
    "Pydantic Settings initialization raised ValidationError: DATABASE_URL field required",
  recommended_action:
    "Set DATABASE_URL in your hosting platform dashboard (e.g. Render / Neon) or in your deployment environment variables.",
  hypotheses: [
    {
      title: "Missing DATABASE_URL in container environment",
      probable_cause: "DATABASE_URL is not set in the container environment",
      confidence: 0.95,
      recommended_action:
        "Define DATABASE_URL in Render environment settings matching Neon database connection URI.",
      log_line_citations: [2, 3],
      file_citations: ["server/app/core/config.py"],
    },
    {
      title: "Variable name typo on hosting platform",
      probable_cause: "Typo in variable name such as DB_URL or DATABASE_URI in platform config",
      confidence: 0.15,
      recommended_action: "Verify the platform variable spelling matches Settings field exactly.",
      log_line_citations: [],
      file_citations: [],
    },
  ],
  referenced_env_vars: ["DATABASE_URL"],
  env_var_check: {
    has_issues: true,
    missing_required: ["DATABASE_URL"],
    referenced_names: ["DATABASE_URL"],
    referenced_missing: ["DATABASE_URL"],
    suspected_typos: [
      {
        referenced_name: "DATABASE_URL",
        template_name: "DATABASE_URL",
        similarity: 1.0,
      },
    ],
    valid_configured: ["REDIS_URL", "CLERK_SECRET_KEY"],
  },
  referenced_files: [
    {
      file_path: "server/app/core/config.py",
      line_number: 42,
      function_name: "get_settings",
    },
  ],
  primary_log_line: 2,
  similar_past_incidents: [
    {
      incident_id: "0192e4a1-0000-7000-8000-000000000099",
      fingerprint: "a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0",
      summary: "Render web service boot crash: missing DATABASE_URL",
      probable_cause: "Missing database connection string during startup",
      failure_category: "missing_env_var",
      similarity_score: 0.92,
      match_type: "similar_tokens",
      last_seen_at: "2026-10-31T12:00:00Z",
      resolution: "Added Neon Postgres connection string into Render Environment Secret Groups",
    },
  ],
  is_insufficient_log: false,
  missing_information_needed: null,
  redaction_count: 1,
  created_at: "2026-11-01T14:02:15Z",
};

export const SAMPLE_INCIDENTS: DeploymentIncidentResponse[] = [
  {
    id: "0192e4a1-0000-7000-8000-000000000001",
    workspace_id: "018f0a00-0000-7000-8000-000000000001",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    fingerprint: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    summary: "Missing DATABASE_URL during FastAPI startup",
    probable_cause: "Pydantic Settings ValidationError for DATABASE_URL",
    resolution: "Added Neon Postgres connection URI into Render Environment Group",
    error_signature:
      "pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings",
    environment: "production",
    service_name: "devmind-api",
    failure_category: "missing_env_var",
    log_snippet: SAMPLE_LOG_SNIPPET,
    occurrence_count: 4,
    last_seen_at: "2026-11-01T14:02:15Z",
    resolved_at: "2026-11-01T14:15:00Z",
    resolved_by: "DevOps Engineer",
    created_at: "2026-10-30T10:00:00Z",
    updated_at: "2026-11-01T14:15:00Z",
  },
  {
    id: "0192e4a1-0000-7000-8000-000000000002",
    workspace_id: "018f0a00-0000-7000-8000-000000000001",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    fingerprint: "9f82d1e03857192837465019283746501928374650192837465019283746e3b0",
    summary: "Alembic schema migration failed: relation already exists",
    probable_cause: "Migration script 0017 attempted to create existing index concurrently",
    resolution: null,
    error_signature: "alembic.util.exc.CommandError: Can't locate revision identified by '0017'",
    environment: "staging",
    service_name: "devmind-migrator",
    failure_category: "database_migration_failed",
    log_snippet:
      "[alembic] INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.\n[alembic] ERROR [alembic.util.exc] Can't locate revision identified by '0017'\nFAILED: migration aborted",
    occurrence_count: 2,
    last_seen_at: "2026-10-31T18:45:00Z",
    resolved_at: null,
    resolved_by: null,
    created_at: "2026-10-31T17:20:00Z",
    updated_at: "2026-10-31T18:45:00Z",
  },
  {
    id: "0192e4a1-0000-7000-8000-000000000003",
    workspace_id: "018f0a00-0000-7000-8000-000000000001",
    project_id: "018f0a00-0000-7000-8000-000000000101",
    fingerprint: "11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff",
    summary: "Port binding error: address already in use on port 8000",
    probable_cause: "Orphaned gunicorn or uvicorn process holding socket",
    resolution: "Configured SO_REUSEPORT and updated health check grace period to 15s",
    error_signature: "OSError: [Errno 98] Address already in use",
    environment: "preview",
    service_name: "devmind-api",
    failure_category: "port_binding_failed",
    log_snippet:
      "ERROR: [Errno 98] error while attempting to bind on address ('0.0.0.0', 8000): address already in use",
    occurrence_count: 1,
    last_seen_at: "2026-10-29T11:10:00Z",
    resolved_at: "2026-10-29T11:40:00Z",
    resolved_by: "System Admin",
    created_at: "2026-10-29T11:10:00Z",
    updated_at: "2026-10-29T11:40:00Z",
  },
];
