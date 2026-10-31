"use client";

import React from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { type TaskRecommendationResponse, type ProjectTaskResponse } from "./types";

interface MentorRecommendationSpotlightProps {
  recommendation: TaskRecommendationResponse | null;
  isLoading: boolean;
  onRefresh: () => void;
  onUpdateStatus: (taskId: string, status: string) => void;
  onSelectTask: (task: ProjectTaskResponse) => void;
}

export function MentorRecommendationSpotlight({
  recommendation,
  isLoading,
  onRefresh,
  onUpdateStatus,
  onSelectTask,
}: MentorRecommendationSpotlightProps) {
  if (isLoading) {
    return (
      <div className="rounded-panel border border-[var(--line-1)] bg-[var(--bg-1)] p-6 animate-pulse">
        <div className="flex items-center justify-between mb-4">
          <div className="h-5 w-48 bg-[var(--line-2)] rounded" />
          <div className="h-5 w-24 bg-[var(--line-2)] rounded" />
        </div>
        <div className="h-7 w-3/4 bg-[var(--line-2)] rounded mb-3" />
        <div className="h-4 w-full bg-[var(--line-2)] rounded mb-2" />
        <div className="h-4 w-2/3 bg-[var(--line-2)] rounded" />
      </div>
    );
  }

  if (!recommendation || !recommendation.recommended_task) {
    return (
      <div className="rounded-panel border border-dashed border-[var(--line-2)] bg-[var(--bg-1)] p-6 text-center">
        <h3 className="text-base font-semibold text-[var(--fg-0)] mb-1">Backlog is Clear</h3>
        <p className="text-sm text-[var(--fg-2)] mb-4">
          {recommendation?.narrative || "No active or pending tasks in project backlog."}
        </p>
        <Button variant="secondary" size="sm" onClick={onRefresh}>
          Refresh Recommendation
        </Button>
      </div>
    );
  }

  const task = recommendation.recommended_task;
  const isReady = recommendation.is_ready;

  return (
    <section
      aria-label="Recommended Next Task Spotlight"
      className="relative overflow-hidden rounded-panel border border-[var(--ref)]/30 bg-[var(--bg-1)] p-6 shadow-sm"
    >
      <div className="absolute top-0 left-0 bottom-0 w-1.5 bg-[var(--signal)]" />

      {/* Header Info */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs uppercase tracking-wider text-[var(--signal)] font-bold">
            ProjectMentor Recommendation · Rank #{recommendation.rank}
          </span>
          <Badge variant={isReady ? "signal" : "warn"} size="sm">
            {isReady ? "Ready to Start" : "Blocked by Prerequisites"}
          </Badge>
          <Badge
            variant={
              task.priority === "critical"
                ? "danger"
                : task.priority === "high"
                  ? "warn"
                  : "neutral"
            }
            size="sm"
          >
            {task.priority.toUpperCase()}
          </Badge>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-[var(--fg-3)]">
            Score: {recommendation.score.toFixed(1)}
          </span>
          <Button
            variant="tertiary"
            size="sm"
            onClick={onRefresh}
            className="text-xs text-[var(--fg-2)] hover:text-[var(--fg-0)]"
          >
            Re-evaluate
          </Button>
        </div>
      </div>

      {/* Title & Description */}
      <div className="mb-4">
        <h2
          onClick={() => onSelectTask(task)}
          className="text-lg font-semibold text-[var(--fg-0)] hover:text-[var(--signal)] cursor-pointer transition-colors"
        >
          {task.title}
        </h2>
        {task.description && (
          <p className="text-sm text-[var(--fg-2)] mt-1 line-clamp-2">{task.description}</p>
        )}
      </div>

      {/* Narrative & Strategic Rationale */}
      <div className="rounded-control bg-[var(--bg-0)] border border-[var(--line-1)] p-3.5 mb-4 text-xs font-sans text-[var(--fg-1)] leading-relaxed">
        <div className="font-semibold text-[var(--signal)] mb-1 flex items-center gap-1.5">
          <svg
            className="w-3.5 h-3.5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <circle cx="12" cy="12" r="10" />
            <path d="M12 16v-4M12 8h.01" />
          </svg>
          Strategic Mentor Guidance
        </div>
        <p>{recommendation.narrative}</p>
        {recommendation.downstream_impact_count > 0 && (
          <p className="mt-2 text-[var(--fg-2)] font-mono">
            ↳ Completing this work item unblocks {recommendation.downstream_impact_count} downstream
            task(s).
          </p>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-1 border-t border-[var(--line-1)]">
        <div className="flex items-center gap-2">
          {task.status !== "in_progress" && (
            <Button
              variant="primary"
              size="sm"
              onClick={() => onUpdateStatus(task.id, "in_progress")}
            >
              Start Working
            </Button>
          )}
          {task.status !== "completed" && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => onUpdateStatus(task.id, "completed")}
            >
              Mark Completed
            </Button>
          )}
          <Button variant="tertiary" size="sm" onClick={() => onSelectTask(task)}>
            View Details & Dependencies
          </Button>
        </div>

        <span className="text-xs font-mono text-[var(--fg-3)]">
          {recommendation.unblocked_count} of {recommendation.total_pending_tasks} pending tasks
          ready
        </span>
      </div>
    </section>
  );
}
