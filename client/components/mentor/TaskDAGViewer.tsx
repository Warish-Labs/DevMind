"use client";

import React, { useMemo } from "react";
import { Badge } from "@/components/ui/Badge";
import { type ProjectTaskResponse } from "./types";

interface TaskDAGViewerProps {
  tasks: ProjectTaskResponse[];
  onSelectTask: (task: ProjectTaskResponse) => void;
}

export function TaskDAGViewer({ tasks, onSelectTask }: TaskDAGViewerProps) {
  // Build task map and dependency graph
  const { taskMap, levels, hasCycle } = useMemo(() => {
    const map = new Map<string, ProjectTaskResponse>();
    tasks.forEach((t) => map.set(t.id, t));

    // Forward adjacency and in-degree calculation for active tasks
    const inDegree = new Map<string, number>();
    const adj = new Map<string, string[]>();

    tasks.forEach((t) => {
      inDegree.set(t.id, 0);
      adj.set(t.id, []);
    });

    tasks.forEach((t) => {
      (t.depends_on_ids || []).forEach((depId) => {
        if (map.has(depId)) {
          // Edge: depId -> t.id (t depends on depId)
          adj.get(depId)?.push(t.id);
          inDegree.set(t.id, (inDegree.get(t.id) || 0) + 1);
        }
      });
    });

    // Compute topological levels using BFS
    const levelsArr: ProjectTaskResponse[][] = [];
    let currentLevel: string[] = [];

    inDegree.forEach((deg, id) => {
      if (deg === 0) currentLevel.push(id);
    });

    let visitedCount = 0;
    const assignedLevel = new Map<string, number>();
    currentLevel.forEach((id) => assignedLevel.set(id, 0));

    while (currentLevel.length > 0) {
      const nextLevel: string[] = [];
      const currentTasks: ProjectTaskResponse[] = [];

      for (const taskId of currentLevel) {
        visitedCount++;
        const t = map.get(taskId);
        if (t) currentTasks.push(t);

        const currentLvlNum = assignedLevel.get(taskId) || 0;

        for (const dependentId of adj.get(taskId) || []) {
          const nextLvlNum = Math.max(assignedLevel.get(dependentId) || 0, currentLvlNum + 1);
          assignedLevel.set(dependentId, nextLvlNum);

          const newDeg = (inDegree.get(dependentId) || 1) - 1;
          inDegree.set(dependentId, newDeg);
          if (newDeg === 0) {
            nextLevel.push(dependentId);
          }
        }
      }

      if (currentTasks.length > 0) {
        levelsArr.push(currentTasks);
      }
      currentLevel = nextLevel;
    }

    const cycleDetected = visitedCount < tasks.length;
    return { taskMap: map, levels: levelsArr, hasCycle: cycleDetected };
  }, [tasks]);

  return (
    <div className="flex flex-col gap-6">
      {/* DAG Header Summary */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]">
        <div>
          <h3 className="text-sm font-semibold text-[var(--fg-0)]">
            Dependency Graph Topological Visualization
          </h3>
          <p className="text-xs text-[var(--fg-2)] mt-0.5">
            Tasks flow from unblocked prerequisites (Level 0) down to dependent milestones.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant={hasCycle ? "danger" : "signal"} size="sm">
            {hasCycle ? "Cyclic Dependency Detected" : "Strictly Acyclic DAG (Verified)"}
          </Badge>
          <span className="font-mono text-xs text-[var(--fg-3)]">
            {levels.length} execution tiers
          </span>
        </div>
      </div>

      {/* Tiers Container */}
      {levels.length === 0 ? (
        <div className="p-12 text-center rounded-panel border border-dashed border-[var(--line-2)] bg-[var(--bg-1)]">
          <p className="text-sm text-[var(--fg-2)]">No task dependencies defined yet.</p>
          <p className="text-xs text-[var(--fg-3)] mt-1">
            Link tasks using the &apos;Link&apos; button in the backlog to generate the dependency
            graph.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          {levels.map((tierTasks, tierIdx) => (
            <div key={tierIdx} className="relative flex flex-col gap-3">
              {/* Tier Label */}
              <div className="flex items-center gap-3">
                <span className="px-2.5 py-1 rounded bg-[var(--bg-2)] border border-[var(--line-2)] font-mono text-[11px] font-bold text-[var(--signal)]">
                  Tier {tierIdx} {tierIdx === 0 ? "· Unblocked & Ready" : "· Downstream Dependent"}
                </span>
                <div className="flex-1 h-[1px] bg-[var(--line-1)]" />
                <span className="font-mono text-[11px] text-[var(--fg-3)]">
                  {tierTasks.length} task(s)
                </span>
              </div>

              {/* Node Cards in this tier */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {tierTasks.map((t) => {
                  const isDone = t.status === "completed";
                  const unmetDeps = (t.depends_on_ids || []).filter((depId) => {
                    const dep = taskMap.get(depId);
                    return dep && dep.status !== "completed";
                  });

                  return (
                    <div
                      key={t.id}
                      onClick={() => onSelectTask(t)}
                      className={`group relative rounded-panel border p-4 cursor-pointer transition-all hover:shadow-md ${
                        isDone
                          ? "bg-[var(--bg-1)]/40 border-[var(--line-1)] opacity-70"
                          : unmetDeps.length === 0
                            ? "bg-[var(--bg-1)] border-[var(--signal)]/40 hover:border-[var(--signal)]"
                            : "bg-[var(--bg-1)] border-amber-500/30 hover:border-amber-500/60"
                      }`}
                    >
                      {/* Top Badges */}
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <Badge
                          variant={
                            t.priority === "critical"
                              ? "danger"
                              : t.priority === "high"
                                ? "warn"
                                : "neutral"
                          }
                          size="sm"
                        >
                          {t.priority.toUpperCase()}
                        </Badge>

                        <span
                          className={`font-mono text-[10px] uppercase px-1.5 py-0.5 rounded ${
                            isDone
                              ? "bg-emerald-500/10 text-emerald-400"
                              : t.status === "in_progress"
                                ? "bg-blue-500/10 text-blue-400"
                                : "bg-[var(--bg-2)] text-[var(--fg-2)]"
                          }`}
                        >
                          {t.status.replace("_", " ")}
                        </span>
                      </div>

                      {/* Title */}
                      <h4
                        className={`text-sm font-semibold mb-2 group-hover:text-[var(--signal)] transition-colors ${
                          isDone ? "line-through text-[var(--fg-3)]" : "text-[var(--fg-0)]"
                        }`}
                      >
                        {t.title}
                      </h4>

                      {/* Dependency Arrows Footer */}
                      <div className="pt-2 border-t border-[var(--line-1)] flex items-center justify-between text-[11px] font-mono text-[var(--fg-3)]">
                        <div>
                          {(t.depends_on_ids || []).length > 0 && (
                            <span>Depends on {t.depends_on_ids?.length}</span>
                          )}
                        </div>
                        <div>
                          {(t.dependent_ids || []).length > 0 && (
                            <span className="text-[var(--signal)]">
                              ↳ Unblocks {t.dependent_ids?.length}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
