import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { ProjectOverview } from "../components/overview/ProjectOverview";
import { CoverageHealthStrip } from "../components/overview/CoverageHealthStrip";
import { NextActionBand } from "../components/overview/NextActionBand";
import { FindingsPanel } from "../components/overview/FindingsPanel";
import { ActivityPanel } from "../components/overview/ActivityPanel";
import {
  SAMPLE_FINDINGS,
  SAMPLE_HEALTH_STATS,
  SAMPLE_SCANS,
  SAMPLE_JOBS,
  getHighestPriorityFinding,
} from "../components/overview/types";
import { AppProvider } from "../context/AppContext";
import type { FindingItem } from "@devmind/common/api";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/018f0a00-0000-7000-8000-000000000101",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

describe("Screen S-04: Project Overview (docs/08 §11 S-04, M8-04)", () => {
  describe("ProjectOverview Master Dashboard", () => {
    it("renders project header, five vision questions, and action triggers", () => {
      const html = renderToString(
        <AppProvider>
          <ProjectOverview projectId="018f0a00-0000-7000-8000-000000000101" />
        </AppProvider>
      );

      // S-04 Screen Header
      expect(html).toContain("S-04 Project Overview");
      expect(html).toContain("DevMind Core");
      expect(html).toContain("Scan AST");
      expect(html).toContain("Ask Project");

      // Answers the five questions
      expect(html).toContain("Question 1 · What Is Happening?");
      expect(html).toContain("Question 2 · What Is Broken?");
      expect(html).toContain("Question 3 · What Is Risky?");
      expect(html).toContain("Question 4 · What Should I Do Next?");
      expect(html).toContain("Question 5 · Is the Project Healthy?");
    });
  });

  describe("Question 5: CoverageHealthStrip", () => {
    it("renders security score, coverage numbers in mono, and unassessed categories", () => {
      const html = renderToString(<CoverageHealthStrip stats={SAMPLE_HEALTH_STATS} />);

      expect(html).toContain("Question 5 · Is the Project Healthy?");
      expect(html).toContain("Security Score");
      expect(html).toContain("88");
      expect(html).toContain("Grade B+");

      expect(html).toContain("Analysis Coverage");
      expect(html).toContain("94%");
      expect(html).toContain("42 of 45 files analyzed");

      // Unassessed categories per docs/08 §11 S-04
      expect(html).toContain("Reliability");
      expect(html).toContain("Performance");
      expect(html).toContain("Documentation");
      expect(html).toContain("Not assessed");
    });
  });

  describe("Question 4: NextActionBand (Deterministic Ordering)", () => {
    it("identifies highest-priority finding and labels it rule-based until 1.3", () => {
      const highest = getHighestPriorityFinding(SAMPLE_FINDINGS);
      expect(highest).not.toBeNull();
      expect(highest?.rule_id).toBe("SEC-AUTH-001");
      expect(highest?.severity).toBe("high");
      expect(highest?.evidence_level).toBe("E2");

      const html = renderToString(
        <NextActionBand projectId="018f0a00-0000-7000-8000-000000000101" finding={highest} />
      );

      expect(html).toContain("Question 4 · What Should I Do Next?");
      expect(html).toContain("Highest-priority finding to fix");
      expect(html).toContain("rule-based until Project Mentor ships (1.3)");
      expect(html).toContain("Missing authorization check on administrative route");
      expect(html).toContain("server/app/api/admin.py");
      expect(html).toContain("Review Finding");
    });

    it("renders clean state when no findings exist", () => {
      const html = renderToString(
        <NextActionBand projectId="018f0a00-0000-7000-8000-000000000101" finding={null} />
      );

      expect(html).toContain("No unresolved critical or high-severity findings");
      expect(html).toContain("Ask Project Brain →");
    });

    it("correctly orders findings by severity then evidence level", () => {
      const testFindings: FindingItem[] = [
        {
          id: "1",
          project_id: "p1",
          fingerprint: "fp1",
          rule_id: "R1",
          source: "scanner",
          category: "security",
          title: "Medium E2",
          summary: "test",
          severity: "medium",
          confidence: "high",
          evidence_level: "E2",
          status: "open",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
        {
          id: "2",
          project_id: "p1",
          fingerprint: "fp2",
          rule_id: "R2",
          source: "scanner",
          category: "security",
          title: "Critical E0",
          summary: "test",
          severity: "critical",
          confidence: "high",
          evidence_level: "E0",
          status: "open",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
        {
          id: "3",
          project_id: "p1",
          fingerprint: "fp3",
          rule_id: "R3",
          source: "scanner",
          category: "security",
          title: "High E1",
          summary: "test",
          severity: "high",
          confidence: "high",
          evidence_level: "E1",
          status: "open",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
        {
          id: "4",
          project_id: "p1",
          fingerprint: "fp4",
          rule_id: "R4",
          source: "scanner",
          category: "security",
          title: "High E2",
          summary: "test",
          severity: "high",
          confidence: "high",
          evidence_level: "E2",
          status: "open",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ];

      // Critical E0 beats High E2
      const top = getHighestPriorityFinding(testFindings);
      expect(top?.title).toBe("Critical E0");

      // High E2 beats High E1
      const withoutCritical = testFindings.filter((f) => f.severity !== "critical");
      const topHigh = getHighestPriorityFinding(withoutCritical);
      expect(topHigh?.title).toBe("High E2");
    });
  });

  describe("Questions 2 & 3: FindingsPanel", () => {
    it("renders open findings breakdown, Bug Memory status, and top risky findings", () => {
      const html = renderToString(
        <FindingsPanel
          projectId="018f0a00-0000-7000-8000-000000000101"
          findings={SAMPLE_FINDINGS}
        />
      );

      // Question 2
      expect(html).toContain("Question 2 · What Is Broken?");
      expect(html).toContain("Critical");
      expect(html).toContain("High");
      expect(html).toContain("Medium");
      expect(html).toContain("Low");
      expect(html).toContain("Bug Memory: 0 known regressions");
      expect(html).toContain("ships in 1.2");

      // Question 3
      expect(html).toContain("Question 3 · What Is Risky?");
      expect(html).toContain("Missing authorization check on administrative route");
      expect(html).toContain("E2");
      expect(html).toContain("Unhandled promise rejection in motion stream handler");
      expect(html).toContain("E1");
    });

    it("renders loading skeleton and error retry states independently", () => {
      const loadingHtml = renderToString(
        <FindingsPanel projectId="p1" findings={[]} isLoading={true} />
      );
      expect(loadingHtml).toContain("animate-pulse");

      const errorHtml = renderToString(
        <FindingsPanel
          projectId="p1"
          findings={[]}
          error="Failed to connect to findings store"
          onRetry={vi.fn()}
        />
      );
      expect(errorHtml).toContain("Failed to load findings");
      expect(errorHtml).toContain("Failed to connect to findings store");
      expect(errorHtml).toContain("Retry Findings");
    });
  });

  describe("Question 1: ActivityPanel", () => {
    it("renders recent scans, sync mode status, and background jobs", () => {
      const html = renderToString(
        <ActivityPanel
          projectId="018f0a00-0000-7000-8000-000000000101"
          syncMode="indexed"
          scans={SAMPLE_SCANS}
          jobs={SAMPLE_JOBS}
          lastSyncAt={SAMPLE_SCANS[0].createdAt}
        />
      );

      expect(html).toContain("Question 1 · What Is Happening?");
      expect(html).toContain("Synchronization Mode");
      expect(html).toContain("indexed");
      expect(html).toContain("VS Code Active");

      // Scans
      expect(html).toContain("Full Scan");
      expect(html).toContain("Incremental Scan");
      expect(html).toContain("42 files");

      // Jobs
      expect(html).toContain("manifest sync");
      expect(html).toContain("graph build");
      expect(html).toContain("embedding sync");
      expect(html).toContain("Job Center (S-09)");
    });

    it("renders loading skeleton and error retry states independently", () => {
      const loadingHtml = renderToString(
        <ActivityPanel projectId="p1" syncMode="indexed" scans={[]} jobs={[]} isLoading={true} />
      );
      expect(loadingHtml).toContain("animate-pulse");

      const errorHtml = renderToString(
        <ActivityPanel
          projectId="p1"
          syncMode="indexed"
          scans={[]}
          jobs={[]}
          error="Scan service unavailable"
          onRetry={vi.fn()}
        />
      );
      expect(errorHtml).toContain("Failed to load activity and scans");
      expect(errorHtml).toContain("Scan service unavailable");
      expect(errorHtml).toContain("Retry Activity");
    });
  });
});
