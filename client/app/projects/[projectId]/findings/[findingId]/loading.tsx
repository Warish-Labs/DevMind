"use client";

import React from "react";
import { Skeleton } from "@/components/ui/Skeleton";

export default function FindingDetailLoading() {
  return (
    <div role="status" aria-label="Loading finding details" className="space-y-6">
      <span className="sr-only">Loading finding details…</span>
      <div className="flex items-center gap-2 text-xs">
        <Skeleton className="h-4 w-24 rounded-[var(--radius-sm)]" />
        <span>/</span>
        <Skeleton className="h-4 w-32 rounded-[var(--radius-sm)]" />
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--line-1)] pb-4">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Skeleton className="h-5 w-16 rounded-[var(--radius-chip)]" />
            <Skeleton className="h-5 w-10 rounded-[var(--radius-chip)]" />
            <Skeleton className="h-5 w-20 rounded-[var(--radius-chip)]" />
          </div>
          <Skeleton className="h-7 w-96 rounded-[var(--radius-control)]" />
        </div>
        <div className="flex items-center gap-2">
          <Skeleton className="h-9 w-24 rounded-[var(--radius-control)]" />
          <Skeleton className="h-9 w-24 rounded-[var(--radius-control)]" />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Skeleton className="h-48 rounded-[var(--radius-panel)]" />
          <Skeleton className="h-64 rounded-[var(--radius-panel)]" />
        </div>
        <div className="space-y-6">
          <Skeleton className="h-40 rounded-[var(--radius-panel)]" />
          <Skeleton className="h-48 rounded-[var(--radius-panel)]" />
        </div>
      </div>
    </div>
  );
}
