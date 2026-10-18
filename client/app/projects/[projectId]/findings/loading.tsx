"use client";

import React from "react";
import { Skeleton } from "@/components/ui/Skeleton";

export default function FindingsLoading() {
  return (
    <div role="status" aria-label="Loading security findings" className="space-y-6">
      <span className="sr-only">Loading security findings…</span>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--line-1)] pb-4">
        <div className="space-y-2">
          <Skeleton className="h-7 w-52 rounded-[var(--radius-control)]" />
          <Skeleton className="h-4 w-80 rounded-[var(--radius-sm)]" />
        </div>
        <Skeleton className="h-9 w-32 rounded-[var(--radius-control)]" />
      </div>

      {/* Filter bar skeleton */}
      <div className="p-4 bg-[var(--bg-1)] rounded-[var(--radius-panel)] border border-[var(--line-1)] space-y-3">
        <div className="flex gap-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-7 w-20 rounded-[var(--radius-chip)]" />
          ))}
        </div>
        <div className="flex gap-3">
          <Skeleton className="h-9 w-64 rounded-[var(--radius-control)]" />
          <Skeleton className="h-9 w-36 rounded-[var(--radius-control)]" />
        </div>
      </div>

      {/* Table rows skeleton */}
      <div className="border border-[var(--line-1)] rounded-[var(--radius-panel)] bg-[var(--bg-0)] p-4 space-y-3">
        {[1, 2, 3, 4, 5, 6].map((row) => (
          <div
            key={row}
            className="flex items-center justify-between py-2 border-b border-[var(--line-1)] last:border-0"
          >
            <div className="flex items-center gap-3">
              <Skeleton className="h-5 w-16 rounded-[var(--radius-chip)]" />
              <Skeleton className="h-5 w-10 rounded-[var(--radius-chip)]" />
              <Skeleton className="h-4 w-64 rounded-[var(--radius-sm)]" />
            </div>
            <div className="flex items-center gap-2">
              <Skeleton className="h-4 w-32 rounded-[var(--radius-sm)]" />
              <Skeleton className="h-7 w-20 rounded-[var(--radius-control)]" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
