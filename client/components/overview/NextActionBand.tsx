"use client";

import React from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { FindingsIcon, ExternalLinkIcon } from "@/components/shell/icons";
import type { FindingItem } from "@devmind/common/api";

interface NextActionBandProps {
  projectId: string;
  finding: FindingItem | null;
}

export function NextActionBand({ projectId, finding }: NextActionBandProps) {
  if (!finding) {
    return (
      <section
        aria-label="Next Action Recommendation"
        className="rounded-panel border border-[var(--line-1)] bg-[var(--bg-1)] p-4 sm:p-5 font-mono text-xs"
      >
        <div className="flex items-center justify-between mb-2 text-[10px] uppercase tracking-wider text-[var(--fg-2)]">
          <span className="flex items-center gap-2 text-[var(--signal)]">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--signal)]" />
            <span>Question 4 · What Should I Do Next?</span>
          </span>
          <span className="italic text-[10px] text-[var(--fg-2)]">
            rule-based until Project Mentor ships (1.3)
          </span>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-1">
          <div>
            <h2 className="text-sm font-semibold text-[var(--fg-0)]">
              No unresolved critical or high-severity findings
            </h2>
            <p className="text-xs text-[var(--fg-2)] mt-0.5 font-sans">
              Codebase matches all verified AST rules. You can trigger an incremental scan or start
              a project conversation.
            </p>
          </div>
          <Link href={`/projects/${projectId}/chat`}>
            <Button variant="secondary" size="sm">
              Ask Project Brain →
            </Button>
          </Link>
        </div>
      </section>
    );
  }

  const lineRef =
    finding.primary_start_line !== undefined && finding.primary_start_line !== null
      ? `#L${finding.primary_start_line}${
          finding.primary_end_line ? `-L${finding.primary_end_line}` : ""
        }`
      : "";

  return (
    <section
      aria-label="Next Action Recommendation"
      className="rounded-panel border-2 border-[var(--line-2)] hover:border-[var(--line-3)] bg-[var(--bg-1)] p-4 sm:p-5 font-mono text-xs transition-colors"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3 pb-2 border-b border-[var(--line-1)]">
        <div className="flex items-center gap-2">
          <FindingsIcon size={16} className="text-[var(--danger)]" />
          <span className="text-[10px] uppercase tracking-wider font-semibold text-[var(--fg-0)]">
            Question 4 · What Should I Do Next?
          </span>
          <span className="text-[var(--line-3)] hidden sm:inline">·</span>
          <span className="text-[10px] text-[var(--ref)]">Highest-priority finding to fix</span>
        </div>
        <span className="italic text-[10px] text-[var(--fg-2)]">
          rule-based until Project Mentor ships (1.3)
        </span>
      </div>

      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        {/* Finding Details */}
        <div className="space-y-1.5 flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge
              variant={
                finding.severity === "critical"
                  ? "danger"
                  : finding.severity === "high"
                    ? "warn"
                    : "neutral"
              }
              size="sm"
            >
              {finding.severity}
            </Badge>

            <Badge evidenceLevel={finding.evidence_level as "E0" | "E1" | "E2"} size="sm">
              {finding.evidence_level}
            </Badge>

            <span className="text-[11px] text-[var(--fg-2)]">
              Rule: <span className="text-[var(--fg-1)]">{finding.rule_id}</span>
            </span>
          </div>

          <h2 className="text-sm font-semibold text-[var(--fg-0)] tracking-tight truncate">
            {finding.title}
          </h2>

          <p className="text-xs text-[var(--fg-1)] font-sans line-clamp-2 leading-relaxed">
            {finding.summary || finding.explanation}
          </p>

          <div className="pt-1 flex items-center gap-2 text-[11px] text-[var(--fg-2)]">
            <span>Location:</span>
            <code className="px-1.5 py-0.5 rounded bg-[var(--bg-2)] border border-[var(--line-1)] text-[var(--ref)] truncate">
              {finding.primary_path}
              {lineRef}
            </code>
          </div>
        </div>

        {/* Action Button */}
        <div className="flex items-center gap-3 flex-shrink-0 pt-2 lg:pt-0">
          <Link href={`/projects/${projectId}/findings`}>
            <Button variant="primary" size="default" className="flex items-center gap-1.5">
              <span>Review Finding</span>
              <ExternalLinkIcon size={14} />
            </Button>
          </Link>
        </div>
      </div>
    </section>
  );
}
