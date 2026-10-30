"use client";

import React from "react";
import Link from "next/link";
import type { PullRequestSummary } from "@devmind/common/api";
import { Badge } from "@/components/ui/Badge";
import { GitPullRequestIcon, ExternalLinkIcon } from "@/components/shell/icons";
import { getPRStatusBadgeVariant } from "./types";

interface PullRequestsTableProps {
  projectId: string;
  pullRequests: PullRequestSummary[];
}

export function PullRequestsTable({ projectId, pullRequests }: PullRequestsTableProps) {
  if (pullRequests.length === 0) {
    return (
      <div className="border border-[var(--line-1)] bg-[var(--bg-1)] rounded-lg p-12 text-center">
        <GitPullRequestIcon size={32} className="mx-auto text-[var(--fg-3)] mb-3" />
        <h3 className="text-sm font-semibold text-[var(--fg-0)]">No pull requests found</h3>
        <p className="text-xs text-[var(--fg-2)] mt-1 max-w-sm mx-auto">
          No pull requests match the current filters or repository synchronization is pending.
        </p>
      </div>
    );
  }

  return (
    <div className="border border-[var(--line-1)] bg-[var(--bg-1)] rounded-lg overflow-hidden shadow-xs">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-[var(--line-1)] bg-[var(--bg-0)] text-[var(--fg-2)] uppercase font-mono tracking-wider text-[10px]">
              <th className="py-3 px-4 w-16">PR</th>
              <th className="py-3 px-4">Title & Branches</th>
              <th className="py-3 px-4 w-28">Status</th>
              <th className="py-3 px-4 w-32">Author</th>
              <th className="py-3 px-4 w-32">Head Commit</th>
              <th className="py-3 px-4 w-28 text-right">Updated</th>
              <th className="py-3 px-4 w-24 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--line-1)]">
            {pullRequests.map((pr) => {
              const statusVariant = getPRStatusBadgeVariant(pr.state);
              const formattedDate =
                pr.updated_at || pr.created_at
                  ? new Date(pr.updated_at || pr.created_at!).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                    })
                  : "—";

              return (
                <tr key={pr.id} className="hover:bg-[var(--bg-2)]/40 transition-colors group">
                  {/* PR Number */}
                  <td className="py-3 px-4 font-mono font-medium text-[var(--fg-1)]">
                    #{pr.number}
                  </td>

                  {/* Title & Branches */}
                  <td className="py-3 px-4">
                    <div className="flex flex-col gap-1">
                      <Link
                        href={`/projects/${projectId}/pull-requests/${pr.id}`}
                        className="font-medium text-[var(--fg-0)] hover:text-[var(--signal)] hover:underline line-clamp-1 transition-colors"
                      >
                        {pr.title}
                      </Link>
                      <div className="flex items-center gap-2 text-[11px] text-[var(--fg-2)] font-mono">
                        <span className="bg-[var(--bg-2)] px-1.5 py-0.2 rounded border border-[var(--line-2)] text-[var(--fg-1)]">
                          {pr.head_ref || pr.head_sha.slice(0, 7)}
                        </span>
                        <span>→</span>
                        <span>{pr.base_ref || "main"}</span>
                      </div>
                    </div>
                  </td>

                  {/* Status Badge */}
                  <td className="py-3 px-4">
                    <Badge variant={statusVariant} size="sm">
                      {pr.state.toUpperCase()}
                    </Badge>
                  </td>

                  {/* Author */}
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-2">
                      <div className="w-5 h-5 rounded-full bg-[var(--bg-2)] border border-[var(--line-2)] flex items-center justify-center font-mono text-[9px] text-[var(--fg-1)] uppercase">
                        {(pr.author_login || "gh").slice(0, 2)}
                      </div>
                      <span
                        className="text-[var(--fg-1)] truncate max-w-[100px]"
                        title={pr.author_login}
                      >
                        {pr.author_login}
                      </span>
                    </div>
                  </td>

                  {/* Head Commit SHA */}
                  <td className="py-3 px-4 font-mono text-[11px] text-[var(--fg-2)]">
                    <code>{pr.head_sha.slice(0, 8)}</code>
                  </td>

                  {/* Updated Time */}
                  <td className="py-3 px-4 text-right text-[var(--fg-2)] font-mono text-[11px]">
                    {formattedDate}
                  </td>

                  {/* Actions */}
                  <td className="py-3 px-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Link
                        href={`/projects/${projectId}/pull-requests/${pr.id}`}
                        className="px-2 py-1 rounded bg-[var(--bg-2)] hover:bg-[var(--bg-3)] border border-[var(--line-2)] text-[11px] font-medium text-[var(--fg-0)] transition-colors"
                      >
                        Inspect
                      </Link>
                      {pr.diff_url && (
                        <a
                          href={pr.diff_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-1 text-[var(--fg-2)] hover:text-[var(--fg-0)] transition-colors"
                          title="View Unified Diff"
                        >
                          <ExternalLinkIcon size={14} />
                        </a>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
