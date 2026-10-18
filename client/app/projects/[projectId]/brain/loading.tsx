"use client";

import React from "react";
import { Skeleton } from "@/components/ui/Skeleton";

export default function BrainLoading() {
  return (
    <div role="status" aria-label="Loading project brain explorer" className="space-y-6">
      <span className="sr-only">Loading project brain explorer…</span>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--line-1)] pb-4">
        <div className="space-y-2">
          <Skeleton className="h-7 w-64 rounded-[var(--radius-control)]" />
          <Skeleton className="h-4 w-96 rounded-[var(--radius-sm)]" />
        </div>
        <div className="flex items-center gap-2">
          <Skeleton className="h-9 w-28 rounded-[var(--radius-control)]" />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[600px]">
        {/* File tree column */}
        <div className="lg:col-span-4 rounded-[var(--radius-panel)] border border-[var(--line-1)] bg-[var(--bg-1)] p-4 space-y-3">
          <Skeleton className="h-8 w-full rounded-[var(--radius-control)]" />
          {[1, 2, 3, 4, 5, 6, 7].map((i) => (
            <Skeleton
              key={i}
              className="h-6 rounded-[var(--radius-sm)]"
              style={{ width: `${60 + (i % 3) * 15}%` }}
            />
          ))}
        </div>

        {/* Brain pane content */}
        <div className="lg:col-span-8 rounded-[var(--radius-panel)] border border-[var(--line-1)] bg-[var(--bg-0)] p-6 space-y-4">
          <Skeleton className="h-6 w-48 rounded-[var(--radius-sm)]" />
          <Skeleton className="h-32 w-full rounded-[var(--radius-panel)]" />
          <Skeleton className="h-48 w-full rounded-[var(--radius-panel)]" />
        </div>
      </div>
    </div>
  );
}
