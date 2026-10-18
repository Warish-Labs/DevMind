import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";

import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { Skeleton } from "../components/ui/Skeleton";
import { AppShell } from "../components/shell/AppShell";

// Route Loading Skeletons
import GlobalLoading from "../app/loading";
import ProjectsLoading from "../app/projects/loading";
import ProjectOverviewLoading from "../app/projects/[projectId]/loading";
import FindingsLoading from "../app/projects/[projectId]/findings/loading";
import FindingDetailLoading from "../app/projects/[projectId]/findings/[findingId]/loading";
import BrainLoading from "../app/projects/[projectId]/brain/loading";
import ChatLoading from "../app/projects/[projectId]/chat/loading";
import JobsLoading from "../app/projects/[projectId]/jobs/loading";
import UsageLoading from "../app/projects/[projectId]/usage/loading";
import WorkspacesLoading from "../app/workspaces/loading";

// Error boundaries
import RootError from "../app/error";
import GlobalError from "../app/global-error";
import ProjectsError from "../app/projects/error";
import ProjectScopedError from "../app/projects/[projectId]/error";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/proj_test_123",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

describe("M8-10 Accessibility, Empty, Error, and Loading State Polish", () => {
  describe("EmptyState Component (docs/08 §6 & §16)", () => {
    it("renders empty state with accessible region and semantic heading", () => {
      const html = renderToString(
        <EmptyState
          title="No projects found"
          description="Create your first project to begin analyzing your codebase mental model."
          action={{ label: "Create Project", onClick: () => {} }}
          docsUrl="https://github.com/Warish-Labs/DevMind"
        />
      );

      expect(html).toContain('role="region"');
      expect(html).toContain("No projects found</h3>");
      expect(html).toContain(
        "Create your first project to begin analyzing your codebase mental model."
      );
      expect(html).toContain("Create Project");
      expect(html).toContain("Docs ↗");
      expect(html).toContain("—"); // Non-illustrative glyph
    });

    it("renders href navigation buttons when href is provided", () => {
      const html = renderToString(
        <EmptyState
          title="No findings detected"
          description="All deterministic guards and AST rules are currently passing."
          action={{ label: "View Brain", href: "/projects/123/brain" }}
          secondaryAction={{ label: "Run Scan", href: "/projects/123/jobs" }}
        />
      );

      expect(html).toContain('href="/projects/123/brain"');
      expect(html).toContain('href="/projects/123/jobs"');
      expect(html).toContain("View Brain");
      expect(html).toContain("Run Scan");
    });
  });

  describe("ErrorState & Error Boundaries (docs/08 §15 & docs/03 §10.1 RFC 9457)", () => {
    it("renders ErrorState with role=alert, error code, cause, next action, and request_id", () => {
      const html = renderToString(
        <ErrorState
          title="Permission Denied"
          code="devmind.authz.permission_denied"
          message="You do not have write access to this project."
          cause="The requesting identity lacks the project:write role."
          nextStep="Request maintainer permission from the workspace owner."
          requestId="req_7f8a9b0c1d2e"
          retry={() => {}}
        />
      );

      expect(html).toContain('role="alert"');
      expect(html).toContain("Permission Denied");
      expect(html).toContain("devmind.authz.permission_denied");
      expect(html).toContain("You do not have write access to this project.");
      expect(html).toContain("cause: ");
      expect(html).toContain("action: ");
      expect(html).toContain("request_id: req_7f8a9b0c");
      expect(html).toContain("Retry request");
    });

    it("renders RootError and scoped error boundaries cleanly", () => {
      const mockError = Object.assign(new Error("Database connection timeout"), {
        digest: "req_digest_999",
      });
      const resetFn = vi.fn();

      const rootHtml = renderToString(<RootError error={mockError} reset={resetFn} />);
      expect(rootHtml).toContain('role="alert"');
      expect(rootHtml).toContain("devmind.client.runtime_error");
      expect(rootHtml).toContain("Database connection timeout");

      const projectsHtml = renderToString(<ProjectsError error={mockError} reset={resetFn} />);
      expect(projectsHtml).toContain("devmind.projects.load_error");

      const projectScopedHtml = renderToString(
        <ProjectScopedError error={mockError} reset={resetFn} />
      );
      expect(projectScopedHtml).toContain("devmind.project.scoped_error");

      const globalHtml = renderToString(<GlobalError error={mockError} reset={resetFn} />);
      expect(globalHtml).toContain("<html");
      expect(globalHtml).toContain("devmind.client.global_failure");
    });
  });

  describe("Loading Skeletons (docs/08 §6 Skeleton loaders)", () => {
    it("renders Skeleton primitive with aria-hidden and reduced-motion support", () => {
      const html = renderToString(<Skeleton className="w-32 h-6" />);
      expect(html).toContain('aria-hidden="true"');
      expect(html).toContain("animate-pulse");
      expect(html).toContain("motion-reduce:animate-none");
    });

    it("renders all route loading skeletons with role=status and accessible text", () => {
      const skeletons = [
        { name: "GlobalLoading", comp: <GlobalLoading />, label: "Loading page content" },
        { name: "ProjectsLoading", comp: <ProjectsLoading />, label: "Loading projects directory" },
        {
          name: "ProjectOverviewLoading",
          comp: <ProjectOverviewLoading />,
          label: "Loading project overview",
        },
        { name: "FindingsLoading", comp: <FindingsLoading />, label: "Loading security findings" },
        {
          name: "FindingDetailLoading",
          comp: <FindingDetailLoading />,
          label: "Loading finding details",
        },
        { name: "BrainLoading", comp: <BrainLoading />, label: "Loading project brain explorer" },
        { name: "ChatLoading", comp: <ChatLoading />, label: "Loading project conversation" },
        { name: "JobsLoading", comp: <JobsLoading />, label: "Loading job center" },
        { name: "UsageLoading", comp: <UsageLoading />, label: "Loading usage and quotas" },
        {
          name: "WorkspacesLoading",
          comp: <WorkspacesLoading />,
          label: "Loading workspaces directory",
        },
      ];

      for (const { name, comp, label } of skeletons) {
        const html = renderToString(comp);
        expect(html, `${name} should have role="status"`).toContain('role="status"');
        expect(html, `${name} should contain label "${label}"`).toContain(label);
        expect(html, `${name} should contain sr-only text`).toContain('class="sr-only"');
      }
    });
  });

  describe("AppShell Landmark Structure (WCAG 2.2 AA)", () => {
    it("renders AppShell without nested main landmark violation", () => {
      const html = renderToString(
        <AppShell>
          <div data-testid="test-content">Dashboard Content</div>
        </AppShell>
      );

      // Verify AppShell does NOT have a <main> tag (to avoid duplicate main landmark when layout.tsx already has <main id="main-content">)
      expect(html).not.toContain("<main");
      expect(html).toContain('id="app-main"');
      expect(html).toContain('role="region"');
      expect(html).toContain('aria-label="Application content"');
      expect(html).toContain("Dashboard Content");
    });
  });
});
