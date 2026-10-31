/**
 * DevMind Type-safe API Client generated from OpenAPI specification (docs/03 §10).
 */

export type { paths, operations, components } from "./schema.js";
import type { components } from "./schema.js";

export interface ProblemDetails {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  code?: string;
  request_id?: string;
  errors?: Array<Record<string, unknown>>;
}

export type WorkspaceResponse = components["schemas"]["WorkspaceResponse"];
export type CreateWorkspaceRequest = components["schemas"]["CreateWorkspaceRequest"];
export type UpdateWorkspaceRequest = components["schemas"]["UpdateWorkspaceRequest"];
export type WorkspaceMemberResponse = components["schemas"]["WorkspaceMemberResponse"];
export type AddWorkspaceMemberRequest = components["schemas"]["AddWorkspaceMemberRequest"];
export type UpdateWorkspaceMemberRequest = components["schemas"]["UpdateWorkspaceMemberRequest"];
export type ProjectResponse = components["schemas"]["ProjectResponse"];
export type CreateProjectRequest = components["schemas"]["CreateProjectRequest"];
export type UpdateProjectRequest = components["schemas"]["UpdateProjectRequest"];
export type ProjectMemberResponse = components["schemas"]["ProjectMemberResponse"];
export type AddProjectMemberRequest = components["schemas"]["AddProjectMemberRequest"];
export type UserProfileResponse = components["schemas"]["UserProfileResponse"];
export type UserPermissionsResponse = components["schemas"]["UserPermissionsResponse"];
export type FindingItem = components["schemas"]["FindingItem"];
export type FindingDetailItem = components["schemas"]["FindingDetailItem"];
export type FindingEvidenceItem = components["schemas"]["FindingEvidenceItem"];
export type FindingStatusHistoryItem = components["schemas"]["FindingStatusHistoryItem"];
export type FindingStatusTransitionRequest =
  components["schemas"]["FindingStatusTransitionRequest"];
export type AnalysisJobResponse = components["schemas"]["AnalysisJobResponse"];
export type AnalysisJobCreatedResponse = components["schemas"]["AnalysisJobCreatedResponse"];
export type CreateAnalysisRequest = components["schemas"]["CreateAnalysisRequest"];
export type SnapshotItem = components["schemas"]["SnapshotItem"];
export type SnapshotDetail = components["schemas"]["SnapshotDetail"];
export type CreateSnapshotRequest = components["schemas"]["CreateSnapshotRequest"];
export type SnapshotDiffItem = components["schemas"]["SnapshotDiffItem"];
export type SnapshotDiffResponse = components["schemas"]["SnapshotDiffResponse"];
export type CodeSymbolItem = components["schemas"]["CodeSymbolItem"];
export type BrainFileItem = components["schemas"]["BrainFileItem"];
export type BrainFileDetail = components["schemas"]["BrainFileDetail"];
export type GraphResponse = components["schemas"]["GraphResponse"];
export type BrainSummaryResponse = components["schemas"]["BrainSummaryResponse"];

export type BugRecordCreate = components["schemas"]["BugRecordCreate"];
export type BugRecordResponse = components["schemas"]["BugRecordResponse"];
export type BugRecordDetailResponse = components["schemas"]["BugRecordDetailResponse"];
export type BugResolutionCreate = components["schemas"]["BugResolutionCreate"];
export type BugResolutionResponse = components["schemas"]["BugResolutionResponse"];
export type BugMatchRequest = components["schemas"]["BugMatchRequest"];
export type BugMatchResponse = components["schemas"]["BugMatchResponse"];
export type BugMatchCandidateResponse = components["schemas"]["BugMatchCandidateResponse"];

export type DocRecordCreate = components["schemas"]["DocRecordCreate"];
export type DocRecordResponse = components["schemas"]["DocRecordResponse"];
export type DocRecordDetailResponse = components["schemas"]["DocRecordDetailResponse"];
export type DocDriftDetectRequest = components["schemas"]["DocDriftDetectRequest"];
export type DocDriftDetectResponse = components["schemas"]["DocDriftDetectResponse"];
export type DocDriftItemResponse = components["schemas"]["DocDriftItemResponse"];
export type DriftApprovalRequest = components["schemas"]["DriftApprovalRequest"];
export type DriftActionResponse = components["schemas"]["DriftActionResponse"];
export type PatchProposalResponse = components["schemas"]["PatchProposalResponse"];
export interface QuotaItem {
  resource: string;
  used: number;
  limit: number;
  unit: string;
  percent: number;
  threshold: "normal" | "warning" | "danger";
}

export interface TaskUsageBreakdown {
  task: string;
  jobCount: number;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
}

export interface ProjectUsageBreakdown {
  projectId: string;
  projectName: string;
  totalTokens: number;
  jobCount: number;
  lastActive: string;
}

export interface WorkspaceUsageSummary {
  workspaceId: string;
  period: string;
  totalPromptTokens: number;
  totalCompletionTokens: number;
  totalTokens: number;
  totalCostUnits: number;
  quotas: QuotaItem[];
  byTask: TaskUsageBreakdown[];
  byProject: ProjectUsageBreakdown[];
}

export interface ExtensionDeviceItem {
  id: string;
  name: string;
  platform: string;
  extensionVersion: string;
  vscodeVersion?: string;
  lastSeenAt: string;
  createdAt: string;
  isRevoked: boolean;
  revokedAt?: string | null;
  status: "active" | "idle" | "revoked";
}

export interface RevokeDeviceResponse {
  id: string;
  success: boolean;
  message: string;
}

export interface SyncModeTransitionResponse {
  project_id: string;
  workspace_id: string;
  previous_sync_mode: "metadata_only" | "indexed";
  new_sync_mode: "metadata_only" | "indexed";
  purged_counts: {
    code_chunks: number;
    embeddings: number;
  };
  transitioned_at: string;
}

export interface ConsentItem {
  id: string;
  workspace_id: string;
  project_id: string;
  user_id: string;
  scope: "snippet_transmission" | "cloud_index" | "llm_processing";
  provider_ids: string[];
  data_categories: string[];
  granted_for: "single_request" | "project";
  policy_version: string;
  preview_hash: string | null;
  granted_at: string;
  expires_at: string | null;
  revoked_at: string | null;
  is_active: boolean;
  purged_counts?: {
    code_chunks: number;
    embeddings: number;
  } | null;
  sync_mode_updated?: boolean;
  new_sync_mode?: string | null;
}

export interface ConsentListResponse {
  items: ConsentItem[];
  total: number;
}

export interface CreateConsentRequest {
  scope: "snippet_transmission" | "cloud_index" | "llm_processing";
  provider_ids?: string[];
  data_categories?: string[];
  granted_for?: "single_request" | "project";
  policy_version?: string;
  preview_hash?: string;
  expires_at?: string;
}

export interface DeletionVerificationReport {
  project_id: string;
  workspace_id: string;
  requested_by: string;
  purged_at: string;
  scope: string;
  stores: {
    postgres: {
      code_chunks: number;
      chunk_embeddings: number;
      evidence_snippets?: number;
      job_events?: number;
    };
    redis: {
      cache_keys_purged: number;
    };
    checkpoints: {
      threads_purged: number;
    };
  };
  verification_hash: string;
  sync_mode: "metadata_only" | "indexed";
  status: "completed" | "failed";
}

export interface PurgeProjectDataRequest {
  scope?: "all" | "chunks_and_embeddings";
  confirmation_slug?: string;
}

export interface RetentionPolicyItem {
  id: string;
  workspace_id: string;
  project_id: string | null;
  kind: string;
  days: number;
  is_override: boolean;
  created_at: string;
  updated_at: string;
}

export interface EffectiveRetentionCategory {
  kind: string;
  days: number;
  default_days: number;
  description: string;
  is_custom: boolean;
  source: "project_override" | "workspace_policy" | "default";
}

export interface EffectiveRetentionSummary {
  workspace_id: string;
  project_id?: string | null;
  backup_retention_notice: string;
  categories: EffectiveRetentionCategory[];
}

export interface UpdateRetentionPolicyRequest {
  days: number;
}

export interface RetentionSweepReport {
  project_id: string;
  swept_at: string;
  purged_counts: Record<string, number>;
  effective_windows: Record<string, number>;
}

export interface AuditEventItem {
  id: string;
  workspace_id: string;
  actor_id?: string | null;
  actor_kind: string;
  action: string;
  target_kind: string;
  target_id?: string | null;
  ip_hash?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ListAuditEventsParams {
  action?: string;
  target_kind?: string;
  target_id?: string;
  actor_id?: string;
  limit?: number;
  offset?: number;
}

// ---------------------------------------------------------------------------
// Pull Requests & PRAgent Intelligence (CAP-06, M11-03, M11-05, M11-06)
// ---------------------------------------------------------------------------

export interface PullRequestSummary {
  id: string;
  repository_id: string;
  number: number;
  title: string;
  author_login: string;
  state: "open" | "closed" | "merged" | string;
  head_sha: string;
  base_sha: string;
  head_ref?: string | null;
  base_ref?: string | null;
  diff_url?: string | null;
  merged_at?: string | null;
  closed_at?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface DirectSymbolItem {
  name: string;
  kind: string;
  file_path: string;
  symbol_key?: string | null;
}

export interface AffectedRouteItem {
  path: string;
  method: string;
  handler: string;
  file_path: string;
}

export interface GraphNodeItem {
  id: string;
  label: string;
  type: "file" | "symbol" | "route" | "test" | "module" | string;
  file_path?: string | null;
}

export interface GraphEdgeItem {
  from_node: string;
  to_node: string;
  kind: string;
}

export interface ChangeImpactReport {
  changed_files: string[];
  direct_symbols: DirectSymbolItem[];
  affected_modules: string[];
  affected_routes: AffectedRouteItem[];
  affected_tests: string[];
  dependency_graph_nodes: GraphNodeItem[];
  dependency_graph_edges: GraphEdgeItem[];
  risk_level: "low" | "medium" | "high" | "critical" | string;
  risk_reasons: string[];
}

export interface PRSummary {
  purpose: string;
  files_changed: string[];
  affected_areas: string[];
  risks: string[];
  security_summary: string;
  testing_concerns: string[];
  documentation_impact: string;
  risk_level: string;
}

export interface PRAnalysisResponse {
  id: string;
  workspace_id: string;
  project_id: string;
  pull_request_id: string;
  head_sha: string;
  job_id?: string | null;
  risk_level: "low" | "medium" | "high" | "critical" | string;
  summary: PRSummary | Record<string, unknown>;
  impact: ChangeImpactReport | Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

export interface TriggerPRAnalysisRequest {
  diff_override?: string | null;
  post_comment?: boolean;
}

export interface ReviewRuleResponse {
  id: string;
  workspace_id: string;
  project_id: string;
  rule_id: string;
  title: string;
  category: string;
  severity: string;
  scope_selector: Record<string, unknown>;
  check_type: string;
  check_config: Record<string, unknown>;
  message: string;
  suggested_fix_template?: string | null;
  is_enabled: boolean;
  is_builtin: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface WorkspaceInvitationItem {
  id: string;
  workspace_id: string;
  email: string;
  role: "admin" | "member" | "viewer" | string;
  invited_by?: string | null;
  expires_at: string;
  accepted_at?: string | null;
  created_at: string;
}

export interface CreateInvitationRequest {
  email: string;
  role?: "admin" | "member" | "viewer" | string;
}

export interface CreateInvitationResponse {
  invitation: WorkspaceInvitationItem;
  accept_url: string;
}

export interface VerifyInvitationResponse {
  invitation_id: string;
  workspace_id: string;
  workspace_name: string;
  email: string;
  role: string;
  inviter_name: string;
  expires_at: string;
}

export interface AcceptInvitationRequest {
  token: string;
}

export interface AcceptInvitationResponse {
  status: string;
  workspace_id: string;
  workspace_name: string;
  role: string;
  user_id: string;
}

export class ApiError extends Error {
  public readonly status: number;
  public readonly code: string;
  public readonly title: string;
  public readonly detail: string;
  public readonly requestId?: string;
  public readonly errors?: Array<Record<string, unknown>>;

  constructor(problem: ProblemDetails, status: number) {
    super(problem.detail || problem.title || "DevMind API Request Failed");
    this.name = "ApiError";
    this.status = status;
    this.code = problem.code || "unknown_error";
    this.title = problem.title || "API Error";
    this.detail = problem.detail || "";
    this.requestId = problem.request_id || undefined;
    this.errors = problem.errors ?? undefined;
  }
}

export interface ApiClientConfig {
  baseUrl: string;
  getToken?: () => Promise<string | null> | string | null;
  defaultHeaders?: Record<string, string>;
}

export class DevMindApiClient {
  private readonly baseUrl: string;
  private readonly getToken?: () => Promise<string | null> | string | null;
  private readonly defaultHeaders: Record<string, string>;

  constructor(config: ApiClientConfig) {
    this.baseUrl = config.baseUrl.replace(/\/+$/, "");
    this.getToken = config.getToken;
    this.defaultHeaders = config.defaultHeaders || {};
  }

  private async fetchInternal<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers: Record<string, string> = {
      Accept: "application/json",
      ...this.defaultHeaders,
      ...((options.headers as Record<string, string>) || {}),
    };

    if (this.getToken) {
      const token = await this.getToken();
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
    }

    if (options.body && typeof options.body === "string" && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let problem: ProblemDetails;
      try {
        problem = await response.json();
      } catch {
        problem = {
          title: response.statusText,
          status: response.status,
          detail: `HTTP request failed with status ${response.status}`,
          code: "http.error",
        };
      }
      throw new ApiError(problem, response.status);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return (await response.json()) as T;
  }

  // -------------------------------------------------------------------------
  // Health & System
  // -------------------------------------------------------------------------

  public async healthz(): Promise<{ status: string }> {
    return this.fetchInternal<{ status: string }>("/healthz");
  }

  public async readyz(): Promise<{ status: string; database: string; redis: string }> {
    return this.fetchInternal<{ status: string; database: string; redis: string }>("/readyz");
  }

  // -------------------------------------------------------------------------
  // Me / Identity
  // -------------------------------------------------------------------------

  public async getMe(): Promise<UserProfileResponse> {
    return this.fetchInternal<UserProfileResponse>("/api/v1/me");
  }

  public async getMyPermissions(
    workspaceId?: string,
    projectId?: string
  ): Promise<UserPermissionsResponse> {
    const query = new URLSearchParams();
    if (workspaceId) query.set("workspace_id", workspaceId);
    if (projectId) query.set("project_id", projectId);
    const qs = query.toString() ? `?${query.toString()}` : "";
    return this.fetchInternal<UserPermissionsResponse>(`/api/v1/me/permissions${qs}`);
  }

  // -------------------------------------------------------------------------
  // Workspaces
  // -------------------------------------------------------------------------

  public async listWorkspaces(): Promise<WorkspaceResponse[]> {
    return this.fetchInternal<WorkspaceResponse[]>("/api/v1/workspaces");
  }

  public async createWorkspace(data: CreateWorkspaceRequest): Promise<WorkspaceResponse> {
    return this.fetchInternal<WorkspaceResponse>("/api/v1/workspaces", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  public async getWorkspace(workspaceId: string): Promise<WorkspaceResponse> {
    return this.fetchInternal<WorkspaceResponse>(`/api/v1/workspaces/${workspaceId}`);
  }

  public async updateWorkspace(
    workspaceId: string,
    data: UpdateWorkspaceRequest
  ): Promise<WorkspaceResponse> {
    return this.fetchInternal<WorkspaceResponse>(`/api/v1/workspaces/${workspaceId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  public async listWorkspaceMembers(workspaceId: string): Promise<WorkspaceMemberResponse[]> {
    return this.fetchInternal<WorkspaceMemberResponse[]>(
      `/api/v1/workspaces/${workspaceId}/members`
    );
  }

  public async addWorkspaceMember(
    workspaceId: string,
    data: AddWorkspaceMemberRequest
  ): Promise<WorkspaceMemberResponse> {
    return this.fetchInternal<WorkspaceMemberResponse>(
      `/api/v1/workspaces/${workspaceId}/members`,
      {
        method: "POST",
        body: JSON.stringify(data),
      }
    );
  }

  public async updateWorkspaceMember(
    workspaceId: string,
    userId: string,
    data: UpdateWorkspaceMemberRequest
  ): Promise<WorkspaceMemberResponse> {
    return this.fetchInternal<WorkspaceMemberResponse>(
      `/api/v1/workspaces/${workspaceId}/members/${userId}`,
      {
        method: "PATCH",
        body: JSON.stringify(data),
      }
    );
  }

  public async removeWorkspaceMember(workspaceId: string, userId: string): Promise<void> {
    return this.fetchInternal<void>(`/api/v1/workspaces/${workspaceId}/members/${userId}`, {
      method: "DELETE",
    });
  }

  public async listWorkspaceInvitations(workspaceId: string): Promise<WorkspaceInvitationItem[]> {
    return this.fetchInternal<WorkspaceInvitationItem[]>(
      `/api/v1/workspaces/${workspaceId}/invitations`
    );
  }

  public async createWorkspaceInvitation(
    workspaceId: string,
    data: CreateInvitationRequest
  ): Promise<CreateInvitationResponse> {
    return this.fetchInternal<CreateInvitationResponse>(
      `/api/v1/workspaces/${workspaceId}/invitations`,
      {
        method: "POST",
        body: JSON.stringify(data),
      }
    );
  }

  public async revokeWorkspaceInvitation(workspaceId: string, invitationId: string): Promise<void> {
    return this.fetchInternal<void>(
      `/api/v1/workspaces/${workspaceId}/invitations/${invitationId}`,
      {
        method: "DELETE",
      }
    );
  }

  public async verifyInvitationToken(token: string): Promise<VerifyInvitationResponse> {
    return this.fetchInternal<VerifyInvitationResponse>(
      `/api/v1/invitations/verify?token=${encodeURIComponent(token)}`
    );
  }

  public async acceptInvitation(data: AcceptInvitationRequest): Promise<AcceptInvitationResponse> {
    return this.fetchInternal<AcceptInvitationResponse>(`/api/v1/invitations/accept`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // -------------------------------------------------------------------------
  // Projects
  // -------------------------------------------------------------------------

  public async listWorkspaceProjects(workspaceId: string): Promise<ProjectResponse[]> {
    return this.fetchInternal<ProjectResponse[]>(`/api/v1/workspaces/${workspaceId}/projects`);
  }

  public async createProject(
    workspaceId: string,
    data: CreateProjectRequest
  ): Promise<ProjectResponse> {
    return this.fetchInternal<ProjectResponse>(`/api/v1/workspaces/${workspaceId}/projects`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  public async getProject(projectId: string): Promise<ProjectResponse> {
    return this.fetchInternal<ProjectResponse>(`/api/v1/projects/${projectId}`);
  }

  public async updateProject(
    projectId: string,
    data: UpdateProjectRequest
  ): Promise<ProjectResponse> {
    return this.fetchInternal<ProjectResponse>(`/api/v1/projects/${projectId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  public async deleteProject(projectId: string): Promise<void> {
    return this.fetchInternal<void>(`/api/v1/projects/${projectId}`, {
      method: "DELETE",
    });
  }

  public async listProjectMembers(projectId: string): Promise<ProjectMemberResponse[]> {
    return this.fetchInternal<ProjectMemberResponse[]>(`/api/v1/projects/${projectId}/members`);
  }

  public async addProjectMember(
    projectId: string,
    data: AddProjectMemberRequest
  ): Promise<ProjectMemberResponse> {
    return this.fetchInternal<ProjectMemberResponse>(`/api/v1/projects/${projectId}/members`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  public async removeProjectMember(projectId: string, userId: string): Promise<void> {
    return this.fetchInternal<void>(`/api/v1/projects/${projectId}/members/${userId}`, {
      method: "DELETE",
    });
  }

  // -------------------------------------------------------------------------
  // Findings
  // -------------------------------------------------------------------------

  public async listFindings(
    projectId: string,
    filters?: {
      status?: string;
      severity?: string;
      category?: string;
      limit?: number;
      offset?: number;
    }
  ): Promise<FindingItem[]> {
    const query = new URLSearchParams();
    if (filters?.status) query.set("status", filters.status);
    if (filters?.severity) query.set("severity", filters.severity);
    if (filters?.category) query.set("category", filters.category);
    if (filters?.limit !== undefined) query.set("limit", String(filters.limit));
    if (filters?.offset !== undefined) query.set("offset", String(filters.offset));
    const qs = query.toString() ? `?${query.toString()}` : "";
    return this.fetchInternal<FindingItem[]>(`/api/v1/projects/${projectId}/findings${qs}`);
  }

  public async getFindingDetail(projectId: string, findingId: string): Promise<FindingDetailItem> {
    return this.fetchInternal<FindingDetailItem>(
      `/api/v1/projects/${projectId}/findings/${findingId}`
    );
  }

  public async transitionFindingStatus(
    projectId: string,
    findingId: string,
    data: FindingStatusTransitionRequest
  ): Promise<FindingDetailItem> {
    return this.fetchInternal<FindingDetailItem>(
      `/api/v1/projects/${projectId}/findings/${findingId}/transitions`,
      {
        method: "POST",
        body: JSON.stringify(data),
      }
    );
  }

  // -------------------------------------------------------------------------
  // Jobs & Analyses (docs/03 §5.2, §12.2)
  // -------------------------------------------------------------------------

  public async listProjectJobs(
    projectId: string,
    filters?: {
      status?: string;
      limit?: number;
      offset?: number;
    }
  ): Promise<AnalysisJobResponse[]> {
    const query = new URLSearchParams();
    if (filters?.status) query.set("status", filters.status);
    if (filters?.limit !== undefined) query.set("limit", String(filters.limit));
    if (filters?.offset !== undefined) query.set("offset", String(filters.offset));
    const qs = query.toString() ? `?${query.toString()}` : "";
    return this.fetchInternal<AnalysisJobResponse[]>(`/api/v1/projects/${projectId}/jobs${qs}`);
  }

  public async getJob(jobId: string): Promise<AnalysisJobResponse> {
    return this.fetchInternal<AnalysisJobResponse>(`/api/v1/jobs/${jobId}`);
  }

  public async cancelJob(jobId: string): Promise<AnalysisJobResponse> {
    return this.fetchInternal<AnalysisJobResponse>(`/api/v1/jobs/${jobId}/cancel`, {
      method: "POST",
    });
  }

  public async createAnalysisJob(
    projectId: string,
    data: CreateAnalysisRequest,
    idempotencyKey?: string
  ): Promise<AnalysisJobCreatedResponse> {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers["Idempotency-Key"] = idempotencyKey;
    }
    return this.fetchInternal<AnalysisJobCreatedResponse>(
      `/api/v1/projects/${projectId}/analyses`,
      {
        method: "POST",
        headers,
        body: JSON.stringify(data),
      }
    );
  }

  public async listSnapshots(projectId: string, limit: number = 20): Promise<SnapshotItem[]> {
    return this.fetchInternal<SnapshotItem[]>(
      `/api/v1/projects/${projectId}/brain/snapshots?limit=${limit}`
    );
  }

  public async getSnapshotDetail(projectId: string, snapshotId: string): Promise<SnapshotDetail> {
    return this.fetchInternal<SnapshotDetail>(
      `/api/v1/projects/${projectId}/brain/snapshots/${snapshotId}`
    );
  }

  public async createSnapshot(
    projectId: string,
    data: CreateSnapshotRequest
  ): Promise<SnapshotItem> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    return this.fetchInternal<SnapshotItem>(`/api/v1/projects/${projectId}/brain/snapshots`, {
      method: "POST",
      headers,
      body: JSON.stringify(data),
    });
  }

  public async compareSnapshots(
    projectId: string,
    snapshotId: string,
    targetSnapshotId?: string
  ): Promise<SnapshotDiffResponse> {
    const query = targetSnapshotId
      ? `?target_snapshot_id=${encodeURIComponent(targetSnapshotId)}`
      : "";
    return this.fetchInternal<SnapshotDiffResponse>(
      `/api/v1/projects/${projectId}/brain/snapshots/${snapshotId}/diff${query}`
    );
  }

  public async listBrainFiles(projectId: string): Promise<BrainFileItem[]> {
    return this.fetchInternal<BrainFileItem[]>(`/api/v1/projects/${projectId}/brain/files`);
  }

  public async getBrainFileDetail(projectId: string, fileId: string): Promise<BrainFileDetail> {
    return this.fetchInternal<BrainFileDetail>(
      `/api/v1/projects/${projectId}/brain/files/${fileId}`
    );
  }

  public async listSymbols(
    projectId: string,
    kind?: string,
    limit: number = 100
  ): Promise<CodeSymbolItem[]> {
    const qs = kind ? `?kind=${encodeURIComponent(kind)}&limit=${limit}` : `?limit=${limit}`;
    return this.fetchInternal<CodeSymbolItem[]>(`/api/v1/projects/${projectId}/brain/symbols${qs}`);
  }

  public async getBrainGraph(
    projectId: string,
    symbolKey?: string,
    depth: number = 2
  ): Promise<GraphResponse> {
    const query = new URLSearchParams({ depth: String(depth) });
    if (symbolKey) query.set("symbol_key", symbolKey);
    return this.fetchInternal<GraphResponse>(
      `/api/v1/projects/${projectId}/brain/graph?${query.toString()}`
    );
  }

  public async getBrainSummary(projectId: string): Promise<BrainSummaryResponse> {
    return this.fetchInternal<BrainSummaryResponse>(`/api/v1/projects/${projectId}/brain/summary`);
  }

  // -------------------------------------------------------------------------
  // Usage & Quotas (docs/03 §3.5, docs/08 §11 S-12)
  // -------------------------------------------------------------------------

  public async getWorkspaceUsage(workspaceId: string): Promise<WorkspaceUsageSummary> {
    return this.fetchInternal<WorkspaceUsageSummary>(`/api/v1/workspaces/${workspaceId}/usage`);
  }

  public async listExtensionDevices(): Promise<ExtensionDeviceItem[]> {
    return this.fetchInternal<ExtensionDeviceItem[]>("/api/v1/ext/devices");
  }

  public async revokeExtensionDevice(deviceId: string): Promise<RevokeDeviceResponse> {
    return this.fetchInternal<RevokeDeviceResponse>(`/api/v1/ext/devices/${deviceId}/revoke`, {
      method: "POST",
    });
  }

  // -------------------------------------------------------------------------
  // Project Synchronization Modes (docs/03 §11.1, ADR-022, docs/08 §11 S-10)
  // -------------------------------------------------------------------------

  public async updateProjectSyncMode(
    projectId: string,
    syncMode: "metadata_only" | "indexed"
  ): Promise<SyncModeTransitionResponse> {
    return this.fetchInternal<SyncModeTransitionResponse>(
      `/api/v1/projects/${projectId}/sync-mode`,
      {
        method: "PATCH",
        body: JSON.stringify({ sync_mode: syncMode }),
      }
    );
  }

  // -------------------------------------------------------------------------
  // Consents & Transmission Controls (docs/03 §11.1, docs/07 §7, Screen S-10)
  // -------------------------------------------------------------------------

  public async listProjectConsents(
    projectId: string,
    params?: { activeOnly?: boolean; scope?: string }
  ): Promise<ConsentListResponse> {
    const query = new URLSearchParams();
    if (params?.activeOnly) query.set("active_only", "true");
    if (params?.scope) query.set("scope", params.scope);
    const qs = query.toString() ? `?${query.toString()}` : "";
    return this.fetchInternal<ConsentListResponse>(`/api/v1/projects/${projectId}/consents${qs}`);
  }

  public async createProjectConsent(
    projectId: string,
    req: CreateConsentRequest
  ): Promise<ConsentItem> {
    return this.fetchInternal<ConsentItem>(`/api/v1/projects/${projectId}/consents`, {
      method: "POST",
      body: JSON.stringify(req),
    });
  }

  public async revokeProjectConsent(projectId: string, consentId: string): Promise<ConsentItem> {
    return this.fetchInternal<ConsentItem>(`/api/v1/projects/${projectId}/consents/${consentId}`, {
      method: "DELETE",
    });
  }

  public async purgeProjectData(
    projectId: string,
    req?: PurgeProjectDataRequest
  ): Promise<DeletionVerificationReport> {
    return this.fetchInternal<DeletionVerificationReport>(`/api/v1/projects/${projectId}/purge`, {
      method: "POST",
      body: JSON.stringify(req || {}),
    });
  }

  // -------------------------------------------------------------------------
  // Retention Windows & Scheduled Sweeps (ADR-026, docs/03 §3.1, docs/07 §9)
  // -------------------------------------------------------------------------

  public async getWorkspaceRetention(workspaceId: string): Promise<EffectiveRetentionSummary> {
    return this.fetchInternal<EffectiveRetentionSummary>(
      `/api/v1/workspaces/${workspaceId}/retention`
    );
  }

  public async updateWorkspaceRetention(
    workspaceId: string,
    kind: string,
    req: UpdateRetentionPolicyRequest
  ): Promise<RetentionPolicyItem> {
    return this.fetchInternal<RetentionPolicyItem>(
      `/api/v1/workspaces/${workspaceId}/retention/${kind}`,
      {
        method: "PUT",
        body: JSON.stringify(req),
      }
    );
  }

  public async getProjectRetention(projectId: string): Promise<EffectiveRetentionSummary> {
    return this.fetchInternal<EffectiveRetentionSummary>(`/api/v1/projects/${projectId}/retention`);
  }

  public async updateProjectRetention(
    projectId: string,
    kind: string,
    req: UpdateRetentionPolicyRequest
  ): Promise<RetentionPolicyItem> {
    return this.fetchInternal<RetentionPolicyItem>(
      `/api/v1/projects/${projectId}/retention/${kind}`,
      {
        method: "PUT",
        body: JSON.stringify(req),
      }
    );
  }

  public async resetProjectRetention(projectId: string, kind: string): Promise<void> {
    return this.fetchInternal<void>(`/api/v1/projects/${projectId}/retention/${kind}`, {
      method: "DELETE",
    });
  }

  public async triggerProjectRetentionSweep(projectId: string): Promise<RetentionSweepReport> {
    return this.fetchInternal<RetentionSweepReport>(
      `/api/v1/projects/${projectId}/retention/sweep`,
      {
        method: "POST",
      }
    );
  }

  // -------------------------------------------------------------------------
  // Audit Events & Compliance Logging (M9-06, docs/03 §3.5 & §11.1, docs/07 §16)
  // -------------------------------------------------------------------------

  public async getWorkspaceAuditEvents(
    workspaceId: string,
    params?: ListAuditEventsParams
  ): Promise<AuditEventItem[]> {
    const searchParams = new URLSearchParams();
    if (params?.action) searchParams.set("action", params.action);
    if (params?.target_kind) searchParams.set("target_kind", params.target_kind);
    if (params?.target_id) searchParams.set("target_id", params.target_id);
    if (params?.actor_id) searchParams.set("actor_id", params.actor_id);
    if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
    if (params?.offset !== undefined) searchParams.set("offset", String(params.offset));

    const qs = searchParams.toString();
    const endpoint = `/api/v1/workspaces/${workspaceId}/audit-events${qs ? `?${qs}` : ""}`;
    return this.fetchInternal<AuditEventItem[]>(endpoint);
  }

  public async getProjectAuditEvents(
    projectId: string,
    params?: { action?: string; limit?: number; offset?: number }
  ): Promise<AuditEventItem[]> {
    const searchParams = new URLSearchParams();
    if (params?.action) searchParams.set("action", params.action);
    if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
    if (params?.offset !== undefined) searchParams.set("offset", String(params.offset));

    const qs = searchParams.toString();
    const endpoint = `/api/v1/projects/${projectId}/audit-events${qs ? `?${qs}` : ""}`;
    return this.fetchInternal<AuditEventItem[]>(endpoint);
  }

  // -------------------------------------------------------------------------
  // Pull Requests & PR Intelligence (CAP-06, M11-03, M11-05, M11-06)
  // -------------------------------------------------------------------------

  public async listProjectPullRequests(
    projectId: string,
    params?: { state?: string; limit?: number; offset?: number }
  ): Promise<PullRequestSummary[]> {
    const searchParams = new URLSearchParams();
    if (params?.state) searchParams.set("state", params.state);
    if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
    if (params?.offset !== undefined) searchParams.set("offset", String(params.offset));

    const qs = searchParams.toString();
    const endpoint = `/api/v1/projects/${projectId}/pull-requests${qs ? `?${qs}` : ""}`;
    return this.fetchInternal<PullRequestSummary[]>(endpoint);
  }

  public async syncProjectPullRequests(
    projectId: string,
    state: string = "open"
  ): Promise<PullRequestSummary[]> {
    return this.fetchInternal<PullRequestSummary[]>(
      `/api/v1/projects/${projectId}/pull-requests/sync?state=${encodeURIComponent(state)}`,
      { method: "POST" }
    );
  }

  public async getPullRequest(pullRequestId: string): Promise<PullRequestSummary> {
    return this.fetchInternal<PullRequestSummary>(`/api/v1/pull-requests/${pullRequestId}`);
  }

  public async analyzePullRequest(
    pullRequestId: string,
    body?: TriggerPRAnalysisRequest
  ): Promise<PRAnalysisResponse> {
    return this.fetchInternal<PRAnalysisResponse>(
      `/api/v1/pull-requests/${pullRequestId}/analyze`,
      {
        method: "POST",
        body: JSON.stringify(body || {}),
      }
    );
  }

  public async getLatestPullRequestAnalysis(pullRequestId: string): Promise<PRAnalysisResponse> {
    return this.fetchInternal<PRAnalysisResponse>(
      `/api/v1/pull-requests/${pullRequestId}/analyses/latest`
    );
  }

  public async listPullRequestAnalyses(
    pullRequestId: string,
    params?: { limit?: number; offset?: number }
  ): Promise<PRAnalysisResponse[]> {
    const searchParams = new URLSearchParams();
    if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
    if (params?.offset !== undefined) searchParams.set("offset", String(params.offset));

    const qs = searchParams.toString();
    const endpoint = `/api/v1/pull-requests/${pullRequestId}/analyses${qs ? `?${qs}` : ""}`;
    return this.fetchInternal<PRAnalysisResponse[]>(endpoint);
  }

  public async listProjectReviewRules(
    projectId: string,
    params?: { enabled_only?: boolean; category?: string }
  ): Promise<ReviewRuleResponse[]> {
    const searchParams = new URLSearchParams();
    if (params?.enabled_only !== undefined)
      searchParams.set("enabled_only", String(params.enabled_only));
    if (params?.category) searchParams.set("category", params.category);

    const qs = searchParams.toString();
    const endpoint = `/api/v1/projects/${projectId}/review-rules${qs ? `?${qs}` : ""}`;
    return this.fetchInternal<ReviewRuleResponse[]>(endpoint);
  }

  // --- Bug Memory Endpoints (CAP-03) ---

  public async listProjectBugs(
    projectId: string,
    params?: { query?: string; status?: string; limit?: number; offset?: number }
  ): Promise<BugRecordResponse[]> {
    const searchParams = new URLSearchParams();
    if (params?.query) searchParams.set("query", params.query);
    if (params?.status) searchParams.set("status", params.status);
    if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
    if (params?.offset !== undefined) searchParams.set("offset", String(params.offset));

    const qs = searchParams.toString();
    const endpoint = `/api/v1/projects/${projectId}/bugs${qs ? `?${qs}` : ""}`;
    return this.fetchInternal<BugRecordResponse[]>(endpoint);
  }

  public async createBug(
    projectId: string,
    data: BugRecordCreate
  ): Promise<BugRecordDetailResponse> {
    return this.fetchInternal<BugRecordDetailResponse>(`/api/v1/projects/${projectId}/bugs`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  public async matchSimilarBugs(
    projectId: string,
    data: BugMatchRequest
  ): Promise<BugMatchResponse> {
    return this.fetchInternal<BugMatchResponse>(`/api/v1/projects/${projectId}/bugs/match`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  public async getBugDetail(bugId: string): Promise<BugRecordDetailResponse> {
    return this.fetchInternal<BugRecordDetailResponse>(`/api/v1/bugs/${bugId}`);
  }

  public async addBugResolution(
    bugId: string,
    data: BugResolutionCreate
  ): Promise<BugResolutionResponse> {
    return this.fetchInternal<BugResolutionResponse>(`/api/v1/bugs/${bugId}/resolutions`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // --- Living Documentation & DocsAlive Endpoints (CAP-04) ---

  public async listProjectDocs(
    projectId: string,
    params?: { kind?: string; limit?: number; offset?: number }
  ): Promise<DocRecordResponse[]> {
    const searchParams = new URLSearchParams();
    if (params?.kind) searchParams.set("kind", params.kind);
    if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
    if (params?.offset !== undefined) searchParams.set("offset", String(params.offset));

    const qs = searchParams.toString();
    const endpoint = `/api/v1/projects/${projectId}/docs${qs ? `?${qs}` : ""}`;
    return this.fetchInternal<DocRecordResponse[]>(endpoint);
  }

  public async registerProjectDoc(
    projectId: string,
    data: DocRecordCreate
  ): Promise<DocRecordDetailResponse> {
    return this.fetchInternal<DocRecordDetailResponse>(`/api/v1/projects/${projectId}/docs`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  public async getProjectDoc(projectId: string, docId: string): Promise<DocRecordDetailResponse> {
    return this.fetchInternal<DocRecordDetailResponse>(
      `/api/v1/projects/${projectId}/docs/${docId}`
    );
  }

  public async detectDocDrift(
    projectId: string,
    data: DocDriftDetectRequest
  ): Promise<DocDriftDetectResponse> {
    return this.fetchInternal<DocDriftDetectResponse>(
      `/api/v1/projects/${projectId}/docs/detect-drift`,
      {
        method: "POST",
        body: JSON.stringify(data),
      }
    );
  }

  public async listProjectDriftItems(
    projectId: string,
    params?: { status?: string; kind?: string; limit?: number; offset?: number }
  ): Promise<DocDriftItemResponse[]> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set("status", params.status);
    if (params?.kind) searchParams.set("kind", params.kind);
    if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
    if (params?.offset !== undefined) searchParams.set("offset", String(params.offset));

    const qs = searchParams.toString();
    const endpoint = `/api/v1/projects/${projectId}/docs/drift${qs ? `?${qs}` : ""}`;
    return this.fetchInternal<DocDriftItemResponse[]>(endpoint);
  }

  public async getDriftItem(driftId: string): Promise<DocDriftItemResponse> {
    return this.fetchInternal<DocDriftItemResponse>(`/api/v1/docs/drift/${driftId}`);
  }

  public async approveDriftProposal(
    driftId: string,
    reason?: string
  ): Promise<DocDriftItemResponse> {
    return this.fetchInternal<DocDriftItemResponse>(`/api/v1/docs/drift/${driftId}/approve`, {
      method: "POST",
      body: JSON.stringify({ reason: reason || "Approved via web interface" }),
    });
  }

  public async rejectDriftProposal(
    driftId: string,
    reason?: string
  ): Promise<DocDriftItemResponse> {
    return this.fetchInternal<DocDriftItemResponse>(`/api/v1/docs/drift/${driftId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason: reason || "Rejected via web interface" }),
    });
  }

  public async applyDriftPatch(driftId: string): Promise<DriftActionResponse> {
    return this.fetchInternal<DriftActionResponse>(`/api/v1/docs/drift/${driftId}/apply`, {
      method: "POST",
    });
  }
}
