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
}
