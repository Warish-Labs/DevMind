"use client";

import React from "react";
import { Skeleton } from "@/components/ui/Skeleton";

export default function WorkspacesLoading() {
  return (
    <div role="status" aria-label="Loading workspaces directory" className="space-y-6">
      <span className="sr-only">Loading workspaces directory…</span>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--line-1)] pb-4">
        <div className="space-y-2">
          <Skeleton className="h-7 w-48 rounded-[var(--radius-control)]" />
          <Skeleton className="h-4 w-72 rounded-[var(--radius-sm)]" />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="p-5 rounded-[var(--radius-panel)] border border-[var(--line-1)] bg-[var(--bg-1)] space-y-3"
          >
            <div className="flex items-center gap-3">
              <Skeleton className="h-9 w-9 rounded-[var(--radius-control)]" />
              <div className="space-y-1">
                <Skeleton className="h-5 w-32 rounded-[var(--radius-sm)]" />
                <Skeleton className="h-3 w-20 rounded-[var(--radius-sm)]" />
              </div>
            </div>
            <Skeleton className="h-4 w-full rounded-[var(--radius-sm)]" />
          </div>
        ))}
      </div>
    </div>
  );
}
