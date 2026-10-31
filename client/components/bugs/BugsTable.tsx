"use client";

import React from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { BugRecordResponse } from "./types";

interface BugsTableProps {
  bugs: BugRecordResponse[];
  onSelectBug: (bugId: string) => void;
  onAddResolution: (bugId: string) => void;
}

export function BugsTable({ bugs, onSelectBug, onAddResolution }: BugsTableProps) {
  if (bugs.length === 0) {
    return (
      <div className="border border-[var(--line-1)] bg-[var(--bg-0)] rounded-panel p-8 text-center font-mono">
        <p className="text-sm font-semibold text-[var(--fg-1)]">No bug memory records found</p>
        <p className="text-xs text-[var(--fg-2)] mt-1">
          No recurring errors logged yet. Use the Error Matcher above or click &quot;Log Recurring
          Bug&quot; to record historical incidents.
        </p>
      </div>
    );
  }

  return (
    <div className="border border-[var(--line-1)] bg-[var(--bg-0)] rounded-panel overflow-hidden font-mono">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-[var(--line-1)] bg-[var(--bg-1)] text-[var(--fg-2)] text-[11px] uppercase tracking-wider font-semibold">
              <th className="py-2.5 px-3">Title &amp; Signature</th>
              <th className="py-2.5 px-3">Module Hint</th>
              <th className="py-2.5 px-3 text-center">Occurrences</th>
              <th className="py-2.5 px-3 text-center">Resolutions</th>
              <th className="py-2.5 px-3">Last Seen</th>
              <th className="py-2.5 px-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--line-1)]">
            {bugs.map((bug) => (
              <tr key={bug.id} className="hover:bg-[var(--bg-1)] transition-colors">
                <td className="py-3 px-3 max-w-[280px]">
                  <div className="font-semibold text-[var(--fg-0)] truncate">{bug.title}</div>
                  <div
                    className="text-[11px] text-[var(--fg-2)] font-mono truncate mt-0.5"
                    title={bug.error_signature}
                  >
                    {bug.error_signature}
                  </div>
                  <div className="text-[10px] text-[var(--signal)] font-mono truncate mt-0.5">
                    fp:{bug.fingerprint.slice(0, 16)}...
                  </div>
                </td>

                <td className="py-3 px-3">
                  {bug.module_hint ? (
                    <code className="text-[11px] text-[var(--ref)] bg-[var(--bg-1)] px-1.5 py-0.5 rounded border border-[var(--line-1)] truncate block max-w-[180px]">
                      {bug.module_hint}
                    </code>
                  ) : (
                    <span className="text-[var(--fg-2)]">—</span>
                  )}
                </td>

                <td className="py-3 px-3 text-center">
                  <Badge
                    variant={
                      bug.occurrence_count > 5
                        ? "danger"
                        : bug.occurrence_count > 1
                          ? "warn"
                          : "neutral"
                    }
                  >
                    {bug.occurrence_count}×
                  </Badge>
                </td>

                <td className="py-3 px-3 text-center">
                  <Badge variant={bug.resolutions_count > 0 ? "signal" : "neutral"}>
                    {bug.resolutions_count > 0 ? `${bug.resolutions_count} resolved` : "unresolved"}
                  </Badge>
                </td>

                <td className="py-3 px-3 text-[11px] text-[var(--fg-2)] whitespace-nowrap">
                  {new Date(bug.last_seen_at).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </td>

                <td className="py-3 px-3 text-right whitespace-nowrap">
                  <div className="flex items-center justify-end gap-1.5">
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={() => onSelectBug(bug.id)}
                      className="text-[11px] py-1 h-7"
                    >
                      Inspect
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={() => onAddResolution(bug.id)}
                      className="text-[11px] py-1 h-7 text-[var(--signal)] border-[var(--line-2)] hover:border-[var(--signal)]"
                    >
                      + Resolution
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
