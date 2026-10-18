"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { apiClient } from "@/lib/api";
import type { JobEventItem, JobWithDetails } from "./types";

export interface UseJobEventsOptions {
  enabled?: boolean;
  pollIntervalMs?: number;
  initialEvents?: JobEventItem[];
  initialStatus?: string;
  initialProgressPct?: number;
  onStatusChange?: (newStatus: string) => void;
}

export interface UseJobEventsResult {
  events: JobEventItem[];
  status: string;
  progressPct: number;
  connectionMode: "sse" | "polling" | "closed";
  isLive: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useJobEvents(jobId: string, options: UseJobEventsOptions = {}): UseJobEventsResult {
  const {
    enabled = true,
    pollIntervalMs = 3000,
    initialEvents = [],
    initialStatus = "running",
    initialProgressPct = 0,
    onStatusChange,
  } = options;

  const [events, setEvents] = useState<JobEventItem[]>(initialEvents);
  const [status, setStatus] = useState<string>(initialStatus);
  const [progressPct, setProgressPct] = useState<number>(initialProgressPct);
  const [internalMode, setInternalMode] = useState<"sse" | "polling">("sse");
  const [error, setError] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isTerminal = ["succeeded", "failed", "cancelled", "timed_out"].includes(status);
  const connectionMode: "sse" | "polling" | "closed" =
    !enabled || isTerminal ? "closed" : internalMode;

  // Manual or fallback polling function
  const fetchJobStatus = useCallback(async () => {
    try {
      const job = (await apiClient.getJob(jobId)) as JobWithDetails;
      if (job) {
        setStatus(job.status);
        if (onStatusChange && job.status !== status) {
          onStatusChange(job.status);
        }
        if (job.progressPct !== undefined) {
          setProgressPct(job.progressPct);
        }
      }
    } catch (err: unknown) {
      const errObj = err as { message?: string };
      setError(errObj.message || "Failed to fetch job status");
    }
  }, [jobId, onStatusChange, status]);

  // Setup streaming or fallback polling
  useEffect(() => {
    if (!enabled || isTerminal) {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      return;
    }

    let isSubscribed = true;

    // Helper to start polling fallback
    const startPolling = () => {
      if (!isSubscribed) return;
      setInternalMode("polling");
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      pollTimerRef.current = setInterval(fetchJobStatus, pollIntervalMs);
    };

    // Attempt EventSource connection if available in browser
    if (typeof window !== "undefined" && "EventSource" in window) {
      try {
        const streamUrl = `/api/v1/jobs/${jobId}/events`;
        const es = new EventSource(streamUrl);
        eventSourceRef.current = es;

        es.onmessage = (e) => {
          if (!isSubscribed) return;
          try {
            const parsed = JSON.parse(e.data);
            const newEvent: JobEventItem = {
              id: parsed.id || `evt-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
              jobId,
              seq: parsed.seq || events.length + 1,
              kind: (parsed.kind || "milestone") as JobEventItem["kind"],
              message: parsed.message || "Job step progressed",
              data: parsed.data || {},
              createdAt: parsed.created_at || new Date().toISOString(),
            };

            setEvents((prev) => {
              // Avoid duplicates
              if (prev.some((item) => item.seq === newEvent.seq)) return prev;
              return [...prev, newEvent];
            });

            if (parsed.progress_pct !== undefined) {
              setProgressPct(parsed.progress_pct);
            }
            if (parsed.status) {
              setStatus(parsed.status);
              if (onStatusChange) onStatusChange(parsed.status);
            }
          } catch {
            // Ignore parse errors on raw messages
          }
        };

        es.onerror = () => {
          if (!isSubscribed) return;
          // Gracefully fallback to polling on error or disconnect
          if (es.readyState === EventSource.CLOSED) {
            es.close();
            eventSourceRef.current = null;
            startPolling();
          }
        };
      } catch {
        startPolling();
      }
    } else {
      startPolling();
    }

    return () => {
      isSubscribed = false;
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [enabled, jobId, isTerminal, pollIntervalMs, fetchJobStatus, onStatusChange, events.length]);

  return {
    events,
    status,
    progressPct,
    connectionMode,
    isLive: connectionMode === "sse" || connectionMode === "polling",
    error,
    refresh: fetchJobStatus,
  };
}
