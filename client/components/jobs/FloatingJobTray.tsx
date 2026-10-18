"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Badge } from "../ui/Badge";
import { type JobWithDetails, getJobStatusBadgeVariant, formatJobType } from "./types";

export interface FloatingJobTrayProps {
  projectId: string;
  activeJobs: JobWithDetails[];
  onCancelJob?: (jobId: string) => Promise<void> | void;
  className?: string;
}

export function FloatingJobTray({
  projectId,
  activeJobs,
  onCancelJob,
  className = "",
}: FloatingJobTrayProps) {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);

  // Filter running or awaiting approval jobs
  const runningJobs = activeJobs.filter(
    (j) => j.status === "running" || j.status === "queued" || j.status === "awaiting_approval"
  );

  if (runningJobs.length === 0) {
    return null;
  }

  const hasAwaitingApproval = runningJobs.some((j) => j.status === "awaiting_approval");

  return (
    <div className={`fixed bottom-5 right-5 z-40 font-mono text-xs ${className}`}>
      {/* Collapsed Pill */}
      {!isExpanded ? (
        <button
          type="button"
          onClick={() => setIsExpanded(true)}
          className={`flex items-center gap-2.5 px-3.5 py-2 rounded-full shadow-lg border backdrop-blur-md transition-all hover:scale-105 ${
            hasAwaitingApproval
              ? "bg-[rgba(240,180,76,0.15)] border-[var(--warn)] text-[var(--warn)]"
              : "bg-[var(--bg-1)] border-[var(--line-strong)] text-[var(--fg-0)]"
          }`}
        >
          <span className="relative flex h-2 w-2">
            <span
              className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                hasAwaitingApproval ? "bg-[var(--warn)]" : "bg-[var(--ref)]"
              }`}
            />
            <span
              className={`relative inline-flex rounded-full h-2 w-2 ${
                hasAwaitingApproval ? "bg-[var(--warn)]" : "bg-[var(--ref)]"
              }`}
            />
          </span>

          <span className="font-semibold text-xs">
            {hasAwaitingApproval
              ? "Action Required · Approval Gate"
              : `${runningJobs.length} active job${runningJobs.length > 1 ? "s" : ""}`}
          </span>

          <svg
            className="w-3.5 h-3.5 text-[var(--fg-2)]"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
          </svg>
        </button>
      ) : (
        /* Expanded Drawer */
        <div className="w-80 sm:w-96 rounded-[var(--radius-lg)] bg-[var(--bg-1)] border border-[var(--line-strong)] shadow-2xl overflow-hidden animate-in fade-in slide-in-from-bottom-2">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-2.5 bg-[var(--bg-2)] border-b border-[var(--line-1)]">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[var(--signal)] animate-pulse" />
              <span className="font-semibold text-[var(--fg-0)] text-xs">
                Active Job Tray ({`${runningJobs.length}`})
              </span>
            </div>

            <button
              type="button"
              onClick={() => setIsExpanded(false)}
              className="text-[var(--fg-3)] hover:text-[var(--fg-0)] p-1 rounded transition-colors"
              aria-label="Collapse job tray"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          </div>

          {/* Job List */}
          <div className="divide-y divide-[var(--line-1)] max-h-72 overflow-y-auto">
            {runningJobs.map((job) => {
              const isAwaiting = job.status === "awaiting_approval";
              const progress = job.progressPct ?? 0;

              return (
                <div
                  key={job.id}
                  className="p-3 space-y-2 hover:bg-[var(--bg-0)] transition-colors"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="space-y-0.5">
                      <Link
                        href={`/projects/${projectId}/jobs/${job.id}`}
                        className="font-semibold text-xs text-[var(--fg-0)] hover:text-[var(--ref)]"
                      >
                        {formatJobType(job.type)}
                      </Link>
                      <div className="text-[10px] text-[var(--fg-3)]">
                        queue: {job.queue || "default"}
                      </div>
                    </div>

                    <Badge variant={getJobStatusBadgeVariant(job.status)} size="sm">
                      {job.status.replace(/_/g, " ")}
                    </Badge>
                  </div>

                  {/* Mini Progress */}
                  <div className="space-y-1">
                    <div className="flex justify-between text-[10px] text-[var(--fg-2)]">
                      <span>Progress</span>
                      <span>{progress}%</span>
                    </div>
                    <div className="h-1.5 w-full bg-[var(--bg-2)] rounded-full overflow-hidden">
                      <div
                        className={`h-full ${
                          isAwaiting ? "bg-[var(--warn)]" : "bg-[var(--signal)]"
                        }`}
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center justify-between pt-1">
                    <Link
                      href={`/projects/${projectId}/jobs/${job.id}`}
                      className="text-[11px] text-[var(--ref)] hover:underline"
                    >
                      {isAwaiting ? "Review Approval →" : "View Live Stream →"}
                    </Link>

                    {onCancelJob && (
                      <button
                        type="button"
                        onClick={() => onCancelJob(job.id)}
                        className="text-[10px] text-[var(--danger)] hover:underline"
                      >
                        Cancel
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Footer */}
          <div className="p-2.5 bg-[var(--bg-2)] border-t border-[var(--line-1)] text-center">
            <Link
              href={`/projects/${projectId}/jobs`}
              className="text-[11px] text-[var(--fg-1)] hover:text-[var(--fg-0)] font-medium"
            >
              Open Full Job Center →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
