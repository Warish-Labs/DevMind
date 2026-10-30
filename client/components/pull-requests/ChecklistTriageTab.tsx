"use client";

import React, { useState, useMemo } from "react";
import { Badge } from "@/components/ui/Badge";
import { ChecklistFindingItem, getSeverityBadgeVariant } from "./types";

interface ChecklistTriageTabProps {
  findings: ChecklistFindingItem[];
  onTriageStatusChange?: (findingId: string, status: "open" | "verified" | "dismissed") => void;
}

type CategoryFilter =
  "all" | "auth" | "input_validation" | "error_handling" | "testing" | "custom_rules";

export function ChecklistTriageTab({
  findings: initialFindings,
  onTriageStatusChange,
}: ChecklistTriageTabProps) {
  const [findings, setFindings] = useState<ChecklistFindingItem[]>(initialFindings);
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>("all");
  const [severityFilter, setSeverityFilter] = useState<string>("all");

  const handleStatusUpdate = (id: string, newStatus: "open" | "verified" | "dismissed") => {
    setFindings((prev) => prev.map((f) => (f.id === id ? { ...f, status: newStatus } : f)));
    onTriageStatusChange?.(id, newStatus);
  };

  const filteredFindings = useMemo(() => {
    return findings.filter((f) => {
      if (categoryFilter !== "all" && f.category !== categoryFilter) {
        return false;
      }
      if (severityFilter !== "all" && f.severity.toLowerCase() !== severityFilter.toLowerCase()) {
        return false;
      }
      return true;
    });
  }, [findings, categoryFilter, severityFilter]);

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = { all: findings.length };
    for (const f of findings) {
      counts[f.category] = (counts[f.category] || 0) + 1;
    }
    return counts;
  }, [findings]);

  return (
    <div className="space-y-4">
      {/* Category & Severity Filter Header */}
      <div className="border border-[var(--line-1)] bg-[var(--bg-1)] p-3 rounded-lg flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
        {/* Category Pills */}
        <div className="flex items-center gap-1 overflow-x-auto text-xs">
          {(
            [
              { id: "all", label: "All Checks" },
              { id: "auth", label: "Auth & Scoping" },
              { id: "input_validation", label: "Validation" },
              { id: "error_handling", label: "Errors" },
              { id: "testing", label: "Testing" },
              { id: "custom_rules", label: "Custom Rules" },
            ] as const
          ).map((cat) => (
            <button
              key={cat.id}
              onClick={() => setCategoryFilter(cat.id)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors flex items-center gap-1.5 ${
                categoryFilter === cat.id
                  ? "bg-[var(--bg-2)] text-[var(--fg-0)] border border-[var(--line-2)] shadow-xs"
                  : "text-[var(--fg-2)] hover:text-[var(--fg-1)] hover:bg-[var(--bg-2)]/40"
              }`}
            >
              <span>{cat.label}</span>
              {(categoryCounts[cat.id] ?? 0) > 0 && (
                <span className="text-[10px] font-mono bg-[var(--bg-0)] px-1 rounded">
                  {categoryCounts[cat.id]}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Severity Selector */}
        <div className="flex items-center gap-2 text-xs">
          <span className="text-[var(--fg-2)] font-mono">Severity:</span>
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="bg-[var(--bg-0)] border border-[var(--line-2)] rounded px-2 py-1 text-xs text-[var(--fg-1)] focus:outline-none"
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>
      </div>

      {/* Findings List */}
      {filteredFindings.length === 0 ? (
        <div className="border border-[var(--line-1)] bg-[var(--bg-1)] rounded-lg p-12 text-center">
          <span className="text-xl">✓</span>
          <h3 className="text-sm font-semibold text-[var(--fg-0)] mt-2">
            No checklist findings in this view
          </h3>
          <p className="text-xs text-[var(--fg-2)] mt-1">
            All automated ReviewBuddy checks passed or are dismissed for this category.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredFindings.map((finding) => {
            const sevVariant = getSeverityBadgeVariant(finding.severity);
            const isDismissed = finding.status === "dismissed";

            return (
              <div
                key={finding.id}
                className={`border rounded-lg p-4 transition-all ${
                  isDismissed
                    ? "bg-[var(--bg-1)]/40 border-[var(--line-1)] opacity-60"
                    : "bg-[var(--bg-1)] border-[var(--line-1)]"
                }`}
              >
                {/* Header Row */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[var(--line-1)]">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={sevVariant} size="sm">
                      {finding.severity.toUpperCase()}
                    </Badge>
                    <Badge evidenceLevel={finding.evidence_level} size="sm" />
                    <span className="font-mono text-[11px] text-[var(--fg-2)] bg-[var(--bg-0)] px-1.5 py-0.5 rounded border border-[var(--line-2)]">
                      {finding.rule_id}
                    </span>
                    <span className="font-semibold text-xs text-[var(--fg-0)]">
                      {finding.title}
                    </span>
                  </div>

                  {/* Triage Status Actions */}
                  <div className="flex items-center gap-1.5 self-end sm:self-auto">
                    <button
                      onClick={() =>
                        handleStatusUpdate(
                          finding.id,
                          finding.status === "verified" ? "open" : "verified"
                        )
                      }
                      className={`px-2 py-0.5 rounded text-[11px] font-mono transition-colors border ${
                        finding.status === "verified"
                          ? "bg-[rgba(32,227,162,0.15)] text-[var(--signal)] border-[rgba(32,227,162,0.3)]"
                          : "bg-[var(--bg-0)] text-[var(--fg-2)] border-[var(--line-2)] hover:text-[var(--fg-1)]"
                      }`}
                    >
                      {finding.status === "verified" ? "✓ Verified" : "Verify"}
                    </button>
                    <button
                      onClick={() =>
                        handleStatusUpdate(
                          finding.id,
                          finding.status === "dismissed" ? "open" : "dismissed"
                        )
                      }
                      className={`px-2 py-0.5 rounded text-[11px] font-mono transition-colors border ${
                        finding.status === "dismissed"
                          ? "bg-[var(--bg-2)] text-[var(--fg-1)] border-[var(--line-2)]"
                          : "bg-[var(--bg-0)] text-[var(--fg-2)] border-[var(--line-2)] hover:text-[var(--fg-1)]"
                      }`}
                    >
                      {finding.status === "dismissed" ? "Dismissed" : "Dismiss"}
                    </button>
                  </div>
                </div>

                {/* Body Details */}
                <div className="mt-3 space-y-2">
                  <div className="flex items-center gap-2 font-mono text-[11px] text-[var(--fg-2)]">
                    <span>File:</span>
                    <span className="text-[var(--fg-1)]">{finding.file_path}</span>
                    <span>
                      L{finding.line_range[0]}-L{finding.line_range[1]}
                    </span>
                  </div>

                  <p className="text-xs text-[var(--fg-1)] leading-relaxed">
                    {finding.explanation}
                  </p>

                  {finding.suggested_fix && (
                    <div className="mt-2 p-2.5 bg-[var(--bg-0)] rounded border border-[var(--line-1)] font-mono text-[11px]">
                      <span className="text-[10px] uppercase text-[var(--signal)] block mb-1">
                        Remediation Suggestion:
                      </span>
                      <pre className="text-[var(--fg-1)] overflow-x-auto whitespace-pre-wrap">
                        {finding.suggested_fix}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
