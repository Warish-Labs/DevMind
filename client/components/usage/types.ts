/**
 * Types and fixtures for Workspace Usage Dashboard & Extension Devices (Screen S-12, docs/08 §11).
 * Adheres strictly to ADR-047 / ADR-046 / docs/07 §15:
 * NEVER exposes or stores prompt texts, completions, code snippets, or secrets.
 * Only aggregates counts, token totals, latencies, and device metadata.
 */

import type {
  QuotaItem,
  TaskUsageBreakdown,
  ProjectUsageBreakdown,
  WorkspaceUsageSummary,
  ExtensionDeviceItem,
} from "@devmind/common/api";

export type {
  QuotaItem,
  TaskUsageBreakdown,
  ProjectUsageBreakdown,
  WorkspaceUsageSummary,
  ExtensionDeviceItem,
};

export interface UsageFilters {
  period: string;
  projectId?: string;
  searchQuery?: string;
}

export const INITIAL_QUOTAS: QuotaItem[] = [
  {
    resource: "Monthly Inference Tokens",
    used: 524180,
    limit: 1000000,
    unit: "tokens",
    percent: 52.4,
    threshold: "normal",
  },
  {
    resource: "Monthly Analysis Jobs",
    used: 42,
    limit: 100,
    unit: "jobs",
    percent: 42.0,
    threshold: "normal",
  },
  {
    resource: "Extension Sync Requests",
    used: 8420,
    limit: 10000,
    unit: "calls",
    percent: 84.2,
    threshold: "warning",
  },
  {
    resource: "Active Workspace Projects",
    used: 3,
    limit: 5,
    unit: "projects",
    percent: 60.0,
    threshold: "normal",
  },
];

export const INITIAL_TASK_USAGE: TaskUsageBreakdown[] = [
  {
    task: "security_scan",
    jobCount: 24,
    promptTokens: 184500,
    completionTokens: 46200,
    totalTokens: 230700,
  },
  {
    task: "ast_indexing",
    jobCount: 12,
    promptTokens: 120400,
    completionTokens: 24100,
    totalTokens: 144500,
  },
  {
    task: "conversation_reasoning",
    jobCount: 18,
    promptTokens: 68400,
    completionTokens: 32180,
    totalTokens: 100580,
  },
  {
    task: "evidence_verification",
    jobCount: 16,
    promptTokens: 28900,
    completionTokens: 11200,
    totalTokens: 40100,
  },
  {
    task: "symbol_resolution",
    jobCount: 8,
    promptTokens: 6200,
    completionTokens: 2100,
    totalTokens: 8300,
  },
];

export const INITIAL_PROJECT_USAGE: ProjectUsageBreakdown[] = [
  {
    projectId: "proj-devmind-core",
    projectName: "DevMind Core",
    totalTokens: 312400,
    jobCount: 46,
    lastActive: "10 minutes ago",
  },
  {
    projectId: "proj-api-gateway",
    projectName: "API Gateway Service",
    totalTokens: 142680,
    jobCount: 22,
    lastActive: "2 hours ago",
  },
  {
    projectId: "proj-web-client",
    projectName: "Web Next.js Client",
    totalTokens: 69100,
    jobCount: 10,
    lastActive: "1 day ago",
  },
];

export const INITIAL_EXTENSION_DEVICES: ExtensionDeviceItem[] = [
  {
    id: "dev-0192e4a1-b850-7111-9a4f-001122334455",
    name: "warish-workstation",
    platform: "linux-x64",
    extensionVersion: "v0.1.1",
    vscodeVersion: "1.95.0",
    lastSeenAt: "5 minutes ago",
    createdAt: "2026-10-15T10:00:00Z",
    isRevoked: false,
    status: "active",
  },
  {
    id: "dev-0192e4a1-c912-7222-8b5e-112233445566",
    name: "dev-laptop-mac",
    platform: "darwin-arm64",
    extensionVersion: "v0.1.1",
    vscodeVersion: "1.94.2",
    lastSeenAt: "2 hours ago",
    createdAt: "2026-10-16T14:30:00Z",
    isRevoked: false,
    status: "idle",
  },
  {
    id: "dev-0192e4a1-d703-7333-7c6d-223344556677",
    name: "legacy-desktop-win",
    platform: "win32-x64",
    extensionVersion: "v0.1.0",
    vscodeVersion: "1.93.1",
    lastSeenAt: "4 days ago",
    createdAt: "2026-10-10T09:15:00Z",
    isRevoked: true,
    revokedAt: "2026-10-17T11:20:00Z",
    status: "revoked",
  },
];
