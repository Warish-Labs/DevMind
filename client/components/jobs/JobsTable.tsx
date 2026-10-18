"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import {
  type JobWithDetails,
  type JobFilterState,
  INITIAL_JOB_FILTER_STATE,
  getJobStatusBadgeVariant,
  formatJobType,
  formatDuration,
} from "./types";

export interface JobsTableProps {
  projectId: string;
  jobs: JobWithDetails[];
  onCancelJob?: (jobId: string) => Promise<void> | void;
  className?: string;
}

export function JobsTable({ projectId, jobs, onCancelJob, className = "" }: JobsTableProps) {
  const [filters, setFilters] = useState<JobFilterState>(INITIAL_JOB_FILTER_STATE);
  const [cancellingJobId, setCancellingJobId] = useState<string | null>(null);

  // Status counts
  const counts = useMemo(() => {
    const c = {
      all: jobs.length,
      running: 0,
      awaiting_approval: 0,
      succeeded: 0,
      failed: 0,
    };
    for (const j of jobs) {
      const s = j.status.toLowerCase();
      if (s === "running" || s === "queued") c.running++;
      else if (s === "awaiting_approval") c.awaiting_approval++;
      else if (s === "succeeded") c.succeeded++;
      else if (s === "failed" || s === "timed_out") c.failed++;
    }
    return c;
  }, [jobs]);

  // Unique job types
  const availableTypes = useMemo(() => {
    const set = new Set<string>();
    for (const j of jobs) {
      if (j.type) set.add(j.type);
    }
    return Array.from(set).sort();
  }, [jobs]);

  // Filtered jobs
  const filteredJobs = useMemo(() => {
    return jobs.filter((j) => {
      // Status filter
      if (filters.status !== "all") {
        const s = j.status.toLowerCase();
        if (filters.status === "running" && s !== "running" && s !== "queued") return false;
        if (filters.status === "awaiting_approval" && s !== "awaiting_approval") return false;
        if (filters.status === "succeeded" && s !== "succeeded") return false;
        if (filters.status === "failed" && s !== "failed" && s !== "timed_out") return false;
      }

      // Type filter
      if (filters.type !== "all") {
        if (j.type.toLowerCase() !== filters.type.toLowerCase()) return false;
      }

      // Query filter
      if (filters.query.trim()) {
        const q = filters.query.toLowerCase().trim();
        const typeStr = j.type.toLowerCase();
        const formattedType = formatJobType(j.type).toLowerCase();
        const idStr = j.id.toLowerCase();
        const errorStr = (j.error_code || "").toLowerCase();
        if (
          !typeStr.includes(q) &&
          !formattedType.includes(q) &&
          !idStr.includes(q) &&
          !errorStr.includes(q)
        ) {
          return false;
        }
      }

      return true;
    });
  }, [jobs, filters]);

  const handleCancel = async (jobId: string) => {
    if (!onCancelJob) return;
    try {
      setCancellingJobId(jobId);
      await onCancelJob(jobId);
    } finally {
      setCancellingJobId(null);
    }
  };

  const resetFilters = () => {
    setFilters(INITIAL_JOB_FILTER_STATE);
  };

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Filter Bar */}
      <div className="space-y-3 bg-[var(--bg-1)] p-4 rounded-[var(--radius-lg)] border border-[var(--line-1)]">
        {/* Status Pills */}
        <div className="flex flex-wrap items-center gap-1.5 border-b border-[var(--line-1)] pb-3">
          {[
            { id: "all", label: "All Jobs", count: counts.all },
            { id: "running", label: "Running / Queued", count: counts.running },
            {
              id: "awaiting_approval",
              label: "Awaiting Approval",
              count: counts.awaiting_approval,
            },
            { id: "succeeded", label: "Succeeded", count: counts.succeeded },
            { id: "failed", label: "Failed", count: counts.failed },
          ].map((pill) => {
            const isActive = filters.status === pill.id;
            return (
              <button
                key={pill.id}
                type="button"
                onClick={() => setFilters((prev) => ({ ...prev, status: pill.id }))}
                className={`px-3 py-1 rounded-[var(--radius-chip)] text-xs font-medium transition-colors flex items-center gap-1.5 ${
                  isActive
                    ? "bg-[var(--line-strong)] text-[var(--fg-0)]"
                    : "text-[var(--fg-2)] hover:text-[var(--fg-0)] hover:bg-[var(--bg-2)]"
                }`}
              >
                <span>{pill.label}</span>
                <span
                  className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                    isActive
                      ? "bg-[var(--bg-0)] text-[var(--fg-0)]"
                      : "bg-[var(--bg-2)] text-[var(--fg-2)]"
                  }`}
                >
                  {pill.count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Dropdown & Search Query */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
          <div className="lg:col-span-2">
            <div className="relative">
              <input
                type="text"
                value={filters.query}
                onChange={(e) => setFilters((prev) => ({ ...prev, query: e.target.value }))}
                placeholder="Search job type, ID, or error code..."
                className="w-full pl-8 pr-3 py-1.5 text-xs rounded-[var(--radius-sm)] bg-[var(--bg-2)] border border-[var(--line-1)] text-[var(--fg-0)] placeholder-[var(--fg-3)] focus:outline-none focus:border-[var(--ref)]"
              />
              <svg
                className="w-3.5 h-3.5 text-[var(--fg-3)] absolute left-2.5 top-2.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
            </div>
          </div>

          <div>
            <select
              value={filters.type}
              onChange={(e) => setFilters((prev) => ({ ...prev, type: e.target.value }))}
              aria-label="Filter by job type"
              className="w-full px-2.5 py-1.5 text-xs rounded-[var(--radius-sm)] bg-[var(--bg-2)] border border-[var(--line-1)] text-[var(--fg-0)] focus:outline-none focus:border-[var(--ref)]"
            >
              <option value="all">All Job Types</option>
              {availableTypes.map((t) => (
                <option key={t} value={t}>
                  {formatJobType(t)}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Summary Header */}
      <div className="flex items-center justify-between text-xs text-[var(--fg-2)] px-1">
        <div>
          Showing {`${filteredJobs.length}`} of {`${jobs.length}`} jobs
        </div>
        {(filters.status !== "all" || filters.type !== "all" || filters.query !== "") && (
          <button
            type="button"
            onClick={resetFilters}
            className="text-[var(--ref)] hover:underline text-xs"
          >
            Reset filters
          </button>
        )}
      </div>

      {/* Jobs Table */}
      {filteredJobs.length === 0 ? (
        <div className="p-8 text-center bg-[var(--bg-1)] border border-[var(--line-1)] rounded-[var(--radius-lg)] space-y-3">
          <div className="text-sm font-medium text-[var(--fg-0)]">No background jobs found</div>
          <div className="text-xs text-[var(--fg-2)]">
            {jobs.length === 0
              ? "No background jobs or agent workflows have been run for this project yet."
              : "No jobs match the current filter selection."}
          </div>
          {jobs.length > 0 && (
            <Button variant="secondary" size="sm" onClick={resetFilters}>
              Clear filters
            </Button>
          )}
        </div>
      ) : (
        <div className="border border-[var(--line-1)] rounded-[var(--radius-lg)] overflow-hidden bg-[var(--bg-0)]">
          {/* Desktop Table */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-[var(--bg-1)] border-b border-[var(--line-1)] text-[var(--fg-2)] select-none">
                  <th className="py-2.5 px-3 font-medium">Job Type &amp; ID</th>
                  <th className="py-2.5 px-3 font-medium w-32">Status</th>
                  <th className="py-2.5 px-3 font-medium w-40">Progress</th>
                  <th className="py-2.5 px-3 font-medium w-20">Attempt</th>
                  <th className="py-2.5 px-3 font-medium w-28">Duration</th>
                  <th className="py-2.5 px-3 font-medium w-36 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--line-1)]">
                {filteredJobs.map((job) => {
                  const isRunning = job.status === "running" || job.status === "queued";
                  const isAwaiting = job.status === "awaiting_approval";
                  const isCancelling = cancellingJobId === job.id;
                  const progress = job.progressPct ?? (job.status === "succeeded" ? 100 : 0);

                  return (
                    <tr key={job.id} className="hover:bg-[var(--bg-1)] transition-colors group">
                      {/* Job Type & ID */}
                      <td className="py-2.5 px-3 align-top">
                        <div className="space-y-0.5">
                          <Link
                            href={`/projects/${projectId}/jobs/${job.id}`}
                            className="text-xs font-semibold text-[var(--fg-0)] hover:text-[var(--ref)] block"
                          >
                            {formatJobType(job.type)}
                          </Link>
                          <div className="font-mono text-[10px] text-[var(--fg-3)] flex items-center gap-1.5">
                            <span>ID: {job.id.substring(0, 8)}...</span>
                            <span>·</span>
                            <span>queue: {job.queue || "default"}</span>
                          </div>
                          {job.error_code && (
                            <div className="text-[10px] text-[var(--danger)] font-mono">
                              Error: {job.error_code}
                            </div>
                          )}
                        </div>
                      </td>

                      {/* Status */}
                      <td className="py-2.5 px-3 align-top">
                        <Badge variant={getJobStatusBadgeVariant(job.status)} size="sm">
                          {job.status.replace(/_/g, " ")}
                        </Badge>
                      </td>

                      {/* Progress Bar */}
                      <td className="py-2.5 px-3 align-top">
                        <div className="space-y-1">
                          <div className="flex items-center justify-between text-[10px] font-mono text-[var(--fg-2)]">
                            <span>{progress}%</span>
                            {isRunning && (
                              <span className="text-[var(--ref)] animate-pulse">active</span>
                            )}
                          </div>
                          <div className="h-1.5 w-full bg-[var(--bg-2)] rounded-full overflow-hidden border border-[var(--line-1)]">
                            <div
                              className={`h-full transition-all duration-300 ${
                                job.status === "failed"
                                  ? "bg-[var(--danger)]"
                                  : job.status === "awaiting_approval"
                                    ? "bg-[var(--warn)]"
                                    : "bg-[var(--signal)]"
                              }`}
                              style={{ width: `${progress}%` }}
                            />
                          </div>
                        </div>
                      </td>

                      {/* Attempt */}
                      <td className="py-2.5 px-3 align-top font-mono text-[11px] text-[var(--fg-2)]">
                        {job.attempt || 1} / {job.max_attempts || 3}
                      </td>

                      {/* Duration */}
                      <td className="py-2.5 px-3 align-top font-mono text-[11px] text-[var(--fg-2)]">
                        {formatDuration(job.started_at, job.finished_at)}
                      </td>

                      {/* Actions */}
                      <td className="py-2.5 px-3 align-top text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Link
                            href={`/projects/${projectId}/jobs/${job.id}`}
                            className="px-2 py-0.5 text-[11px] rounded-[var(--radius-sm)] border border-[var(--line-1)] text-[var(--fg-1)] hover:bg-[var(--bg-2)] transition-colors"
                          >
                            {isAwaiting ? "Review" : "View"}
                          </Link>

                          {(isRunning || isAwaiting) && (
                            <button
                              type="button"
                              disabled={isCancelling}
                              onClick={() => handleCancel(job.id)}
                              className="px-2 py-0.5 text-[11px] rounded-[var(--radius-sm)] border border-[var(--line-1)] text-[var(--danger)] hover:bg-[rgba(255,107,94,0.1)] transition-colors"
                            >
                              {isCancelling ? "Cancelling..." : "Cancel"}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile Collapsed Cards */}
          <div className="md:hidden divide-y divide-[var(--line-1)]">
            {filteredJobs.map((job) => (
              <div key={job.id} className="p-3 space-y-2 hover:bg-[var(--bg-1)]">
                <div className="flex items-center justify-between">
                  <Link
                    href={`/projects/${projectId}/jobs/${job.id}`}
                    className="text-xs font-semibold text-[var(--fg-0)] hover:text-[var(--ref)]"
                  >
                    {formatJobType(job.type)}
                  </Link>
                  <Badge variant={getJobStatusBadgeVariant(job.status)} size="sm">
                    {job.status.replace(/_/g, " ")}
                  </Badge>
                </div>

                <div className="flex items-center justify-between text-[11px] text-[var(--fg-2)] font-mono">
                  <span>Duration: {formatDuration(job.started_at, job.finished_at)}</span>
                  <span>
                    Attempt: {job.attempt || 1}/{job.max_attempts || 3}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
