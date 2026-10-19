import React from "react";
import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { SnapshotHistoryModal } from "../components/brain/SnapshotHistoryModal";
import { BrainHeader } from "../components/brain/BrainHeader";
import { SAMPLE_SNAPSHOTS } from "../components/brain/types";
import type { SnapshotItem, SnapshotDiffResponse } from "@devmind/common/api";

const { mockSnapshots, mockDiff } = vi.hoisted(() => {
  const mockSnapshots: SnapshotItem[] = [
    {
      id: "snap-001",
      project_id: "018f0a00-0000-7000-8000-000000000101",
      kind: "scan",
      ref: "scan_run_01",
      label: "v1.0 baseline",
      created_at: "2026-10-18T09:00:00Z",
      file_count: 248,
    },
    {
      id: "snap-002",
      project_id: "018f0a00-0000-7000-8000-000000000101",
      kind: "commit",
      ref: "1c02bbd",
      label: "M9 retention commit",
      created_at: "2026-10-17T18:30:00Z",
      file_count: 242,
    },
    {
      id: "snap-003",
      project_id: "018f0a00-0000-7000-8000-000000000101",
      kind: "manual",
      ref: "manual-backup",
      label: "Pre-refactor checkpoint",
      created_at: "2026-10-16T12:00:00Z",
      file_count: 235,
    },
  ];

  const mockDiff: SnapshotDiffResponse = {
    base_snapshot_id: "snap-002",
    target_snapshot_id: "snap-001",
    added: 6,
    removed: 1,
    modified: 4,
    unchanged: 231,
    differences: [
      {
        path: "server/app/domain/retention/service.py",
        status: "added",
        base_version_id: null,
        base_content_hash: null,
        target_version_id: "ver-1",
        target_content_hash: "a1b2c3d4e5f67890",
      },
      {
        path: "server/app/domain/deprecated/old.py",
        status: "removed",
        base_version_id: "ver-0",
        base_content_hash: "f6e5d4c3b2a10987",
        target_version_id: null,
        target_content_hash: null,
      },
      {
        path: "common/src/api/index.ts",
        status: "modified",
        base_version_id: "ver-old",
        base_content_hash: "1122334455667788",
        target_version_id: "ver-new",
        target_content_hash: "9988776655443322",
      },
      {
        path: "server/app/core/settings.py",
        status: "unchanged",
        base_version_id: "ver-same",
        base_content_hash: "abcdef1234567890",
        target_version_id: "ver-same",
        target_content_hash: "abcdef1234567890",
      },
    ],
  };

  return { mockSnapshots, mockDiff };
});

// Mock apiClient
vi.mock("../lib/api", () => ({
  apiClient: {
    listSnapshots: vi.fn().mockResolvedValue(mockSnapshots),
    compareSnapshots: vi.fn().mockResolvedValue(mockDiff),
    createSnapshot: vi.fn().mockImplementation((_pid, req) =>
      Promise.resolve({
        id: "snap-new",
        project_id: "018f0a00-0000-7000-8000-000000000101",
        kind: req.kind || "manual",
        ref: req.ref || "manual-ref",
        label: req.label || "New Checkpoint",
        created_at: new Date().toISOString(),
        file_count: 248,
      })
    ),
  },
}));

describe("M9-05: Project Snapshot History and Point-in-time Diffs (Screen S-05 per docs/08 §11)", () => {
  const projectId = "018f0a00-0000-7000-8000-000000000101";

  it("renders BrainHeader with History & Diffs action button", () => {
    const handleOpenHistory = vi.fn();
    const html = renderToString(
      <BrainHeader
        projectId={projectId}
        snapshots={SAMPLE_SNAPSHOTS}
        selectedSnapshotId="snap-001"
        onSelectSnapshot={vi.fn()}
        projectMode="indexed"
        searchQuery=""
        onSearchChange={vi.fn()}
        onOpenHistory={handleOpenHistory}
      />
    );

    expect(html).toContain("History &amp; Diffs");
  });

  it("renders SnapshotHistoryModal timeline with snapshot items, badges, and file counts", () => {
    const html = renderToString(
      <SnapshotHistoryModal
        projectId={projectId}
        isOpen={true}
        onClose={vi.fn()}
        currentSnapshotId="snap-001"
        initialSnapshots={mockSnapshots}
      />
    );

    expect(html).toContain("Project Snapshot History &amp; Diffs");
    expect(html).toContain("Timeline (3)");
    expect(html).toContain("Diff &amp; Comparison");
    expect(html).toContain("+ Capture Snapshot");

    // Check rendered snapshot entries
    expect(html).toContain("v1.0 baseline");
    expect(html).toContain("scan");
    expect(html).toContain("current active");
    expect(html).toContain("248 files");

    expect(html).toContain("M9 retention commit");
    expect(html).toContain("commit");
    expect(html).toContain("242 files");

    expect(html).toContain("Pre-refactor checkpoint");
    expect(html).toContain("manual");
    expect(html).toContain("235 files");
  });

  it("renders SnapshotHistoryModal diff tab with comparison metrics and differences list", () => {
    const html = renderToString(
      <SnapshotHistoryModal
        projectId={projectId}
        isOpen={true}
        onClose={vi.fn()}
        currentSnapshotId="snap-001"
        initialSnapshots={mockSnapshots}
        initialTab="diff"
        initialDiff={mockDiff}
      />
    );

    // Diff selectors and action
    expect(html).toContain("Base Snapshot");
    expect(html).toContain("Target Snapshot");
    expect(html).toContain("Run Snapshot Diff");

    // Metrics
    expect(html).toContain("Added Files");
    expect(html).toContain("+6");
    expect(html).toContain("Removed Files");
    expect(html).toContain("-1");
    expect(html).toContain("Modified Files");
    expect(html).toContain("~4");
    expect(html).toContain("Unchanged");
    expect(html).toContain("=231");

    // Differences items
    expect(html).toContain("server/app/domain/retention/service.py");
    expect(html).toContain("added");
    expect(html).toContain("server/app/domain/deprecated/old.py");
    expect(html).toContain("removed");
    expect(html).toContain("common/src/api/index.ts");
    expect(html).toContain("modified");
  });

  it("renders SnapshotHistoryModal capture tab with input fields and action button", () => {
    const html = renderToString(
      <SnapshotHistoryModal
        projectId={projectId}
        isOpen={true}
        onClose={vi.fn()}
        currentSnapshotId="snap-001"
        initialSnapshots={mockSnapshots}
        initialTab="capture"
      />
    );

    expect(html).toContain("Point-in-Time Project Snapshot");
    expect(html).toContain("Origin Kind");
    expect(html).toContain("Reference / SHA (optional)");
    expect(html).toContain("Human Label (optional)");
    expect(html).toContain("Capture Snapshot Now");
    expect(html).toContain("Back to Timeline");
  });

  it("renders modal when closed without content (null safety)", () => {
    const html = renderToString(
      <SnapshotHistoryModal
        projectId={projectId}
        isOpen={false}
        onClose={vi.fn()}
        currentSnapshotId="snap-001"
        initialSnapshots={mockSnapshots}
      />
    );

    expect(html).toBe("");
  });
});
