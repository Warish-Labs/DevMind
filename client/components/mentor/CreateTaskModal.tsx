"use client";

import React, { useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { type ProjectTaskResponse, type ProjectTaskCreate } from "./types";

interface CreateTaskModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: ProjectTaskCreate) => Promise<void>;
  existingTasks: ProjectTaskResponse[];
}

export function CreateTaskModal({
  isOpen,
  onClose,
  onSubmit,
  existingTasks,
}: CreateTaskModalProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<"critical" | "high" | "medium" | "low">("medium");
  const [selectedDependencies, setSelectedDependencies] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("Task title is required.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await onSubmit({
        title: title.trim(),
        description: description.trim() || undefined,
        priority,
        source: "user",
        depends_on_ids: selectedDependencies,
      });
      // Reset form
      setTitle("");
      setDescription("");
      setPriority("medium");
      setSelectedDependencies([]);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create task.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const toggleDependency = (taskId: string) => {
    setSelectedDependencies((prev) =>
      prev.includes(taskId) ? prev.filter((id) => id !== taskId) : [...prev, taskId]
    );
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title="Create New Project Task"
      description="Add a work item to the backlog with priority and prerequisite dependencies."
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4 text-xs">
        {error && (
          <div className="p-3 rounded bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
            {error}
          </div>
        )}

        <div>
          <label className="block font-semibold text-[var(--fg-1)] mb-1">Task Title *</label>
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Implement Multi-factor Authentication flow"
            className="w-full text-xs"
            required
          />
        </div>

        <div>
          <label className="block font-semibold text-[var(--fg-1)] mb-1">Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Technical implementation notes, acceptance criteria, or security guardrails..."
            rows={3}
            className="w-full px-3 py-2 rounded-control bg-[var(--bg-0)] border border-[var(--line-2)] text-xs text-[var(--fg-1)] focus:outline-none focus:ring-1 focus:ring-[var(--ref)]"
          />
        </div>

        <div>
          <label className="block font-semibold text-[var(--fg-1)] mb-1">Priority</label>
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value as "critical" | "high" | "medium" | "low")}
            className="w-full h-9 px-3 rounded-control bg-[var(--bg-0)] border border-[var(--line-2)] text-xs text-[var(--fg-1)] focus:outline-none focus:ring-1 focus:ring-[var(--ref)]"
          >
            <option value="critical">Critical (P0 - Blocks Release)</option>
            <option value="high">High (P1)</option>
            <option value="medium">Medium (P2)</option>
            <option value="low">Low (P3)</option>
          </select>
        </div>

        {/* Prerequisites Multi-select */}
        <div>
          <label className="block font-semibold text-[var(--fg-1)] mb-1">
            Prerequisites (Must be completed before this task)
          </label>
          {existingTasks.length === 0 ? (
            <p className="text-[var(--fg-3)] italic">No other tasks in backlog.</p>
          ) : (
            <div className="max-h-36 overflow-y-auto border border-[var(--line-1)] rounded p-2 flex flex-col gap-1.5 bg-[var(--bg-0)]">
              {existingTasks.map((t) => (
                <label
                  key={t.id}
                  className="flex items-center gap-2 text-xs text-[var(--fg-2)] hover:text-[var(--fg-0)] cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedDependencies.includes(t.id)}
                    onChange={() => toggleDependency(t.id)}
                    className="rounded border-[var(--line-2)] text-[var(--signal)] focus:ring-0"
                  />
                  <span className="truncate">{t.title}</span>
                </label>
              ))}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 pt-3 border-t border-[var(--line-1)] mt-2">
          <Button type="button" variant="tertiary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={isSubmitting}>
            {isSubmitting ? "Creating..." : "Create Task"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
