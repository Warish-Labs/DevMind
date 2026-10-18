"use client";

import React from "react";
import { Skeleton } from "@/components/ui/Skeleton";

export default function JobsLoading() {
  return (
    <div role="status" aria-label="Loading job center" className="space-y-6">
      <span className="sr-only">Loading job center…</span>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--line-1)] pb-4">
        <div className="space-y-2">
          <Skeleton className="h-7 w-48 rounded-[var(--radius-control)]" />
          <Skeleton className="h-4 w-80 rounded-[var(--radius-sm)]" />
        </div>
        <Skeleton className="h-9 w-32 rounded-[var(--radius-control)]" />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-20 rounded-[var(--radius-panel)]" />
        ))}
      </div>

      <div className="border border-[var(--line-1)] rounded-[var(--radius-panel)] bg-[var(--bg-0)] p-4 space-y-3">
        {[1, 2, 3, 4, 5].map((row) => (
          <div
            key={row}
            className="flex items-center justify-between py-2 border-b border-[var(--line-1)] last:border-0"
          >
            <div className="flex items-center gap-3">
              <Skeleton className="h-5 w-20 rounded-[var(--radius-chip)]" />
              <Skeleton className="h-4 w-44 rounded-[var(--radius-sm)]" />
            </div>
            <div className="flex items-center gap-3">
              <Skeleton className="h-4 w-28 rounded-[var(--radius-sm)]" />
              <Skeleton className="h-4 w-16 rounded-[var(--radius-sm)]" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
