"use client";

import React from "react";
import { Skeleton } from "@/components/ui/Skeleton";

export default function ProjectOverviewLoading() {
  return (
    <div role="status" aria-label="Loading project overview" className="space-y-6">
      <span className="sr-only">Loading project overview…</span>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--line-1)] pb-4">
        <div className="space-y-2">
          <Skeleton className="h-7 w-60 rounded-[var(--radius-control)]" />
          <Skeleton className="h-4 w-96 rounded-[var(--radius-sm)]" />
        </div>
        <div className="flex items-center gap-2">
          <Skeleton className="h-9 w-28 rounded-[var(--radius-control)]" />
          <Skeleton className="h-9 w-28 rounded-[var(--radius-control)]" />
        </div>
      </div>

      {/* Coverage & Health Strip Skeleton */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-28 rounded-[var(--radius-panel)]" />
        ))}
      </div>

      {/* Next Actions Band */}
      <Skeleton className="h-20 rounded-[var(--radius-panel)] w-full" />

      {/* Two-panel Grid (Findings & Activity) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Skeleton className="h-80 rounded-[var(--radius-panel)]" />
        <Skeleton className="h-80 rounded-[var(--radius-panel)]" />
      </div>
    </div>
  );
}
