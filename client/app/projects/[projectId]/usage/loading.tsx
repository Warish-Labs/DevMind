"use client";

import React from "react";
import { Skeleton } from "@/components/ui/Skeleton";

export default function UsageLoading() {
  return (
    <div role="status" aria-label="Loading usage and quotas" className="space-y-6">
      <span className="sr-only">Loading usage and quotas…</span>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--line-1)] pb-4">
        <div className="space-y-2">
          <Skeleton className="h-7 w-56 rounded-[var(--radius-control)]" />
          <Skeleton className="h-4 w-96 rounded-[var(--radius-sm)]" />
        </div>
        <Skeleton className="h-9 w-28 rounded-[var(--radius-control)]" />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-28 rounded-[var(--radius-panel)]" />
        ))}
      </div>

      <div className="space-y-4">
        <div className="flex gap-2">
          <Skeleton className="h-9 w-32 rounded-[var(--radius-control)]" />
          <Skeleton className="h-9 w-32 rounded-[var(--radius-control)]" />
        </div>
        <Skeleton className="h-64 rounded-[var(--radius-panel)] w-full" />
      </div>
    </div>
  );
}
