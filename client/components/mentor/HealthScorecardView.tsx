"use client";

import React from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { type ProjectEvaluationResponse } from "./types";

interface HealthScorecardViewProps {
  evaluation: ProjectEvaluationResponse | null;
  isLoading: boolean;
  onRunEvaluation: () => void;
}

const DIMENSION_METADATA: Record<string, { label: string; weight: string; description: string }> = {
  security: {
    label: "Security & Safety",
    weight: "25%",
    description: "Evaluates open vulnerabilities, secret redaction, and multi-tenant isolation.",
  },
  code_quality: {
    label: "Code Quality & Bugs",
    weight: "20%",
    description: "Review rule violations and recurring unresolved errors from Bug Memory.",
  },
  testing: {
    label: "Testing & CI Readiness",
    weight: "20%",
    description: "Automated test pass rates, suite execution, and CI coverage signals.",
  },
  documentation: {
    label: "Documentation & Living Sync",
    weight: "15%",
    description: "DocsAlive alignment between codebase routes, symbols, and Markdown records.",
  },
  functionality: {
    label: "Functionality & Milestones (OQ-18)",
    weight: "10%",
    description: "User-declared feature checklist completion rate.",
  },
  architecture: {
    label: "Architecture & DAG Health",
    weight: "10%",
    description: "Cyclic dependency freedom and backlog blocking complexity.",
  },
};

export function HealthScorecardView({
  evaluation,
  isLoading,
  onRunEvaluation,
}: HealthScorecardViewProps) {
  if (isLoading) {
    return (
      <div className="rounded-panel border border-[var(--line-1)] bg-[var(--bg-1)] p-8 animate-pulse">
        <div className="h-6 w-64 bg-[var(--line-2)] rounded mb-4" />
        <div className="h-32 w-full bg-[var(--line-2)] rounded mb-6" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-28 bg-[var(--line-2)] rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (!evaluation) {
    return (
      <div className="rounded-panel border border-dashed border-[var(--line-2)] bg-[var(--bg-1)] p-12 text-center">
        <h3 className="text-base font-semibold text-[var(--fg-0)] mb-1">
          No Health Evaluations Run Yet
        </h3>
        <p className="text-sm text-[var(--fg-2)] mb-4 max-w-md mx-auto">
          Execute an on-demand audit to compute health scores across 6 core dimensions and
          synthesize an honest release-readiness verdict.
        </p>
        <Button variant="primary" onClick={onRunEvaluation}>
          Run Project Evaluation
        </Button>
      </div>
    );
  }

  const getVerdictBadge = (verdict: string) => {
    switch (verdict) {
      case "ready":
        return <Badge variant="signal">READY FOR RELEASE</Badge>;
      case "ready_with_warnings":
        return <Badge variant="warn">READY WITH WARNINGS</Badge>;
      default:
        return <Badge variant="danger">NOT READY · BLOCKED</Badge>;
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 90) return "text-emerald-400";
    if (score >= 70) return "text-amber-400";
    return "text-rose-400";
  };

  const getBarColor = (score: number) => {
    if (score >= 90) return "bg-emerald-500";
    if (score >= 70) return "bg-amber-500";
    return "bg-rose-500";
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Top Hero Banner */}
      <div className="rounded-panel border border-[var(--line-1)] bg-[var(--bg-1)] p-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 pb-6 border-b border-[var(--line-1)]">
          {/* Overall Score Meter */}
          <div className="flex items-center gap-5">
            <div className="relative flex items-center justify-center w-24 h-24 rounded-full border-4 border-[var(--bg-2)] bg-[var(--bg-0)]">
              <span
                className={`text-2xl font-bold font-mono ${getScoreColor(evaluation.overall_score)}`}
              >
                {evaluation.overall_score.toFixed(0)}
              </span>
              <span className="absolute bottom-3 text-[10px] font-mono text-[var(--fg-3)]">
                / 100
              </span>
            </div>

            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="font-mono text-xs uppercase tracking-wider text-[var(--fg-3)]">
                  Release Readiness Verdict
                </span>
                {getVerdictBadge(evaluation.verdict)}
              </div>
              <h2 className="text-xl font-bold text-[var(--fg-0)]">Project Health Scorecard</h2>
              <div className="flex items-center gap-3 mt-1 text-xs text-[var(--fg-2)] font-mono">
                <span>Rubric v{evaluation.rubric_version}</span>
                <span>•</span>
                <span>
                  Functionality Confidence:{" "}
                  <strong
                    className={
                      evaluation.functionality_confidence === "high"
                        ? "text-emerald-400"
                        : "text-amber-400"
                    }
                  >
                    {evaluation.functionality_confidence.toUpperCase()}
                  </strong>
                </span>
              </div>
            </div>
          </div>

          {/* Trigger Button */}
          <div className="flex items-center gap-3">
            <Button variant="secondary" onClick={onRunEvaluation}>
              Re-run Health Evaluation
            </Button>
          </div>
        </div>

        {/* Narrative Box */}
        {evaluation.narrative && (
          <div className="mt-5 p-4 rounded-control bg-[var(--bg-0)] border border-[var(--line-1)]">
            <h4 className="text-xs font-semibold text-[var(--signal)] font-mono uppercase mb-1">
              ProjectMentor Health Narrative
            </h4>
            <p className="text-sm text-[var(--fg-1)] leading-relaxed">{evaluation.narrative}</p>
          </div>
        )}
      </div>

      {/* 6 Dimensions Grid */}
      <div>
        <h3 className="text-sm font-semibold text-[var(--fg-0)] font-mono uppercase tracking-wider mb-3">
          Dimensions Breakdown (Weighted Rubric)
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Object.entries(DIMENSION_METADATA).map(([key, meta]) => {
            const score = evaluation.dimension_scores?.[key] ?? 100.0;
            return (
              <div
                key={key}
                className="rounded-panel border border-[var(--line-1)] bg-[var(--bg-1)] p-4 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono text-xs font-bold text-[var(--fg-0)]">
                      {meta.label}
                    </span>
                    <span className="font-mono text-[11px] text-[var(--fg-3)]">
                      wt: {meta.weight}
                    </span>
                  </div>

                  <p className="text-xs text-[var(--fg-2)] line-clamp-2 mb-3">{meta.description}</p>
                </div>

                <div>
                  {/* Score bar */}
                  <div className="flex items-center justify-between text-xs font-mono mb-1">
                    <span className="text-[var(--fg-3)]">Score</span>
                    <span className={`font-bold ${getScoreColor(score)}`}>
                      {score.toFixed(1)} / 100
                    </span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-[var(--bg-0)] overflow-hidden">
                    <div
                      className={`h-full ${getBarColor(score)} transition-all duration-500`}
                      style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
