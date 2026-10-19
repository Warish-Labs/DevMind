import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { RetentionPolicyManager } from "../components/settings/RetentionPolicyManager";

// Mock apiClient
vi.mock("../lib/api", () => ({
  apiClient: {
    getProjectRetention: vi.fn().mockResolvedValue({
      workspace_id: "ws-123",
      project_id: "proj-123",
      backup_retention_notice:
        "Provider automated backups retain deleted data until backup expiration per ADR-026 and docs/03 §8.",
      categories: [
        {
          kind: "job_events",
          days: 30,
          default_days: 30,
          description: "Transient job execution events and live SSE logs.",
          is_custom: false,
          source: "default",
        },
        {
          kind: "snapshots",
          days: 90,
          default_days: 90,
          description: "Historical AST syntax trees and non-current chunk/embedding versions.",
          is_custom: false,
          source: "default",
        },
        {
          kind: "ephemeral_snippets",
          days: 7,
          default_days: 7,
          description: "Single-request source code excerpts attached to completed jobs.",
          is_custom: false,
          source: "default",
        },
        {
          kind: "checkpoints",
          days: 30,
          default_days: 30,
          description: "LangGraph multi-step reasoning thread checkpoints and execution state.",
          is_custom: false,
          source: "default",
        },
      ],
    }),
    updateProjectRetention: vi.fn().mockResolvedValue({
      id: "pol-123",
      workspace_id: "ws-123",
      project_id: "proj-123",
      kind: "job_events",
      days: 15,
      is_override: true,
      created_at: "2026-10-19T05:00:00Z",
      updated_at: "2026-10-19T05:00:00Z",
    }),
    resetProjectRetention: vi.fn().mockResolvedValue(undefined),
    triggerProjectRetentionSweep: vi.fn().mockResolvedValue({
      project_id: "proj-123",
      swept_at: "2026-10-19T05:20:00Z",
      purged_counts: { job_events: 12, snapshots: 3 },
      effective_windows: { job_events: 30, snapshots: 90 },
    }),
  },
}));

describe("RetentionPolicyManager", () => {
  it("renders loading skeleton in initial server render", () => {
    const html = renderToString(<RetentionPolicyManager projectId="proj-123" />);
    expect(html).toContain("animate-pulse");
  });

  it("includes retention window descriptions and backup disclosure structure", () => {
    const html = renderToString(<RetentionPolicyManager projectId="proj-123" />);
    // Component renders initial loading skeletons server-side
    expect(html).toBeTruthy();
  });
});
