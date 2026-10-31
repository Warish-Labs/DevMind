"use client";

import React, { useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { type ProjectTaskResponse } from "./types";

interface LinkDependencyModalProps {
  task: ProjectTaskResponse | null;
  isOpen: boolean;
  onClose: () => void;
  allTasks: ProjectTaskResponse[];
  onAddDependency: (taskId: string, dependsOnTaskId: string) => Promise<void>;
  onRemoveDependency: (taskId: string, dependsOnTaskId: string) => Promise<void>;
}

export function LinkDependencyModal({
  task,
  isOpen,
  onClose,
  allTasks,
  onAddDependency,
  onRemoveDependency,
}: LinkDependencyModalProps) {
  const [selectedDependsOn, setSelectedDependsOn] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!task) return null;

  const taskMap = new Map<string, ProjectTaskResponse>();
  allTasks.forEach((t) => taskMap.set(t.id, t));

  // Eligible tasks: cannot depend on self, and cannot depend on tasks that are already prerequisites
  const eligibleTasks = allTasks.filter(
    (t) => t.id !== task.id && !(task.depends_on_ids || []).includes(t.id)
  );

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDependsOn) return;

    setIsSubmitting(true);
    setError(null);

    try {
      await onAddDependency(task.id, selectedDependsOn);
      setSelectedDependsOn("");
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to link dependency. A circular cycle may have been detected."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRemove = async (depId: string) => {
    setIsSubmitting(true);
    setError(null);
    try {
      await onRemoveDependency(task.id, depId);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to remove dependency.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title="Manage Task Dependencies"
      description={`Link prerequisite tasks that must be completed before '${task.title}'.`}
    >
      <div className="flex flex-col gap-4 text-xs">
        {error && (
          <div className="p-3 rounded bg-rose-500/10 border border-rose-500/20 text-rose-400">
            {error}
          </div>
        )}

        {/* Existing Dependencies */}
        <div>
          <label className="block font-semibold text-[var(--fg-1)] mb-2 font-mono uppercase text-[11px]">
            Current Prerequisites ({task.depends_on_ids?.length || 0})
          </label>
          {(task.depends_on_ids || []).length === 0 ? (
            <p className="text-[var(--fg-3)] italic">
              No prerequisites. This task is unblocked and can be started immediately.
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {task.depends_on_ids?.map((depId) => {
                const dep = taskMap.get(depId);
                return (
                  <div
                    key={depId}
                    className="flex items-center justify-between p-2 rounded border border-[var(--line-1)] bg-[var(--bg-0)]"
                  >
                    <div>
                      <span className="font-semibold text-[var(--fg-0)]">
                        {dep ? dep.title : depId}
                      </span>
                      {dep && (
                        <span className="ml-2 font-mono text-[10px] text-[var(--fg-3)]">
                          [{dep.status}]
                        </span>
                      )}
                    </div>
                    <Button
                      variant="tertiary"
                      size="sm"
                      onClick={() => handleRemove(depId)}
                      disabled={isSubmitting}
                      className="text-rose-400 hover:text-rose-300 text-[11px]"
                    >
                      Remove
                    </Button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Add New Prerequisite */}
        <form onSubmit={handleAdd} className="pt-3 border-t border-[var(--line-1)]">
          <label className="block font-semibold text-[var(--fg-1)] mb-2 font-mono uppercase text-[11px]">
            Add Prerequisite Task
          </label>
          <div className="flex gap-2">
            <select
              value={selectedDependsOn}
              onChange={(e) => setSelectedDependsOn(e.target.value)}
              className="flex-1 h-9 px-3 rounded-control bg-[var(--bg-0)] border border-[var(--line-2)] text-xs text-[var(--fg-1)] focus:outline-none focus:ring-1 focus:ring-[var(--ref)]"
            >
              <option value="">Select a prerequisite work item...</option>
              {eligibleTasks.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.title} ({t.priority})
                </option>
              ))}
            </select>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={!selectedDependsOn || isSubmitting}
            >
              {isSubmitting ? "Linking..." : "Add Link"}
            </Button>
          </div>
          <p className="text-[10px] text-[var(--fg-3)] mt-1.5 font-mono">
            ℹ Topological sorter prevents circular cycles. Circular links will be rejected with 409
            Conflict.
          </p>
        </form>

        <div className="flex justify-end pt-3 border-t border-[var(--line-1)]">
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
