"use client";

import React from "react";
import { Skeleton } from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div
      role="status"
      aria-label="Loading page content"
      className="w-full max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 space-y-6 animate-pulse motion-reduce:animate-none"
    >
      <span className="sr-only">Loading page content…</span>
      <div className="flex items-center justify-between border-b border-[var(--line-1)] pb-4">
        <div className="space-y-2">
          <Skeleton className="h-7 w-48 rounded-[var(--radius-control)]" />
          <Skeleton className="h-4 w-72 rounded-[var(--radius-sm)]" />
        </div>
        <Skeleton className="h-9 w-28 rounded-[var(--radius-control)]" />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Skeleton className="h-24 rounded-[var(--radius-panel)]" />
        <Skeleton className="h-24 rounded-[var(--radius-panel)]" />
        <Skeleton className="h-24 rounded-[var(--radius-panel)]" />
        <Skeleton className="h-24 rounded-[var(--radius-panel)]" />
      </div>

      <Skeleton className="h-64 rounded-[var(--radius-panel)] w-full" />
    </div>
  );
}
