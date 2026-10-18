import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import {
  QuotaOverview,
  UsageBreakdownPane,
  ExtensionDevicesPane,
  UsageDashboard,
  INITIAL_QUOTAS,
  INITIAL_TASK_USAGE,
  INITIAL_PROJECT_USAGE,
  INITIAL_EXTENSION_DEVICES,
} from "../components/usage";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/proj-123/usage",
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

describe("Workspace Usage Dashboard & Extension Devices (Screen S-12, docs/08 §11, M8-09)", () => {
  describe("QuotaOverview Component", () => {
    it("renders summary statistics cards and ADR-046 Free Profile badge", () => {
      const html = renderToString(
        <QuotaOverview
          quotas={INITIAL_QUOTAS}
          totalTokens={524180}
          totalJobs={42}
          activeDevicesCount={2}
        />
      );

      expect(html).toContain("Inference Metering");
      expect(html).toContain("524,180");
      expect(html).toContain("42");
      expect(html).toContain("Jobs");
      expect(html).toContain("Connected");
      expect(html).toContain("ADR-046");
      expect(html).toContain("Free Operational Tier");
    });

    it("renders progress bars with accessible ARIA values and threshold indicators", () => {
      const html = renderToString(
        <QuotaOverview
          quotas={INITIAL_QUOTAS}
          totalTokens={524180}
          totalJobs={42}
          activeDevicesCount={2}
        />
      );

      expect(html).toContain('role="progressbar"');
      expect(html).toContain('aria-valuenow="524180"');
      expect(html).toContain('aria-valuemax="1000000"');
      expect(html).toContain("84.2%");
      expect(html).toContain("52.4%");
    });
  });

  describe("UsageBreakdownPane Component", () => {
    it("renders agent task usage table with token accounting totals", () => {
      const html = renderToString(
        <UsageBreakdownPane
          tasks={INITIAL_TASK_USAGE}
          projects={INITIAL_PROJECT_USAGE}
          totalTokens={524180}
        />
      );

      expect(html).toContain("Token Consumption Accounting");
      expect(html).toContain('data-testid="task-usage-table"');
      expect(html).toContain("security_scan");
      expect(html).toContain("ast_indexing");
      expect(html).toContain("conversation_reasoning");
      expect(html).toContain("230,700");

      // Check disclosure presence
      expect(html).toContain("Privacy Disclosure:");
      expect(html).toContain("ADR-047");
      expect(html).toContain("docs/07 §15");
    });

    it("renders project accounting rows and tabular columns", () => {
      const html = renderToString(
        <UsageBreakdownPane
          tasks={INITIAL_TASK_USAGE}
          projects={INITIAL_PROJECT_USAGE}
          totalTokens={524180}
        />
      );

      // Verify tabs exist
      expect(html).toContain("By Agent Task");
      expect(html).toContain("By Project");
    });
  });

  describe("ExtensionDevicesPane Component", () => {
    it("renders registered extension devices list and platform badges", () => {
      const html = renderToString(<ExtensionDevicesPane devices={INITIAL_EXTENSION_DEVICES} />);

      expect(html).toContain("Authorized Extension Devices");
      expect(html).toContain('data-testid="extension-devices-table"');
      expect(html).toContain("warish-workstation");
      expect(html).toContain("dev-laptop-mac");
      expect(html).toContain("legacy-desktop-win");
      expect(html).toContain("Linux");
      expect(html).toContain("macOS");
      expect(html).toContain("ACTIVE");
      expect(html).toContain("REVOKED");
    });

    it("renders revocation actions and connect device controls", () => {
      const html = renderToString(<ExtensionDevicesPane devices={INITIAL_EXTENSION_DEVICES} />);

      expect(html).toContain("Revoke");
      expect(html).toContain("+ Connect Device");
      expect(html).toContain("ADR-012");
    });
  });

  describe("UsageDashboard Master Component", () => {
    it("renders breadcrumbs, period header, quota limits, token tables, and devices", () => {
      const html = renderToString(
        <UsageDashboard
          workspaceId="ws-test"
          projectId="proj-test"
          workspaceName="Test Workspace"
        />
      );

      expect(html).toContain("Test Workspace");
      expect(html).toContain("Usage Dashboard");
      expect(html).toContain("S-12 Usage &amp; Quotas");
      expect(html).toContain("October 2026");
      expect(html).toContain("Audit Events");
      expect(html).toContain("Workspace Quota Limits");
      expect(html).toContain("Token Consumption Accounting");
      expect(html).toContain("Authorized Extension Devices");
    });
  });
});
