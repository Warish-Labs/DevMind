import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import {
  DriftItemsTable,
  TrackedDocsTable,
  PatchApprovalModal,
  LivingDocsPageClient,
  SAMPLE_DOCS,
  SAMPLE_DRIFT_ITEMS,
} from "../components/living-docs";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/018f0a00-0000-7000-8000-000000000101/docs",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

describe("M12-05: Living Documentation & DocsAlive Drift Web Screens (Screen S-16)", () => {
  const projectId = "018f0a00-0000-7000-8000-000000000101";

  describe("DriftItemsTable", () => {
    it("renders table headers, target routes, drift kinds, status badges, and action buttons", () => {
      const html = renderToString(
        <DriftItemsTable items={SAMPLE_DRIFT_ITEMS} onReviewProposal={vi.fn()} />
      );

      // Headers
      expect(html).toContain("Discrepancy &amp; Target");
      expect(html).toContain("Kind");
      expect(html).toContain("Status");
      expect(html).toContain("Gate");
      expect(html).toContain("Detected");
      expect(html).toContain("Actions");

      // Drift item 1
      expect(html).toContain("POST /api/v1/projects/{project_id}/bugs/match");
      expect(html).toContain("UNDOCUMENTED ROUTE");
      expect(html).toContain("DETECTED");
      expect(html).toContain("HUMAN GATE");

      // Drift item 2
      expect(html).toContain("DELETE /api/v1/projects/{project_id}/docs/all");
      expect(html).toContain("REMOVED ROUTE");
      expect(html).toContain("APPROVED");

      // Action button
      expect(html).toContain("Review Proposal");
    });

    it("renders empty state when no drift items exist", () => {
      const html = renderToString(<DriftItemsTable items={[]} onReviewProposal={vi.fn()} />);

      expect(html).toContain("No documentation drift detected");
    });
  });

  describe("TrackedDocsTable", () => {
    it("renders documentation records, titles, paths, kinds, content hashes, and inspect buttons", () => {
      const html = renderToString(<TrackedDocsTable docs={SAMPLE_DOCS} onInspectDoc={vi.fn()} />);

      expect(html).toContain("Path &amp; Title");
      expect(html).toContain("Kind");
      expect(html).toContain("Content Hash");
      expect(html).toContain("Status");
      expect(html).toContain("Last Parsed");

      expect(html).toContain("Data Model &amp; API Specification");
      expect(html).toContain("docs/03-data-model-and-api.md");
      expect(html).toContain("API");
      expect(html).toContain("TRACKED");

      expect(html).toContain("Project Readme");
      expect(html).toContain("README.md");

      expect(html).toContain("Inspect");
    });
  });

  describe("PatchApprovalModal", () => {
    it("renders unified diff inspection viewer, proposal summary, confidence score, and approval gates", () => {
      const html = renderToString(
        <PatchApprovalModal
          driftItem={SAMPLE_DRIFT_ITEMS[0]}
          docPath="docs/03-data-model-and-api.md"
          isOpen={true}
          onClose={vi.fn()}
          onStatusChange={vi.fn()}
        />
      );

      expect(html).toContain("DocsAlive Patch Proposal &amp; Human Gate (CAP-04)");
      expect(html).toContain("docs/03-data-model-and-api.md");
      expect(html).toContain("DETECTED");
      expect(html).toContain("UNDOCUMENTED ROUTE");
      expect(html).toContain("Proposed Unified Diff");
      expect(html).toContain("Confidence:");
      expect(html).toContain("95");
      expect(html).toContain("Human Approval Gate Required");
      expect(html).toContain("Approve Proposal");
      expect(html).toContain("Reject Proposal");
    });

    it("renders apply button when drift proposal is already approved", () => {
      const html = renderToString(
        <PatchApprovalModal
          driftItem={SAMPLE_DRIFT_ITEMS[1]}
          docPath="docs/03-data-model-and-api.md"
          isOpen={true}
          onClose={vi.fn()}
          onStatusChange={vi.fn()}
        />
      );

      expect(html).toContain("Approval Gate Cleared");
      expect(html).toContain("lead_architect");
      expect(html).toContain("Apply Patch to Documentation");
    });

    it("does not render when isOpen is false", () => {
      const html = renderToString(
        <PatchApprovalModal
          driftItem={SAMPLE_DRIFT_ITEMS[0]}
          isOpen={false}
          onClose={vi.fn()}
          onStatusChange={vi.fn()}
        />
      );

      expect(html).toBe("");
    });
  });

  describe("LivingDocsPageClient", () => {
    it("renders page header, CAP-04 badge, tabs, Detect Drift Now, and Register Document buttons", () => {
      const html = renderToString(<LivingDocsPageClient projectId={projectId} />);

      expect(html).toContain("Living Documentation &amp; DocsAlive Drift");
      expect(html).toContain("CAP-04 · Screen S-16");
      expect(html).toContain("Detect Drift Now");
      expect(html).toContain("Register Document");
      expect(html).toContain("Drift Review &amp; Patch Proposals");
      expect(html).toContain("Tracked Documentation Files");
    });
  });
});
