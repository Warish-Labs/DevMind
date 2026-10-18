"use client";

import React from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tooltip } from "@/components/ui/Tooltip";
import { JobsIcon, ExternalLinkIcon } from "@/components/shell/icons";
import type { ScanRunItem, ActivityJobItem } from "./types";

interface ActivityPanelProps {
  projectId: string;
  syncMode: "indexed" | "metadata_only";
  scans: ScanRunItem[];
  jobs: ActivityJobItem[];
  lastSyncAt?: string;
  isLoading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onTriggerScan?: () => void;
}

function formatRelativeTime(dateString?: string): string {
  if (!dateString) return "Never";
  const diff = Date.now() - new Date(dateString).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function ActivityPanel({
  projectId,
  syncMode,
  scans,
  jobs,
  lastSyncAt,
  isLoading = false,
  error = null,
  onRetry,
  onTriggerScan,
}: ActivityPanelProps) {
  if (isLoading) {
    return (
      <div className="rounded-panel border border-[var(--line-1)] bg-[var(--bg-1)] p-5 space-y-4">
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-panel border border-[var(--danger)]/40 bg-[var(--danger)]/5 p-5 font-mono text-xs space-y-3">
        <div className="flex items-center gap-2 text-[var(--danger)] font-semibold">
          <span>Failed to load activity and scans</span>
        </div>
        <p className="text-[var(--fg-1)] text-xs">{error}</p>
        {onRetry && (
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Retry Activity
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-panel border border-[var(--line-1)] bg-[var(--bg-1)] p-4 sm:p-5 font-mono text-xs space-y-5">
      {/* Question 1: What is happening? */}
      <div>
        <div className="flex items-center justify-between pb-2 border-b border-[var(--line-1)] mb-3">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--signal)]" />
            <span className="text-[10px] uppercase tracking-wider font-semibold text-[var(--fg-0)]">
              Question 1 · What Is Happening?
            </span>
          </div>
          <span className="text-[10px] text-[var(--fg-2)]">Scans &amp; Jobs</span>
        </div>

        {/* Sync & Connection Summary Card */}
        <div className="p-3 rounded-control bg-[var(--bg-0)] border border-[var(--line-1)] space-y-2 mb-4">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-[var(--fg-2)]">Synchronization Mode</span>
            <Tooltip
              content={
                syncMode === "indexed"
                  ? "Full AST, symbols, embeddings, and evidence citations active."
                  : "Metadata-only: source code never leaves your local machine."
              }
              position="left"
            >
              <div>
                <Badge
                  variant={syncMode === "indexed" ? "signal" : "warn"}
                  size="sm"
                  className="cursor-help"
                >
                  {syncMode}
                </Badge>
              </div>
            </Tooltip>
          </div>

          <div className="flex items-center justify-between text-[11px] text-[var(--fg-2)]">
            <span>Last Synchronized</span>
            <span className="text-[var(--fg-1)]">{formatRelativeTime(lastSyncAt)}</span>
          </div>

          <div className="flex items-center justify-between text-[11px] text-[var(--fg-2)]">
            <span>Extension Companion</span>
            <div className="flex items-center gap-1.5 text-[var(--signal)]">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--signal)]" />
              <span>VS Code Active</span>
            </div>
          </div>
        </div>

        {/* Recent Scans */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-[11px] text-[var(--fg-2)] font-semibold">
            <span>Recent Scans</span>
            {onTriggerScan && (
              <button
                type="button"
                onClick={onTriggerScan}
                className="text-[10px] text-[var(--signal)] hover:underline cursor-pointer"
              >
                + Run scan
              </button>
            )}
          </div>

          {scans.length === 0 ? (
            <div className="py-4 text-center text-[11px] text-[var(--fg-2)]">
              No recent scans recorded
            </div>
          ) : (
            scans.map((scan) => (
              <div
                key={scan.id}
                className="p-2.5 rounded-control bg-[var(--bg-0)] border border-[var(--line-1)] flex items-center justify-between"
              >
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--signal)]" />
                  <div>
                    <div className="font-medium text-xs text-[var(--fg-0)] capitalize">
                      {scan.scanKind === "full" ? "Full Scan" : "Incremental Scan"}
                    </div>
                    <div className="text-[10px] text-[var(--fg-2)]">
                      {`${scan.filesAnalyzed} files · ${scan.durationMs}ms`}
                    </div>
                  </div>
                </div>
                <span className="text-[10px] text-[var(--fg-2)]">
                  {formatRelativeTime(scan.createdAt)}
                </span>
              </div>
            ))
          )}
        </div>

        {/* Recent Jobs */}
        <div className="space-y-2 mt-4 pt-3 border-t border-[var(--line-1)]">
          <div className="flex items-center justify-between text-[11px] text-[var(--fg-2)] font-semibold">
            <span>Background Jobs</span>
            <Link
              href={`/projects/${projectId}/jobs`}
              className="text-[10px] text-[var(--ref)] hover:underline flex items-center gap-1"
            >
              <span>Job Center (S-09)</span>
              <ExternalLinkIcon size={10} />
            </Link>
          </div>

          {jobs.length === 0 ? (
            <div className="py-4 text-center text-[11px] text-[var(--fg-2)]">
              No recent background jobs
            </div>
          ) : (
            jobs.map((job) => (
              <div
                key={job.id}
                className="p-2.5 rounded-control bg-[var(--bg-0)] border border-[var(--line-1)] flex items-center justify-between"
              >
                <div className="flex items-center gap-2">
                  <JobsIcon size={14} className="text-[var(--ref)]" />
                  <div>
                    <div className="font-medium text-xs text-[var(--fg-0)] capitalize">
                      {job.jobType.replace(/_/g, " ")}
                    </div>
                    <div className="text-[10px] text-[var(--fg-2)]">Status: {job.status}</div>
                  </div>
                </div>
                <Badge variant={job.status === "completed" ? "signal" : "neutral"} size="sm">
                  {job.status}
                </Badge>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
