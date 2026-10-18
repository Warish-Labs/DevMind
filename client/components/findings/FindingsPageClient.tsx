"use client";

import React, { useState, useEffect } from "react";
import type { FindingItem } from "@devmind/common/api";
import { apiClient } from "@/lib/api";
import { FindingsTable } from "./FindingsTable";
import { SAMPLE_FINDINGS_LIST } from "./types";

export interface FindingsPageClientProps {
  projectId: string;
}

export function FindingsPageClient({ projectId }: FindingsPageClientProps) {
  const [findings, setFindings] = useState<FindingItem[]>(SAMPLE_FINDINGS_LIST);

  useEffect(() => {
    let active = true;
    apiClient
      .listFindings(projectId)
      .then((items) => {
        if (active && items && items.length > 0) {
          setFindings(items);
        }
      })
      .catch(() => {
        // Offline / sample fallback
      });

    return () => {
      active = false;
    };
  }, [projectId]);

  const handleStatusTransition = async (
    findingId: string,
    payload: { to_status: string; reason?: string }
  ) => {
    try {
      await apiClient.transitionFindingStatus(projectId, findingId, {
        to_status: payload.to_status,
        reason: payload.reason,
      });
      // Update local state
      setFindings((prev) =>
        prev.map((f) =>
          f.id === findingId
            ? { ...f, status: payload.to_status, status_reason: payload.reason || f.status_reason }
            : f
        )
      );
    } catch {
      // Optimistic/mock update fallback
      setFindings((prev) =>
        prev.map((f) =>
          f.id === findingId
            ? { ...f, status: payload.to_status, status_reason: payload.reason || f.status_reason }
            : f
        )
      );
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-[var(--fg-0)]">Project Findings</h1>
          <p className="text-xs text-[var(--fg-2)] mt-0.5">
            Security vulnerabilities, architecture violations, and machine-verified evidence (Screen
            S-07)
          </p>
        </div>
      </div>

      {/* Findings Table */}
      <FindingsTable
        projectId={projectId}
        findings={findings}
        isAnalyzed={true}
        hasMaintainerPermission={true}
        onStatusTransition={handleStatusTransition}
      />
    </div>
  );
}
