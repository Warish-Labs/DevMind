"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import {
  type JobWithDetails,
  getJobStatusBadgeVariant,
  formatJobType,
  formatDuration,
} from "./types";
import { useJobEvents } from "./useJobEvents";

export interface JobDetailViewProps {
  projectId: string;
  initialJob: JobWithDetails;
  onCancelJob?: (jobId: string) => Promise<void> | void;
  onApproveJob?: (jobId: string, approved: boolean) => Promise<void> | void;
  className?: string;
}

export function JobDetailView({
  projectId,
  initialJob,
  onCancelJob,
  onApproveJob,
  className = "",
}: JobDetailViewProps) {
  const [job, setJob] = useState<JobWithDetails>(initialJob);
  const [isActionLoading, setIsActionLoading] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const { events, status, progressPct, connectionMode } = useJobEvents(job.id, {
    initialEvents: job.events || [],
    initialStatus: job.status,
    initialProgressPct: job.progressPct || 0,
    onStatusChange: (newStatus) => {
      setJob((prev) => ({ ...prev, status: newStatus }));
    },
  });

  const isRunning = status === "running" || status === "queued";
  const isAwaitingApproval = status === "awaiting_approval";

  const handleCancel = async () => {
    if (!onCancelJob) return;
    try {
      setIsActionLoading(true);
      setActionError(null);
      await onCancelJob(job.id);
      setJob((prev) => ({ ...prev, status: "cancelled" }));
    } catch (err: unknown) {
      const errObj = err as { message?: string };
      setActionError(errObj.message || "Failed to cancel job");
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleApprove = async (approved: boolean) => {
    if (!onApproveJob) return;
    try {
      setIsActionLoading(true);
      setActionError(null);
      await onApproveJob(job.id, approved);
      setJob((prev) => ({
        ...prev,
        status: approved ? "running" : "cancelled",
      }));
    } catch (err: unknown) {
      const errObj = err as { message?: string };
      setActionError(errObj.message || "Failed to process approval");
    } finally {
      setIsActionLoading(false);
    }
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Top Navigation */}
      <div className="flex items-center justify-between">
        <Link
          href={`/projects/${projectId}/jobs`}
          className="inline-flex items-center gap-1.5 text-xs text-[var(--fg-2)] hover:text-[var(--fg-0)] transition-colors"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to job center
        </Link>

        {/* Live SSE / Polling Stream Status Indicator */}
        <div className="flex items-center gap-2">
          {connectionMode === "sse" ? (
            <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-[var(--radius-chip)] bg-[rgba(32,227,162,0.1)] text-[var(--signal)] border border-[rgba(32,227,162,0.3)] text-[10px] font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--signal)] animate-ping" />
              Live SSE Stream
            </span>
          ) : connectionMode === "polling" ? (
            <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-[var(--radius-chip)] bg-[rgba(240,180,76,0.1)] text-[var(--warn)] border border-[rgba(240,180,76,0.3)] text-[10px] font-mono">
              ⟳ Polling Fallback
            </span>
          ) : (
            <span className="text-[10px] font-mono text-[var(--fg-3)]">Stream Closed</span>
          )}
        </div>
      </div>

      {actionError && (
        <div className="p-3 rounded-[var(--radius-md)] border border-[var(--danger)] bg-[rgba(255,107,94,0.1)] text-xs text-[var(--danger)]">
          {actionError}
        </div>
      )}

      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 bg-[var(--bg-1)] p-5 rounded-[var(--radius-lg)] border border-[var(--line-1)]">
        <div className="space-y-2 max-w-2xl">
          <div className="flex items-center gap-2">
            <Badge variant={getJobStatusBadgeVariant(status)}>
              {status.replace(/_/g, " ").toUpperCase()}
            </Badge>
            <span className="text-xs font-mono text-[var(--fg-3)]">{`ID: ${job.id}`}</span>
          </div>
          <h1 className="text-lg md:text-xl font-semibold text-[var(--fg-0)]">
            {formatJobType(job.type)}
          </h1>
          <p className="text-xs text-[var(--fg-2)]">
            {`Queue: ${job.queue || "default"} · Attempt: ${job.attempt || 1} of ${job.max_attempts || 3}`}
          </p>
        </div>

        {/* Actions */}
        {(isRunning || isAwaitingApproval) && (
          <Button
            variant="destructive"
            size="sm"
            isLoading={isActionLoading}
            onClick={handleCancel}
          >
            Cancel Job
          </Button>
        )}
      </div>

      {/* Progress Strip */}
      <div className="bg-[var(--bg-0)] p-4 rounded-[var(--radius-md)] border border-[var(--line-1)] space-y-2">
        <div className="flex items-center justify-between text-xs font-mono">
          <span className="text-[var(--fg-1)] font-semibold">Workflow Progress</span>
          <span className="text-[var(--fg-0)] font-bold">{`${progressPct}%`}</span>
        </div>
        <div className="h-2 w-full bg-[var(--bg-2)] rounded-full overflow-hidden border border-[var(--line-1)]">
          <div
            className={`h-full transition-all duration-300 ${
              status === "failed"
                ? "bg-[var(--danger)]"
                : status === "awaiting_approval"
                  ? "bg-[var(--warn)]"
                  : "bg-[var(--signal)]"
            }`}
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <div className="flex items-center justify-between text-[11px] font-mono text-[var(--fg-3)] pt-1">
          <span>
            Started: {job.started_at ? new Date(job.started_at).toLocaleTimeString() : "—"}
          </span>
          <span>Duration: {formatDuration(job.started_at, job.finished_at)}</span>
        </div>
      </div>

      {/* Approval Prompt Card (docs/08 §11 S-09: approval prompts when status is awaiting_approval; the approval card states exactly what will happen) */}
      {isAwaitingApproval && (
        <div className="p-5 rounded-[var(--radius-lg)] border-2 border-[var(--warn)] bg-[rgba(240,180,76,0.06)] space-y-4">
          <div className="flex items-start gap-3">
            <span className="text-xl">⚠️</span>
            <div className="space-y-1">
              <h2 className="text-sm font-bold text-[var(--warn)]">
                Human Approval Required (ADR-006 &amp; S-09)
              </h2>
              <div className="text-xs text-[var(--fg-1)] font-medium">
                {job.approval?.actionTitle || "Agent workflow paused before external side effect"}
              </div>
              <p className="text-xs text-[var(--fg-2)] leading-relaxed">
                {job.approval?.actionDescription ||
                  "The agent has computed a proposed resolution that requires human confirmation before modifying files or executing side effects."}
              </p>
            </div>
          </div>

          {job.approval?.impactScope && (
            <div className="bg-[var(--bg-0)] p-3 rounded-[var(--radius-sm)] border border-[var(--line-1)] font-mono text-xs text-[var(--fg-1)]">
              <span className="text-[var(--fg-3)]">Declared Impact Scope:</span>{" "}
              {job.approval.impactScope}
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-2 border-t border-[rgba(240,180,76,0.2)]">
            <Button
              variant="secondary"
              size="sm"
              isLoading={isActionLoading}
              onClick={() => handleApprove(false)}
            >
              Reject &amp; Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              isLoading={isActionLoading}
              onClick={() => handleApprove(true)}
            >
              Approve and Proceed
            </Button>
          </div>
        </div>
      )}

      {/* Diagnostics / Error Card */}
      {(status === "failed" || job.error_code) && (
        <div className="p-4 rounded-[var(--radius-md)] border border-[var(--danger)] bg-[rgba(255,107,94,0.08)] space-y-2">
          <div className="text-xs font-bold text-[var(--danger)] flex items-center gap-2">
            <span>Execution Failure Diagnostics</span>
            {job.error_code && (
              <code className="bg-[rgba(255,107,94,0.15)] px-1.5 py-0.2 rounded text-[11px] font-mono">
                {job.error_code}
              </code>
            )}
          </div>
          <div className="text-xs text-[var(--fg-1)] font-mono leading-relaxed">
            {job.error_detail || "The job stopped with an unhandled exception."}
          </div>
        </div>
      )}

      {/* Milestone Event Stream */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold text-[var(--fg-1)] uppercase tracking-wider">
            Milestone Events Log ({`${events.length}`})
          </h2>
          <span className="text-[11px] font-mono text-[var(--fg-3)]">RFC 8895 SSE Stream</span>
        </div>

        {events.length === 0 ? (
          <div className="p-6 text-center bg-[var(--bg-0)] border border-[var(--line-1)] rounded-[var(--radius-md)] text-xs text-[var(--fg-3)]">
            Waiting for initial milestone events from Celery worker...
          </div>
        ) : (
          <div className="border border-[var(--line-1)] rounded-[var(--radius-md)] bg-[var(--bg-0)] divide-y divide-[var(--line-1)] overflow-hidden font-mono text-xs">
            {events.map((evt) => (
              <div
                key={evt.id}
                className="p-3.5 space-y-1.5 hover:bg-[var(--bg-1)] transition-colors"
              >
                <div className="flex items-center justify-between text-[11px]">
                  <div className="flex items-center gap-2">
                    <span className="text-[var(--fg-3)] font-semibold">{`#${evt.seq}`}</span>
                    <span
                      className={`px-1.5 py-0.2 rounded text-[10px] uppercase font-mono ${
                        evt.kind === "approval_request"
                          ? "bg-[rgba(240,180,76,0.15)] text-[var(--warn)]"
                          : evt.kind === "error"
                            ? "bg-[rgba(255,107,94,0.15)] text-[var(--danger)]"
                            : "bg-[var(--bg-2)] text-[var(--fg-2)]"
                      }`}
                    >
                      {evt.kind}
                    </span>
                  </div>
                  <span className="text-[var(--fg-3)]">
                    {new Date(evt.createdAt).toLocaleTimeString()}
                  </span>
                </div>

                <div className="text-[var(--fg-1)] font-sans text-xs">{evt.message}</div>

                {evt.data && Object.keys(evt.data).length > 0 && (
                  <div className="bg-[var(--bg-1)] p-2 rounded-[var(--radius-sm)] border border-[var(--line-1)] text-[11px] text-[var(--fg-2)] space-y-0.5">
                    {Object.entries(evt.data).map(([k, v]) => (
                      <div key={k} className="flex items-start gap-2 font-mono">
                        <span className="text-[var(--fg-3)] shrink-0">{k}:</span>
                        <span className="text-[var(--fg-1)]">{String(v)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
