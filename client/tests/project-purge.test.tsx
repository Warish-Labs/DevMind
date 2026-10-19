import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { ProjectPurgeManager } from "../components/settings/ProjectPurgeManager";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/proj-123/settings",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

// Mock AppContext
vi.mock("../context/AppContext", () => ({
  useApp: () => ({
    currentWorkspace: { id: "ws-123", name: "Warish Labs Core", slug: "warish-labs" },
    currentProject: {
      id: "proj-123",
      name: "DevMind Core",
      slug: "devmind-core",
      sync_mode: "indexed",
    },
    workspaces: [{ id: "ws-123", name: "Warish Labs Core", slug: "warish-labs" }],
    projects: [
      { id: "proj-123", name: "DevMind Core", slug: "devmind-core", sync_mode: "indexed" },
    ],
    syncMode: "indexed",
    setSyncMode: vi.fn(),
    setCurrentWorkspace: vi.fn(),
    setCurrentProject: vi.fn(),
  }),
}));

// Mock apiClient
vi.mock("../lib/api", () => ({
  apiClient: {
    purgeProjectData: vi.fn().mockResolvedValue({
      project_id: "proj-123",
      workspace_id: "ws-123",
      requested_by: "usr-admin",
      purged_at: "2026-10-19T05:00:00Z",
      scope: "all",
      stores: {
        postgres: {
          code_chunks: 142,
          chunk_embeddings: 142,
          evidence_snippets: 10,
          job_events: 25,
        },
        redis: {
          cache_keys_purged: 12,
        },
        checkpoints: {
          threads_purged: 4,
        },
      },
      verification_hash: "sha256:7f9a2e8c1b4d0e6f3a5c7b9e1d3f5a7b9c1d3e5f7a9b1c3d5e7f9a1b3c5d7e9f",
      sync_mode: "metadata_only",
      status: "completed",
    }),
  },
}));

describe("ProjectPurgeManager Component (Screen S-10, docs/11, M9-03)", () => {
  it("renders Danger Zone Purge Action card and irreversible warning", () => {
    const html = renderToString(<ProjectPurgeManager projectId="proj-123" />);

    expect(html).toContain("Purge Project Data Across Cloud Stores");
    expect(html).toContain("ADR-047");
    expect(html).toContain("Zero Residual Storage at Rest");
    expect(html).toContain("Initiate Project Data Purge...");
  });

  it("references metadata_only reset consequence in notice", () => {
    const html = renderToString(<ProjectPurgeManager projectId="proj-123" />);

    expect(html).toContain("metadata_only");
    expect(html).toContain("Project Maintainer or Admin permissions");
  });
});
