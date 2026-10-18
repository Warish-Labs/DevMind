"use client";

import React from "react";
import { Badge } from "@/components/ui/Badge";
import { Tooltip } from "@/components/ui/Tooltip";
import type { ProjectHealthStats } from "./types";

interface CoverageHealthStripProps {
  stats: ProjectHealthStats;
}

export function CoverageHealthStrip({ stats }: CoverageHealthStripProps) {
  return (
    <section
      aria-label="Project Health and Analysis Coverage Strip"
      className="rounded-panel border border-[var(--line-1)] bg-[var(--bg-1)] p-4 font-mono text-xs"
    >
      <div className="flex items-center justify-between mb-3 text-[10px] uppercase tracking-wider text-[var(--fg-2)] border-b border-[var(--line-1)] pb-2">
        <span className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--signal)]" />
          <span>Question 5 · Is the Project Healthy?</span>
        </span>
        <span className="text-[var(--line-3)]">E0 Grounded Reality</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        {/* Metric 1: Security Score */}
        <div className="flex flex-col gap-1 p-2.5 rounded-control bg-[var(--bg-0)] border border-[var(--line-1)]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-[var(--fg-2)] font-sans">Security Score</span>
            <Badge variant="signal" size="sm">
              {`Grade ${stats.securityGrade}`}
            </Badge>
          </div>
          <div className="text-2xl font-bold tracking-tight text-[var(--signal)]">
            {stats.securityScore}
            <span className="text-xs text-[var(--fg-2)] font-normal"> / 100</span>
          </div>
          <div className="text-[10px] text-[var(--fg-2)]">Verified AST &amp; graph rules</div>
        </div>

        {/* Metric 2: Analysis Coverage */}
        <div className="flex flex-col gap-1 p-2.5 rounded-control bg-[var(--bg-0)] border border-[var(--line-1)]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-[var(--fg-2)] font-sans">Analysis Coverage</span>
            <span className="text-[10px] text-[var(--signal)]">Active</span>
          </div>
          <div className="text-2xl font-bold tracking-tight text-[var(--fg-0)]">
            {`${stats.analysisCoveragePct}%`}
          </div>
          <Tooltip
            content={`Tier 1 (AST): ${stats.tier1AstFiles} files · Tier 2 (Graph): ${stats.tier2GraphFiles} · Tier 3 (Semantics): ${stats.tier3SemanticsFiles}`}
            position="bottom"
          >
            <div className="text-[10px] text-[var(--fg-2)] truncate cursor-help underline decoration-dotted">
              {`${stats.analyzedFiles} of ${stats.totalFiles} files analyzed`}
            </div>
          </Tooltip>
        </div>

        {/* Metric 3: Reliability */}
        <div className="flex flex-col gap-1 p-2.5 rounded-control bg-[var(--bg-0)] border border-[var(--line-1)] opacity-75">
          <span className="text-[11px] text-[var(--fg-2)] font-sans">Reliability</span>
          <div className="text-base font-semibold text-[var(--fg-2)] pt-1">Not assessed</div>
          <div className="text-[10px] text-[var(--line-3)]">Release 1.2 target</div>
        </div>

        {/* Metric 4: Performance */}
        <div className="flex flex-col gap-1 p-2.5 rounded-control bg-[var(--bg-0)] border border-[var(--line-1)] opacity-75">
          <span className="text-[11px] text-[var(--fg-2)] font-sans">Performance</span>
          <div className="text-base font-semibold text-[var(--fg-2)] pt-1">Not assessed</div>
          <div className="text-[10px] text-[var(--line-3)]">Release 1.3 target</div>
        </div>

        {/* Metric 5: Documentation */}
        <div className="col-span-2 sm:col-span-1 flex flex-col gap-1 p-2.5 rounded-control bg-[var(--bg-0)] border border-[var(--line-1)] opacity-75">
          <span className="text-[11px] text-[var(--fg-2)] font-sans">Documentation</span>
          <div className="text-base font-semibold text-[var(--fg-2)] pt-1">Not assessed</div>
          <div className="text-[10px] text-[var(--line-3)]">Release 1.2 target</div>
        </div>
      </div>
    </section>
  );
}
