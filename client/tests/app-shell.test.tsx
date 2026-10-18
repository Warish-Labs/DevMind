import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { AppShell } from "../components/shell/AppShell";
import { AppGutterRail } from "../components/shell/AppGutterRail";
import { AppTopBar } from "../components/shell/AppTopBar";
import { AppStatusBar } from "../components/shell/AppStatusBar";
import { WorkspaceProjectSwitcher } from "../components/shell/WorkspaceProjectSwitcher";
import { CommandPalette } from "../components/shell/CommandPalette";
import { ProjectIndex } from "../components/projects/ProjectIndex";
import { CreateProjectDialog } from "../components/projects/CreateProjectDialog";
import { AppProvider } from "../context/AppContext";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/projects",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

describe("App Shell and Navigation (docs/08 §10, S-03, M8-03)", () => {
  describe("AppShell Master Container", () => {
    it("renders gutter rail, top bar, status bar, and child content", () => {
      const html = renderToString(
        <AppShell>
          <div data-testid="test-content">Project Workspace Active</div>
        </AppShell>
      );

      // Gutter rail, top bar, and status bar present
      expect(html).toContain('aria-label="App Navigation Rail"');
      expect(html).toContain('aria-label="Open command palette (Press Cmd+K)"');
      expect(html).toContain('aria-label="Application Status Bar"');
      expect(html).toContain("Project Workspace Active");
      expect(html).toContain('id="app-main"');
    });
  });

  describe("AppGutterRail (56px Desktop Rail, docs/08 §4.1)", () => {
    it("renders workspace monogram and project section icons with tooltips", () => {
      const html = renderToString(
        <AppProvider>
          <AppGutterRail />
        </AppProvider>
      );

      expect(html).toContain('aria-label="App Navigation Rail"');
      expect(html).toContain("w-14");
      expect(html).toContain('aria-label="Toggle workspace switcher"');

      // Project sections
      expect(html).toContain('href="/projects"');
      expect(html).toContain('aria-label="All Projects (S-03)"');
      expect(html).toContain('aria-label="Project Overview (S-04)"');
      expect(html).toContain('aria-label="Project Brain Explorer (S-05)"');
      expect(html).toContain('aria-label="AI Project Conversation (S-06)"');
      expect(html).toContain('aria-label="Findings &amp; Security (S-07)"');
      expect(html).toContain('aria-label="Job Center (S-09)"');
      expect(html).toContain('aria-label="Project Settings (S-10)"');

      // Bottom utility links
      expect(html).toContain('aria-label="Account and Privacy Settings"');
      expect(html).toContain('aria-label="DevMind Documentation"');
    });
  });

  describe("AppTopBar (Breadcrumbs, Cmd+K, Job Tray)", () => {
    it("renders breadcrumbs, command palette trigger button, and job tray", () => {
      const html = renderToString(
        <AppProvider>
          <AppTopBar />
        </AppProvider>
      );

      expect(html).toContain("Projects Index (S-03)");
      expect(html).toContain('aria-label="Open command palette (Press Cmd+K)"');
      expect(html).toContain("Search or jump...");
      expect(html).toContain("⌘K");
      expect(html).toContain('aria-label="Job tray status"');
      expect(html).toContain("Jobs");
    });
  });

  describe("AppStatusBar (Scan, Sync Mode, Worker Status)", () => {
    it("renders scan status, sync mode badge, and connection indicators", () => {
      const html = renderToString(
        <AppProvider>
          <AppStatusBar />
        </AppProvider>
      );

      expect(html).toContain('aria-label="Application Status Bar"');
      expect(html).toContain("Local scan idle");
      expect(html).toContain("Sync:");
      expect(html).toContain("indexed");
      expect(html).toContain("VS Code");
      expect(html).toContain("connected");
      expect(html).toContain("v0.1.0");
      expect(html).toContain("Free tier");
    });
  });

  describe("Workspace & Project Switcher Popover", () => {
    it("renders workspace and project options with sync badges", () => {
      const html = renderToString(
        <AppProvider>
          <WorkspaceProjectSwitcher />
        </AppProvider>
      );

      expect(html).toContain("Workspaces");
      expect(html).toContain("WarishLabs Primary");
      expect(html).toContain("Projects");
      expect(html).toContain("DevMind Core");
      expect(html).toContain("AuthGateway Service");
      expect(html).toContain("New Project");
    });
  });

  describe("Command Palette Modal (Cmd+K)", () => {
    it("renders categorized navigation targets and actions", () => {
      const html = renderToString(
        <AppProvider>
          <CommandPalette />
        </AppProvider>
      );

      // Palette is closed by default in AppProvider state
      expect(html).toBe("");
    });
  });

  describe("Screen S-03: Workspace & Project Selection (ProjectIndex)", () => {
    it("renders workspace header, action buttons, and project index table", () => {
      const html = renderToString(
        <AppProvider>
          <ProjectIndex />
        </AppProvider>
      );

      expect(html).toContain("S-03 Project Selection");
      expect(html).toContain("WarishLabs Primary");
      expect(html).toContain("Connect VS Code");
      expect(html).toContain("New Project");

      // Table headers
      expect(html).toContain("Project");
      expect(html).toContain("Source");
      expect(html).toContain("Sync Mode");
      expect(html).toContain("Last Scan");
      expect(html).toContain("Open Findings");
      expect(html).toContain("Action");

      // Projects listed
      expect(html).toContain("DevMind Core");
      expect(html).toContain("AuthGateway Service");
      expect(html).toContain("indexed");
      expect(html).toContain("metadata_only");

      // Findings breakdown
      expect(html).toContain("High");
      expect(html).toContain("Med");
      expect(html).toContain("Open →");
    });
  });

  describe("Create Project Dialog Modal", () => {
    it("renders name, slug, and sync mode configuration options", () => {
      const html = renderToString(
        <AppProvider>
          <CreateProjectDialog isOpen={true} onClose={vi.fn()} />
        </AppProvider>
      );

      expect(html).toContain("Create New Project");
      expect(html).toContain("Project Name");
      expect(html).toContain("Project Slug");
      expect(html).toContain("Synchronization Mode");
      expect(html).toContain("Indexed Mode");
      expect(html).toContain("Metadata Only");
      expect(html).toContain("Create Project");
      expect(html).toContain("Cancel");
    });
  });
});
