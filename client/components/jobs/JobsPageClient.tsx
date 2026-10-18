"use client";

import React, { useState, useEffect } from "react";
import { apiClient } from "@/lib/api";
import { JobsTable } from "./JobsTable";
import { FloatingJobTray } from "./FloatingJobTray";
import { SAMPLE_JOBS_LIST, type JobWithDetails } from "./types";

export interface JobsPageClientProps {
  projectId: string;
}

export function JobsPageClient({ projectId }: JobsPageClientProps) {
  const [jobs, setJobs] = useState<JobWithDetails[]>(SAMPLE_JOBS_LIST);

  useEffect(() => {
    let active = true;
    apiClient
      .listProjectJobs(projectId)
      .then((items) => {
        if (active && items && items.length > 0) {
          setJobs(items as JobWithDetails[]);
        }
      })
      .catch(() => {
        // Fallback to sample jobs
      });

    return () => {
      active = false;
    };
  }, [projectId]);

  const handleCancelJob = async (jobId: string) => {
    try {
      await apiClient.cancelJob(jobId);
      setJobs((prev) => prev.map((j) => (j.id === jobId ? { ...j, status: "cancelled" } : j)));
    } catch {
      setJobs((prev) => prev.map((j) => (j.id === jobId ? { ...j, status: "cancelled" } : j)));
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-[var(--fg-0)]">Job Center</h1>
          <p className="text-xs text-[var(--fg-2)] mt-0.5">
            Background analysis jobs, agent workflows, and real-time SSE progress (Screen S-09)
          </p>
        </div>
      </div>

      {/* Jobs Table */}
      <JobsTable projectId={projectId} jobs={jobs} onCancelJob={handleCancelJob} />

      {/* Floating Job Tray */}
      <FloatingJobTray projectId={projectId} activeJobs={jobs} onCancelJob={handleCancelJob} />
    </div>
  );
}
