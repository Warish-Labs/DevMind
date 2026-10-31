"use client";

import React from "react";
import { Badge } from "@/components/ui/Badge";
import { type ProjectEvaluationResponse } from "./types";

interface EvaluationItem {
  id?: string;
  title?: string;
  dimension?: string;
  severity?: string;
  reason?: string;
  detail?: string;
}

interface BlockersAndWarningsListProps {
  evaluation: ProjectEvaluationResponse | null;
}

export function BlockersAndWarningsList({ evaluation }: BlockersAndWarningsListProps) {
  if (!evaluation) {
    return (
      <div className="p-8 text-center text-xs text-[var(--fg-3)]">
        Run an evaluation to analyze release blockers and positive health indicators.
      </div>
    );
  }

  const blockers = (evaluation.blockers || []) as EvaluationItem[];
  const warnings = (evaluation.warnings || []) as EvaluationItem[];
  const positives = evaluation.positive_indicators || [];

  return (
    <div className="flex flex-col gap-6">
      {/* 1. Critical Blockers Section */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <h3 className="text-sm font-semibold text-[var(--fg-0)] font-mono uppercase tracking-wider">
            Release Blockers
          </h3>
          <Badge variant={blockers.length > 0 ? "danger" : "signal"} size="sm">
            {blockers.length} Active
          </Badge>
        </div>

        {blockers.length === 0 ? (
          <div className="rounded-panel border border-[var(--line-1)] bg-emerald-500/5 p-4 flex items-center gap-3">
            <span className="text-emerald-400 text-base">✓</span>
            <div className="text-xs text-[var(--fg-1)]">
              <strong>Zero Release Blockers.</strong> No critical security findings, failing tests,
              or cyclic architectural dependencies detected.
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {blockers.map((blocker, idx) => (
              <div
                key={idx}
                className="rounded-panel border border-rose-500/30 bg-rose-500/5 p-4 flex flex-col gap-1"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-rose-400 font-bold">✕</span>
                    <span className="font-semibold text-sm text-[var(--fg-0)]">
                      {blocker.title || "Critical Blocker"}
                    </span>
                  </div>
                  <Badge variant="danger" size="sm">
                    {blocker.dimension?.toUpperCase() || "BLOCKER"}
                  </Badge>
                </div>
                {blocker.reason && (
                  <p className="text-xs text-[var(--fg-2)] mt-1 ml-5">{blocker.reason}</p>
                )}
                {blocker.detail && (
                  <p className="text-xs text-[var(--fg-3)] mt-0.5 ml-5 font-mono">
                    {blocker.detail}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 2. Warnings Section */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <h3 className="text-sm font-semibold text-[var(--fg-0)] font-mono uppercase tracking-wider">
            Health Warnings & Improvements
          </h3>
          <Badge variant={warnings.length > 0 ? "warn" : "neutral"} size="sm">
            {warnings.length} Notices
          </Badge>
        </div>

        {warnings.length === 0 ? (
          <div className="rounded-panel border border-[var(--line-1)] bg-[var(--bg-1)] p-4 text-xs text-[var(--fg-2)]">
            No active quality or documentation warnings.
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {warnings.map((warn, idx) => (
              <div
                key={idx}
                className="rounded-panel border border-amber-500/30 bg-amber-500/5 p-4 flex flex-col gap-1"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-amber-400 font-bold">⚠️</span>
                    <span className="font-semibold text-sm text-[var(--fg-0)]">
                      {warn.title || "Warning Item"}
                    </span>
                  </div>
                  {warn.dimension && (
                    <Badge variant="warn" size="sm">
                      {warn.dimension.toUpperCase()}
                    </Badge>
                  )}
                </div>
                {warn.reason && (
                  <p className="text-xs text-[var(--fg-2)] mt-1 ml-5">{warn.reason}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 3. Positive Health Indicators */}
      {positives.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-[var(--fg-0)] font-mono uppercase tracking-wider mb-3">
            Positive Indicators & Health Strengths
          </h3>

          <div className="rounded-panel border border-[var(--line-1)] bg-[var(--bg-1)] p-4">
            <ul className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-[var(--fg-1)]">
              {positives.map((pos, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="text-emerald-400 mt-0.5 font-bold">✓</span>
                  <span>{pos}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
