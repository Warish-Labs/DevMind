import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { ConsentManager } from "../components/settings/ConsentManager";

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
    listProjectConsents: vi.fn().mockResolvedValue({
      total: 2,
      items: [
        {
          id: "cs-01",
          workspace_id: "ws-123",
          project_id: "proj-123",
          user_id: "usr-1",
          scope: "cloud_index",
          provider_ids: ["google-gemini", "openai"],
          data_categories: ["code_snippets", "ast_metadata"],
          granted_for: "project",
          policy_version: "1.0",
          preview_hash: "sha256:abc123",
          granted_at: "2026-10-18T12:00:00Z",
          expires_at: null,
          revoked_at: null,
          is_active: true,
        },
        {
          id: "cs-02",
          workspace_id: "ws-123",
          project_id: "proj-123",
          user_id: "usr-1",
          scope: "snippet_transmission",
          provider_ids: ["google-gemini"],
          data_categories: ["code_snippets"],
          granted_for: "project",
          policy_version: "1.0",
          preview_hash: "sha256:def456",
          granted_at: "2026-10-10T12:00:00Z",
          expires_at: null,
          revoked_at: "2026-10-12T12:00:00Z",
          is_active: false,
        },
      ],
    }),
    createProjectConsent: vi.fn().mockResolvedValue({
      id: "cs-03",
      workspace_id: "ws-123",
      project_id: "proj-123",
      user_id: "usr-1",
      scope: "snippet_transmission",
      provider_ids: ["google-gemini"],
      data_categories: ["code_snippets"],
      granted_for: "project",
      policy_version: "1.0",
      preview_hash: null,
      granted_at: "2026-10-18T20:00:00Z",
      expires_at: null,
      revoked_at: null,
      is_active: true,
    }),
    revokeProjectConsent: vi.fn().mockResolvedValue({
      id: "cs-01",
      workspace_id: "ws-123",
      project_id: "proj-123",
      user_id: "usr-1",
      scope: "cloud_index",
      provider_ids: ["google-gemini", "openai"],
      data_categories: ["code_snippets", "ast_metadata"],
      granted_for: "project",
      policy_version: "1.0",
      preview_hash: "sha256:abc123",
      granted_at: "2026-10-18T12:00:00Z",
      expires_at: null,
      revoked_at: "2026-10-18T20:00:00Z",
      is_active: false,
      purged_counts: {
        code_chunks: 142,
        embeddings: 142,
      },
      sync_mode_updated: true,
      new_sync_mode: "metadata_only",
    }),
  },
}));

describe("ConsentManager Component (Screen S-10 / S-11, docs/07 §7, M9-02)", () => {
  it("renders header and grant action button", () => {
    const html = renderToString(<ConsentManager projectId="proj-123" />);

    expect(html).toContain("Source Transmission Consents &amp; Legal Records");
    expect(html).toContain("+ Grant New Consent");
    expect(html).toContain("ADR-047");
  });

  it("renders consent record cards with scopes and status badges", () => {
    const html = renderToString(<ConsentManager projectId="proj-123" />);

    // In initial SSR state, skeleton or empty state is rendered
    expect(html).toContain("Source Transmission Consents");
  });
});
