"use client";

import React, { useState, useMemo } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { type ProjectTaskResponse } from "./types";

interface TaskBacklogTableProps {
  tasks: ProjectTaskResponse[];
  onSelectTask: (task: ProjectTaskResponse) => void;
  onUpdateStatus: (taskId: string, status: string) => void;
  onDeleteTask: (taskId: string) => void;
  onOpenLinkModal: (task: ProjectTaskResponse) => void;
}

export function TaskBacklogTable({
  tasks,
  onSelectTask,
  onUpdateStatus,
  onDeleteTask,
  onOpenLinkModal,
}: TaskBacklogTableProps) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("all");

  const filteredTasks = useMemo(() => {
    return tasks.filter((t) => {
      if (statusFilter !== "all" && t.status !== statusFilter) return false;
      if (priorityFilter !== "all" && t.priority !== priorityFilter) return false;
      if (search.trim()) {
        const query = search.toLowerCase();
        return (
          t.title.toLowerCase().includes(query) ||
          (t.description && t.description.toLowerCase().includes(query))
        );
      }
      return true;
    });
  }, [tasks, search, statusFilter, priorityFilter]);

  const taskMap = useMemo(() => {
    const map = new Map<string, ProjectTaskResponse>();
    tasks.forEach((t) => map.set(t.id, t));
    return map;
  }, [tasks]);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return <Badge variant="signal">Completed</Badge>;
      case "in_progress":
        return <Badge variant="ref">In Progress</Badge>;
      case "blocked":
        return <Badge variant="danger">Blocked</Badge>;
      default:
        return <Badge variant="neutral">Open</Badge>;
    }
  };

  const getPriorityBadge = (priority: string) => {
    switch (priority) {
      case "critical":
        return <Badge variant="danger">CRITICAL</Badge>;
      case "high":
        return <Badge variant="warn">HIGH</Badge>;
      case "medium":
        return <Badge variant="neutral">MEDIUM</Badge>;
      default:
        return <Badge variant="neutral">LOW</Badge>;
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-[var(--bg-1)] p-3 rounded-panel border border-[var(--line-1)]">
        <div className="flex flex-wrap items-center gap-2 flex-1 min-w-[280px]">
          <Input
            placeholder="Search tasks..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full sm:w-64"
          />

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-9 px-3 rounded-control bg-[var(--bg-0)] border border-[var(--line-2)] text-xs text-[var(--fg-1)] font-sans focus:outline-none focus:ring-1 focus:ring-[var(--ref)]"
          >
            <option value="all">All Statuses</option>
            <option value="open">Open</option>
            <option value="in_progress">In Progress</option>
            <option value="blocked">Blocked</option>
            <option value="completed">Completed</option>
          </select>

          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="h-9 px-3 rounded-control bg-[var(--bg-0)] border border-[var(--line-2)] text-xs text-[var(--fg-1)] font-sans focus:outline-none focus:ring-1 focus:ring-[var(--ref)]"
          >
            <option value="all">All Priorities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        <div className="text-xs font-mono text-[var(--fg-3)]">
          Showing {filteredTasks.length} of {tasks.length} tasks
        </div>
      </div>

      {/* Table */}
      {filteredTasks.length === 0 ? (
        <div className="rounded-panel border border-dashed border-[var(--line-2)] p-12 text-center bg-[var(--bg-1)]">
          <p className="text-sm text-[var(--fg-2)] mb-1">No tasks match criteria</p>
          <p className="text-xs text-[var(--fg-3)]">
            Adjust search filter or click &apos;New Task&apos; to add a backlog work item.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-panel border border-[var(--line-1)] bg-[var(--bg-0)]">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-[var(--line-1)] bg-[var(--bg-1)] text-[var(--fg-2)] font-mono uppercase tracking-wider text-[11px]">
                <th className="py-3 px-4">Task</th>
                <th className="py-3 px-3">Priority</th>
                <th className="py-3 px-3">Status</th>
                <th className="py-3 px-3">Prerequisites</th>
                <th className="py-3 px-3">Impact</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--line-1)]">
              {filteredTasks.map((t) => {
                const unmetDeps = (t.depends_on_ids || []).filter((depId) => {
                  const dep = taskMap.get(depId);
                  return dep && dep.status !== "completed";
                });
                const isBlocked = unmetDeps.length > 0;

                return (
                  <tr key={t.id} className="hover:bg-[var(--bg-1)]/60 transition-colors group">
                    {/* Task Title & Details */}
                    <td className="py-3.5 px-4 max-w-md">
                      <div className="flex flex-col">
                        <span
                          onClick={() => onSelectTask(t)}
                          className={`font-semibold text-sm cursor-pointer transition-colors hover:text-[var(--signal)] ${
                            t.status === "completed"
                              ? "line-through text-[var(--fg-3)]"
                              : "text-[var(--fg-0)]"
                          }`}
                        >
                          {t.title}
                        </span>
                        {t.description && (
                          <span className="text-xs text-[var(--fg-2)] mt-0.5 line-clamp-1">
                            {t.description}
                          </span>
                        )}
                        {t.source && t.source !== "user" && (
                          <span className="font-mono text-[10px] text-[var(--fg-3)] mt-1">
                            Source: {t.source}
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Priority */}
                    <td className="py-3.5 px-3">{getPriorityBadge(t.priority)}</td>

                    {/* Status with Quick Toggle */}
                    <td className="py-3.5 px-3">
                      <div className="flex items-center gap-1.5">
                        {getStatusBadge(t.status)}
                        {isBlocked && t.status !== "completed" && (
                          <span
                            title={`Blocked by ${unmetDeps.length} pending task(s)`}
                            className="text-amber-500 font-mono text-[10px] cursor-help"
                          >
                            ⚠️
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Prerequisites */}
                    <td className="py-3.5 px-3">
                      {(t.depends_on_ids || []).length === 0 ? (
                        <span className="text-[var(--fg-3)] font-mono text-[11px]">—</span>
                      ) : (
                        <div className="flex flex-wrap gap-1 max-w-[200px]">
                          {t.depends_on_ids?.map((depId) => {
                            const dep = taskMap.get(depId);
                            const isDone = dep?.status === "completed";
                            return (
                              <span
                                key={depId}
                                title={dep?.title || depId}
                                className={`px-1.5 py-0.5 rounded font-mono text-[10px] border ${
                                  isDone
                                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                                    : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                                }`}
                              >
                                {dep ? dep.title.slice(0, 16) + "…" : depId.slice(0, 8)}
                              </span>
                            );
                          })}
                        </div>
                      )}
                    </td>

                    {/* Downstream Impact */}
                    <td className="py-3.5 px-3">
                      {(t.dependent_ids || []).length > 0 ? (
                        <span className="font-mono text-xs text-[var(--signal)]">
                          Unblocks {t.dependent_ids?.length}
                        </span>
                      ) : (
                        <span className="text-[var(--fg-3)] font-mono text-[11px]">—</span>
                      )}
                    </td>

                    {/* Actions */}
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5 opacity-90 group-hover:opacity-100">
                        {t.status !== "completed" ? (
                          <Button
                            variant="tertiary"
                            size="sm"
                            onClick={() => onUpdateStatus(t.id, "completed")}
                            className="text-xs text-emerald-400 hover:text-emerald-300"
                          >
                            Done
                          </Button>
                        ) : (
                          <Button
                            variant="tertiary"
                            size="sm"
                            onClick={() => onUpdateStatus(t.id, "open")}
                            className="text-xs text-[var(--fg-2)] hover:text-[var(--fg-1)]"
                          >
                            Reopen
                          </Button>
                        )}

                        <Button
                          variant="tertiary"
                          size="sm"
                          onClick={() => onOpenLinkModal(t)}
                          className="text-xs text-[var(--fg-2)] hover:text-[var(--fg-0)]"
                        >
                          Link
                        </Button>

                        <Button
                          variant="tertiary"
                          size="sm"
                          onClick={() => onDeleteTask(t.id)}
                          className="text-xs text-rose-400 hover:text-rose-300"
                        >
                          Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
