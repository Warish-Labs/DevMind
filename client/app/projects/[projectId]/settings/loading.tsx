"use client";

import React from "react";
import { Skeleton } from "@/components/ui/Skeleton";

export default function ProjectSettingsLoading() {
  return (
    <div role="status" aria-label="Loading project settings" className="space-y-6">
      <span className="sr-only">Loading project settings…</span>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--line-1)] pb-4">
        <div className="space-y-2">
          <Skeleton className="h-7 w-64 rounded-[var(--radius-control)]" />
          <Skeleton className="h-4 w-96 rounded-[var(--radius-sm)]" />
        </div>
        <div className="flex items-center gap-2">
          <Skeleton className="h-9 w-32 rounded-[var(--radius-control)]" />
        </div>
      </div>

      {/* Tabs Skeleton */}
      <div className="flex items-center gap-4 border-b border-[var(--line-1)] pb-2">
        <Skeleton className="h-6 w-36 rounded-[var(--radius-sm)]" />
        <Skeleton className="h-6 w-36 rounded-[var(--radius-sm)]" />
        <Skeleton className="h-6 w-24 rounded-[var(--radius-sm)]" />
      </div>

      {/* Cards Skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Skeleton className="h-72 rounded-[var(--radius-panel)]" />
        <Skeleton className="h-72 rounded-[var(--radius-panel)]" />
      </div>
    </div>
  );
}
