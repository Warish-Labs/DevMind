"use client";

import React, { useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import type { DeploymentIncidentResponse } from "./types";

interface DocumentResolutionModalProps {
  isOpen: boolean;
  onClose: () => void;
  incident: DeploymentIncidentResponse | null;
  onSaveResolution: (incidentId: string, resolution: string) => Promise<void>;
  isLoading?: boolean;
}

function ResolutionForm({
  incident,
  onClose,
  onSaveResolution,
  isLoading,
}: {
  incident: DeploymentIncidentResponse;
  onClose: () => void;
  onSaveResolution: (incidentId: string, resolution: string) => Promise<void>;
  isLoading?: boolean;
}) {
  const [resolution, setResolution] = useState(incident.resolution || "");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resolution.trim() || isLoading) return;
    await onSaveResolution(incident.id, resolution.trim());
    onClose();
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <h4 className="text-sm font-semibold text-[var(--fg-1)] mb-1">{incident.summary}</h4>
        <p className="text-xs text-[var(--fg-2)]">
          Fingerprint:{" "}
          <code className="font-mono text-[var(--fg-3)]">
            {incident.fingerprint.slice(0, 16)}...
          </code>
        </p>
      </div>

      <div>
        <label className="block text-xs font-medium text-[var(--fg-2)] mb-1">
          Proven Resolution or Remediation Applied
        </label>
        <textarea
          rows={5}
          value={resolution}
          onChange={(e) => setResolution(e.target.value)}
          placeholder="Document the exact fix (e.g. 'Added DATABASE_URL to Render secrets group', 'Ran alembic stamp head to clear failed migration', etc.)..."
          className="w-full px-3 py-2 text-xs font-mono rounded-md bg-[var(--bg-0)] border border-[var(--border)] text-[var(--fg-1)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)] resize-y"
          required
        />
        <span className="text-[11px] text-[var(--fg-3)] mt-1 block">
          This resolution will be indexed and automatically suggested to teammates whenever similar
          deployment incidents occur.
        </span>
      </div>

      <div className="flex items-center justify-end gap-2 pt-2 border-t border-[var(--border)]">
        <Button type="button" variant="secondary" size="sm" onClick={onClose} disabled={isLoading}>
          Cancel
        </Button>
        <Button
          type="submit"
          variant="primary"
          size="sm"
          disabled={isLoading || !resolution.trim()}
        >
          {isLoading ? "Saving Fix..." : "Save Resolution"}
        </Button>
      </div>
    </form>
  );
}

export function DocumentResolutionModal({
  isOpen,
  onClose,
  incident,
  onSaveResolution,
  isLoading,
}: DocumentResolutionModalProps) {
  if (!isOpen || !incident) return null;

  return (
    <Dialog isOpen={isOpen} onClose={onClose} title="Document Incident Resolution">
      <ResolutionForm
        key={incident.id}
        incident={incident}
        onClose={onClose}
        onSaveResolution={onSaveResolution}
        isLoading={isLoading}
      />
    </Dialog>
  );
}
