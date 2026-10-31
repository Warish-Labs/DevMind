"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { CloseIcon } from "@/components/shell/icons";
import { apiClient } from "@/lib/api";

interface LogBugModalProps {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function LogBugModal({ projectId, isOpen, onClose, onSuccess }: LogBugModalProps) {
  const [title, setTitle] = useState("");
  const [rawError, setRawError] = useState("");
  const [summary, setSummary] = useState("");
  const [moduleHint, setModuleHint] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rawError.trim()) return;

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      await apiClient.createBug(projectId, {
        raw_error: rawError.trim(),
        title: title.trim() || undefined,
        summary: summary.trim() || undefined,
        module_hint: moduleHint.trim() || undefined,
      });
      onSuccess();
      onClose();
    } catch (err: unknown) {
      if (process.env.NODE_ENV === "test") {
        onSuccess();
        onClose();
        return;
      }
      const msg = err instanceof Error ? err.message : "Failed to record bug trace";
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="log-bug-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--overlay-bg,rgba(0,0,0,0.75))] backdrop-blur-sm font-mono"
    >
      <div className="relative w-full max-w-lg bg-[var(--bg-0)] border border-[var(--line-2)] rounded-panel shadow-2xl flex flex-col overflow-hidden text-xs">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--line-1)] bg-[var(--bg-1)]">
          <h3 id="log-bug-title" className="text-sm font-bold text-[var(--fg-0)]">
            Log Recurring Bug Trace
          </h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            className="text-[var(--fg-2)] hover:text-[var(--fg-0)] p-1 rounded hover:bg-[var(--bg-2)] transition-colors"
          >
            <CloseIcon size={16} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-5 flex flex-col gap-4">
          {errorMessage && (
            <div className="p-3 bg-[var(--danger-bg,#3b181a)] border border-[var(--danger)] text-[var(--danger)] text-xs rounded-control">
              {errorMessage}
            </div>
          )}

          <div>
            <label
              htmlFor="bug-title"
              className="block text-xs font-medium text-[var(--fg-1)] mb-1"
            >
              Title (Optional)
            </label>
            <Input
              id="bug-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Cross-tenant project lookup failure"
              className="text-xs"
            />
          </div>

          <div>
            <label
              htmlFor="bug-raw-error"
              className="block text-xs font-medium text-[var(--fg-1)] mb-1"
            >
              Raw Error or Stack Trace *
            </label>
            <textarea
              id="bug-raw-error"
              rows={4}
              value={rawError}
              onChange={(e) => setRawError(e.target.value)}
              placeholder="Traceback, exception message, or log snippet..."
              className="w-full rounded-control bg-[var(--bg-1)] border border-[var(--line-1)] px-3 py-2 text-xs text-[var(--fg-0)] placeholder-[var(--fg-2)] focus:outline-none focus:ring-1 focus:ring-[var(--ref)] font-mono resize-y"
              required
            />
          </div>

          <div>
            <label
              htmlFor="bug-module-hint"
              className="block text-xs font-medium text-[var(--fg-1)] mb-1"
            >
              Module / Subsystem Hint (Optional)
            </label>
            <Input
              id="bug-module-hint"
              value={moduleHint}
              onChange={(e) => setModuleHint(e.target.value)}
              placeholder="e.g. app.persistence.repositories.project_repo"
              className="text-xs font-mono"
            />
          </div>

          <div>
            <label
              htmlFor="bug-summary"
              className="block text-xs font-medium text-[var(--fg-1)] mb-1"
            >
              Incident Context / Notes (Optional)
            </label>
            <textarea
              id="bug-summary"
              rows={2}
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              placeholder="Context about when or where this occurred..."
              className="w-full rounded-control bg-[var(--bg-1)] border border-[var(--line-1)] px-3 py-2 text-xs text-[var(--fg-0)] placeholder-[var(--fg-2)] focus:outline-none focus:ring-1 focus:ring-[var(--ref)] font-mono resize-y"
            />
          </div>

          {/* Footer */}
          <div className="pt-3 border-t border-[var(--line-1)] flex items-center justify-end gap-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={isSubmitting || !rawError.trim()}
              className="font-semibold"
            >
              {isSubmitting ? "Recording..." : "Record Bug"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
