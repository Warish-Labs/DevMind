"use client";

import React from "react";
import { Skeleton } from "@/components/ui/Skeleton";

export default function ChatLoading() {
  return (
    <div
      role="status"
      aria-label="Loading project conversation"
      className="space-y-6 max-w-5xl mx-auto h-[calc(100vh-140px)] flex flex-col justify-between"
    >
      <span className="sr-only">Loading project conversation…</span>
      <div className="flex items-center justify-between border-b border-[var(--line-1)] pb-4 shrink-0">
        <div className="space-y-2">
          <Skeleton className="h-6 w-52 rounded-[var(--radius-control)]" />
          <Skeleton className="h-4 w-72 rounded-[var(--radius-sm)]" />
        </div>
        <Skeleton className="h-8 w-24 rounded-[var(--radius-control)]" />
      </div>

      <div className="flex-1 space-y-4 py-4 overflow-hidden">
        <div className="flex items-start gap-3">
          <Skeleton className="h-8 w-8 rounded-full shrink-0" />
          <Skeleton className="h-16 w-3/4 rounded-[var(--radius-panel)]" />
        </div>
        <div className="flex items-start justify-end gap-3">
          <Skeleton className="h-12 w-1/2 rounded-[var(--radius-panel)]" />
        </div>
        <div className="flex items-start gap-3">
          <Skeleton className="h-8 w-8 rounded-full shrink-0" />
          <Skeleton className="h-28 w-4/5 rounded-[var(--radius-panel)]" />
        </div>
      </div>

      <div className="shrink-0 pt-4 border-t border-[var(--line-1)] space-y-2">
        <Skeleton className="h-24 w-full rounded-[var(--radius-panel)]" />
        <div className="flex justify-between items-center">
          <Skeleton className="h-4 w-40 rounded-[var(--radius-sm)]" />
          <Skeleton className="h-8 w-24 rounded-[var(--radius-control)]" />
        </div>
      </div>
    </div>
  );
}
