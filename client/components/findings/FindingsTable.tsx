"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";
import type { FindingItem } from "@devmind/common/api";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import {
  type FindingFilterState,
  INITIAL_FILTER_STATE,
  getSeverityBadgeVariant,
  getStatusBadgeVariant,
} from "./types";
import { FindingTriageModal } from "./FindingTriageModal";

export interface FindingsTableProps {
  projectId: string;
  findings: FindingItem[];
  isAnalyzed?: boolean;
  hasMaintainerPermission?: boolean;
  onStatusTransition?: (
    findingId: string,
    payload: { to_status: string; reason?: string }
  ) => Promise<void> | void;
  className?: string;
}

export function FindingsTable({
  projectId,
  findings,
  isAnalyzed = true,
  hasMaintainerPermission = true,
  onStatusTransition,
  className = "",
}: FindingsTableProps) {
  const [filters, setFilters] = useState<FindingFilterState>(INITIAL_FILTER_STATE);
  const [triageFinding, setTriageFinding] = useState<FindingItem | null>(null);
  const [isTransitioningId, setIsTransitioningId] = useState<string | null>(null);

  // Status counts for filter pills
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {
      all: findings.length,
      open: 0,
      in_progress: 0,
      resolved: 0,
      dismissed: 0,
      stale: 0,
    };
    for (const f of findings) {
      const s = f.status.toLowerCase();
      if (s === "open" || s === "acknowledged") counts.open++;
      else if (s === "in_progress") counts.in_progress++;
      else if (s === "resolved") counts.resolved++;
      else if (s === "dismissed" || s === "accepted_risk") counts.dismissed++;
      else if (s === "stale") counts.stale++;
    }
    return counts;
  }, [findings]);

  // Extract unique categories for category filter
  const availableCategories = useMemo(() => {
    const set = new Set<string>();
    for (const f of findings) {
      if (f.category) set.add(f.category);
    }
    return Array.from(set).sort();
  }, [findings]);

  // Filtered findings list
  const filteredFindings = useMemo(() => {
    return findings.filter((f) => {
      // Status filter
      if (filters.status !== "all") {
        const s = f.status.toLowerCase();
        if (filters.status === "open" && s !== "open" && s !== "acknowledged") return false;
        if (filters.status === "in_progress" && s !== "in_progress") return false;
        if (filters.status === "resolved" && s !== "resolved") return false;
        if (filters.status === "dismissed" && s !== "dismissed" && s !== "accepted_risk")
          return false;
        if (filters.status === "stale" && s !== "stale") return false;
      }

      // Severity filter
      if (filters.severity !== "all") {
        if (f.severity.toLowerCase() !== filters.severity.toLowerCase()) return false;
      }

      // Category filter
      if (filters.category !== "all") {
        if (f.category.toLowerCase() !== filters.category.toLowerCase()) return false;
      }

      // Evidence level filter
      if (filters.evidenceLevel !== "all") {
        if (f.evidence_level.toUpperCase() !== filters.evidenceLevel.toUpperCase()) return false;
      }

      // Search query (rule_id, title, summary, primary_path)
      if (filters.query.trim()) {
        const q = filters.query.toLowerCase().trim();
        const ruleId = f.rule_id.toLowerCase();
        const title = f.title.toLowerCase();
        const summary = (f.summary || "").toLowerCase();
        const path = (f.primary_path || "").toLowerCase();
        if (
          !ruleId.includes(q) &&
          !title.includes(q) &&
          !summary.includes(q) &&
          !path.includes(q)
        ) {
          return false;
        }
      }

      return true;
    });
  }, [findings, filters]);

  const handleQuickTransition = async (
    findingId: string,
    targetStatus: string,
    reason?: string
  ) => {
    if (!onStatusTransition) return;
    try {
      setIsTransitioningId(findingId);
      await onStatusTransition(findingId, {
        to_status: targetStatus,
        reason: reason || `Transitioned to ${targetStatus} via web UI`,
      });
    } finally {
      setIsTransitioningId(null);
    }
  };

  const handleTriageSubmit = async (payload: { to_status: string; reason: string }) => {
    if (!triageFinding || !onStatusTransition) return;
    await onStatusTransition(triageFinding.id, payload);
    setTriageFinding(null);
  };

  const resetFilters = () => {
    setFilters(INITIAL_FILTER_STATE);
  };

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Filter Bar */}
      <div className="space-y-3 bg-[var(--bg-1)] p-4 rounded-[var(--radius-lg)] border border-[var(--line-1)]">
        {/* Status Pills */}
        <div className="flex flex-wrap items-center gap-1.5 border-b border-[var(--line-1)] pb-3">
          {[
            { id: "all", label: "All Findings", count: statusCounts.all },
            { id: "open", label: "Open / Acknowledged", count: statusCounts.open },
            { id: "in_progress", label: "In Progress", count: statusCounts.in_progress },
            { id: "resolved", label: "Resolved", count: statusCounts.resolved },
            { id: "dismissed", label: "Dismissed / Triaged", count: statusCounts.dismissed },
            { id: "stale", label: "Stale (Changed Files)", count: statusCounts.stale },
          ].map((pill) => {
            const isActive = filters.status === pill.id;
            return (
              <button
                key={pill.id}
                type="button"
                onClick={() => setFilters((prev) => ({ ...prev, status: pill.id }))}
                className={`px-3 py-1 rounded-[var(--radius-chip)] text-xs font-medium transition-colors flex items-center gap-1.5 ${
                  isActive
                    ? "bg-[var(--line-strong)] text-[var(--fg-0)]"
                    : "text-[var(--fg-2)] hover:text-[var(--fg-0)] hover:bg-[var(--bg-2)]"
                }`}
              >
                <span>{pill.label}</span>
                <span
                  className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                    isActive
                      ? "bg-[var(--bg-0)] text-[var(--fg-0)]"
                      : "bg-[var(--bg-2)] text-[var(--fg-2)]"
                  }`}
                >
                  {pill.count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Dropdowns & Search */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
          {/* Search Input */}
          <div className="lg:col-span-2">
            <div className="relative">
              <input
                type="text"
                value={filters.query}
                onChange={(e) => setFilters((prev) => ({ ...prev, query: e.target.value }))}
                placeholder="Search rule, title, or file path..."
                className="w-full pl-8 pr-3 py-1.5 text-xs rounded-[var(--radius-sm)] bg-[var(--bg-2)] border border-[var(--line-1)] text-[var(--fg-0)] placeholder-[var(--fg-3)] focus:outline-none focus:border-[var(--ref)]"
              />
              <svg
                className="w-3.5 h-3.5 text-[var(--fg-3)] absolute left-2.5 top-2.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
            </div>
          </div>

          {/* Severity Dropdown */}
          <div>
            <select
              value={filters.severity}
              onChange={(e) => setFilters((prev) => ({ ...prev, severity: e.target.value }))}
              aria-label="Filter by severity"
              className="w-full px-2.5 py-1.5 text-xs rounded-[var(--radius-sm)] bg-[var(--bg-2)] border border-[var(--line-1)] text-[var(--fg-0)] focus:outline-none focus:border-[var(--ref)]"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="info">Info</option>
            </select>
          </div>

          {/* Category Dropdown */}
          <div>
            <select
              value={filters.category}
              onChange={(e) => setFilters((prev) => ({ ...prev, category: e.target.value }))}
              aria-label="Filter by category"
              className="w-full px-2.5 py-1.5 text-xs rounded-[var(--radius-sm)] bg-[var(--bg-2)] border border-[var(--line-1)] text-[var(--fg-0)] focus:outline-none focus:border-[var(--ref)]"
            >
              <option value="all">All Categories</option>
              {availableCategories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat.charAt(0).toUpperCase() + cat.slice(1).replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </div>

          {/* Evidence Level Dropdown */}
          <div>
            <select
              value={filters.evidenceLevel}
              onChange={(e) => setFilters((prev) => ({ ...prev, evidenceLevel: e.target.value }))}
              aria-label="Filter by evidence level"
              className="w-full px-2.5 py-1.5 text-xs rounded-[var(--radius-sm)] bg-[var(--bg-2)] border border-[var(--line-1)] text-[var(--fg-0)] focus:outline-none focus:border-[var(--ref)]"
            >
              <option value="all">All Evidence</option>
              <option value="E2">E2 · Deterministic Guard</option>
              <option value="E1">E1 · Machine Rule Match</option>
              <option value="E0">E0 · Heuristic / Advisory</option>
            </select>
          </div>
        </div>
      </div>

      {/* Counter & Active Filter Pills */}
      <div className="flex items-center justify-between text-xs text-[var(--fg-2)] px-1">
        <div>
          Showing {`${filteredFindings.length}`} of {`${findings.length}`} findings
        </div>
        {(filters.status !== "all" ||
          filters.severity !== "all" ||
          filters.category !== "all" ||
          filters.evidenceLevel !== "all" ||
          filters.query !== "") && (
          <button
            type="button"
            onClick={resetFilters}
            className="text-[var(--ref)] hover:underline text-xs"
          >
            Reset all filters
          </button>
        )}
      </div>

      {/* Dense Table / Responsive List */}
      {filteredFindings.length === 0 ? (
        <div className="p-8 text-center bg-[var(--bg-1)] border border-[var(--line-1)] rounded-[var(--radius-lg)]">
          {findings.length === 0 ? (
            !isAnalyzed ? (
              <div className="space-y-3">
                <div className="text-sm font-medium text-[var(--fg-0)]">
                  Project not analyzed yet
                </div>
                <div className="text-xs text-[var(--fg-2)] max-w-md mx-auto">
                  Run your first repository scan or connect the DevMind companion in VS Code to
                  discover security findings and architecture rules.
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="text-sm font-medium text-[var(--signal)]">
                  ✓ No security findings detected
                </div>
                <div className="text-xs text-[var(--fg-2)]">
                  All active rules and deterministic guards are passing across analyzed files.
                </div>
              </div>
            )
          ) : (
            <div className="space-y-3">
              <div className="text-sm font-medium text-[var(--fg-0)]">
                No findings match the current filters
              </div>
              <div className="text-xs text-[var(--fg-2)]">
                Try loosening your search query, status, or severity filters.
              </div>
              <Button variant="secondary" size="sm" onClick={resetFilters}>
                Clear filters
              </Button>
            </div>
          )}
        </div>
      ) : (
        <div className="border border-[var(--line-1)] rounded-[var(--radius-lg)] overflow-hidden bg-[var(--bg-0)]">
          {/* Desktop Dense Table */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-[var(--bg-1)] border-b border-[var(--line-1)] text-[var(--fg-2)] select-none">
                  <th scope="col" className="py-2.5 px-3 font-medium w-24">
                    Severity
                  </th>
                  <th scope="col" className="py-2.5 px-2 font-medium w-14">
                    Evid.
                  </th>
                  <th scope="col" className="py-2.5 px-3 font-medium">
                    Rule & Finding
                  </th>
                  <th scope="col" className="py-2.5 px-3 font-medium">
                    Location
                  </th>
                  <th scope="col" className="py-2.5 px-3 font-medium w-28">
                    Status
                  </th>
                  <th scope="col" className="py-2.5 px-3 font-medium w-44 text-right">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--line-1)]">
                {filteredFindings.map((finding) => {
                  const isTransitioning = isTransitioningId === finding.id;
                  const locationString = finding.primary_path
                    ? `${finding.primary_path}${
                        finding.primary_start_line ? `#L${finding.primary_start_line}` : ""
                      }`
                    : "No location";

                  return (
                    <tr key={finding.id} className="hover:bg-[var(--bg-1)] transition-colors group">
                      {/* Severity */}
                      <td className="py-2.5 px-3 align-top">
                        <Badge variant={getSeverityBadgeVariant(finding.severity)} size="sm">
                          {finding.severity.toUpperCase()}
                        </Badge>
                      </td>

                      {/* Evidence Level */}
                      <td className="py-2.5 px-2 align-top">
                        <Badge
                          evidenceLevel={finding.evidence_level as "E0" | "E1" | "E2"}
                          size="sm"
                        >
                          {finding.evidence_level}
                        </Badge>
                      </td>

                      {/* Rule & Title */}
                      <td className="py-2.5 px-3 align-top">
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-[10px] text-[var(--fg-2)]">
                              {finding.rule_id}
                            </span>
                            <span className="text-[10px] text-[var(--fg-3)]">·</span>
                            <span className="text-[10px] text-[var(--fg-2)] capitalize">
                              {finding.category}
                            </span>
                          </div>
                          <Link
                            href={`/projects/${projectId}/findings/${finding.id}`}
                            className="text-[var(--fg-0)] hover:text-[var(--ref)] font-medium block leading-snug"
                          >
                            {finding.title}
                          </Link>
                          {finding.summary && (
                            <p className="text-[11px] text-[var(--fg-2)] line-clamp-1">
                              {finding.summary}
                            </p>
                          )}
                        </div>
                      </td>

                      {/* Location */}
                      <td className="py-2.5 px-3 align-top font-mono text-[11px] text-[var(--fg-2)] max-w-xs truncate">
                        <span title={locationString}>{locationString}</span>
                      </td>

                      {/* Status */}
                      <td className="py-2.5 px-3 align-top">
                        <Badge variant={getStatusBadgeVariant(finding.status)} size="sm">
                          {finding.status.replace(/_/g, " ")}
                        </Badge>
                      </td>

                      {/* Actions */}
                      <td className="py-2.5 px-3 align-top text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {finding.status === "open" && (
                            <>
                              <button
                                type="button"
                                disabled={isTransitioning}
                                onClick={() => handleQuickTransition(finding.id, "acknowledged")}
                                className="px-2 py-0.5 text-[11px] rounded-[var(--radius-sm)] border border-[var(--line-1)] text-[var(--fg-1)] hover:bg-[var(--bg-2)] transition-colors"
                              >
                                Ack
                              </button>
                              <button
                                type="button"
                                disabled={isTransitioning}
                                onClick={() => handleQuickTransition(finding.id, "in_progress")}
                                className="px-2 py-0.5 text-[11px] rounded-[var(--radius-sm)] border border-[var(--signal)] text-[var(--signal)] hover:bg-[rgba(32,227,162,0.1)] transition-colors"
                              >
                                Progress
                              </button>
                              <button
                                type="button"
                                onClick={() => setTriageFinding(finding)}
                                className="px-2 py-0.5 text-[11px] rounded-[var(--radius-sm)] border border-[var(--line-1)] text-[var(--fg-2)] hover:text-[var(--fg-0)] hover:bg-[var(--bg-2)] transition-colors"
                              >
                                Triage
                              </button>
                            </>
                          )}

                          {finding.status === "acknowledged" && (
                            <>
                              <button
                                type="button"
                                disabled={isTransitioning}
                                onClick={() => handleQuickTransition(finding.id, "in_progress")}
                                className="px-2 py-0.5 text-[11px] rounded-[var(--radius-sm)] border border-[var(--signal)] text-[var(--signal)] hover:bg-[rgba(32,227,162,0.1)] transition-colors"
                              >
                                Start
                              </button>
                              <button
                                type="button"
                                onClick={() => setTriageFinding(finding)}
                                className="px-2 py-0.5 text-[11px] rounded-[var(--radius-sm)] border border-[var(--line-1)] text-[var(--fg-2)] hover:text-[var(--fg-0)] hover:bg-[var(--bg-2)] transition-colors"
                              >
                                Triage
                              </button>
                            </>
                          )}

                          {finding.status === "in_progress" && (
                            <>
                              <button
                                type="button"
                                disabled={isTransitioning}
                                onClick={() => handleQuickTransition(finding.id, "resolved")}
                                className="px-2 py-0.5 text-[11px] rounded-[var(--radius-sm)] border border-[var(--signal)] text-[var(--signal)] hover:bg-[rgba(32,227,162,0.1)] transition-colors"
                              >
                                Resolve
                              </button>
                              <button
                                type="button"
                                onClick={() => setTriageFinding(finding)}
                                className="px-2 py-0.5 text-[11px] rounded-[var(--radius-sm)] border border-[var(--line-1)] text-[var(--fg-2)] hover:text-[var(--fg-0)] hover:bg-[var(--bg-2)] transition-colors"
                              >
                                Triage
                              </button>
                            </>
                          )}

                          {finding.status === "stale" && (
                            <button
                              type="button"
                              disabled={isTransitioning}
                              onClick={() =>
                                handleQuickTransition(
                                  finding.id,
                                  "open",
                                  "Manual re-verification triggered"
                                )
                              }
                              className="px-2 py-0.5 text-[11px] rounded-[var(--radius-sm)] border border-[var(--danger)] text-[var(--danger)] hover:bg-[rgba(255,107,94,0.1)] transition-colors"
                            >
                              Re-verify
                            </button>
                          )}

                          {(finding.status === "dismissed" ||
                            finding.status === "accepted_risk" ||
                            finding.status === "resolved") && (
                            <button
                              type="button"
                              disabled={isTransitioning}
                              onClick={() =>
                                handleQuickTransition(
                                  finding.id,
                                  "open",
                                  "Finding reopened by user"
                                )
                              }
                              className="px-2 py-0.5 text-[11px] rounded-[var(--radius-sm)] border border-[var(--line-1)] text-[var(--fg-2)] hover:text-[var(--fg-0)] hover:bg-[var(--bg-2)] transition-colors"
                            >
                              Reopen
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile Collapsed Cards (docs/08 §11 S-07: Responsive: rows collapse to two-line items) */}
          <div className="md:hidden divide-y divide-[var(--line-1)]">
            {filteredFindings.map((finding) => (
              <div key={finding.id} className="p-3 space-y-1.5 hover:bg-[var(--bg-1)]">
                {/* Line 1: Severity + Evidence + Title */}
                <div className="flex items-center gap-2">
                  <Badge variant={getSeverityBadgeVariant(finding.severity)} size="sm">
                    {finding.severity.toUpperCase()}
                  </Badge>
                  <Badge evidenceLevel={finding.evidence_level as "E0" | "E1" | "E2"} size="sm">
                    {finding.evidence_level}
                  </Badge>
                  <Link
                    href={`/projects/${projectId}/findings/${finding.id}`}
                    className="text-xs font-medium text-[var(--fg-0)] hover:text-[var(--ref)] truncate flex-1"
                  >
                    {finding.title}
                  </Link>
                </div>

                {/* Line 2: Rule ID + Location + Status */}
                <div className="flex items-center justify-between text-[11px] text-[var(--fg-2)]">
                  <div className="flex items-center gap-1.5 font-mono truncate">
                    <span>{finding.rule_id}</span>
                    <span>·</span>
                    <span className="truncate">{finding.primary_path}</span>
                  </div>
                  <Badge variant={getStatusBadgeVariant(finding.status)} size="sm">
                    {finding.status}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Triage Modal */}
      {triageFinding && (
        <FindingTriageModal
          isOpen={Boolean(triageFinding)}
          onClose={() => setTriageFinding(null)}
          finding={triageFinding}
          hasMaintainerPermission={hasMaintainerPermission}
          onConfirm={handleTriageSubmit}
        />
      )}
    </div>
  );
}
