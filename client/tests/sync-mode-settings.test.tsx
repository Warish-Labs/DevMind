import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { SyncModeManager } from "../components/settings/SyncModeManager";
import { ProjectSettingsClient } from "../components/settings/ProjectSettingsClient";

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
    updateProjectSyncMode: vi.fn().mockResolvedValue({
      project_id: "proj-123",
      previous_sync_mode: "indexed",
      new_sync_mode: "metadata_only",
      purged_counts: {
        code_chunks: 142,
        embeddings: 142,
      },
      retention_policy: {
        metadata_retention_days: 90,
        content_purged: true,
      },
      updated_at: "2026-10-18T20:00:00Z",
    }),
  },
}));

describe("Project Settings & Sync Mode Manager (Screen S-10, ADR-022, M9-01)", () => {
  describe("SyncModeManager Component", () => {
    it("renders both sync modes in comparison diptych (metadata_only vs indexed)", () => {
      const html = renderToString(
        <SyncModeManager projectId="proj-123" initialSyncMode="indexed" />
      );

      expect(html).toContain("Metadata-Only Mode");
      expect(html).toContain("Indexed Mode (Persistent Retrieval)");
      expect(html).toContain("Zero source code leaves your local workstation");
      expect(html).toContain("Consented, redacted code chunks are stored");
    });

    it("displays Active Mode badge on currently active synchronization mode", () => {
      const html = renderToString(
        <SyncModeManager projectId="proj-123" initialSyncMode="indexed" />
      );

      expect(html).toContain("ACTIVE MODE");
      expect(html).toContain("Currently Active");
      expect(html).toContain("Switch to Metadata-Only");
    });

    it("details consequence breakdown: purging chunks and embeddings warning", () => {
      const html = renderToString(
        <SyncModeManager projectId="proj-123" initialSyncMode="indexed" />
      );

      expect(html).toContain("Persistent code chunks and embeddings purged");
      expect(html).toContain("Reversible anytime with verifiable purge");
    });

    it("renders initial metadata-only active mode correctly", () => {
      const html = renderToString(
        <SyncModeManager projectId="proj-123" initialSyncMode="metadata_only" />
      );

      expect(html).toContain("Switch to Indexed Mode");
    });
  });

  describe("ProjectSettingsClient Component", () => {
    it("renders S-10 header, breadcrumb navigation, and tabs", () => {
      const html = renderToString(<ProjectSettingsClient projectId="proj-123" />);

      expect(html).toContain("Project Settings &amp; Privacy Controls");
      expect(html).toContain("S-10");
      expect(html).toContain("Sync Modes &amp; Privacy (ADR-022)");
      expect(html).toContain("Consent Records (docs/07 §7)");
      expect(html).toContain("Retention Windows (ADR-026)");
      expect(html).toContain("Danger Zone");
    });

    it("renders Return to Overview button linking back to /projects/proj-123", () => {
      const html = renderToString(<ProjectSettingsClient projectId="proj-123" />);

      expect(html).toContain('href="/projects/proj-123"');
      expect(html).toContain("Return to Overview");
    });
  });
});
