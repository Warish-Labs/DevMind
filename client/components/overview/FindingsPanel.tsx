"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { ExternalLinkIcon } from "@/components/shell/icons";
import type { FindingItem } from "@devmind/common/api";

interface FindingsPanelProps {
  projectId: string;
  findings: FindingItem[];
  isLoading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

export function FindingsPanel({
  projectId,
  findings,
  isLoading = false,
  error = null,
  onRetry,
}: FindingsPanelProps) {
  const [filterSeverity, setFilterSeverity] = useState<string>("all");

  if (isLoading) {
    return (
      <div className="rounded-panel border border-[var(--line-1)] bg-[var(--bg-1)] p-5 space-y-4">
        <Skeleton className="h-6 w-1/3" />
        <div className="grid grid-cols-4 gap-2">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-panel border border-[var(--danger)]/40 bg-[var(--danger)]/5 p-5 font-mono text-xs space-y-3">
        <div className="flex items-center gap-2 text-[var(--danger)] font-semibold">
          <span>Failed to load findings</span>
        </div>
        <p className="text-[var(--fg-1)] text-xs">{error}</p>
        {onRetry && (
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Retry Findings
          </Button>
        )}
      </div>
    );
  }

  // Count severities
  const counts = {
    critical: findings.filter((f) => f.severity === "critical" && f.status === "open").length,
    high: findings.filter((f) => f.severity === "high" && f.status === "open").length,
    medium: findings.filter((f) => f.severity === "medium" && f.status === "open").length,
    low: findings.filter((f) => f.severity === "low" && f.status === "open").length,
  };

  const filtered = findings.filter(
    (f) => filterSeverity === "all" || f.severity === filterSeverity
  );

  return (
    <div className="rounded-panel border border-[var(--line-1)] bg-[var(--bg-1)] p-4 sm:p-5 font-mono text-xs space-y-5">
      {/* Question 2: What is broken? */}
      <div>
        <div className="flex items-center justify-between pb-2 border-b border-[var(--line-1)] mb-3">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--warn)]" />
            <span className="text-[10px] uppercase tracking-wider font-semibold text-[var(--fg-0)]">
              Question 2 · What Is Broken?
            </span>
          </div>
          <span className="text-[10px] text-[var(--fg-2)]">Open Findings</span>
        </div>

        {/* Severity Metrics Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
          <button
            type="button"
            onClick={() => setFilterSeverity(filterSeverity === "critical" ? "all" : "critical")}
            className={`p-2 rounded-control text-left border transition-colors cursor-pointer ${
              filterSeverity === "critical"
                ? "border-[var(--danger)] bg-[var(--bg-2)]"
                : "border-[var(--line-1)] bg-[var(--bg-0)] hover:border-[var(--line-2)]"
            }`}
          >
            <div className="flex items-center justify-between text-[10px] text-[var(--fg-2)] mb-1">
              <span>Critical</span>
              <span className="text-[var(--danger)]">✕</span>
            </div>
            <div className="text-xl font-bold text-[var(--danger)]">{counts.critical}</div>
          </button>

          <button
            type="button"
            onClick={() => setFilterSeverity(filterSeverity === "high" ? "all" : "high")}
            className={`p-2 rounded-control text-left border transition-colors cursor-pointer ${
              filterSeverity === "high"
                ? "border-[var(--warn)] bg-[var(--bg-2)]"
                : "border-[var(--line-1)] bg-[var(--bg-0)] hover:border-[var(--line-2)]"
            }`}
          >
            <div className="flex items-center justify-between text-[10px] text-[var(--fg-2)] mb-1">
              <span>High</span>
              <span className="text-[var(--warn)]">▲</span>
            </div>
            <div className="text-xl font-bold text-[var(--warn)]">{counts.high}</div>
          </button>

          <button
            type="button"
            onClick={() => setFilterSeverity(filterSeverity === "medium" ? "all" : "medium")}
            className={`p-2 rounded-control text-left border transition-colors cursor-pointer ${
              filterSeverity === "medium"
                ? "border-[var(--ref)] bg-[var(--bg-2)]"
                : "border-[var(--line-1)] bg-[var(--bg-0)] hover:border-[var(--line-2)]"
            }`}
          >
            <div className="flex items-center justify-between text-[10px] text-[var(--fg-2)] mb-1">
              <span>Medium</span>
              <span className="text-[var(--ref)]">◆</span>
            </div>
            <div className="text-xl font-bold text-[var(--ref)]">{counts.medium}</div>
          </button>

          <button
            type="button"
            onClick={() => setFilterSeverity(filterSeverity === "low" ? "all" : "low")}
            className={`p-2 rounded-control text-left border transition-colors cursor-pointer ${
              filterSeverity === "low"
                ? "border-[var(--line-3)] bg-[var(--bg-2)]"
                : "border-[var(--line-1)] bg-[var(--bg-0)] hover:border-[var(--line-2)]"
            }`}
          >
            <div className="flex items-center justify-between text-[10px] text-[var(--fg-2)] mb-1">
              <span>Low</span>
              <span className="text-[var(--fg-2)]">●</span>
            </div>
            <div className="text-xl font-bold text-[var(--fg-1)]">{counts.low}</div>
          </button>
        </div>

        {/* Bug Memory release label per docs/08 §11 S-04 */}
        <div className="mt-2.5 px-3 py-1.5 rounded-control bg-[var(--bg-0)] border border-[var(--line-1)] flex items-center justify-between text-[11px] text-[var(--fg-2)]">
          <span>Bug Memory: 0 known regressions</span>
          <span className="italic text-[10px] text-[var(--line-3)]">ships in 1.2</span>
        </div>
      </div>

      {/* Question 3: What is risky? */}
      <div>
        <div className="flex items-center justify-between pb-2 border-b border-[var(--line-1)] mb-3">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--danger)]" />
            <span className="text-[10px] uppercase tracking-wider font-semibold text-[var(--fg-0)]">
              Question 3 · What Is Risky?
            </span>
          </div>
          <Link
            href={`/projects/${projectId}/findings`}
            className="text-[10px] text-[var(--ref)] hover:underline"
          >
            View all ({findings.length}) →
          </Link>
        </div>

        {filtered.length === 0 ? (
          <div className="py-6 text-center text-xs text-[var(--fg-2)]">
            No open findings match the selected severity filter.
          </div>
        ) : (
          <div className="space-y-2">
            {filtered.slice(0, 4).map((f) => {
              const lineRef =
                f.primary_start_line !== undefined && f.primary_start_line !== null
                  ? `#L${f.primary_start_line}${f.primary_end_line ? `-L${f.primary_end_line}` : ""}`
                  : "";

              return (
                <div
                  key={f.id}
                  className="p-3 rounded-control border border-[var(--line-1)] bg-[var(--bg-0)] hover:border-[var(--line-2)] transition-colors group space-y-1.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 truncate">
                      <Badge
                        variant={
                          f.severity === "critical"
                            ? "danger"
                            : f.severity === "high"
                              ? "warn"
                              : "neutral"
                        }
                        size="sm"
                      >
                        {f.severity}
                      </Badge>

                      <Badge evidenceLevel={f.evidence_level as "E0" | "E1" | "E2"} size="sm">
                        {f.evidence_level}
                      </Badge>

                      <span className="text-xs font-semibold text-[var(--fg-0)] group-hover:text-[var(--signal)] transition-colors truncate">
                        {f.title}
                      </span>
                    </div>

                    <Link
                      href={`/projects/${projectId}/findings`}
                      aria-label={`View finding ${f.title}`}
                      className="text-[var(--fg-2)] group-hover:text-[var(--fg-0)] flex-shrink-0"
                    >
                      <ExternalLinkIcon size={12} />
                    </Link>
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-[var(--fg-2)]">
                    <code className="text-[10px] text-[var(--ref)] truncate max-w-xs">
                      {f.primary_path}
                      {lineRef}
                    </code>
                    <span>Confidence: {f.confidence}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
