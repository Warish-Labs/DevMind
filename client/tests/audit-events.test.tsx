import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { AuditLogViewer, AuditLogModal } from "../components/audit";
import { UsageDashboard } from "../components/usage";
import { ProjectSettingsClient } from "../components/settings/ProjectSettingsClient";

// Mock apiClient
vi.mock("../lib/api", () => ({
  apiClient: {
    getWorkspaceAuditEvents: vi.fn().mockResolvedValue([
      {
        id: "evt-001",
        workspace_id: "ws-123",
        actor_id: "user-456",
        actor_kind: "user",
        action: "project.sync_mode_updated",
        target_kind: "project",
        target_id: "proj-789",
        ip_hash: "hash_abc123",
        metadata: { previous_sync_mode: "indexed", new_sync_mode: "metadata_only" },
        created_at: "2026-10-19T06:00:00Z",
      },
      {
        id: "evt-002",
        workspace_id: "ws-123",
        actor_id: "user-456",
        actor_kind: "user",
        action: "consent.revoked",
        target_kind: "consent",
        target_id: "con-111",
        ip_hash: "hash_abc123",
        metadata: { scope: "cloud_index", purged_chunks: 142 },
        created_at: "2026-10-19T06:10:00Z",
      },
    ]),
    getProjectAuditEvents: vi.fn().mockResolvedValue([
      {
        id: "evt-003",
        workspace_id: "ws-123",
        actor_id: "user-456",
        actor_kind: "user",
        action: "project.data_purged",
        target_kind: "project",
        target_id: "proj-789",
        ip_hash: "hash_xyz789",
        metadata: { verification_hash: "sha256_mock_hash", scope: "all" },
        created_at: "2026-10-19T06:15:00Z",
      },
    ]),
  },
}));

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
    currentProject: { id: "proj-123", name: "DevMind Core", slug: "devmind-core" },
    workspaces: [{ id: "ws-123", name: "Warish Labs Core", slug: "warish-labs" }],
    projects: [{ id: "proj-123", name: "DevMind Core", slug: "devmind-core" }],
    syncMode: "indexed",
    setSyncMode: vi.fn(),
    setCurrentWorkspace: vi.fn(),
    setCurrentProject: vi.fn(),
  }),
}));

describe("Audit Event UI Components (M9-06, docs/03 §3.5 & §11.1, docs/07 §16)", () => {
  describe("AuditLogViewer", () => {
    it("renders loading skeleton and filter toolbar on initial render", () => {
      const html = renderToString(<AuditLogViewer workspaceId="ws-123" />);
      expect(html).toContain("Audit Event Log");
      expect(html).toContain("Immutable Log");
      expect(html).toContain("Filter Action:");
      expect(html).toContain("All Actions");
      expect(html).toContain("animate-pulse");
    });

    it("renders header with action options in select filter", () => {
      const html = renderToString(
        <AuditLogViewer
          projectId="proj-123"
          title="Project Security Audit"
          description="Detailed compliance events"
        />
      );
      expect(html).toContain("Project Security Audit");
      expect(html).toContain("Detailed compliance events");
      expect(html).toContain("Sync Mode Updated");
      expect(html).toContain("Data Purged");
      expect(html).toContain("Consent Revoked");
      expect(html).toContain("Retention Swept");
    });
  });

  describe("AuditLogModal", () => {
    it("renders modal dialog container when open", () => {
      const html = renderToString(
        <AuditLogModal
          isOpen={true}
          onClose={vi.fn()}
          workspaceId="ws-123"
          title="Workspace Compliance Events"
        />
      );
      expect(html).toContain("Workspace Compliance Events");
      expect(html).toContain("Immutable governance log recording");
      expect(html).toContain('role="dialog"');
    });

    it("does not render when closed", () => {
      const html = renderToString(
        <AuditLogModal isOpen={false} onClose={vi.fn()} workspaceId="ws-123" />
      );
      expect(html).toBe("");
    });
  });

  describe("UsageDashboard Audit Integration (Screen S-12)", () => {
    it("renders the Audit Events button in header bar", () => {
      const html = renderToString(<UsageDashboard workspaceId="ws-123" />);
      expect(html).toContain("Audit Events");
      expect(html).toContain("Usage Dashboard");
      expect(html).toContain("Warish Labs Core");
    });
  });

  describe("ProjectSettingsClient Audit Tab (Screen S-10)", () => {
    it("renders Audit Trail tab button among security & governance tabs", () => {
      const html = renderToString(<ProjectSettingsClient projectId="proj-123" />);
      expect(html).toContain("Audit Trail (docs/07 §16)");
      expect(html).toContain("Sync Modes &amp; Privacy");
      expect(html).toContain("Consent Records");
      expect(html).toContain("Retention Windows");
      expect(html).toContain("Danger Zone &amp; Deletion");
    });
  });
});
