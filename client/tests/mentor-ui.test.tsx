import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import {
  MentorRecommendationSpotlight,
  TaskBacklogTable,
  TaskDAGViewer,
  HealthScorecardView,
  BlockersAndWarningsList,
  MentorPageClient,
  SAMPLE_TASKS,
  SAMPLE_RECOMMENDATION,
  SAMPLE_EVALUATION,
} from "../components/mentor";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/018f0a00-0000-7000-8000-000000000101/tasks",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

describe("M12-11: Project Mentor & Release Health Web Screens (Screen S-17)", () => {
  const projectId = "018f0a00-0000-7000-8000-000000000101";

  describe("MentorRecommendationSpotlight", () => {
    it("renders recommendation rank, readiness badge, title, and AI guidance narrative", () => {
      const html = renderToString(
        <MentorRecommendationSpotlight
          recommendation={SAMPLE_RECOMMENDATION}
          isLoading={false}
          onRefresh={vi.fn()}
          onUpdateStatus={vi.fn()}
          onSelectTask={vi.fn()}
        />
      );

      expect(html).toContain("ProjectMentor Recommendation");
      expect(html).toContain("Ready to Start");
      expect(html).toContain("CRITICAL");
      expect(html).toContain(
        "Enforce Workspace &amp; Project Tenant Scoping on Repository Queries"
      );
      expect(html).toContain("Strategic Mentor Guidance");
      expect(html).toContain(
        "Tackling tenant isolation guards first resolves high-severity security findings"
      );
      expect(html).toContain("Mark Completed");
      expect(html).toContain("View Details &amp; Dependencies");
    });

    it("renders empty state when backlog is clear", () => {
      const emptyRec = {
        recommended_task: null,
        rank: 0,
        score: 0,
        is_ready: false,
        downstream_impact_count: 0,
        reason: "Backlog is clear.",
        narrative: "All work items are completed or cancelled.",
        unblocked_count: 0,
        total_pending_tasks: 0,
      };

      const html = renderToString(
        <MentorRecommendationSpotlight
          recommendation={emptyRec}
          isLoading={false}
          onRefresh={vi.fn()}
          onUpdateStatus={vi.fn()}
          onSelectTask={vi.fn()}
        />
      );

      expect(html).toContain("Backlog is Clear");
      expect(html).toContain("All work items are completed or cancelled.");
    });
  });

  describe("TaskBacklogTable", () => {
    it("renders backlog tasks with titles, status chips, priority badges, and action buttons", () => {
      const html = renderToString(
        <TaskBacklogTable
          tasks={SAMPLE_TASKS}
          onSelectTask={vi.fn()}
          onUpdateStatus={vi.fn()}
          onDeleteTask={vi.fn()}
          onOpenLinkModal={vi.fn()}
        />
      );

      // Headers
      expect(html).toContain("Task");
      expect(html).toContain("Priority");
      expect(html).toContain("Status");
      expect(html).toContain("Prerequisites");
      expect(html).toContain("Impact");
      expect(html).toContain("Actions");

      // Task items
      expect(html).toContain("Implement Clerk User Authentication &amp; RBAC Guards");
      expect(html).toContain(
        "Enforce Workspace &amp; Project Tenant Scoping on Repository Queries"
      );
      expect(html).toContain("Fix Memory Leak in LangGraph Checkpointer Redis Adapter");

      // Actions
      expect(html).toContain("Link");
      expect(html).toContain("Delete");
    });
  });

  describe("TaskDAGViewer", () => {
    it("renders topological execution tiers, tier badges, and acyclic verification notice", () => {
      const html = renderToString(<TaskDAGViewer tasks={SAMPLE_TASKS} onSelectTask={vi.fn()} />);

      expect(html).toContain("Dependency Graph Topological Visualization");
      expect(html).toContain("Strictly Acyclic DAG (Verified)");
      expect(html).toContain("Unblocked &amp; Ready");
      expect(html).toContain("Downstream Dependent");
    });
  });

  describe("HealthScorecardView", () => {
    it("renders overall health score, release-readiness verdict badge, and 6 dimensions breakdown", () => {
      const html = renderToString(
        <HealthScorecardView
          evaluation={SAMPLE_EVALUATION}
          isLoading={false}
          onRunEvaluation={vi.fn()}
        />
      );

      expect(html).toContain("92"); // Rounded 91.5
      expect(html).toContain("READY WITH WARNINGS");
      expect(html).toContain("Project Health Scorecard");
      expect(html).toContain("HIGH"); // Functionality confidence

      // 6 Dimensions
      expect(html).toContain("Security &amp; Safety");
      expect(html).toContain("Code Quality &amp; Bugs");
      expect(html).toContain("Testing &amp; CI Readiness");
      expect(html).toContain("Documentation &amp; Living Sync");
      expect(html).toContain("Functionality &amp; Milestones (OQ-18)");
      expect(html).toContain("Architecture &amp; DAG Health");

      // Narrative
      expect(html).toContain("ProjectMentor Health Narrative");
      expect(html).toContain(
        "Project DevMind achieves an overall release readiness health score of 91.5"
      );
    });
  });

  describe("BlockersAndWarningsList", () => {
    it("renders release blockers status, active warnings, and positive health indicators", () => {
      const html = renderToString(<BlockersAndWarningsList evaluation={SAMPLE_EVALUATION} />);

      expect(html).toContain("Release Blockers");
      expect(html).toContain("Zero Release Blockers.");
      expect(html).toContain("Health Warnings &amp; Improvements");
      expect(html).toContain("Playwright E2E suite skipped in fast verification mode");
      expect(html).toContain("Positive Indicators &amp; Health Strengths");
      expect(html).toContain("Zero critical open security vulnerabilities detected");
      expect(html).toContain("Task dependency graph is strictly acyclic with 0 cycles");
    });
  });

  describe("MentorPageClient", () => {
    it("renders full page layout, quick metric stats, tab controls, and action buttons", () => {
      const html = renderToString(<MentorPageClient projectId={projectId} />);

      expect(html).toContain("Project Mentor &amp; Release Health");
      expect(html).toContain("Screen S-17");
      expect(html).toContain("Run Health Audit");
      expect(html).toContain("+ New Task");

      // Metric stat tiles
      expect(html).toContain("Ready to Execute");
      expect(html).toContain("Completed Backlog");
      expect(html).toContain("Health Score");
      expect(html).toContain("Release Blockers");

      // Tabs
      expect(html).toContain("Task Backlog");
      expect(html).toContain("Dependency DAG Flow");
      expect(html).toContain("Health Scorecard");
      expect(html).toContain("Blockers &amp; Warnings");
    });
  });
});
