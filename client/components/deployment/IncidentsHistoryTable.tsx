"use client";

import React, { useState, useMemo } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { SearchIcon } from "@/components/shell/icons";
import {
  type DeploymentIncidentResponse,
  getCategoryBadgeVariant,
  formatCategoryLabel,
} from "./types";

interface IncidentsHistoryTableProps {
  incidents: DeploymentIncidentResponse[];
  onSelectIncident: (incidentId: string) => void;
  onDocumentResolution: (incidentId: string) => void;
  onDeleteIncident?: (incidentId: string) => Promise<void>;
}

export function IncidentsHistoryTable({
  incidents,
  onSelectIncident,
  onDocumentResolution,
  onDeleteIncident,
}: IncidentsHistoryTableProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [selectedEnvironment, setSelectedEnvironment] = useState<string>("all");
  const [selectedStatus, setSelectedStatus] = useState<"all" | "resolved" | "unresolved">("all");

  const filteredIncidents = useMemo(() => {
    return incidents.filter((inc) => {
      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesSummary = inc.summary.toLowerCase().includes(q);
        const matchesCause = inc.probable_cause.toLowerCase().includes(q);
        const matchesSig = inc.error_signature.toLowerCase().includes(q);
        const matchesFp = inc.fingerprint.toLowerCase().includes(q);
        if (!matchesSummary && !matchesCause && !matchesSig && !matchesFp) return false;
      }

      // Category filter
      if (selectedCategory !== "all" && inc.failure_category !== selectedCategory) {
        return false;
      }

      // Environment filter
      if (selectedEnvironment !== "all" && inc.environment !== selectedEnvironment) {
        return false;
      }

      // Resolution status filter
      if (selectedStatus === "resolved" && !inc.resolved_at) return false;
      if (selectedStatus === "unresolved" && inc.resolved_at) return false;

      return true;
    });
  }, [incidents, searchQuery, selectedCategory, selectedEnvironment, selectedStatus]);

  return (
    <div className="space-y-4">
      {/* Filters Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="relative flex-1">
          <SearchIcon
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--fg-3)]"
          />
          <Input
            type="text"
            placeholder="Search incidents by summary, error, or fingerprint..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 text-xs"
          />
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="px-2.5 py-1.5 text-xs rounded-md bg-[var(--bg-1)] border border-[var(--border)] text-[var(--fg-1)] font-mono focus:outline-none"
          >
            <option value="all">All Categories</option>
            <option value="missing_env_var">Missing Env Var</option>
            <option value="database_migration_failed">Migration Failed</option>
            <option value="dependency_mismatch">Dependency Mismatch</option>
            <option value="port_binding_failed">Port Binding Failed</option>
            <option value="build_compilation_failed">Build Failed</option>
            <option value="timeout">Timeout</option>
            <option value="unhandled_exception">Unhandled Exception</option>
          </select>

          <select
            value={selectedEnvironment}
            onChange={(e) => setSelectedEnvironment(e.target.value)}
            className="px-2.5 py-1.5 text-xs rounded-md bg-[var(--bg-1)] border border-[var(--border)] text-[var(--fg-1)] font-mono focus:outline-none"
          >
            <option value="all">All Environments</option>
            <option value="production">Production</option>
            <option value="staging">Staging</option>
            <option value="preview">Preview</option>
          </select>

          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value as "all" | "resolved" | "unresolved")}
            className="px-2.5 py-1.5 text-xs rounded-md bg-[var(--bg-1)] border border-[var(--border)] text-[var(--fg-1)] font-mono focus:outline-none"
          >
            <option value="all">All Statuses</option>
            <option value="resolved">Resolved</option>
            <option value="unresolved">Open / Unresolved</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-md border border-[var(--border)] bg-[var(--bg-1)] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--bg-0)] text-[var(--fg-2)] font-mono uppercase text-[11px]">
                <th className="py-2.5 px-4 font-medium">Incident & Category</th>
                <th className="py-2.5 px-4 font-medium">Probable Cause</th>
                <th className="py-2.5 px-4 font-medium">Environment</th>
                <th className="py-2.5 px-4 font-medium">Occurrences</th>
                <th className="py-2.5 px-4 font-medium">Status</th>
                <th className="py-2.5 px-4 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {filteredIncidents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-[var(--fg-3)]">
                    No deployment incidents found matching current filters.
                  </td>
                </tr>
              ) : (
                filteredIncidents.map((inc) => (
                  <tr key={inc.id} className="hover:bg-[var(--bg-0)]/60 transition-colors">
                    <td className="py-3 px-4">
                      <div className="flex flex-col gap-1">
                        <span className="font-semibold text-[var(--fg-1)] line-clamp-1">
                          {inc.summary}
                        </span>
                        <div className="flex items-center gap-1.5">
                          <Badge variant={getCategoryBadgeVariant(inc.failure_category)} size="sm">
                            {formatCategoryLabel(inc.failure_category)}
                          </Badge>
                          <code className="text-[10px] text-[var(--fg-3)] font-mono">
                            {inc.fingerprint.slice(0, 8)}
                          </code>
                        </div>
                      </div>
                    </td>

                    <td className="py-3 px-4 max-w-xs">
                      <p className="text-[var(--fg-2)] line-clamp-2">{inc.probable_cause}</p>
                    </td>

                    <td className="py-3 px-4 font-mono text-[var(--fg-2)]">
                      <span className="capitalize">{inc.environment}</span>
                      {inc.service_name && (
                        <span className="text-[var(--fg-3)] block text-[11px]">
                          {inc.service_name}
                        </span>
                      )}
                    </td>

                    <td className="py-3 px-4 font-mono">
                      <Badge variant={inc.occurrence_count > 1 ? "warn" : "neutral"} size="sm">
                        {`${inc.occurrence_count}x`}
                      </Badge>
                    </td>

                    <td className="py-3 px-4">
                      {inc.resolved_at ? (
                        <div className="flex flex-col gap-0.5">
                          <Badge variant="signal" size="sm">
                            Resolved
                          </Badge>
                          {inc.resolved_by && (
                            <span className="text-[10px] text-[var(--fg-3)]">
                              by {inc.resolved_by}
                            </span>
                          )}
                        </div>
                      ) : (
                        <Badge variant="danger" size="sm">
                          Open
                        </Badge>
                      )}
                    </td>

                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          type="button"
                          variant="tertiary"
                          size="sm"
                          onClick={() => onSelectIncident(inc.id)}
                          className="text-xs font-mono"
                        >
                          View
                        </Button>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => onDocumentResolution(inc.id)}
                          className="text-xs font-mono"
                        >
                          {inc.resolution ? "Edit Fix" : "Document Fix"}
                        </Button>
                        {onDeleteIncident && (
                          <Button
                            type="button"
                            variant="destructive"
                            size="sm"
                            onClick={() => onDeleteIncident(inc.id)}
                            className="text-xs font-mono"
                          >
                            Delete
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
