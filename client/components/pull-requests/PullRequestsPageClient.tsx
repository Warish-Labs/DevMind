"use client";

import React, { useState, useEffect, useMemo } from "react";
import { apiClient } from "@/lib/api";
import type { PullRequestSummary } from "@devmind/common/api";
import { GitPullRequestIcon, SearchIcon } from "@/components/shell/icons";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { PullRequestsTable } from "./PullRequestsTable";
import { SAMPLE_PULL_REQUESTS } from "./types";

interface PullRequestsPageClientProps {
  projectId: string;
}

type PRStateFilter = "all" | "open" | "merged" | "closed";

export function PullRequestsPageClient({ projectId }: PullRequestsPageClientProps) {
  const [pullRequests, setPullRequests] = useState<PullRequestSummary[]>(SAMPLE_PULL_REQUESTS);
  const [isSyncing, setIsSyncing] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Filters
  const [stateFilter, setStateFilter] = useState<PRStateFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    let active = true;
    apiClient
      .listProjectPullRequests(projectId)
      .then((items) => {
        if (active && items && items.length > 0) {
          setPullRequests(items);
        }
      })
      .catch(() => {
        // Fallback to sample data for offline preview
      });

    return () => {
      active = false;
    };
  }, [projectId]);

  const handleSync = async () => {
    setIsSyncing(true);
    setStatusMessage(null);
    setErrorMessage(null);
    try {
      const synced = await apiClient.syncProjectPullRequests(projectId, "open");
      if (synced && synced.length > 0) {
        setPullRequests(synced);
        setStatusMessage(
          `Successfully synchronized ${synced.length} pull request${synced.length === 1 ? "" : "s"}.`
        );
      } else {
        setStatusMessage("Synchronization complete. No open pull requests found.");
      }
      setTimeout(() => setStatusMessage(null), 4000);
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : "Failed to synchronize pull requests. Ensure repository is linked in Settings.";
      setErrorMessage(message);
    } finally {
      setIsSyncing(false);
    }
  };

  // Filtered list
  const filteredPRs = useMemo(() => {
    return pullRequests.filter((pr) => {
      // State match
      if (stateFilter !== "all") {
        if (stateFilter === "open" && pr.state.toLowerCase() !== "open") return false;
        if (stateFilter === "merged" && pr.state.toLowerCase() !== "merged") return false;
        if (stateFilter === "closed" && pr.state.toLowerCase() !== "closed") return false;
      }

      // Query match
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchesTitle = pr.title.toLowerCase().includes(q);
        const matchesAuthor = (pr.author_login || "").toLowerCase().includes(q);
        const matchesNumber = String(pr.number).includes(q);
        const matchesBranch =
          (pr.head_ref || "").toLowerCase().includes(q) ||
          (pr.base_ref || "").toLowerCase().includes(q);

        if (!matchesTitle && !matchesAuthor && !matchesNumber && !matchesBranch) {
          return false;
        }
      }

      return true;
    });
  }, [pullRequests, stateFilter, searchQuery]);

  const counts = useMemo(() => {
    let open = 0;
    let merged = 0;
    let closed = 0;
    for (const pr of pullRequests) {
      const s = pr.state.toLowerCase();
      if (s === "open") open++;
      else if (s === "merged") merged++;
      else if (s === "closed") closed++;
    }
    return { all: pullRequests.length, open, merged, closed };
  }, [pullRequests]);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <GitPullRequestIcon size={22} className="text-[var(--signal)]" />
            <h1 className="text-xl font-bold text-[var(--fg-0)]">Pull Requests & Intelligence</h1>
          </div>
          <p className="text-xs text-[var(--fg-2)] mt-1">
            Mirrored GitHub pull requests, change-impact blast radius, and ReviewBuddy automated
            triage (Screen S-14)
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleSync}
            disabled={isSyncing}
            className="flex items-center gap-2"
          >
            <GitPullRequestIcon size={14} className={isSyncing ? "animate-spin" : ""} />
            <span>{isSyncing ? "Syncing from GitHub..." : "Sync PRs"}</span>
          </Button>
        </div>
      </div>

      {/* Status & Error Alerts */}
      {statusMessage && (
        <div className="p-3 bg-[rgba(32,227,162,0.1)] border border-[rgba(32,227,162,0.3)] text-[var(--signal)] text-xs rounded-lg flex items-center justify-between">
          <span>{statusMessage}</span>
          <button
            onClick={() => setStatusMessage(null)}
            className="text-[var(--fg-2)] hover:text-[var(--fg-0)] ml-2 text-sm"
          >
            ×
          </button>
        </div>
      )}

      {errorMessage && (
        <div className="p-3 bg-[rgba(255,107,94,0.1)] border border-[rgba(255,107,94,0.3)] text-[var(--danger)] text-xs rounded-lg flex items-center justify-between">
          <span>{errorMessage}</span>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-[var(--fg-2)] hover:text-[var(--fg-0)] ml-2 text-sm"
          >
            ×
          </button>
        </div>
      )}

      {/* Filter Bar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 bg-[var(--bg-1)] border border-[var(--line-1)] p-3 rounded-lg">
        {/* State Tabs */}
        <div className="flex items-center gap-1 overflow-x-auto">
          {(
            [
              { id: "all", label: "All", count: counts.all },
              { id: "open", label: "Open", count: counts.open },
              { id: "merged", label: "Merged", count: counts.merged },
              { id: "closed", label: "Closed", count: counts.closed },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              onClick={() => setStateFilter(tab.id)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors flex items-center gap-1.5 ${
                stateFilter === tab.id
                  ? "bg-[var(--bg-2)] text-[var(--fg-0)] border border-[var(--line-2)] shadow-xs"
                  : "text-[var(--fg-2)] hover:text-[var(--fg-1)] hover:bg-[var(--bg-2)]/50"
              }`}
            >
              <span>{tab.label}</span>
              <span className="text-[10px] font-mono opacity-70 bg-[var(--bg-0)] px-1 rounded">
                {tab.count}
              </span>
            </button>
          ))}
        </div>

        {/* Search Input */}
        <div className="relative w-full md:w-72">
          <SearchIcon
            size={14}
            className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--fg-3)] pointer-events-none"
          />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by title, branch, #number..."
            className="pl-8 text-xs h-8"
          />
        </div>
      </div>

      {/* Pull Requests List */}
      <PullRequestsTable projectId={projectId} pullRequests={filteredPRs} />
    </div>
  );
}
