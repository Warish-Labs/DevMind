import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import {
  BugsTable,
  ErrorMatcherPanel,
  BugDetailModal,
  BugsPageClient,
  SAMPLE_BUGS,
  SAMPLE_BUG_DETAIL,
} from "../components/bugs";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/018f0a00-0000-7000-8000-000000000101/bugs",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

describe("M12-05: Bug Memory Web Screens & Incident Ledger (Screen S-15)", () => {
  const projectId = "018f0a00-0000-7000-8000-000000000101";

  describe("BugsTable", () => {
    it("renders table headers, titles, error signatures, occurrence badges, and actions", () => {
      const html = renderToString(
        <BugsTable bugs={SAMPLE_BUGS} onSelectBug={vi.fn()} onAddResolution={vi.fn()} />
      );

      // Table headers
      expect(html).toContain("Title &amp; Signature");
      expect(html).toContain("Module Hint");
      expect(html).toContain("Occurrences");
      expect(html).toContain("Resolutions");
      expect(html).toContain("Last Seen");
      expect(html).toContain("Actions");

      // Bug row 1
      expect(html).toContain("Project cross-tenant scoping lookup failure");
      expect(html).toContain("NotFoundError: Project not found in tenant scope");
      expect(html).toContain("app.persistence.repositories.project_repo");
      expect(html).toContain("7");
      expect(html).toContain("1 resolved");

      // Bug row 2
      expect(html).toContain("Attribute mismatch on Markdown extracted entities serialization");
      expect(html).toContain("app.analysis.doc_parser");

      // Action buttons
      expect(html).toContain("Inspect");
      expect(html).toContain("+ Resolution");
    });

    it("renders empty state when no bug records exist", () => {
      const html = renderToString(
        <BugsTable bugs={[]} onSelectBug={vi.fn()} onAddResolution={vi.fn()} />
      );

      expect(html).toContain("No bug memory records found");
      expect(html).toContain("Log Recurring Bug");
    });
  });

  describe("ErrorMatcherPanel", () => {
    it("renders error input textarea, module hint, search button, and sample trace loader", () => {
      const html = renderToString(
        <ErrorMatcherPanel projectId={projectId} onSelectCandidate={vi.fn()} />
      );

      expect(html).toContain("Interactive Error Matcher");
      expect(html).toContain("CAP-03");
      expect(html).toContain("Load Example Trace");
      expect(html).toContain("Raw Stack Trace or Error Message");
      expect(html).toContain("Optional Module Hint");
      expect(html).toContain("Search Memory");
    });
  });

  describe("BugDetailModal", () => {
    it("renders full bug record metadata, fingerprint, raw error, and historical resolutions", () => {
      const html = renderToString(
        <BugDetailModal
          bug={SAMPLE_BUG_DETAIL}
          isOpen={true}
          onClose={vi.fn()}
          onAddResolution={vi.fn()}
        />
      );

      expect(html).toContain("Project cross-tenant scoping lookup failure");
      expect(html).toContain("a9f8b4c2d1e03857192837465019283746501928374650192837465019283746");
      expect(html).toContain("Root Cause");
      expect(html).toContain("Fix Summary");
      expect(html).toContain("ProjectRepository.get_by_id expected single Project");
      expect(html).toContain("Resolution by");
      expect(html).toContain("system_admin");
      expect(html).toContain("+ Add Resolution");
    });

    it("does not render when isOpen is false", () => {
      const html = renderToString(
        <BugDetailModal
          bug={SAMPLE_BUG_DETAIL}
          isOpen={false}
          onClose={vi.fn()}
          onAddResolution={vi.fn()}
        />
      );

      expect(html).toBe("");
    });
  });

  describe("BugsPageClient", () => {
    it("renders header, CAP-03 badge, Log Recurring Bug button, and incident ledger", () => {
      const html = renderToString(<BugsPageClient projectId={projectId} />);

      expect(html).toContain("Bug Memory &amp; Historical Resolutions");
      expect(html).toContain("CAP-03 · Screen S-15");
      expect(html).toContain("Log Recurring Bug");
      expect(html).toContain("Project Incident Ledger");
      expect(html).toContain("Filter by signature or module...");
    });
  });
});
