"use client";

import React, { useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";
import { type ProjectTaskResponse, type ProjectTaskUpdate } from "./types";

interface TaskDetailModalProps {
  task: ProjectTaskResponse | null;
  isOpen: boolean;
  onClose: () => void;
  onUpdateTask: (taskId: string, payload: ProjectTaskUpdate) => Promise<void>;
  allTasks: ProjectTaskResponse[];
}

function TaskDetailDialogContent({
  task,
  isOpen,
  onClose,
  onUpdateTask,
  allTasks,
}: TaskDetailModalProps & { task: ProjectTaskResponse }) {
  const [title, setTitle] = useState(task.title);
  const [description, setDescription] = useState(task.description || "");
  const [status, setStatus] = useState(task.status);
  const [priority, setPriority] = useState(task.priority);
  const [isEditing, setIsEditing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const taskMap = new Map<string, ProjectTaskResponse>();
  allTasks.forEach((t) => taskMap.set(t.id, t));

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      await onUpdateTask(task.id, {
        title: title.trim(),
        description: description.trim() || undefined,
        status,
        priority,
      });
      setIsEditing(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update task.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title="Task Details"
      description={`Work item ID: ${task.id}`}
    >
      <div className="flex flex-col gap-4 text-xs">
        {error && (
          <div className="p-3 rounded bg-rose-500/10 border border-rose-500/20 text-rose-400">
            {error}
          </div>
        )}

        {isEditing ? (
          <form onSubmit={handleSave} className="flex flex-col gap-3">
            <div>
              <label className="block font-semibold text-[var(--fg-1)] mb-1">Title</label>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
                className="w-full text-xs"
              />
            </div>

            <div>
              <label className="block font-semibold text-[var(--fg-1)] mb-1">Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 rounded-control bg-[var(--bg-0)] border border-[var(--line-2)] text-xs text-[var(--fg-1)] focus:outline-none focus:ring-1 focus:ring-[var(--ref)]"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-[var(--fg-1)] mb-1">Status</label>
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  className="w-full h-9 px-3 rounded-control bg-[var(--bg-0)] border border-[var(--line-2)] text-xs text-[var(--fg-1)]"
                >
                  <option value="open">Open</option>
                  <option value="in_progress">In Progress</option>
                  <option value="blocked">Blocked</option>
                  <option value="completed">Completed</option>
                </select>
              </div>

              <div>
                <label className="block font-semibold text-[var(--fg-1)] mb-1">Priority</label>
                <select
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                  className="w-full h-9 px-3 rounded-control bg-[var(--bg-0)] border border-[var(--line-2)] text-xs text-[var(--fg-1)]"
                >
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-[var(--line-1)]">
              <Button type="button" variant="tertiary" onClick={() => setIsEditing(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" disabled={isSubmitting}>
                {isSubmitting ? "Saving..." : "Save Changes"}
              </Button>
            </div>
          </form>
        ) : (
          <div className="flex flex-col gap-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Badge
                  variant={
                    task.priority === "critical"
                      ? "danger"
                      : task.priority === "high"
                        ? "warn"
                        : "neutral"
                  }
                >
                  {task.priority.toUpperCase()}
                </Badge>
                <Badge variant={task.status === "completed" ? "signal" : "neutral"}>
                  {task.status.replace("_", " ").toUpperCase()}
                </Badge>
                {task.source && (
                  <span className="font-mono text-[10px] text-[var(--fg-3)]">
                    source: {task.source}
                  </span>
                )}
              </div>

              <h3 className="text-base font-semibold text-[var(--fg-0)]">{task.title}</h3>
              {task.description && (
                <p className="text-xs text-[var(--fg-2)] mt-1.5 whitespace-pre-wrap leading-relaxed">
                  {task.description}
                </p>
              )}
            </div>

            {/* Prerequisites */}
            <div className="p-3 rounded bg-[var(--bg-0)] border border-[var(--line-1)]">
              <span className="block font-mono text-[10px] uppercase tracking-wider text-[var(--fg-3)] mb-1.5 font-bold">
                Prerequisites (Depends On)
              </span>
              {(task.depends_on_ids || []).length === 0 ? (
                <span className="text-[var(--fg-3)] text-xs">No prerequisites. Unblocked.</span>
              ) : (
                <ul className="flex flex-col gap-1">
                  {task.depends_on_ids?.map((id) => {
                    const dep = taskMap.get(id);
                    return (
                      <li key={id} className="text-xs text-[var(--fg-1)] flex items-center gap-2">
                        <span>•</span>
                        <span>{dep?.title || id}</span>
                        {dep && (
                          <span className="font-mono text-[10px] text-[var(--fg-3)]">
                            ({dep.status})
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {/* Downstream */}
            <div className="p-3 rounded bg-[var(--bg-0)] border border-[var(--line-1)]">
              <span className="block font-mono text-[10px] uppercase tracking-wider text-[var(--fg-3)] mb-1.5 font-bold">
                Downstream Impact (Unblocks)
              </span>
              {(task.dependent_ids || []).length === 0 ? (
                <span className="text-[var(--fg-3)] text-xs">
                  No downstream tasks depend on this work item.
                </span>
              ) : (
                <ul className="flex flex-col gap-1">
                  {task.dependent_ids?.map((id) => {
                    const dep = taskMap.get(id);
                    return (
                      <li key={id} className="text-xs text-[var(--signal)] flex items-center gap-2">
                        <span>↳</span>
                        <span>{dep?.title || id}</span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            <div className="flex justify-between items-center pt-3 border-t border-[var(--line-1)]">
              <span className="text-[10px] font-mono text-[var(--fg-3)]">
                Created {new Date(task.created_at).toLocaleDateString()}
              </span>
              <div className="flex gap-2">
                <Button variant="secondary" onClick={() => setIsEditing(true)}>
                  Edit
                </Button>
                <Button variant="tertiary" onClick={onClose}>
                  Close
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Dialog>
  );
}

export function TaskDetailModal(props: TaskDetailModalProps) {
  if (!props.isOpen || !props.task) return null;
  return <TaskDetailDialogContent key={props.task.id} {...props} task={props.task} />;
}
