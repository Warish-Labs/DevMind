import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { BrainHeader } from "../components/brain/BrainHeader";
import { FileTreePane } from "../components/brain/FileTreePane";
import { CodeSymbolPane } from "../components/brain/CodeSymbolPane";
import { RelationshipsPane } from "../components/brain/RelationshipsPane";
import { BrainExplorer } from "../components/brain/BrainExplorer";
import {
  SAMPLE_SNAPSHOTS,
  SAMPLE_FILE_TREE,
  SAMPLE_FILE_CONTENTS,
} from "../components/brain/types";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/018f0a00-0000-7000-8000-000000000101/brain",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

describe("M8-08: Project Brain Explorer (Screen S-05 per docs/08 §11)", () => {
  const projectId = "018f0a00-0000-7000-8000-000000000101";

  describe("BrainHeader component", () => {
    it("renders project title, S-05 badge, snapshot selector with current/stale flags, and search bar", () => {
      const html = renderToString(
        <BrainHeader
          projectId={projectId}
          snapshots={SAMPLE_SNAPSHOTS}
          selectedSnapshotId="snap-001"
          onSelectSnapshot={vi.fn()}
          projectMode="indexed"
          searchQuery=""
          onSearchChange={vi.fn()}
        />
      );

      expect(html).toContain("Project Brain Explorer");
      expect(html).toContain("Screen S-05");
      expect(html).toContain("Indexed Mode (AST Verified)");
      expect(html).toContain("Search symbols or files");
      expect(html).toContain("snapshot-20261018-090000 (current)");
    });

    it("renders metadata-only mode badge and Enable Indexed Mode action button", () => {
      const html = renderToString(
        <BrainHeader
          projectId={projectId}
          snapshots={SAMPLE_SNAPSHOTS}
          selectedSnapshotId="snap-001"
          onSelectSnapshot={vi.fn()}
          projectMode="metadata_only"
          searchQuery=""
          onSearchChange={vi.fn()}
        />
      );

      expect(html).toContain("Metadata-Only Mode");
      expect(html).toContain("Enable Indexed Mode");
    });
  });

  describe("FileTreePane component", () => {
    it("renders directory structure, file leaves, language tier badges, and findings count", () => {
      const html = renderToString(
        <FileTreePane
          tree={SAMPLE_FILE_TREE}
          selectedFilePath="server/app/domain/auth/permissions.py"
          onSelectFile={vi.fn()}
        />
      );

      expect(html).toContain("Repository Files");
      expect(html).toContain("permissions.py");
      expect(html).toContain("findings.py");
      expect(html).toContain("tier1");
      expect(html).toContain("!1");
    });
  });

  describe("CodeSymbolPane component", () => {
    it("renders file header, line numbers, and source code in indexed mode", () => {
      const file = SAMPLE_FILE_CONTENTS["server/app/domain/auth/permissions.py"];
      const html = renderToString(
        <CodeSymbolPane
          projectId={projectId}
          fileContent={file}
          projectMode="indexed"
          selectedSymbolId={null}
          onSelectSymbol={vi.fn()}
        />
      );

      expect(html).toContain("server/app/domain/auth/permissions.py");
      expect(html).toContain("85 lines");
      expect(html).toContain("TIER1");
      expect(html).toContain("def require_permission");
      expect(html).toContain("def declare_permission");
    });

    it("renders Metadata-Only banner and redacted source text notice when projectMode is metadata_only", () => {
      const file = SAMPLE_FILE_CONTENTS["server/app/domain/auth/permissions.py"];
      const html = renderToString(
        <CodeSymbolPane
          projectId={projectId}
          fileContent={file}
          projectMode="metadata_only"
          selectedSymbolId={null}
          onSelectSymbol={vi.fn()}
        />
      );

      expect(html).toContain("Metadata-Only Mode: Source Text Redacted");
      expect(html).toContain("This project is configured in metadata-only mode (ADR-034)");
      expect(html).toContain("Enable Indexed Mode with Consent");
      expect(html).toContain("Extracted AST Symbols (2)");
      expect(html).toContain("require_permission");
      expect(html).toContain("declare_permission");
    });
  });

  describe("RelationshipsPane component", () => {
    it("renders relationships tab with outgoing and incoming edges", () => {
      const file = SAMPLE_FILE_CONTENTS["server/app/domain/auth/permissions.py"];
      const html = renderToString(
        <RelationshipsPane
          projectId={projectId}
          relationships={file.relationships}
          findings={file.findings}
        />
      );

      expect(html).toContain("Relationships");
      expect(html).toContain("calls");
      expect(html).toContain("AuthContext.has_permission");
      expect(html).toContain("transition_finding_status");
      expect(html).toContain("ForbiddenError");
    });

    it("renders findings with severity chip, evidence level, and view link", () => {
      const file = SAMPLE_FILE_CONTENTS["server/app/api/findings.py"];
      const html = renderToString(
        <RelationshipsPane
          projectId={projectId}
          relationships={file.relationships}
          findings={file.findings}
        />
      );

      expect(html).toContain("Findings");
      expect(html).toContain("1");
    });
  });

  describe("BrainExplorer integration component (Screen S-05)", () => {
    it("renders full 3-pane layout with tree, code viewer, and relationships panel", () => {
      const html = renderToString(
        <BrainExplorer
          projectId={projectId}
          initialMode="indexed"
          initialFilePath="server/app/domain/auth/permissions.py"
        />
      );

      // Header
      expect(html).toContain("Project Brain Explorer");
      expect(html).toContain("Screen S-05");

      // Left pane
      expect(html).toContain("Repository Files");
      expect(html).toContain("permissions.py");

      // Center pane
      expect(html).toContain("server/app/domain/auth/permissions.py");
      expect(html).toContain("def require_permission");

      // Right pane
      expect(html).toContain("Relationships");
      expect(html).toContain("AuthContext.has_permission");
    });
  });
});
