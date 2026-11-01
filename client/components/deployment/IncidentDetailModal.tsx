"use client";

import React from "react";
import { Dialog } from "@/components/ui/Dialog";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  type DeploymentIncidentResponse,
  getCategoryBadgeVariant,
  formatCategoryLabel,
} from "./types";

interface IncidentDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  incident: DeploymentIncidentResponse | null;
  onDocumentResolution: (incidentId: string) => void;
}

export function IncidentDetailModal({
  isOpen,
  onClose,
  incident,
  onDocumentResolution,
}: IncidentDetailModalProps) {
  if (!incident) return null;

  return (
    <Dialog isOpen={isOpen} onClose={onClose} title="Deployment Incident Record">
      <div className="space-y-4 max-h-[75vh] overflow-y-auto pr-1">
        {/* Title & Metadata */}
        <div>
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <Badge variant={getCategoryBadgeVariant(incident.failure_category)}>
              {formatCategoryLabel(incident.failure_category)}
            </Badge>
            <Badge variant="neutral">{incident.environment}</Badge>
            {incident.resolved_at ? (
              <Badge variant="signal">Resolved</Badge>
            ) : (
              <Badge variant="danger">Unresolved</Badge>
            )}
            <span className="text-xs font-mono text-[var(--fg-3)]">
              Occurrences: {incident.occurrence_count}x
            </span>
          </div>

          <h3 className="text-base font-semibold text-[var(--fg-1)]">{incident.summary}</h3>
          <p className="text-xs font-mono text-[var(--fg-3)] mt-0.5">
            Fingerprint: {incident.fingerprint}
          </p>
        </div>

        {/* Probable Cause */}
        <div className="p-3 rounded-md bg-[var(--bg-0)] border border-[var(--border)]">
          <h4 className="text-xs font-semibold text-[var(--danger)] uppercase tracking-wider mb-1">
            Probable Root Cause
          </h4>
          <p className="text-xs text-[var(--fg-1)] leading-relaxed">{incident.probable_cause}</p>
        </div>

        {/* Error Signature */}
        <div>
          <h4 className="text-xs font-semibold text-[var(--fg-2)] uppercase tracking-wider mb-1">
            Canonical Error Signature
          </h4>
          <pre className="p-2.5 rounded-md bg-[var(--bg-0)] border border-[var(--border)] text-xs font-mono text-[var(--fg-1)] overflow-x-auto select-text whitespace-pre-wrap">
            {incident.error_signature}
          </pre>
        </div>

        {/* Resolution */}
        <div className="p-3 rounded-md bg-[var(--bg-0)] border border-[var(--border)]">
          <div className="flex items-center justify-between mb-1">
            <h4 className="text-xs font-semibold text-[var(--signal)] uppercase tracking-wider">
              Documented Resolution
            </h4>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => onDocumentResolution(incident.id)}
              className="text-[11px] h-6 px-2 font-mono"
            >
              {incident.resolution ? "Edit Fix" : "Add Fix"}
            </Button>
          </div>
          {incident.resolution ? (
            <p className="text-xs text-[var(--fg-1)] leading-relaxed">{incident.resolution}</p>
          ) : (
            <p className="text-xs text-[var(--fg-3)] italic">
              No resolution recorded yet. Document remediation steps to help future diagnoses.
            </p>
          )}
        </div>

        {/* Log Snippet */}
        {incident.log_snippet && (
          <div>
            <h4 className="text-xs font-semibold text-[var(--fg-2)] uppercase tracking-wider mb-1">
              Sanitized Log Snippet (Redacted)
            </h4>
            <pre className="p-3 rounded-md bg-[var(--bg-0)] border border-[var(--border)] text-[11px] font-mono text-[var(--fg-2)] max-h-48 overflow-auto select-text whitespace-pre-wrap">
              {incident.log_snippet}
            </pre>
          </div>
        )}

        {/* Timeline */}
        <div className="grid grid-cols-2 gap-3 text-xs font-mono text-[var(--fg-3)] pt-2 border-t border-[var(--border)]">
          <div>First Seen: {new Date(incident.created_at).toLocaleString()}</div>
          <div>Last Seen: {new Date(incident.last_seen_at).toLocaleString()}</div>
        </div>
      </div>
    </Dialog>
  );
}
