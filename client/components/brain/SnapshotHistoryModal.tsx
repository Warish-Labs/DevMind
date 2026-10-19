"use client";

import React, { useState, useEffect, useMemo } from "react";
import { apiClient } from "../../lib/api";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";
import { Dialog } from "../ui/Dialog";
import type {
  SnapshotItem,
  SnapshotDiffResponse,
  SnapshotDiffItem,
  CreateSnapshotRequest,
} from "@devmind/common/api";

export interface SnapshotHistoryModalProps {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
  currentSnapshotId?: string;
  onSelectSnapshot?: (snapshotId: string) => void;
  initialSnapshots?: SnapshotItem[];
  initialTab?: "history" | "diff" | "capture";
  initialDiff?: SnapshotDiffResponse;
}

type ModalTab = "history" | "diff" | "capture";

export function SnapshotHistoryModal({
  projectId,
  isOpen,
  onClose,
  currentSnapshotId,
  onSelectSnapshot,
  initialSnapshots,
  initialTab = "history",
  initialDiff,
}: SnapshotHistoryModalProps) {
  const [activeTab, setActiveTab] = useState<ModalTab>(initialTab);
  const [snapshots, setSnapshots] = useState<SnapshotItem[]>(initialSnapshots || []);
  const [isLoadingSnapshots, setIsLoadingSnapshots] = useState<boolean>(!initialSnapshots);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);

  // Diff state
  const [baseSnapshotId, setBaseSnapshotId] = useState<string>(
    initialSnapshots && initialSnapshots.length > 0 ? initialSnapshots[0].id : ""
  );
  const [targetSnapshotId, setTargetSnapshotId] = useState<string>("active");
  const [diffReport, setDiffReport] = useState<SnapshotDiffResponse | null>(initialDiff || null);
  const [isLoadingDiff, setIsLoadingDiff] = useState<boolean>(false);
  const [diffError, setDiffError] = useState<string | null>(null);
  const [diffFilter, setDiffFilter] = useState<
    "all" | "added" | "removed" | "modified" | "unchanged"
  >("all");
  const [diffSearch, setDiffSearch] = useState<string>("");

  // Capture state
  const [captureKind, setCaptureKind] = useState<"manual" | "scan" | "commit">("manual");
  const [captureRef, setCaptureRef] = useState<string>("");
  const [captureLabel, setCaptureLabel] = useState<string>("");
  const [isCapturing, setIsCapturing] = useState<boolean>(false);
  const [captureNotice, setCaptureNotice] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  // Fetch snapshots when modal opens
  useEffect(() => {
    if (!isOpen) return;

    let isMounted = true;

    apiClient
      .listSnapshots(projectId, 50)
      .then((items) => {
        if (!isMounted) return;
        setSnapshots(items);
        setIsLoadingSnapshots(false);
        if (items.length > 0 && !baseSnapshotId) {
          setBaseSnapshotId(items[0].id);
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        setSnapshotError(err instanceof Error ? err.message : "Failed to load snapshot history");
        setIsLoadingSnapshots(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, projectId, baseSnapshotId]);

  // Load Diff
  const handleLoadDiff = async (baseId: string, targetId: string) => {
    if (!baseId) return;
    setIsLoadingDiff(true);
    setDiffError(null);
    try {
      const realTarget = targetId === "active" ? undefined : targetId;
      const res = await apiClient.compareSnapshots(projectId, baseId, realTarget);
      setDiffReport(res);
    } catch (err) {
      setDiffError(err instanceof Error ? err.message : "Failed to compute snapshot diff");
      setDiffReport(null);
    } finally {
      setIsLoadingDiff(false);
    }
  };

  // Compare on tab change or button click
  const handleSelectCompare = (snapId: string) => {
    setBaseSnapshotId(snapId);
    setTargetSnapshotId("active");
    setActiveTab("diff");
    void handleLoadDiff(snapId, "active");
  };

  // Handle Capture Snapshot
  const handleCaptureSnapshot = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsCapturing(true);
    setCaptureNotice(null);

    const payload: CreateSnapshotRequest = {
      kind: captureKind,
      ref: captureRef.trim() || `manual-${new Date().toISOString().slice(0, 10)}`,
      label: captureLabel.trim() || undefined,
    };

    try {
      const newSnap = await apiClient.createSnapshot(projectId, payload);
      setSnapshots((prev) => [newSnap, ...prev]);
      setCaptureNotice({
        type: "success",
        message: `Captured snapshot successfully (${newSnap.file_count} files linked).`,
      });
      setCaptureRef("");
      setCaptureLabel("");
    } catch (err) {
      setCaptureNotice({
        type: "error",
        message: err instanceof Error ? err.message : "Failed to capture snapshot",
      });
    } finally {
      setIsCapturing(false);
    }
  };

  // Filtered differences
  const filteredDifferences = useMemo(() => {
    if (!diffReport?.differences) return [];
    return diffReport.differences.filter((item: SnapshotDiffItem) => {
      if (diffFilter !== "all" && item.status !== diffFilter) return false;
      if (diffSearch.trim() && !item.path.toLowerCase().includes(diffSearch.toLowerCase().trim())) {
        return false;
      }
      return true;
    });
  }, [diffReport, diffFilter, diffSearch]);

  const formatDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return isoString;
    }
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title="Project Snapshot History & Diffs"
      description="Point-in-time repository snapshots, version histories, and AST structure comparisons (M4-04 / M9-05)."
      className="max-w-3xl max-h-[85vh] flex flex-col"
    >
      {/* Modal Tab Controls */}
      <div className="flex border-b border-[var(--line-1)] mb-4 -mt-2 shrink-0">
        <button
          type="button"
          onClick={() => setActiveTab("history")}
          className={`px-4 py-2 text-xs font-mono font-medium border-b-2 transition-colors ${
            activeTab === "history"
              ? "border-[var(--ref)] text-[var(--ref)]"
              : "border-transparent text-[var(--fg-2)] hover:text-[var(--fg-0)]"
          }`}
        >
          {`Timeline (${snapshots.length})`}
        </button>
        <button
          type="button"
          onClick={() => {
            setActiveTab("diff");
            if (!diffReport && baseSnapshotId) {
              void handleLoadDiff(baseSnapshotId, targetSnapshotId);
            }
          }}
          className={`px-4 py-2 text-xs font-mono font-medium border-b-2 transition-colors ${
            activeTab === "diff"
              ? "border-[var(--ref)] text-[var(--ref)]"
              : "border-transparent text-[var(--fg-2)] hover:text-[var(--fg-0)]"
          }`}
        >
          Diff & Comparison
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("capture")}
          className={`px-4 py-2 text-xs font-mono font-medium border-b-2 transition-colors ${
            activeTab === "capture"
              ? "border-[var(--ref)] text-[var(--ref)]"
              : "border-transparent text-[var(--fg-2)] hover:text-[var(--fg-0)]"
          }`}
        >
          + Capture Snapshot
        </button>
      </div>

      {/* TAB 1: HISTORY TIMELINE */}
      {activeTab === "history" && (
        <div className="flex-1 overflow-y-auto space-y-3 pr-1">
          {snapshotError && (
            <div className="p-3 text-xs rounded bg-[rgba(255,107,94,0.1)] border border-[rgba(255,107,94,0.3)] text-[var(--danger)]">
              {snapshotError}
            </div>
          )}

          {isLoadingSnapshots ? (
            <div className="py-8 text-center text-xs font-mono text-[var(--fg-3)]">
              Loading snapshot timeline...
            </div>
          ) : snapshots.length === 0 ? (
            <div className="py-8 text-center text-xs font-mono text-[var(--fg-3)] space-y-2">
              <p>No snapshots captured for this project yet.</p>
              <Button variant="secondary" size="sm" onClick={() => setActiveTab("capture")}>
                Capture First Snapshot
              </Button>
            </div>
          ) : (
            <div className="divide-y divide-[var(--line-1)] border border-[var(--line-1)] rounded-[var(--radius-md)] overflow-hidden">
              {snapshots.map((snap) => {
                const isCurrent = snap.id === currentSnapshotId;
                const kindVariant =
                  snap.kind === "commit" ? "signal" : snap.kind === "manual" ? "warn" : "ref";

                return (
                  <div
                    key={snap.id}
                    className="p-3 bg-[var(--bg-1)] hover:bg-[var(--bg-2)] transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono font-semibold text-xs text-[var(--fg-0)]">
                          {snap.label || snap.ref || snap.id.slice(0, 8)}
                        </span>
                        <Badge variant={kindVariant} size="sm">
                          {snap.kind}
                        </Badge>
                        {isCurrent && (
                          <Badge variant="signal" size="sm">
                            current active
                          </Badge>
                        )}
                        <span className="text-[11px] font-mono text-[var(--fg-3)]">
                          {`${snap.file_count} files`}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-[11px] font-mono text-[var(--fg-3)]">
                        <span>Ref: {snap.ref || "—"}</span>
                        <span>•</span>
                        <span>{formatDate(snap.created_at)}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleSelectCompare(snap.id)}
                        className="text-xs h-7"
                      >
                        Compare Diff
                      </Button>
                      {onSelectSnapshot && (
                        <Button
                          variant="tertiary"
                          size="sm"
                          onClick={() => {
                            onSelectSnapshot(snap.id);
                            onClose();
                          }}
                          className="text-xs h-7"
                        >
                          View in Brain
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: DIFF & COMPARISON */}
      {activeTab === "diff" && (
        <div className="flex-1 overflow-y-auto space-y-4 pr-1">
          {/* Snapshot Comparison Selectors */}
          <div className="p-3 bg-[var(--bg-1)] border border-[var(--line-1)] rounded-[var(--radius-md)] space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-mono text-[var(--fg-2)] mb-1">
                  Base Snapshot
                </label>
                <select
                  value={baseSnapshotId}
                  onChange={(e) => setBaseSnapshotId(e.target.value)}
                  className="w-full bg-[var(--bg-0)] border border-[var(--line-1)] rounded px-2.5 py-1.5 text-xs font-mono text-[var(--fg-0)] focus:border-[var(--ref)] focus:outline-none"
                >
                  {snapshots.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.label || s.ref || s.id.slice(0, 8)} ({s.kind}) — {formatDate(s.created_at)}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-mono text-[var(--fg-2)] mb-1">
                  Target Snapshot
                </label>
                <select
                  value={targetSnapshotId}
                  onChange={(e) => setTargetSnapshotId(e.target.value)}
                  className="w-full bg-[var(--bg-0)] border border-[var(--line-1)] rounded px-2.5 py-1.5 text-xs font-mono text-[var(--fg-0)] focus:border-[var(--ref)] focus:outline-none"
                >
                  <option value="active">Current Active Project State</option>
                  {snapshots.map((s) => (
                    <option key={s.id} value={s.id} disabled={s.id === baseSnapshotId}>
                      {s.label || s.ref || s.id.slice(0, 8)} ({s.kind})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex justify-end">
              <Button
                variant="primary"
                size="sm"
                onClick={() => handleLoadDiff(baseSnapshotId, targetSnapshotId)}
                isLoading={isLoadingDiff}
                disabled={!baseSnapshotId}
              >
                Run Snapshot Diff
              </Button>
            </div>
          </div>

          {diffError && (
            <div className="p-3 text-xs rounded bg-[rgba(255,107,94,0.1)] border border-[rgba(255,107,94,0.3)] text-[var(--danger)]">
              {diffError}
            </div>
          )}

          {/* Diff Result Summary */}
          {diffReport && (
            <div className="space-y-3">
              {/* Stat Counters */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <div
                  onClick={() => setDiffFilter(diffFilter === "added" ? "all" : "added")}
                  className={`p-2.5 rounded border cursor-pointer transition-colors ${
                    diffFilter === "added"
                      ? "border-[var(--signal)] bg-[rgba(32,227,162,0.12)]"
                      : "border-[var(--line-1)] bg-[var(--bg-1)] hover:border-[var(--signal)]"
                  }`}
                >
                  <div className="text-[10px] font-mono uppercase text-[var(--fg-3)]">
                    Added Files
                  </div>
                  <div className="text-lg font-mono font-bold text-[var(--signal)]">
                    {`+${diffReport.added}`}
                  </div>
                </div>

                <div
                  onClick={() => setDiffFilter(diffFilter === "removed" ? "all" : "removed")}
                  className={`p-2.5 rounded border cursor-pointer transition-colors ${
                    diffFilter === "removed"
                      ? "border-[var(--danger)] bg-[rgba(255,107,94,0.12)]"
                      : "border-[var(--line-1)] bg-[var(--bg-1)] hover:border-[var(--danger)]"
                  }`}
                >
                  <div className="text-[10px] font-mono uppercase text-[var(--fg-3)]">
                    Removed Files
                  </div>
                  <div className="text-lg font-mono font-bold text-[var(--danger)]">
                    {`-${diffReport.removed}`}
                  </div>
                </div>

                <div
                  onClick={() => setDiffFilter(diffFilter === "modified" ? "all" : "modified")}
                  className={`p-2.5 rounded border cursor-pointer transition-colors ${
                    diffFilter === "modified"
                      ? "border-[var(--warn)] bg-[rgba(240,180,76,0.12)]"
                      : "border-[var(--line-1)] bg-[var(--bg-1)] hover:border-[var(--warn)]"
                  }`}
                >
                  <div className="text-[10px] font-mono uppercase text-[var(--fg-3)]">
                    Modified Files
                  </div>
                  <div className="text-lg font-mono font-bold text-[var(--warn)]">
                    {`~${diffReport.modified}`}
                  </div>
                </div>

                <div
                  onClick={() => setDiffFilter(diffFilter === "unchanged" ? "all" : "unchanged")}
                  className={`p-2.5 rounded border cursor-pointer transition-colors ${
                    diffFilter === "unchanged"
                      ? "border-[var(--line-2)] bg-[var(--bg-2)]"
                      : "border-[var(--line-1)] bg-[var(--bg-1)] hover:border-[var(--line-2)]"
                  }`}
                >
                  <div className="text-[10px] font-mono uppercase text-[var(--fg-3)]">
                    Unchanged
                  </div>
                  <div className="text-lg font-mono font-bold text-[var(--fg-2)]">
                    {`=${diffReport.unchanged}`}
                  </div>
                </div>
              </div>

              {/* Filter and Search Bar */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-1">
                  {(["all", "added", "removed", "modified", "unchanged"] as const).map((filter) => (
                    <button
                      key={filter}
                      type="button"
                      onClick={() => setDiffFilter(filter)}
                      className={`px-2 py-0.5 rounded text-[11px] font-mono capitalize transition-colors ${
                        diffFilter === filter
                          ? "bg-[var(--ref)] text-[var(--bg-0)] font-bold"
                          : "text-[var(--fg-3)] hover:text-[var(--fg-1)]"
                      }`}
                    >
                      {filter}
                    </button>
                  ))}
                </div>

                <input
                  type="search"
                  placeholder="Filter path..."
                  value={diffSearch}
                  onChange={(e) => setDiffSearch(e.target.value)}
                  className="bg-[var(--bg-0)] border border-[var(--line-1)] rounded px-2.5 py-1 text-xs font-mono text-[var(--fg-0)] placeholder-[var(--fg-3)] focus:border-[var(--ref)] focus:outline-none min-w-[200px]"
                />
              </div>

              {/* Differences List */}
              <div className="border border-[var(--line-1)] rounded-[var(--radius-md)] overflow-hidden divide-y divide-[var(--line-1)]">
                {filteredDifferences.length === 0 ? (
                  <div className="p-4 text-center text-xs font-mono text-[var(--fg-3)]">
                    No file differences match the selected filter.
                  </div>
                ) : (
                  filteredDifferences.map((item) => {
                    const statusBadgeVariant =
                      item.status === "added"
                        ? "signal"
                        : item.status === "removed"
                          ? "danger"
                          : item.status === "modified"
                            ? "warn"
                            : "neutral";

                    const statusGlyph =
                      item.status === "added"
                        ? "+"
                        : item.status === "removed"
                          ? "-"
                          : item.status === "modified"
                            ? "~"
                            : "=";

                    return (
                      <div
                        key={item.path}
                        className="p-2.5 bg-[var(--bg-1)] hover:bg-[var(--bg-2)] transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <Badge variant={statusBadgeVariant} size="sm" glyph={statusGlyph}>
                            {item.status}
                          </Badge>
                          <span className="font-mono text-[var(--fg-0)] truncate">{item.path}</span>
                        </div>

                        <div className="flex items-center gap-2 text-[10px] font-mono text-[var(--fg-3)] shrink-0">
                          {item.base_content_hash && (
                            <span title={`Base hash: ${item.base_content_hash}`}>
                              {item.base_content_hash.slice(0, 8)}
                            </span>
                          )}
                          {item.base_content_hash && item.target_content_hash && <span>→</span>}
                          {item.target_content_hash && (
                            <span
                              className="text-[var(--fg-1)]"
                              title={`Target hash: ${item.target_content_hash}`}
                            >
                              {item.target_content_hash.slice(0, 8)}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: CAPTURE SNAPSHOT */}
      {activeTab === "capture" && (
        <form onSubmit={handleCaptureSnapshot} className="flex-1 overflow-y-auto space-y-4 pr-1">
          <div className="p-3 bg-[var(--bg-1)] border border-[var(--line-1)] rounded-[var(--radius-md)] text-xs text-[var(--fg-2)] space-y-1">
            <p className="font-semibold text-[var(--fg-0)]">Point-in-Time Project Snapshot</p>
            <p>
              Captures an immutable snapshot of all currently active repository files and versions.
              Historical snapshots are preserved permanently and unaffected by future scans or
              deletions.
            </p>
          </div>

          {captureNotice && (
            <div
              className={`p-3 text-xs rounded border ${
                captureNotice.type === "success"
                  ? "bg-[rgba(32,227,162,0.1)] border-[rgba(32,227,162,0.3)] text-[var(--signal)]"
                  : "bg-[rgba(255,107,94,0.1)] border-[rgba(255,107,94,0.3)] text-[var(--danger)]"
              }`}
            >
              {captureNotice.message}
            </div>
          )}

          <div className="space-y-3">
            <div>
              <label className="block text-xs font-mono text-[var(--fg-2)] mb-1">Origin Kind</label>
              <select
                value={captureKind}
                onChange={(e) => setCaptureKind(e.target.value as "manual" | "scan" | "commit")}
                className="w-full bg-[var(--bg-1)] border border-[var(--line-1)] rounded px-3 py-1.5 text-xs font-mono text-[var(--fg-0)] focus:border-[var(--ref)] focus:outline-none"
              >
                <option value="manual">manual (User-triggered checkpoint)</option>
                <option value="scan">scan (Local scan or extension sync)</option>
                <option value="commit">commit (Git commit / PR head)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-mono text-[var(--fg-2)] mb-1">
                Reference / SHA (optional)
              </label>
              <input
                type="text"
                value={captureRef}
                onChange={(e) => setCaptureRef(e.target.value)}
                placeholder="e.g. 1c02bbd or feature/m9-snapshot-history"
                className="w-full bg-[var(--bg-1)] border border-[var(--line-1)] rounded px-3 py-1.5 text-xs font-mono text-[var(--fg-0)] placeholder-[var(--fg-3)] focus:border-[var(--ref)] focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-mono text-[var(--fg-2)] mb-1">
                Human Label (optional)
              </label>
              <input
                type="text"
                value={captureLabel}
                onChange={(e) => setCaptureLabel(e.target.value)}
                placeholder="e.g. Baseline before M9 refactoring"
                className="w-full bg-[var(--bg-1)] border border-[var(--line-1)] rounded px-3 py-1.5 text-xs text-[var(--fg-0)] placeholder-[var(--fg-3)] focus:border-[var(--ref)] focus:outline-none"
              />
            </div>
          </div>

          <div className="pt-2 flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={() => setActiveTab("history")}>
              Back to Timeline
            </Button>
            <Button type="submit" variant="primary" size="sm" isLoading={isCapturing}>
              Capture Snapshot Now
            </Button>
          </div>
        </form>
      )}
    </Dialog>
  );
}
