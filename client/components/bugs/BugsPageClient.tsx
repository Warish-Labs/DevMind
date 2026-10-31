"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { BugIcon, SearchIcon, PlusIcon } from "@/components/shell/icons";
import { apiClient } from "@/lib/api";
import {
  type BugRecordResponse,
  type BugRecordDetailResponse,
  SAMPLE_BUGS,
  SAMPLE_BUG_DETAIL,
} from "./types";
import { ErrorMatcherPanel } from "./ErrorMatcherPanel";
import { BugsTable } from "./BugsTable";
import { BugDetailModal } from "./BugDetailModal";
import { AddResolutionModal } from "./AddResolutionModal";
import { LogBugModal } from "./LogBugModal";

interface BugsPageClientProps {
  projectId: string;
}

export function BugsPageClient({ projectId }: BugsPageClientProps) {
  const [bugs, setBugs] = useState<BugRecordResponse[]>(SAMPLE_BUGS);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedBugDetail, setSelectedBugDetail] = useState<BugRecordDetailResponse | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [activeBugForResolution, setActiveBugForResolution] = useState<string | null>(null);
  const [isLogBugOpen, setIsLogBugOpen] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const fetchBugs = useCallback(async () => {
    try {
      const items = await apiClient.listProjectBugs(projectId);
      if (items && items.length > 0) {
        setBugs(items);
      }
    } catch {
      // Fallback to sample data for preview
    }
  }, [projectId]);

  useEffect(() => {
    let active = true;
    apiClient
      .listProjectBugs(projectId)
      .then((items) => {
        if (active && items && items.length > 0) {
          setBugs(items);
        }
      })
      .catch(() => {
        // Fallback to sample data for preview
      });

    return () => {
      active = false;
    };
  }, [projectId]);

  const handleSelectBug = async (bugId: string) => {
    try {
      const detail = await apiClient.getBugDetail(bugId);
      setSelectedBugDetail(detail);
      setIsDetailOpen(true);
    } catch {
      // Fallback matching sample
      const found = SAMPLE_BUGS.find((b) => b.id === bugId);
      if (found) {
        setSelectedBugDetail({
          ...SAMPLE_BUG_DETAIL,
          id: found.id,
          title: found.title,
          error_signature: found.error_signature,
          occurrence_count: found.occurrence_count,
          resolutions_count: found.resolutions_count,
        });
      } else {
        setSelectedBugDetail(SAMPLE_BUG_DETAIL);
      }
      setIsDetailOpen(true);
    }
  };

  const handleResolutionSuccess = () => {
    setStatusMessage("Resolution successfully documented and added to Bug Memory.");
    fetchBugs();
    setTimeout(() => setStatusMessage(null), 4000);
  };

  const handleLogBugSuccess = () => {
    setStatusMessage("Bug record successfully registered and indexed.");
    fetchBugs();
    setTimeout(() => setStatusMessage(null), 4000);
  };

  const filteredBugs = useMemo(() => {
    if (!searchQuery.trim()) return bugs;
    const q = searchQuery.toLowerCase().trim();
    return bugs.filter(
      (b) =>
        b.title.toLowerCase().includes(q) ||
        b.error_signature.toLowerCase().includes(q) ||
        (b.module_hint && b.module_hint.toLowerCase().includes(q)) ||
        b.fingerprint.toLowerCase().includes(q)
    );
  }, [bugs, searchQuery]);

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto w-full p-4 sm:p-6 lg:p-8 font-mono">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--line-1)] pb-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-control bg-[var(--bg-1)] border border-[var(--line-1)] flex items-center justify-center text-[var(--danger)]">
              <BugIcon size={18} />
            </div>
            <h1 className="text-xl font-bold text-[var(--fg-0)] tracking-tight">
              Bug Memory &amp; Historical Resolutions
            </h1>
            <Badge variant="neutral" className="text-[10px]">
              CAP-03 · Screen S-15
            </Badge>
          </div>
          <p className="text-xs text-[var(--fg-2)] mt-1.5 max-w-3xl">
            Never re-solve the same recurring bug from zero. Normalizes stack traces into
            deterministic fingerprints, retrieves past incident resolutions, and applies specialist
            agent AI recommendations.
          </p>
        </div>

        <Button
          type="button"
          variant="primary"
          size="sm"
          onClick={() => setIsLogBugOpen(true)}
          className="self-start sm:self-auto flex items-center gap-1.5 text-xs font-semibold shrink-0"
        >
          <PlusIcon size={14} />
          <span>Log Recurring Bug</span>
        </Button>
      </div>

      {statusMessage && (
        <div className="p-3 bg-[var(--bg-1)] border-l-2 border-[var(--signal)] text-[var(--fg-0)] text-xs rounded-control flex items-center justify-between transition-all">
          <span>{statusMessage}</span>
          <button
            type="button"
            onClick={() => setStatusMessage(null)}
            className="text-[var(--fg-2)] hover:text-[var(--fg-0)] text-xs"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Interactive Error Matcher Panel */}
      <ErrorMatcherPanel projectId={projectId} onSelectCandidate={handleSelectBug} />

      {/* Tracked Incidents Ledger */}
      <div className="flex flex-col gap-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-[var(--fg-0)] uppercase tracking-wider">
              Project Incident Ledger
            </h2>
            <Badge variant="neutral" className="text-[11px]">
              {filteredBugs.length} recorded
            </Badge>
          </div>

          <div className="relative w-full sm:w-64">
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter by signature or module..."
              className="text-xs pl-8 font-mono"
            />
            <SearchIcon
              size={14}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--fg-2)] pointer-events-none"
            />
          </div>
        </div>

        <BugsTable
          bugs={filteredBugs}
          onSelectBug={handleSelectBug}
          onAddResolution={(bugId) => setActiveBugForResolution(bugId)}
        />
      </div>

      {/* Modals */}
      <BugDetailModal
        bug={selectedBugDetail}
        isOpen={isDetailOpen}
        onClose={() => setIsDetailOpen(false)}
        onAddResolution={(bugId) => setActiveBugForResolution(bugId)}
      />

      <AddResolutionModal
        bugId={activeBugForResolution}
        isOpen={Boolean(activeBugForResolution)}
        onClose={() => setActiveBugForResolution(null)}
        onSuccess={handleResolutionSuccess}
      />

      <LogBugModal
        projectId={projectId}
        isOpen={isLogBugOpen}
        onClose={() => setIsLogBugOpen(false)}
        onSuccess={handleLogBugSuccess}
      />
    </div>
  );
}
