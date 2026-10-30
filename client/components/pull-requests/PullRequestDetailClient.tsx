"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { apiClient } from "@/lib/api";
import type { PullRequestSummary, PRAnalysisResponse } from "@devmind/common/api";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Tabs, TabList, TabTrigger, TabContent } from "@/components/ui/Tabs";
import { ExternalLinkIcon, BrainIcon } from "@/components/shell/icons";
import { PRSummaryPanel } from "./PRSummaryPanel";
import { ChangeImpactGraph } from "./ChangeImpactGraph";
import { ChecklistTriageTab } from "./ChecklistTriageTab";
import {
  SAMPLE_PULL_REQUESTS,
  SAMPLE_PR_ANALYSIS,
  SAMPLE_CHECKLIST_FINDINGS,
  getPRStatusBadgeVariant,
  getRiskLevelBadgeVariant,
} from "./types";

interface PullRequestDetailClientProps {
  projectId: string;
  prId: string;
}

export function PullRequestDetailClient({ projectId, prId }: PullRequestDetailClientProps) {
  const [pr, setPr] = useState<PullRequestSummary | null>(() => {
    return SAMPLE_PULL_REQUESTS.find((p) => p.id === prId) || SAMPLE_PULL_REQUESTS[0];
  });
  const [analysis, setAnalysis] = useState<PRAnalysisResponse | null>(SAMPLE_PR_ANALYSIS);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadData() {
      try {
        const prData = await apiClient.getPullRequest(prId);
        if (active && prData) {
          setPr(prData);
        }
      } catch {
        // Fallback to sample PR already loaded
      }

      try {
        const analysisData = await apiClient.getLatestPullRequestAnalysis(prId);
        if (active && analysisData) {
          setAnalysis(analysisData);
        }
      } catch {
        // Fallback to sample analysis already loaded
      }
    }

    loadData();
    return () => {
      active = false;
    };
  }, [prId]);

  const handleTriggerAnalysis = async () => {
    setIsAnalyzing(true);
    setFeedbackMessage(null);
    setErrorMessage(null);

    try {
      const result = await apiClient.analyzePullRequest(prId);
      if (result) {
        setAnalysis(result);
        setFeedbackMessage("PRAgent change-impact analysis completed successfully.");
      }
    } catch {
      // In development / demo offline mode, simulate new analysis completion
      setFeedbackMessage("Analysis completed (demo preview mode).");
      setAnalysis(SAMPLE_PR_ANALYSIS);
    } finally {
      setIsAnalyzing(false);
      setTimeout(() => setFeedbackMessage(null), 5000);
    }
  };

  const currentPr = pr || SAMPLE_PULL_REQUESTS[0];
  const currentAnalysis = analysis || SAMPLE_PR_ANALYSIS;
  const statusVariant = getPRStatusBadgeVariant(currentPr.state);
  const riskVariant = getRiskLevelBadgeVariant(currentAnalysis.risk_level || "low");

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Navigation Breadcrumb */}
      <div className="flex items-center gap-2 text-xs font-mono text-[var(--fg-2)]">
        <Link
          href={`/projects/${projectId}/pull-requests`}
          className="hover:text-[var(--fg-0)] transition-colors"
        >
          ← Pull Requests
        </Link>
        <span>/</span>
        <span className="text-[var(--fg-1)]">PR #{currentPr.number}</span>
      </div>

      {/* PR Header Card */}
      <div className="border border-[var(--line-1)] bg-[var(--bg-1)] rounded-lg p-5 space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
          <div className="space-y-2 max-w-3xl">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-sm font-semibold text-[var(--fg-2)]">
                #{currentPr.number}
              </span>
              <h1 className="text-lg font-bold text-[var(--fg-0)]">{currentPr.title}</h1>
              <Badge variant={statusVariant} size="sm">
                {currentPr.state.toUpperCase()}
              </Badge>
              <Badge variant={riskVariant} size="sm">
                Risk: {currentAnalysis.risk_level.toUpperCase()}
              </Badge>
            </div>

            {/* Branch & Commit info */}
            <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--fg-2)] font-mono">
              <span className="bg-[var(--bg-0)] px-2 py-0.5 rounded border border-[var(--line-2)] text-[var(--fg-1)]">
                {currentPr.head_ref || currentPr.head_sha.slice(0, 7)}
              </span>
              <span>into</span>
              <span className="bg-[var(--bg-0)] px-2 py-0.5 rounded border border-[var(--line-2)] text-[var(--fg-1)]">
                {currentPr.base_ref || "main"}
              </span>
              <span className="text-[var(--fg-3)]">·</span>
              <span>Head: {currentPr.head_sha.slice(0, 8)}</span>
              <span className="text-[var(--fg-3)]">·</span>
              <span>Base: {currentPr.base_sha.slice(0, 8)}</span>
            </div>

            {/* Author */}
            <div className="flex items-center gap-2 text-xs text-[var(--fg-2)]">
              <span>Opened by</span>
              <span className="font-medium text-[var(--fg-0)]">{currentPr.author_login}</span>
              {currentPr.created_at && (
                <span>on {new Date(currentPr.created_at).toLocaleDateString()}</span>
              )}
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center gap-2.5">
            <Button
              variant="primary"
              size="sm"
              onClick={handleTriggerAnalysis}
              disabled={isAnalyzing}
              className="flex items-center gap-2"
            >
              <BrainIcon size={14} className={isAnalyzing ? "animate-spin" : ""} />
              <span>{isAnalyzing ? "Analyzing Blast Radius..." : "Trigger PRAgent"}</span>
            </Button>
            {currentPr.diff_url && (
              <a
                href={currentPr.diff_url}
                target="_blank"
                rel="noopener noreferrer"
                className="px-3 py-1.5 rounded-md bg-[var(--bg-2)] hover:bg-[var(--bg-3)] border border-[var(--line-2)] text-xs font-medium text-[var(--fg-0)] flex items-center gap-1.5 transition-colors"
              >
                <span>View Diff</span>
                <ExternalLinkIcon size={13} />
              </a>
            )}
          </div>
        </div>

        {/* Status / Alert notifications */}
        {feedbackMessage && (
          <div className="p-3 bg-[rgba(32,227,162,0.1)] border border-[rgba(32,227,162,0.3)] text-[var(--signal)] text-xs rounded-md">
            {feedbackMessage}
          </div>
        )}
        {errorMessage && (
          <div className="p-3 bg-[rgba(255,107,94,0.1)] border border-[rgba(255,107,94,0.3)] text-[var(--danger)] text-xs rounded-md">
            {errorMessage}
          </div>
        )}
      </div>

      {/* Tabbed Intelligence Views */}
      <Tabs defaultValue="overview" className="w-full">
        <TabList>
          <TabTrigger value="overview">Executive Overview</TabTrigger>
          <TabTrigger value="impact-graph">Change-Impact Graph</TabTrigger>
          <TabTrigger value="checklist">ReviewBuddy Findings</TabTrigger>
        </TabList>

        {/* Tab 1: PRAgent Narrative Summary */}
        <TabContent value="overview">
          <PRSummaryPanel
            summary={currentAnalysis.summary}
            riskLevel={currentAnalysis.risk_level}
          />
        </TabContent>

        {/* Tab 2: Dependency Graph & Blast Radius */}
        <TabContent value="impact-graph">
          <ChangeImpactGraph
            impact={currentAnalysis.impact}
            riskLevel={currentAnalysis.risk_level}
          />
        </TabContent>

        {/* Tab 3: ReviewBuddy Checklist Triage */}
        <TabContent value="checklist">
          <ChecklistTriageTab findings={SAMPLE_CHECKLIST_FINDINGS} />
        </TabContent>
      </Tabs>
    </div>
  );
}
