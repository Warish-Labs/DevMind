"use client";

import React from "react";
import Link from "next/link";
import type { BrainSnapshotSummary, ProjectBrainMode } from "./types";
import { Button } from "../ui/Button";

export interface BrainHeaderProps {
  projectId: string;
  snapshots: BrainSnapshotSummary[];
  selectedSnapshotId: string;
  onSelectSnapshot: (id: string) => void;
  projectMode: ProjectBrainMode;
  onToggleMode?: () => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  onOpenHistory?: () => void;
  className?: string;
}

export function BrainHeader({
  projectId,
  snapshots,
  selectedSnapshotId,
  onSelectSnapshot,
  projectMode,
  onToggleMode,
  searchQuery,
  onSearchChange,
  onOpenHistory,
  className = "",
}: BrainHeaderProps) {
  const currentSnapshot = snapshots.find((s) => s.id === selectedSnapshotId) || snapshots[0];

  return (
    <header
      className={`border-b border-[var(--line-1)] bg-[var(--bg-0)] px-6 py-3 shrink-0 select-none ${className}`}
    >
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        {/* Left: Title & Mode Info */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[var(--signal)]" />
            <h1 className="text-sm font-semibold text-[var(--fg-0)]">Project Brain Explorer</h1>
          </div>

          <span className="px-2 py-0.5 rounded-[var(--radius-chip)] bg-[var(--bg-1)] border border-[var(--line-1)] text-[10px] font-mono text-[var(--fg-2)]">
            Screen S-05
          </span>

          {projectMode === "metadata_only" ? (
            <span className="px-2 py-0.5 rounded-[var(--radius-chip)] bg-[rgba(240,180,76,0.12)] border border-[rgba(240,180,76,0.3)] text-[10px] font-mono text-[var(--warn)] font-bold">
              Metadata-Only Mode
            </span>
          ) : (
            <span className="px-2 py-0.5 rounded-[var(--radius-chip)] bg-[rgba(78,161,255,0.12)] border border-[rgba(78,161,255,0.3)] text-[10px] font-mono text-[var(--ref)] font-bold">
              Indexed Mode (AST Verified)
            </span>
          )}

          {onToggleMode && (
            <button
              type="button"
              onClick={onToggleMode}
              className="text-[11px] font-mono text-[var(--fg-3)] hover:text-[var(--fg-0)] underline transition-colors"
              title="Toggle preview between indexed and metadata-only mode"
            >
              Toggle mode
            </button>
          )}
        </div>

        {/* Right: Snapshot Selector & Hybrid Search Input */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Hybrid Search Input */}
          <div className="relative min-w-[240px]">
            <input
              type="search"
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Search symbols or files (POST /brain/search)..."
              className="w-full bg-[var(--bg-1)] border border-[var(--line-1)] focus:border-[var(--ref)] rounded-[var(--radius-md)] px-3 py-1.5 text-xs text-[var(--fg-0)] placeholder-[var(--fg-3)] font-mono focus:outline-none transition-colors"
            />
          </div>

          {/* Snapshot Selector */}
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono text-[var(--fg-3)]">Snapshot:</span>
            <select
              value={selectedSnapshotId}
              onChange={(e) => onSelectSnapshot(e.target.value)}
              className="bg-[var(--bg-1)] border border-[var(--line-1)] text-[11px] font-mono text-[var(--fg-0)] rounded-[var(--radius-md)] px-2.5 py-1.5 focus:border-[var(--ref)] focus:outline-none cursor-pointer"
            >
              {snapshots.map((snap) => (
                <option key={snap.id} value={snap.id}>
                  {`${snap.name}${snap.isCurrent ? " (current)" : ""}${snap.isStale ? " [stale]" : ""}`}
                </option>
              ))}
            </select>

            {onOpenHistory && (
              <Button
                variant="secondary"
                size="sm"
                onClick={onOpenHistory}
                className="h-7 text-xs font-mono"
              >
                History & Diffs
              </Button>
            )}
          </div>

          {/* Stale Warning Badge if selected snapshot is not current */}
          {currentSnapshot?.isStale && (
            <span className="px-2 py-0.5 rounded-[var(--radius-chip)] bg-[rgba(235,90,90,0.12)] border border-[rgba(235,90,90,0.3)] text-[10px] font-mono text-[var(--danger)] font-bold">
              Stale Snapshot
            </span>
          )}

          {/* Consent / Settings Link */}
          {projectMode === "metadata_only" && (
            <Link href={`/projects/${projectId}/settings`}>
              <Button variant="primary" size="sm" className="h-7 text-xs">
                Enable Indexed Mode
              </Button>
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
