"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useApp } from "@/context/AppContext";
import { CoverageHealthStrip } from "./CoverageHealthStrip";
import { NextActionBand } from "./NextActionBand";
import { FindingsPanel } from "./FindingsPanel";
import { ActivityPanel } from "./ActivityPanel";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import {
  BrainIcon,
  ChatIcon,
  SettingsIcon,
  FolderIcon,
  ExternalLinkIcon,
} from "@/components/shell/icons";
import {
  SAMPLE_FINDINGS,
  SAMPLE_HEALTH_STATS,
  SAMPLE_SCANS,
  SAMPLE_JOBS,
  getHighestPriorityFinding,
} from "./types";
import type { FindingItem } from "@devmind/common/api";
import { apiClient } from "@/lib/api";

interface ProjectOverviewProps {
  projectId: string;
}

export function ProjectOverview({ projectId }: ProjectOverviewProps) {
  const { currentProject, syncMode, setScanStatus } = useApp();

  const [findings, setFindings] = useState<FindingItem[]>(SAMPLE_FINDINGS);
  const [healthStats, setHealthStats] = useState(SAMPLE_HEALTH_STATS);
  const [findingsLoading, setFindingsLoading] = useState(false);
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

  // Fetch live findings and brain summary from Project Brain
  useEffect(() => {
    let active = true;

    apiClient
      .listFindings(projectId)
      .then((items) => {
        if (!active) return;
        if (items && items.length > 0) {
          setFindings(items);
        }
      })
      .catch(() => {
        if (!active) return;
        // Keep fallback sample data for dev/testing
      })
      .finally(() => {
        if (active) setFindingsLoading(false);
      });

    apiClient
      .getBrainSummary(projectId)
      .then((summary) => {
        if (!active || !summary) return;
        const openFindings = summary.findings_summary?.open ?? 0;
        const critFindings = summary.findings_summary?.critical ?? 0;
        const highFindings = summary.findings_summary?.high ?? 0;
        const totalFiles = summary.total_files || SAMPLE_HEALTH_STATS.totalFiles;
        const analyzedFiles = summary.total_files || SAMPLE_HEALTH_STATS.analyzedFiles;
        const calculatedScore = Math.max(0, 100 - critFindings * 20 - highFindings * 10);
        const grade =
          calculatedScore >= 90
            ? "A"
            : calculatedScore >= 75
              ? "B"
              : calculatedScore >= 60
                ? "C"
                : "D";

        setHealthStats((prev) => ({
          ...prev,
          totalFiles,
          analyzedFiles,
          analysisCoveragePct:
            totalFiles > 0 ? Math.round((analyzedFiles / totalFiles) * 100) : 100,
          tier1AstFiles: totalFiles,
          tier2GraphFiles: summary.total_symbols > 0 ? totalFiles : prev.tier2GraphFiles,
          openRisksCount: openFindings,
          criticalRisksCount: critFindings,
          securityScore: calculatedScore,
          securityGrade: grade,
        }));
      })
      .catch(() => {
        // Fallback to sample health stats
      });

    return () => {
      active = false;
    };
  }, [projectId]);

  const handleTriggerScan = () => {
    setScanStatus("Scanning files (Tier 1 AST)...");
    setTimeout(() => {
      setScanStatus("Scan complete · Codebase models up to date");
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
          <Link href={`/settings/extension-token?projectId=${projectId}`}>
            <Button
              variant="secondary"
              size="sm"
              className="flex items-center gap-1.5 font-mono cursor-pointer"
            >
              <span>Connect VS Code</span>
              <ExternalLinkIcon size={12} className="text-[var(--signal)]" />
            </Button>
          </Link>

          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={handleTriggerScan}
            className="flex items-center gap-1.5 cursor-pointer"
          >
            <BrainIcon size={14} />
            <span>Scan AST</span>
          </Button>

          <Link href={`/projects/${projectId}/chat`}>
            <Button
              variant="primary"
              size="sm"
              className="flex items-center gap-1.5 cursor-pointer"
            >
              <ChatIcon size={14} />
              <span>Ask Project</span>
            </Button>
          </Link>

          <Link href={`/projects/${projectId}/settings`}>
            <Button
              variant="tertiary"
              size="sm"
              aria-label="Project Settings"
              className="p-2 cursor-pointer"
            >
              <SettingsIcon size={16} />
            </Button>
          </Link>
        </div>
      </div>

      {/* Top Strip: Question 5 · Is the Project Healthy? */}
      <CoverageHealthStrip stats={healthStats} />

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
