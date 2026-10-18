"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useApp } from "@/context/AppContext";
import { CoverageHealthStrip } from "./CoverageHealthStrip";
import { NextActionBand } from "./NextActionBand";
import { FindingsPanel } from "./FindingsPanel";
import { ActivityPanel } from "./ActivityPanel";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { BrainIcon, ChatIcon, SettingsIcon, FolderIcon } from "@/components/shell/icons";
import {
  SAMPLE_FINDINGS,
  SAMPLE_HEALTH_STATS,
  SAMPLE_SCANS,
  SAMPLE_JOBS,
  getHighestPriorityFinding,
} from "./types";
import type { FindingItem } from "@devmind/common/api";

interface ProjectOverviewProps {
  projectId: string;
}

export function ProjectOverview({ projectId }: ProjectOverviewProps) {
  const { currentProject, syncMode, setScanStatus } = useApp();

  const [findings, setFindings] = useState<FindingItem[]>(SAMPLE_FINDINGS);
  const [findingsLoading] = useState(false);
  const [findingsError, setFindingsError] = useState<string | null>(null);

  const [activityLoading] = useState(false);
  const [activityError, setActivityError] = useState<string | null>(null);

  // Sync active project if matching
  const project = currentProject?.id === projectId ? currentProject : currentProject;
  const projectName = project?.name || "DevMind Core";
  const projectSlug = project?.slug || "devmind-core";
  const primaryLanguage = project?.primary_language || "TypeScript";
  const defaultBranch = project?.default_branch || "main";

  // Derive highest-priority finding deterministically
  const highestPriorityFinding = getHighestPriorityFinding(
    findings.filter((f) => f.status === "open")
  );

  const handleTriggerScan = () => {
    setScanStatus("Scanning 42 files (Tier 1 AST)...");
    setTimeout(() => {
      setScanStatus("Scan complete · 42 files up to date");
    }, 2000);
  };

  return (
    <div className="space-y-6 font-mono text-xs">
      {/* S-04 Screen Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[var(--line-1)]">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-[var(--fg-2)]">
            <Link href="/projects" className="hover:text-[var(--fg-0)] hover:underline">
              Projects
            </Link>
            <span className="text-[var(--line-3)]">/</span>
            <span className="text-[var(--signal)]">S-04 Project Overview</span>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl sm:text-2xl font-bold text-[var(--fg-0)] tracking-tight flex items-center gap-2">
              <FolderIcon size={22} className="text-[var(--signal)]" />
              <span>{projectName}</span>
            </h1>

            <Badge variant={syncMode === "indexed" ? "signal" : "warn"} size="sm">
              {syncMode}
            </Badge>

            <span className="text-xs text-[var(--fg-2)]">
              {projectSlug} · {primaryLanguage} · branch:{" "}
              <code className="text-[var(--ref)]">{defaultBranch}</code>
            </span>
          </div>
        </div>

        {/* Quick Screen Actions */}
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={handleTriggerScan}
            className="flex items-center gap-1.5"
          >
            <BrainIcon size={14} />
            <span>Scan AST</span>
          </Button>

          <Link href={`/projects/${projectId}/chat`}>
            <Button variant="primary" size="sm" className="flex items-center gap-1.5">
              <ChatIcon size={14} />
              <span>Ask Project</span>
            </Button>
          </Link>

          <Link href={`/projects/${projectId}/settings`}>
            <Button variant="tertiary" size="sm" aria-label="Project Settings" className="p-2">
              <SettingsIcon size={16} />
            </Button>
          </Link>
        </div>
      </div>

      {/* Top Strip: Question 5 · Is the Project Healthy? */}
      <CoverageHealthStrip stats={SAMPLE_HEALTH_STATS} />

      {/* Next-Action Band: Question 4 · What Should I Do Next? */}
      {/* Rendered first on mobile, full width on desktop */}
      <NextActionBand projectId={projectId} finding={highestPriorityFinding} />

      {/* Two-Column Grid: Questions 2 & 3 (Findings) + Question 1 (Activity) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Questions 2 & 3 · Findings & Risks (7 cols) */}
        <div className="lg:col-span-7">
          <FindingsPanel
            projectId={projectId}
            findings={findings}
            isLoading={findingsLoading}
            error={findingsError}
            onRetry={() => {
              setFindingsError(null);
              setFindings(SAMPLE_FINDINGS);
            }}
          />
        </div>

        {/* Right Column: Question 1 · Scans, Jobs & Activity (5 cols) */}
        <div className="lg:col-span-5">
          <ActivityPanel
            projectId={projectId}
            syncMode={syncMode}
            scans={SAMPLE_SCANS}
            jobs={SAMPLE_JOBS}
            lastSyncAt={SAMPLE_SCANS[0]?.createdAt}
            isLoading={activityLoading}
            error={activityError}
            onRetry={() => {
              setActivityError(null);
            }}
            onTriggerScan={handleTriggerScan}
          />
        </div>
      </div>
    </div>
  );
}
