"use client";

import React, { useEffect, useState } from "react";
import { apiClient } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import type { AuditEventItem } from "@devmind/common";

export interface AuditLogViewerProps {
  workspaceId?: string;
  projectId?: string;
  title?: string;
  description?: string;
  showHeader?: boolean;
}

const COMMON_ACTIONS = [
  { value: "", label: "All Actions" },
  { value: "project.sync_mode_updated", label: "Sync Mode Updated" },
  { value: "project.data_purged", label: "Data Purged" },
  { value: "consent.granted", label: "Consent Granted" },
  { value: "consent.revoked", label: "Consent Revoked" },
  { value: "membership.added", label: "Member Added" },
  { value: "membership.updated", label: "Member Updated" },
  { value: "membership.removed", label: "Member Removed" },
  { value: "workspace.updated", label: "Workspace Updated" },
  { value: "project.created", label: "Project Created" },
  { value: "project.deleted", label: "Project Deleted" },
  { value: "retention.updated", label: "Retention Updated" },
  { value: "retention.swept", label: "Retention Swept" },
  { value: "device.revoked", label: "Device Revoked" },
];

function getActionBadgeVariant(action: string): "signal" | "danger" | "neutral" | "ref" {
  if (
    action.includes("purged") ||
    action.includes("deleted") ||
    action.includes("revoked") ||
    action.includes("removed")
  ) {
    return "danger";
  }
  if (action.includes("granted") || action.includes("sync_mode") || action.includes("created")) {
    return "signal";
  }
  if (action.includes("membership") || action.includes("updated")) {
    return "ref";
  }
  return "neutral";
}

function formatDate(isoString: string): string {
  try {
    const d = new Date(isoString);
    return d
      .toISOString()
      .replace("T", " ")
      .replace(/\.\d+Z$/, " UTC");
  } catch {
    return isoString;
  }
}

export function AuditLogViewer({
  workspaceId,
  projectId,
  title = "Audit Event Log",
  description = "Append-only, immutable record of security and data-governance actions (docs/03 §3.5, docs/07 §16).",
  showHeader = true,
}: AuditLogViewerProps) {
  const [events, setEvents] = useState<AuditEventItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionFilter, setActionFilter] = useState<string>("");
  const [limit] = useState<number>(25);
  const [offset, setOffset] = useState<number>(0);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    const loadData = async () => {
      try {
        let data: AuditEventItem[] = [];
        if (projectId) {
          data = await apiClient.getProjectAuditEvents(projectId, {
            action: actionFilter || undefined,
            limit,
            offset,
          });
        } else if (workspaceId) {
          data = await apiClient.getWorkspaceAuditEvents(workspaceId, {
            action: actionFilter || undefined,
            limit,
            offset,
          });
        }
        if (isMounted) {
          setEvents(data);
          setError(null);
          setIsLoading(false);
        }
      } catch (err: unknown) {
        if (isMounted) {
          const msg = err instanceof Error ? err.message : "Failed to load audit events";
          setError(msg);
          setIsLoading(false);
        }
      }
    };

    loadData();

    return () => {
      isMounted = false;
    };
  }, [workspaceId, projectId, actionFilter, limit, offset]);

  const reloadEvents = async () => {
    try {
      setIsLoading(true);
      setError(null);
      let data: AuditEventItem[] = [];
      if (projectId) {
        data = await apiClient.getProjectAuditEvents(projectId, {
          action: actionFilter || undefined,
          limit,
          offset,
        });
      } else if (workspaceId) {
        data = await apiClient.getWorkspaceAuditEvents(workspaceId, {
          action: actionFilter || undefined,
          limit,
          offset,
        });
      }
      setEvents(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load audit events";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleActionChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setActionFilter(e.target.value);
    setOffset(0);
  };

  const handlePrevPage = () => {
    setOffset((prev) => Math.max(0, prev - limit));
  };

  const handleNextPage = () => {
    setOffset((prev) => prev + limit);
  };

  const toggleExpand = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="space-y-4 font-mono text-xs">
      {showHeader && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[var(--line-1)]">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base sm:text-lg font-bold text-[var(--fg-0)] tracking-tight">
                {title}
              </h2>
              <Badge variant="neutral" size="sm">
                Immutable Log
              </Badge>
            </div>
            {description && <p className="text-xs text-[var(--fg-2)] mt-0.5">{description}</p>}
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={reloadEvents}
              disabled={isLoading}
              className="text-xs"
            >
              {isLoading ? "Refreshing..." : "↻ Refresh"}
            </Button>
          </div>
        </div>
      )}

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-[var(--bg-1)] p-3 rounded-[var(--radius-card)] border border-[var(--line-1)]">
        <div className="flex items-center gap-2 flex-wrap">
          <label htmlFor="audit-action-filter" className="text-[11px] text-[var(--fg-2)]">
            Filter Action:
          </label>
          <select
            id="audit-action-filter"
            value={actionFilter}
            onChange={handleActionChange}
            className="bg-[var(--bg-0)] text-[var(--fg-0)] border border-[var(--line-2)] rounded px-2.5 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-[var(--ref)]"
          >
            {COMMON_ACTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div className="text-[11px] text-[var(--fg-2)]">
          Page offset: <span className="text-[var(--fg-1)] font-semibold">{offset}</span>
        </div>
      </div>

      {/* Error Notice */}
      {error && (
        <div
          role="alert"
          className="p-3 bg-[rgba(239,68,68,0.1)] border border-[var(--danger)] text-[var(--danger)] rounded-[var(--radius-control)] text-xs flex items-center justify-between"
        >
          <span>Error loading audit logs: {error}</span>
          <Button variant="secondary" size="sm" onClick={reloadEvents}>
            Retry
          </Button>
        </div>
      )}

      {/* Audit Log Table */}
      <div className="border border-[var(--line-1)] rounded-[var(--radius-card)] overflow-hidden bg-[var(--bg-0)]">
        {isLoading ? (
          <div className="p-4 space-y-3">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : events.length === 0 ? (
          <div className="p-8 text-center space-y-2">
            <div className="text-sm font-semibold text-[var(--fg-1)]">No audit events found</div>
            <p className="text-xs text-[var(--fg-2)] max-w-sm mx-auto">
              {actionFilter
                ? `No events match action filter "${actionFilter}".`
                : "No sensitive or security governance actions have been recorded yet."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-[var(--line-1)] bg-[var(--bg-1)] text-[var(--fg-2)] text-[11px]">
                  <th scope="col" className="p-3">
                    Timestamp
                  </th>
                  <th scope="col" className="p-3">
                    Action
                  </th>
                  <th scope="col" className="p-3">
                    Target
                  </th>
                  <th scope="col" className="p-3">
                    Actor
                  </th>
                  <th scope="col" className="p-3">
                    IP Hash
                  </th>
                  <th scope="col" className="p-3 text-right">
                    Details
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--line-1)]">
                {events.map((evt) => {
                  const isExpanded = expandedId === evt.id;
                  const hasMetadata = evt.metadata && Object.keys(evt.metadata).length > 0;

                  return (
                    <React.Fragment key={evt.id}>
                      <tr className="hover:bg-[var(--bg-1)] transition-colors">
                        <td className="p-3 text-[var(--fg-2)] whitespace-nowrap">
                          {formatDate(evt.created_at)}
                        </td>
                        <td className="p-3 whitespace-nowrap">
                          <Badge variant={getActionBadgeVariant(evt.action)} size="sm">
                            {evt.action}
                          </Badge>
                        </td>
                        <td className="p-3 text-[var(--fg-1)]">
                          <span className="font-semibold text-[var(--fg-0)]">
                            {evt.target_kind}
                          </span>
                          {evt.target_id && (
                            <span
                              className="ml-1 text-[10px] text-[var(--fg-2)] block truncate max-w-[120px]"
                              title={evt.target_id}
                            >
                              {evt.target_id.slice(0, 8)}...
                            </span>
                          )}
                        </td>
                        <td className="p-3 text-[var(--fg-2)] whitespace-nowrap">
                          <span className="text-[var(--fg-1)]">{evt.actor_kind}</span>
                          {evt.actor_id && (
                            <span
                              className="ml-1 text-[10px] block truncate max-w-[100px]"
                              title={evt.actor_id}
                            >
                              {evt.actor_id.slice(0, 8)}...
                            </span>
                          )}
                        </td>
                        <td className="p-3 text-[var(--fg-2)] whitespace-nowrap">
                          {evt.ip_hash ? (
                            <code className="text-[10px] bg-[var(--bg-2)] px-1.5 py-0.5 rounded border border-[var(--line-2)] text-[var(--fg-1)]">
                              #{evt.ip_hash.slice(0, 8)}
                            </code>
                          ) : (
                            <span className="text-[10px] text-[var(--line-3)]">-</span>
                          )}
                        </td>
                        <td className="p-3 text-right whitespace-nowrap">
                          {hasMetadata ? (
                            <button
                              type="button"
                              onClick={() => toggleExpand(evt.id)}
                              aria-expanded={isExpanded}
                              className="text-[11px] text-[var(--signal)] hover:underline focus:outline-none"
                            >
                              {isExpanded ? "Hide Data ▲" : "View Data ▼"}
                            </button>
                          ) : (
                            <span className="text-[11px] text-[var(--fg-2)]">No data</span>
                          )}
                        </td>
                      </tr>

                      {/* Expanded Metadata JSON Drawer */}
                      {isExpanded && hasMetadata && (
                        <tr className="bg-[var(--bg-1)]">
                          <td colSpan={6} className="p-4 border-b border-[var(--line-1)]">
                            <div className="space-y-2">
                              <div className="flex items-center justify-between text-[11px] text-[var(--fg-2)]">
                                <span className="font-semibold text-[var(--fg-1)]">
                                  Event Metadata &amp; Parameters
                                </span>
                                <span className="text-[10px]">ID: {evt.id}</span>
                              </div>
                              <pre className="p-3 bg-[var(--bg-0)] rounded border border-[var(--line-2)] overflow-x-auto text-[11px] text-[var(--fg-1)] leading-relaxed">
                                {JSON.stringify(evt.metadata, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        <div className="flex items-center justify-between p-3 border-t border-[var(--line-1)] bg-[var(--bg-1)]">
          <span className="text-[11px] text-[var(--fg-2)]">
            Showing {events.length} event{events.length === 1 ? "" : "s"}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={handlePrevPage}
              disabled={offset === 0 || isLoading}
              className="text-xs"
            >
              &larr; Previous
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleNextPage}
              disabled={events.length < limit || isLoading}
              className="text-xs"
            >
              Next &rarr;
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
