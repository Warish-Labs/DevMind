import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { FindingsTable } from "../components/findings/FindingsTable";
import { FindingDetail } from "../components/findings/FindingDetail";
import { FindingTriageModal } from "../components/findings/FindingTriageModal";
import { CodeExcerpt } from "../components/findings/CodeExcerpt";
import {
  SAMPLE_FINDINGS_LIST,
  SAMPLE_FINDING_DETAILS,
  SAMPLE_CODE_SNIPPETS,
} from "../components/findings/types";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/018f0a00-0000-7000-8000-000000000101/findings",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

describe("M8-05: Findings UI (Screens S-07 and S-08 per docs/08 §11)", () => {
  const projectId = "018f0a00-0000-7000-8000-000000000101";

  describe("Screen S-07: Dense Findings Table (FindingsTable)", () => {
    it("renders dense table headers, status pills, and sample finding rows", () => {
      const html = renderToString(
        <FindingsTable projectId={projectId} findings={SAMPLE_FINDINGS_LIST} isAnalyzed={true} />
      );

      // Status pills
      expect(html).toContain("All Findings");
      expect(html).toContain("Open / Acknowledged");
      expect(html).toContain("In Progress");
      expect(html).toContain("Resolved");
      expect(html).toContain("Dismissed / Triaged");
      expect(html).toContain("Stale (Changed Files)");

      // Filter controls
      expect(html).toContain("All Severities");
      expect(html).toContain("All Categories");
      expect(html).toContain("All Evidence");
      expect(html).toContain("Search rule, title, or file path...");

      // Table column headers
      expect(html).toContain("Severity");
      expect(html).toContain("Evid.");
      expect(html).toContain("Rule &amp; Finding");
      expect(html).toContain("Location");
      expect(html).toContain("Status");
      expect(html).toContain("Actions");

      // Finding items
      expect(html).toContain("SEC-AUTH-001");
      expect(html).toContain("Missing authorization check on administrative route");
      expect(html).toContain("server/app/api/admin.py#L42");
      expect(html).toContain("CRITICAL");
      expect(html).toContain("E2");

      // Row quick action buttons
      expect(html).toContain("Ack");
      expect(html).toContain("Progress");
      expect(html).toContain("Triage");
    });

    it("distinguishes empty states: no findings detected vs not analyzed yet", () => {
      // 1. Analyzed with 0 findings
      const analyzedHtml = renderToString(
        <FindingsTable projectId={projectId} findings={[]} isAnalyzed={true} />
      );
      expect(analyzedHtml).toContain("No security findings detected");
      expect(analyzedHtml).toContain(
        "All active rules and deterministic guards are passing across analyzed files."
      );

      // 2. Not analyzed yet
      const unanalyzedHtml = renderToString(
        <FindingsTable projectId={projectId} findings={[]} isAnalyzed={false} />
      );
      expect(unanalyzedHtml).toContain("Project not analyzed yet");
      expect(unanalyzedHtml).toContain(
        "Run your first repository scan or connect the DevMind companion in VS Code"
      );
    });

    it("renders responsive mobile two-line items", () => {
      const html = renderToString(
        <FindingsTable projectId={projectId} findings={SAMPLE_FINDINGS_LIST} isAnalyzed={true} />
      );

      // Mobile section container
      expect(html).toContain("md:hidden");
      // Finding title present in mobile list
      expect(html).toContain("Missing authorization check on administrative route");
      expect(html).toContain("Unhandled promise rejection in motion stream handler");
    });
  });

  describe("Finding Triage Modal (FindingTriageModal)", () => {
    const finding = SAMPLE_FINDINGS_LIST[0];

    it("renders triage modal options, reason code selector, and audit notice", () => {
      const html = renderToString(
        <FindingTriageModal
          isOpen={true}
          onClose={vi.fn()}
          finding={finding}
          hasMaintainerPermission={true}
          onConfirm={vi.fn()}
        />
      );

      expect(html).toContain("Triage Finding · SEC-AUTH-001");
      expect(html).toContain("Dismiss Finding");
      expect(html).toContain("Accept Risk");
      expect(html).toContain("Dismiss Reason Code");
      expect(html).toContain("False positive");
      expect(html).toContain("Not applicable");
      expect(html).toContain("Duplicate");
      expect(html).toContain("Audit notice:");
      expect(html).toContain("finding_status_history");
    });

    it("disables confirmation and displays warning when maintainer permission is absent", () => {
      const html = renderToString(
        <FindingTriageModal
          isOpen={true}
          onClose={vi.fn()}
          finding={finding}
          hasMaintainerPermission={false}
          onConfirm={vi.fn()}
        />
      );

      expect(html).toContain("Maintainer permission required to triage.");
      expect(html).toContain("disabled");
    });
  });

  describe("CodeExcerpt Component", () => {
    it("renders line numbers and highlights target lines", () => {
      const sampleSnippet = SAMPLE_CODE_SNIPPETS["server/app/api/admin.py"];
      const html = renderToString(
        <CodeExcerpt
          path="server/app/api/admin.py"
          code={sampleSnippet.code}
          startLine={sampleSnippet.startLine}
          highlightStart={42}
          highlightEnd={56}
        />
      );

      expect(html).toContain("server/app/api/admin.py");
      expect(html).toContain("lines 42-56");
      expect(html).toContain("Copy reference");
      expect(html).toContain("async def list_admin_users");
      // Highlight styling check
      expect(html).toContain("border-l-[var(--danger)]");
    });
  });

  describe("Screen S-08: Finding Detail View (FindingDetail)", () => {
    it("renders evidence-first hierarchy with strip, excerpt, why it matters, evidence, remediation, and history", () => {
      const findingDetail = SAMPLE_FINDING_DETAILS["018f0a00-0000-7000-8000-000000001001"];

      const html = renderToString(
        <FindingDetail
          projectId={projectId}
          finding={findingDetail}
          hasMaintainerPermission={true}
        />
      );

      // Back navigation & header
      expect(html).toContain("Back to findings list");
      expect(html).toContain("SEC-AUTH-001");
      expect(html).toContain("Missing authorization check on administrative route");

      // Actions
      expect(html).toContain("Acknowledge");
      expect(html).toContain("Start Progress");
      expect(html).toContain("Triage...");

      // Severity / Confidence / Evidence strip
      expect(html).toContain("Severity");
      expect(html).toContain("CRITICAL");
      expect(html).toContain("Evidence Level");
      expect(html).toContain("E2");
      expect(html).toContain("Deterministic");
      expect(html).toContain("Confidence");
      expect(html).toContain("high confidence");
      expect(html).toContain("Category");
      expect(html).toContain("authorization");

      // What and Where
      expect(html).toContain("What and Where");
      expect(html).toContain("Snapshot resolvable location");
      expect(html).toContain("server/app/api/admin.py");

      // Why It Matters
      expect(html).toContain("Why It Matters");
      expect(html).toContain(
        "handles user modification but does not depend on `require_permission(PERM_ADMIN_ACCESS)`"
      );

      // Machine-checkable evidence
      expect(html).toContain("Machine-Checkable Evidence");
      expect(html).toContain("structural check");
      expect(html).toContain("retrieved context");
      expect(html).toContain("sha256:4a8b79e19d67e6c1e34");
      expect(html).toContain("current");
      expect(html).toContain("ast_visitor_missing_guard");

      // Suggested remediation
      expect(html).toContain("Suggested Remediation");
      expect(html).toContain("Proposal only · Review and apply yourself (no auto-apply)");
      expect(html).toContain("Add require_permission dependency and AuthContext parameter");
      expect(html).toContain("Action Steps:");
      expect(html).toContain("Suggested Diff:");
      expect(html).toContain("+@declare_permission(PERM_ADMIN_ACCESS)");

      // Status history & audit trail
      expect(html).toContain("Status History &amp; Audit Trail");
      expect(html).toContain("detected");
      expect(html).toContain("open");
      expect(html).toContain("Initial AST static check detection during full scan");
    });

    it("displays stale warning banner and re-verify action when status is stale", () => {
      const staleFinding = SAMPLE_FINDING_DETAILS["018f0a00-0000-7000-8000-000000001006"];

      const html = renderToString(
        <FindingDetail
          projectId={projectId}
          finding={staleFinding}
          hasMaintainerPermission={true}
        />
      );

      expect(html).toContain("Stale Finding · Evidence file modified");
      expect(html).toContain("The underlying source code changed since this finding was produced");
      expect(html).toContain("Re-verify finding");
    });
  });
});
