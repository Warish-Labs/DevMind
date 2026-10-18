"use client";

import React from "react";
import { Skeleton } from "@/components/ui/Skeleton";

export default function ProjectsLoading() {
  return (
    <div role="status" aria-label="Loading projects directory" className="space-y-6">
      <span className="sr-only">Loading projects directory…</span>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--line-1)] pb-4">
        <div className="space-y-2">
          <Skeleton className="h-7 w-48 rounded-[var(--radius-control)]" />
          <Skeleton className="h-4 w-80 rounded-[var(--radius-sm)]" />
        </div>
        <Skeleton className="h-9 w-36 rounded-[var(--radius-control)]" />
      </div>

      <div className="flex items-center gap-3">
        <Skeleton className="h-9 w-72 rounded-[var(--radius-control)]" />
        <Skeleton className="h-9 w-32 rounded-[var(--radius-control)]" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3, 4, 5, 6].map((idx) => (
          <div
            key={idx}
            className="p-5 rounded-[var(--radius-panel)] border border-[var(--line-1)] bg-[var(--bg-1)] space-y-3"
          >
            <div className="flex items-start justify-between">
              <Skeleton className="h-5 w-36 rounded-[var(--radius-sm)]" />
              <Skeleton className="h-5 w-16 rounded-[var(--radius-chip)]" />
            </div>
            <Skeleton className="h-4 w-full rounded-[var(--radius-sm)]" />
            <Skeleton className="h-4 w-3/4 rounded-[var(--radius-sm)]" />
            <div className="pt-3 border-t border-[var(--line-1)] flex items-center justify-between">
              <Skeleton className="h-4 w-24 rounded-[var(--radius-sm)]" />
              <Skeleton className="h-4 w-16 rounded-[var(--radius-sm)]" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
