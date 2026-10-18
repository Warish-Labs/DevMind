"use client";

import React, { useState, useEffect } from "react";
import { apiClient } from "@/lib/api";
import { JobDetailView } from "./JobDetailView";
import { FloatingJobTray } from "./FloatingJobTray";
import { SAMPLE_JOBS_LIST, type JobWithDetails } from "./types";

export interface JobDetailPageClientProps {
  projectId: string;
  jobId: string;
}

export function JobDetailPageClient({ projectId, jobId }: JobDetailPageClientProps) {
  const [job, setJob] = useState<JobWithDetails | null>(() => {
    return SAMPLE_JOBS_LIST.find((j) => j.id === jobId) || SAMPLE_JOBS_LIST[0];
  });

  useEffect(() => {
    let active = true;
    apiClient
      .getJob(jobId)
      .then((item) => {
        if (active && item) {
          setJob((prev) => ({
            ...prev,
            ...item,
            events: prev?.events || [],
          }));
        }
      })
      .catch(() => {
        // Fallback to sample job
      });

    return () => {
      active = false;
    };
  }, [jobId]);

  const handleCancelJob = async (id: string) => {
    try {
      await apiClient.cancelJob(id);
      setJob((prev) => (prev ? { ...prev, status: "cancelled" } : null));
    } catch {
      setJob((prev) => (prev ? { ...prev, status: "cancelled" } : null));
    }
  };

  const handleApproveJob = async (id: string, approved: boolean) => {
    // Optimistic approval update
    setJob((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        status: approved ? "running" : "cancelled",
        events: [
          ...(prev.events || []),
          {
            id: `evt-approve-${Date.now()}`,
            jobId: id,
            seq: (prev.events?.length || 0) + 1,
            kind: approved ? "milestone" : "status",
            message: approved
              ? "Human approval granted by user. Proceeding with execution."
              : "Human approval rejected by user. Workflow terminated.",
            createdAt: new Date().toISOString(),
          },
        ],
      };
    });
  };

  if (!job) {
    return (
      <div className="p-8 text-center text-xs text-[var(--fg-2)] font-mono">Job not found.</div>
    );
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <JobDetailView
        projectId={projectId}
        initialJob={job}
        onCancelJob={handleCancelJob}
        onApproveJob={handleApproveJob}
      />

      <FloatingJobTray
        projectId={projectId}
        activeJobs={job ? [job] : []}
        onCancelJob={handleCancelJob}
      />
    </div>
  );
}
