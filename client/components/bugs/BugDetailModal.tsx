"use client";

import React from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CloseIcon, CheckIcon } from "@/components/shell/icons";
import type { BugRecordDetailResponse } from "./types";

interface BugDetailModalProps {
  bug: BugRecordDetailResponse | null;
  isOpen: boolean;
  onClose: () => void;
  onAddResolution: (bugId: string) => void;
}

export function BugDetailModal({ bug, isOpen, onClose, onAddResolution }: BugDetailModalProps) {
  if (!isOpen || !bug) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="bug-detail-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--overlay-bg,rgba(0,0,0,0.75))] backdrop-blur-sm font-mono"
    >
      <div className="relative w-full max-w-2xl max-h-[90vh] bg-[var(--bg-0)] border border-[var(--line-2)] rounded-panel shadow-2xl flex flex-col overflow-hidden text-xs">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--line-1)] bg-[var(--bg-1)]">
          <div className="flex items-center gap-2 overflow-hidden pr-2">
            <span className="w-2.5 h-2.5 rounded-full bg-[var(--danger)]" />
            <h3 id="bug-detail-title" className="text-sm font-bold text-[var(--fg-0)] truncate">
              {bug.title}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            className="text-[var(--fg-2)] hover:text-[var(--fg-0)] p-1 rounded hover:bg-[var(--bg-2)] transition-colors"
          >
            <CloseIcon size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 flex flex-col gap-4 overflow-y-auto">
          {/* Metadata Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-[var(--bg-1)] p-3 rounded-control border border-[var(--line-1)] text-[11px]">
            <div>
              <span className="text-[var(--fg-2)] block uppercase mb-0.5">Occurrences</span>
              <span className="font-bold text-[var(--fg-0)]">{bug.occurrence_count} times</span>
            </div>
            <div>
              <span className="text-[var(--fg-2)] block uppercase mb-0.5">Resolutions</span>
              <span className="font-bold text-[var(--signal)]">
                {bug.resolutions_count} documented
              </span>
            </div>
            <div>
              <span className="text-[var(--fg-2)] block uppercase mb-0.5">First Seen</span>
              <span className="text-[var(--fg-1)]">
                {new Date(bug.first_seen_at).toLocaleDateString()}
              </span>
            </div>
            <div>
              <span className="text-[var(--fg-2)] block uppercase mb-0.5">Last Seen</span>
              <span className="text-[var(--fg-1)]">
                {new Date(bug.last_seen_at).toLocaleDateString()}
              </span>
            </div>
          </div>

          {/* Module & Fingerprint */}
          <div className="flex flex-col gap-1.5">
            <span className="text-[11px] font-semibold text-[var(--fg-2)] uppercase tracking-wider">
              Error Fingerprint &amp; Subsystem
            </span>
            <div className="bg-[var(--bg-1)] p-3 rounded-control border border-[var(--line-1)] flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <span className="text-[var(--fg-2)] text-[11px]">Module Hint:</span>
                <code className="text-[var(--ref)]">{bug.module_hint || "None"}</code>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[var(--fg-2)] text-[11px]">Fingerprint:</span>
                <code className="text-[var(--signal)] break-all text-[11px]">
                  {bug.fingerprint}
                </code>
              </div>
            </div>
          </div>

          {/* Error Signature */}
          <div className="flex flex-col gap-1.5">
            <span className="text-[11px] font-semibold text-[var(--fg-2)] uppercase tracking-wider">
              Canonical Error Signature
            </span>
            <pre className="p-3 bg-[var(--bg-1)] border border-[var(--line-1)] rounded-control text-xs text-[var(--fg-0)] overflow-x-auto whitespace-pre-wrap">
              {bug.error_signature}
            </pre>
          </div>

          {/* Raw Error Trace if available */}
          {bug.raw_error && (
            <div className="flex flex-col gap-1.5">
              <span className="text-[11px] font-semibold text-[var(--fg-2)] uppercase tracking-wider">
                Raw Stack Trace Snippet
              </span>
              <pre className="p-3 bg-[var(--bg-1)] border border-[var(--line-1)] rounded-control text-[11px] text-[var(--fg-1)] font-mono overflow-x-auto max-h-40 whitespace-pre">
                {bug.raw_error}
              </pre>
            </div>
          )}

          {/* Historical Resolutions */}
          <div className="flex flex-col gap-2 mt-1">
            <div className="flex items-center justify-between border-b border-[var(--line-1)] pb-1.5">
              <span className="text-[11px] font-semibold text-[var(--fg-0)] uppercase tracking-wider">
                Documented Resolutions ({bug.resolutions?.length || 0})
              </span>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => {
                  onClose();
                  onAddResolution(bug.id);
                }}
                className="text-[11px] h-6 py-0.5 text-[var(--signal)]"
              >
                + Add Resolution
              </Button>
            </div>

            {!bug.resolutions || bug.resolutions.length === 0 ? (
              <div className="p-4 bg-[var(--bg-1)] rounded-control border border-[var(--line-1)] text-center text-[var(--fg-2)] text-xs">
                No resolution has been recorded for this error signature yet.
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {bug.resolutions.map((res) => (
                  <div
                    key={res.id}
                    className="p-3.5 bg-[var(--bg-1)] border border-[var(--line-1)] rounded-control flex flex-col gap-2"
                  >
                    <div className="flex items-center justify-between text-[11px]">
                      <div className="flex items-center gap-1.5 text-[var(--success,#10b981)] font-bold">
                        <CheckIcon size={14} />
                        <span>Resolution by {res.resolved_by || "Contributor"}</span>
                      </div>
                      <span className="text-[var(--fg-2)]">
                        {new Date(res.created_at).toLocaleDateString()}
                      </span>
                    </div>

                    <div>
                      <span className="text-[10px] text-[var(--fg-2)] uppercase block">
                        Root Cause
                      </span>
                      <p className="text-xs text-[var(--fg-0)] mt-0.5">{res.cause}</p>
                    </div>

                    <div>
                      <span className="text-[10px] text-[var(--fg-2)] uppercase block">
                        Fix Summary
                      </span>
                      <p className="text-xs text-[var(--fg-0)] mt-0.5">{res.fix_summary}</p>
                    </div>

                    {res.files && res.files.length > 0 && (
                      <div>
                        <span className="text-[10px] text-[var(--fg-2)] uppercase block">
                          Affected Files
                        </span>
                        <div className="flex flex-wrap gap-1.5 mt-1">
                          {res.files.map((f: unknown, idx: number) => {
                            const label =
                              typeof f === "string"
                                ? f
                                : typeof f === "object" && f !== null && "path" in f
                                  ? String((f as { path: unknown }).path)
                                  : JSON.stringify(f);
                            return (
                              <Badge key={idx} variant="neutral" className="text-[10px]">
                                {label}
                              </Badge>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-[var(--line-1)] bg-[var(--bg-1)] flex items-center justify-end">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}
