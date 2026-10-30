"use client";

import React from "react";
import type { PRSummary } from "@devmind/common/api";
import { Badge } from "@/components/ui/Badge";
import { getRiskLevelBadgeVariant } from "./types";

interface PRSummaryPanelProps {
  summary: PRSummary | Record<string, unknown>;
  riskLevel: string;
}

export function PRSummaryPanel({ summary, riskLevel }: PRSummaryPanelProps) {
  const riskVariant = getRiskLevelBadgeVariant(riskLevel);

  const purpose = (summary as Partial<PRSummary>).purpose || "No narrative summary generated yet.";
  const filesChanged = ((summary as Partial<PRSummary>).files_changed as string[]) || [];
  const affectedAreas = ((summary as Partial<PRSummary>).affected_areas as string[]) || [];
  const risks = ((summary as Partial<PRSummary>).risks as string[]) || [];
  const securitySummary =
    (summary as Partial<PRSummary>).security_summary || "No security implications identified.";
  const testingConcerns = ((summary as Partial<PRSummary>).testing_concerns as string[]) || [];
  const docImpact = (summary as Partial<PRSummary>).documentation_impact || "None identified.";

  return (
    <div className="space-y-6">
      {/* Risk & Purpose Header Card */}
      <div className="border border-[var(--line-1)] bg-[var(--bg-1)] rounded-lg p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[var(--line-1)]">
          <div>
            <h3 className="text-sm font-semibold text-[var(--fg-0)]">PRAgent Executive Summary</h3>
            <p className="text-xs text-[var(--fg-2)] mt-0.5">
              Automated multi-perspective reasoning synthesized from diff and dependency graph
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-[var(--fg-2)] font-mono">Assessed Risk:</span>
            <Badge variant={riskVariant} size="md">
              {riskLevel.toUpperCase()}
            </Badge>
          </div>
        </div>

        <div className="mt-4">
          <h4 className="text-xs font-mono text-[var(--fg-2)] uppercase tracking-wider mb-1.5">
            Purpose & Intent
          </h4>
          <p className="text-xs text-[var(--fg-0)] leading-relaxed bg-[var(--bg-0)] p-3 rounded-md border border-[var(--line-1)]">
            {purpose}
          </p>
        </div>
      </div>

      {/* Grid of Key Perspectives */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Security Assessment */}
        <div className="border border-[var(--line-1)] bg-[var(--bg-1)] rounded-lg p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-2 mb-2 border-b border-[var(--line-1)]">
              <span className="text-xs font-semibold text-[var(--fg-0)]">Security Assessment</span>
              <Badge variant="signal" size="sm">
                E1 Verified
              </Badge>
            </div>
            <p className="text-xs text-[var(--fg-1)] leading-relaxed">{securitySummary}</p>
          </div>
          {risks.length > 0 && (
            <div className="mt-3 pt-3 border-t border-[var(--line-1)]">
              <span className="text-[11px] font-mono text-[var(--warn)] uppercase">Key Risks:</span>
              <ul className="mt-1 list-disc list-inside text-xs text-[var(--fg-2)] space-y-1">
                {risks.map((risk, idx) => (
                  <li key={idx} className="leading-snug">
                    {risk}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Testing & Verification Concerns */}
        <div className="border border-[var(--line-1)] bg-[var(--bg-1)] rounded-lg p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-2 mb-2 border-b border-[var(--line-1)]">
              <span className="text-xs font-semibold text-[var(--fg-0)]">Testing Concerns</span>
              <Badge variant="neutral" size="sm">
                Gaps & Flakiness
              </Badge>
            </div>
            {testingConcerns.length > 0 ? (
              <ul className="list-disc list-inside text-xs text-[var(--fg-1)] space-y-1.5 leading-relaxed">
                {testingConcerns.map((concern, idx) => (
                  <li key={idx}>{concern}</li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-[var(--fg-2)] italic">
                No critical testing concerns reported.
              </p>
            )}
          </div>
          <div className="mt-3 pt-3 border-t border-[var(--line-1)]">
            <span className="text-[11px] font-mono text-[var(--fg-2)] uppercase">
              Documentation Impact:
            </span>
            <p className="text-xs text-[var(--fg-1)] mt-0.5">{docImpact}</p>
          </div>
        </div>
      </div>

      {/* Affected Areas & Files Changed */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Affected Functional Areas */}
        <div className="border border-[var(--line-1)] bg-[var(--bg-1)] rounded-lg p-4">
          <h4 className="text-xs font-semibold text-[var(--fg-0)] pb-2 mb-2 border-b border-[var(--line-1)]">
            Affected Subsystems & Modules
          </h4>
          {affectedAreas.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {affectedAreas.map((area, idx) => (
                <span
                  key={idx}
                  className="px-2 py-1 rounded bg-[var(--bg-0)] border border-[var(--line-2)] text-[11px] font-mono text-[var(--fg-1)]"
                >
                  {area}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-xs text-[var(--fg-2)] italic">No specific subsystems mapped.</p>
          )}
        </div>

        {/* Files Changed */}
        <div className="border border-[var(--line-1)] bg-[var(--bg-1)] rounded-lg p-4">
          <h4 className="text-xs font-semibold text-[var(--fg-0)] pb-2 mb-2 border-b border-[var(--line-1)]">
            Changed Files ({filesChanged.length})
          </h4>
          {filesChanged.length > 0 ? (
            <ul className="space-y-1 max-h-40 overflow-y-auto pr-1">
              {filesChanged.map((file, idx) => (
                <li
                  key={idx}
                  className="text-[11px] font-mono text-[var(--fg-2)] truncate hover:text-[var(--fg-0)]"
                  title={file}
                >
                  {file}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-[var(--fg-2)] italic">No changed files recorded.</p>
          )}
        </div>
      </div>
    </div>
  );
}
