import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import {
  PullRequestsTable,
  PullRequestsPageClient,
  PullRequestDetailClient,
  PRSummaryPanel,
  ChangeImpactGraph,
  ChecklistTriageTab,
  SAMPLE_PULL_REQUESTS,
  SAMPLE_PR_ANALYSIS,
  SAMPLE_CHECKLIST_FINDINGS,
  getPRStatusBadgeVariant,
  getRiskLevelBadgeVariant,
} from "../components/pull-requests";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/018f0a00-0000-7000-8000-000000000101/pull-requests",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

describe("M11-06: Pull Request Web Screens & Intelligence (Screen S-14)", () => {
  const projectId = "018f0a00-0000-7000-8000-000000000101";

  describe("PullRequestsTable", () => {
    it("renders table headers, PR numbers, titles, branches, and status badges", () => {
      const html = renderToString(
        <PullRequestsTable projectId={projectId} pullRequests={SAMPLE_PULL_REQUESTS} />
      );

      // Table headers
      expect(html).toContain("PR");
      expect(html).toContain("Title &amp; Branches");
      expect(html).toContain("Status");
      expect(html).toContain("Author");
      expect(html).toContain("Head Commit");
      expect(html).toContain("Updated");
      expect(html).toContain("Actions");

      // PR entries
      expect(html).toContain("87");
      expect(html).toContain("feat(server): implement M11-05 PRAgent change-impact analysis");
      expect(html).toContain("feature/m11-pr-agent");
      expect(html).toContain("MERGED");
      expect(html).toContain("devmind-bot");

      expect(html).toContain("88");
      expect(html).toContain("fix(auth): enforce strict tenant scoping on webhook event replay");
      expect(html).toContain("fix/webhook-tenant-scoping");
      expect(html).toContain("OPEN");
      expect(html).toContain("alice-engineer");

      // Action links
      expect(html).toContain("Inspect");
    });

    it("renders empty state when no pull requests exist", () => {
      const html = renderToString(<PullRequestsTable projectId={projectId} pullRequests={[]} />);

      expect(html).toContain("No pull requests found");
      expect(html).toContain("No pull requests match the current filters");
    });
  });

  describe("PullRequestsPageClient", () => {
    it("renders header, sync PRs button, filter tabs, and search bar", () => {
      const html = renderToString(<PullRequestsPageClient projectId={projectId} />);

      expect(html).toContain("Pull Requests &amp; Intelligence");
      expect(html).toContain("Screen S-14");
      expect(html).toContain("Sync PRs");
      expect(html).toContain("All");
      expect(html).toContain("Open");
      expect(html).toContain("Merged");
      expect(html).toContain("Closed");
      expect(html).toContain("Search by title, branch, #number...");
    });
  });

  describe("PRSummaryPanel", () => {
    it("renders executive summary, purpose, security verdict, testing concerns, and modules", () => {
      const html = renderToString(
        <PRSummaryPanel
          summary={SAMPLE_PR_ANALYSIS.summary}
          riskLevel={SAMPLE_PR_ANALYSIS.risk_level}
        />
      );

      expect(html).toContain("PRAgent Executive Summary");
      expect(html).toContain("HIGH");
      expect(html).toContain("Purpose &amp; Intent");
      expect(html).toContain("Enforces strict workspace tenant isolation");
      expect(html).toContain("Security Assessment");
      expect(html).toContain("E1 Verified");
      expect(html).toContain("High positive security impact");
      expect(html).toContain("Testing Concerns");
      expect(html).toContain("Affected Subsystems &amp; Modules");
      expect(html).toContain("Changed Files");
    });
  });

  describe("ChangeImpactGraph", () => {
    it("renders blast radius counts, graph filter controls, nodes, and relationships", () => {
      const html = renderToString(
        <ChangeImpactGraph
          impact={SAMPLE_PR_ANALYSIS.impact}
          riskLevel={SAMPLE_PR_ANALYSIS.risk_level}
        />
      );

      expect(html).toContain("Direct Symbols");
      expect(html).toContain("Impacted Modules");
      expect(html).toContain("API Routes");
      expect(html).toContain("Impacted Tests");
      expect(html).toContain("Change-Impact Blast Radius");
      expect(html).toContain("All Nodes");
      expect(html).toContain("Symbols");
      expect(html).toContain("Routes");
      expect(html).toContain("Tests");
      expect(html).toContain("verify_and_replay_delivery");
      expect(html).toContain("Graph Relationships");
    });
  });

  describe("ChecklistTriageTab", () => {
    it("renders review rules, severity badges, E1 verification badges, and remediation advice", () => {
      const html = renderToString(
        <ChecklistTriageTab findings={SAMPLE_CHECKLIST_FINDINGS} onTriageStatusChange={vi.fn()} />
      );

      expect(html).toContain("All Checks");
      expect(html).toContain("Auth &amp; Scoping");
      expect(html).toContain("Validation");
      expect(html).toContain("Errors");
      expect(html).toContain("Testing");

      expect(html).toContain("sec-tenant-context-enforcement");
      expect(html).toContain("HIGH");
      expect(html).toContain("Explicit AuthContext validation required on replay dispatcher");
      expect(html).toContain("Remediation Suggestion");
      expect(html).toContain("Pass `auth_ctx: AuthContext` directly");
      expect(html).toContain("Verify");
      expect(html).toContain("Dismiss");
    });
  });

  describe("PullRequestDetailClient", () => {
    it("renders detail navigation, commit hashes, trigger analysis button, and tabs", () => {
      const html = renderToString(<PullRequestDetailClient projectId={projectId} prId="pr-102" />);

      expect(html).toContain("Pull Requests");
      expect(html).toContain("88");
      expect(html).toContain("Trigger PRAgent");
      expect(html).toContain("View Diff");
      expect(html).toContain("Executive Overview");
      expect(html).toContain("Change-Impact Graph");
      expect(html).toContain("ReviewBuddy Findings");
    });
  });

  describe("Status and Risk badge variant helpers", () => {
    it("maps status and risk levels to appropriate UI variants", () => {
      expect(getPRStatusBadgeVariant("open")).toBe("signal");
      expect(getPRStatusBadgeVariant("merged")).toBe("ref");
      expect(getPRStatusBadgeVariant("closed")).toBe("neutral");

      expect(getRiskLevelBadgeVariant("critical")).toBe("danger");
      expect(getRiskLevelBadgeVariant("high")).toBe("warn");
      expect(getRiskLevelBadgeVariant("medium")).toBe("ref");
      expect(getRiskLevelBadgeVariant("low")).toBe("signal");
      expect(getRiskLevelBadgeVariant("unknown")).toBe("neutral");
    });
  });
});
