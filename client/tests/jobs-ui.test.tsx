import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { JobsTable } from "../components/jobs/JobsTable";
import { JobDetailView } from "../components/jobs/JobDetailView";
import { FloatingJobTray } from "../components/jobs/FloatingJobTray";
import { SAMPLE_JOBS_LIST, formatJobType, formatDuration } from "../components/jobs/types";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/018f0a00-0000-7000-8000-000000000101/jobs",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

describe("M8-06: Job Center UI & SSE Streaming (Screen S-09 per docs/08 §11)", () => {
  const projectId = "018f0a00-0000-7000-8000-000000000101";

  describe("JobsTable (Screen S-09 list)", () => {
    it("renders job table headers, status pills, and job rows", () => {
      const html = renderToString(
        <JobsTable projectId={projectId} jobs={SAMPLE_JOBS_LIST} onCancelJob={vi.fn()} />
      );

      // Status pills
      expect(html).toContain("All Jobs");
      expect(html).toContain("Running / Queued");
      expect(html).toContain("Awaiting Approval");
      expect(html).toContain("Succeeded");
      expect(html).toContain("Failed");

      // Filter controls
      expect(html).toContain("All Job Types");
      expect(html).toContain("Search job type, ID, or error code...");

      // Table headers
      expect(html).toContain("Job Type &amp; ID");
      expect(html).toContain("Status");
      expect(html).toContain("Progress");
      expect(html).toContain("Attempt");
      expect(html).toContain("Duration");
      expect(html).toContain("Actions");

      // Sample jobs
      expect(html).toContain("Security Review");
      expect(html).toContain("Code Review");
      expect(html).toContain("Embed Chunks");
      expect(html).toContain("Change Impact");

      // Actions
      expect(html).toContain("View");
      expect(html).toContain("Review");
      expect(html).toContain("Cancel");
    });

    it("displays empty state when no jobs match", () => {
      const html = renderToString(
        <JobsTable projectId={projectId} jobs={[]} onCancelJob={vi.fn()} />
      );

      expect(html).toContain("No background jobs found");
      expect(html).toContain(
        "No background jobs or agent workflows have been run for this project yet."
      );
    });

    it("renders mobile collapsed cards", () => {
      const html = renderToString(
        <JobsTable projectId={projectId} jobs={SAMPLE_JOBS_LIST} onCancelJob={vi.fn()} />
      );

      expect(html).toContain("md:hidden");
      expect(html).toContain("Security Review");
    });
  });

  describe("JobDetailView (Screen S-09 detail)", () => {
    it("renders live progress, queue, and milestone event stream log", () => {
      const runningJob = SAMPLE_JOBS_LIST[0]; // security_review, running

      const html = renderToString(
        <JobDetailView projectId={projectId} initialJob={runningJob} onCancelJob={vi.fn()} />
      );

      // Back navigation & Header
      expect(html).toContain("Back to job center");
      expect(html).toContain("Security Review");
      expect(html).toContain("RUNNING");
      expect(html).toContain("analysis");
      expect(html).toContain("Cancel Job");

      // Progress strip
      expect(html).toContain("Workflow Progress");
      expect(html).toContain("65%");

      // Milestone events log
      expect(html).toContain("Milestone Events Log");
      expect(html).toContain("#1");
      expect(html).toContain("Job dispatched to Celery worker: analysis-pool-01");
      expect(html).toContain("#2");
      expect(html).toContain("Resolved 42 files across Tier 1 AST and Tier 2 code relationships");
      expect(html).toContain("#3");
      expect(html).toContain("Evaluating auth and permission guards with AuthCheck workflow node");
    });

    it("displays human approval card when status is awaiting_approval", () => {
      const approvalJob = SAMPLE_JOBS_LIST[1]; // code_review, awaiting_approval

      const html = renderToString(
        <JobDetailView projectId={projectId} initialJob={approvalJob} onApproveJob={vi.fn()} />
      );

      expect(html).toContain("Human Approval Required (ADR-006 &amp; S-09)");
      expect(html).toContain("Apply Suggested Auth Middleware Fix");
      expect(html).toContain("CodeMate workflow paused before external side effect");
      expect(html).toContain("Declared Impact Scope:");
      expect(html).toContain("1 file, 3 insertions (+@declare_permission, require_permission)");
      expect(html).toContain("Approve and Proceed");
      expect(html).toContain("Reject &amp; Cancel");
    });

    it("displays error diagnostics card when job has failed", () => {
      const failedJob = SAMPLE_JOBS_LIST[3]; // change_impact, failed

      const html = renderToString(<JobDetailView projectId={projectId} initialJob={failedJob} />);

      expect(html).toContain("Execution Failure Diagnostics");
      expect(html).toContain("git.diff_timeout");
      expect(html).toContain("Base git tree commit reference");
      expect(html).toContain("not resolvable in remote repository.");
    });
  });

  describe("FloatingJobTray (Global floating tray per docs/08 §11 S-09)", () => {
    it("renders collapsed pill indicating active jobs", () => {
      const html = renderToString(
        <FloatingJobTray
          projectId={projectId}
          activeJobs={SAMPLE_JOBS_LIST}
          onCancelJob={vi.fn()}
        />
      );

      expect(html).toContain("Action Required · Approval Gate");
    });

    it("returns null when there are no active running jobs", () => {
      const completedJobs = SAMPLE_JOBS_LIST.filter(
        (j) => j.status === "succeeded" || j.status === "failed" || j.status === "cancelled"
      );

      const html = renderToString(
        <FloatingJobTray projectId={projectId} activeJobs={completedJobs} onCancelJob={vi.fn()} />
      );

      expect(html).toBe("");
    });
  });

  describe("Helper formatters", () => {
    it("formats job types and durations correctly", () => {
      expect(formatJobType("security_review")).toBe("Security Review");
      expect(formatJobType("ask_project")).toBe("Ask Project (Agent)");
      expect(formatJobType("embed_chunks")).toBe("Embed Chunks");

      const start = new Date("2026-10-18T10:00:00Z").toISOString();
      const end = new Date("2026-10-18T10:02:15Z").toISOString();
      expect(formatDuration(start, end)).toBe("2m 15s");
      expect(formatDuration(null, null)).toBe("Not started");
    });
  });
});
