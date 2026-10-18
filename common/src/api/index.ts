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
export type CodeSymbolItem = components["schemas"]["CodeSymbolItem"];
export type BrainFileItem = components["schemas"]["BrainFileItem"];
export type BrainFileDetail = components["schemas"]["BrainFileDetail"];
export type GraphResponse = components["schemas"]["GraphResponse"];
export type BrainSummaryResponse = components["schemas"]["BrainSummaryResponse"];
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
}
