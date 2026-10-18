"use client";

import React, { useState, useEffect } from "react";
import type { FindingDetailItem } from "@devmind/common/api";
import { apiClient } from "@/lib/api";
import { FindingDetail } from "./FindingDetail";
import { SAMPLE_FINDING_DETAILS } from "./types";

export interface FindingDetailPageClientProps {
  projectId: string;
  findingId: string;
}

export function FindingDetailPageClient({ projectId, findingId }: FindingDetailPageClientProps) {
  const [finding, setFinding] = useState<FindingDetailItem | null>(() => {
    return SAMPLE_FINDING_DETAILS[findingId] || Object.values(SAMPLE_FINDING_DETAILS)[0];
  });

  useEffect(() => {
    let active = true;
    apiClient
      .getFindingDetail(projectId, findingId)
      .then((item) => {
        if (active && item) {
          setFinding(item);
        }
      })
      .catch(() => {
        // Fallback to sample finding
      });

    return () => {
      active = false;
    };
  }, [projectId, findingId]);

  const handleStatusTransition = async (
    targetFindingId: string,
    payload: { to_status: string; reason?: string }
  ) => {
    try {
      const updated = await apiClient.transitionFindingStatus(projectId, targetFindingId, {
        to_status: payload.to_status,
        reason: payload.reason,
      });
      if (updated) {
        setFinding(updated);
      }
    } catch {
      // Optimistic/mock update fallback
      setFinding((prev) => {
        if (!prev) return null;
        const newHistory = [
          ...(prev.history || []),
          {
            id: `hist-client-${Date.now()}`,
            finding_id: targetFindingId,
            from_status: prev.status,
            to_status: payload.to_status,
            actor_kind: "user",
            actor_id: "current_user",
            reason: payload.reason || "Updated via web UI",
            created_at: new Date().toISOString(),
          },
        ];
        return {
          ...prev,
          status: payload.to_status,
          status_reason: payload.reason || prev.status_reason,
          history: newHistory,
        };
      });
    }
  };

  if (!finding) {
    return <div className="p-8 text-center text-xs text-[var(--fg-2)]">Finding not found.</div>;
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <FindingDetail
        projectId={projectId}
        finding={finding}
        hasMaintainerPermission={true}
        onStatusTransition={handleStatusTransition}
      />
    </div>
  );
}
