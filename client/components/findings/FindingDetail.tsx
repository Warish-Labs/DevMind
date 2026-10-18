"use client";

import React, { useState } from "react";
import Link from "next/link";
import type { FindingDetailItem, FindingEvidenceItem } from "@devmind/common/api";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { CodeExcerpt } from "./CodeExcerpt";
import { FindingTriageModal } from "./FindingTriageModal";
import { getSeverityBadgeVariant, getStatusBadgeVariant, SAMPLE_CODE_SNIPPETS } from "./types";

export interface FindingDetailProps {
  projectId: string;
  finding: FindingDetailItem;
  hasMaintainerPermission?: boolean;
  onStatusTransition?: (
    findingId: string,
    payload: { to_status: string; reason?: string }
  ) => Promise<void> | void;
  className?: string;
}

export function FindingDetail({
  projectId,
  finding,
  hasMaintainerPermission = true,
  onStatusTransition,
  className = "",
}: FindingDetailProps) {
  const [isTriageOpen, setIsTriageOpen] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [transitionError, setTransitionError] = useState<string | null>(null);

  // Retrieve code snippet for this path if available in mock/sample
  const snippetInfo = finding.primary_path ? SAMPLE_CODE_SNIPPETS[finding.primary_path] : undefined;

  const handleTransition = async (toStatus: string, reason?: string) => {
    if (!onStatusTransition) return;
    try {
      setIsSubmitting(true);
      setTransitionError(null);
      await onStatusTransition(finding.id, {
        to_status: toStatus,
        reason: reason || `Status changed to ${toStatus} via web UI`,
      });
    } catch (err: unknown) {
      const errObj = err as { message?: string };
      setTransitionError(errObj.message || "Failed to update status");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleTriageSubmit = async (payload: { to_status: string; reason: string }) => {
    if (!onStatusTransition) return;
    try {
      setTransitionError(null);
      await onStatusTransition(finding.id, payload);
      setIsTriageOpen(false);
    } catch (err: unknown) {
      const errObj = err as { message?: string };
      setTransitionError(errObj.message || "Failed to triage finding");
    }
  };

  const suggestedFix = finding.suggested_fix as
    | {
        summary?: string;
        remediation_steps?: string[];
        code_suggestion?: string;
      }
    | null
    | undefined;

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Top Breadcrumb & Navigation */}
      <div className="flex items-center justify-between">
        <Link
          href={`/projects/${projectId}/findings`}
          className="inline-flex items-center gap-1.5 text-xs text-[var(--fg-2)] hover:text-[var(--fg-0)] transition-colors"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to findings list
        </Link>

        <div className="text-xs text-[var(--fg-3)] font-mono">ID: {finding.id}</div>
      </div>

      {/* Error Alert */}
      {transitionError && (
        <div className="p-3 rounded-[var(--radius-md)] border border-[var(--danger)] bg-[rgba(255,107,94,0.1)] text-xs text-[var(--danger)]">
          {transitionError}
        </div>
      )}

      {/* Stale Finding Warning Banner (docs/08 §11 S-08: A stale finding shows a banner and a 'Re-verify' action) */}
      {finding.status === "stale" && (
        <div className="p-4 rounded-[var(--radius-md)] border border-[var(--danger)] bg-[rgba(255,107,94,0.08)] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-start gap-3">
            <span className="text-lg">⚠️</span>
            <div className="space-y-0.5">
              <div className="text-xs font-semibold text-[var(--danger)]">
                Stale Finding · Evidence file modified
              </div>
              <div className="text-[11px] text-[var(--fg-1)]">
                The underlying source code changed since this finding was produced. Re-verify to
                confirm if the issue still reproduces or has been resolved.
              </div>
            </div>
          </div>
          <Button
            variant="destructive"
            size="sm"
            isLoading={isSubmitting}
            onClick={() =>
              handleTransition("open", "Triggered re-verification scan from finding view")
            }
          >
            Re-verify finding
          </Button>
        </div>
      )}

      {/* Header & Status Actions */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 bg-[var(--bg-1)] p-5 rounded-[var(--radius-lg)] border border-[var(--line-1)]">
        <div className="space-y-2 max-w-2xl">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs font-semibold text-[var(--fg-2)] bg-[var(--bg-2)] px-2 py-0.5 rounded-[var(--radius-sm)] border border-[var(--line-1)]">
              {finding.rule_id}
            </span>
            <Badge variant={getStatusBadgeVariant(finding.status)}>
              {finding.status.replace(/_/g, " ").toUpperCase()}
            </Badge>
          </div>
          <h1 className="text-lg md:text-xl font-semibold text-[var(--fg-0)]">{finding.title}</h1>
          {finding.summary && (
            <p className="text-xs text-[var(--fg-2)] leading-relaxed">{finding.summary}</p>
          )}
        </div>

        {/* Transition Action Buttons */}
        <div className="flex flex-wrap items-center gap-2 self-start shrink-0">
          {finding.status === "open" && (
            <>
              <Button
                variant="secondary"
                size="sm"
                isLoading={isSubmitting}
                onClick={() => handleTransition("acknowledged")}
              >
                Acknowledge
              </Button>
              <Button
                variant="primary"
                size="sm"
                isLoading={isSubmitting}
                onClick={() => handleTransition("in_progress")}
              >
                Start Progress
              </Button>
              <Button variant="tertiary" size="sm" onClick={() => setIsTriageOpen(true)}>
                Triage...
              </Button>
            </>
          )}

          {finding.status === "acknowledged" && (
            <>
              <Button
                variant="primary"
                size="sm"
                isLoading={isSubmitting}
                onClick={() => handleTransition("in_progress")}
              >
                Start Progress
              </Button>
              <Button variant="tertiary" size="sm" onClick={() => setIsTriageOpen(true)}>
                Triage...
              </Button>
            </>
          )}

          {finding.status === "in_progress" && (
            <>
              <Button
                variant="primary"
                size="sm"
                isLoading={isSubmitting}
                onClick={() => handleTransition("resolved", "Verified by developer in branch")}
              >
                Mark as Resolved
              </Button>
              <Button variant="tertiary" size="sm" onClick={() => setIsTriageOpen(true)}>
                Triage...
              </Button>
            </>
          )}

          {(finding.status === "dismissed" ||
            finding.status === "accepted_risk" ||
            finding.status === "resolved") && (
            <Button
              variant="secondary"
              size="sm"
              isLoading={isSubmitting}
              onClick={() => handleTransition("open", "Reopened by user")}
            >
              Reopen Finding
            </Button>
          )}
        </div>
      </div>

      {/* Severity / Confidence / Evidence-level Strip (docs/08 §11 S-08) */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-[var(--bg-0)] p-3 rounded-[var(--radius-md)] border border-[var(--line-1)]">
        <div className="space-y-1">
          <div className="text-[10px] text-[var(--fg-3)] uppercase tracking-wider font-semibold">
            Severity
          </div>
          <div className="flex items-center gap-1.5">
            <Badge variant={getSeverityBadgeVariant(finding.severity)} size="sm">
              {finding.severity.toUpperCase()}
            </Badge>
          </div>
        </div>

        <div className="space-y-1">
          <div className="text-[10px] text-[var(--fg-3)] uppercase tracking-wider font-semibold">
            Evidence Level
          </div>
          <div className="flex items-center gap-1.5">
            <Badge evidenceLevel={finding.evidence_level as "E0" | "E1" | "E2"} size="sm">
              {finding.evidence_level}
            </Badge>
            <span className="text-[11px] text-[var(--fg-2)]">
              {finding.evidence_level === "E2"
                ? "Deterministic"
                : finding.evidence_level === "E1"
                  ? "Rule match"
                  : "Heuristic"}
            </span>
          </div>
        </div>

        <div className="space-y-1">
          <div className="text-[10px] text-[var(--fg-3)] uppercase tracking-wider font-semibold">
            Confidence
          </div>
          <div className="text-xs font-mono text-[var(--fg-1)] capitalize">
            {`${finding.confidence} confidence`}
          </div>
        </div>

        <div className="space-y-1">
          <div className="text-[10px] text-[var(--fg-3)] uppercase tracking-wider font-semibold">
            Category
          </div>
          <div className="text-xs text-[var(--fg-1)] capitalize">
            {finding.category.replace(/_/g, " ")}
          </div>
        </div>
      </div>

      {/* What and Where · Code Excerpt with Highlighted Lines */}
      {finding.primary_path && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold text-[var(--fg-1)] uppercase tracking-wider">
              What and Where
            </h2>
            <div className="text-[11px] font-mono text-[var(--fg-2)]">
              Snapshot resolvable location
            </div>
          </div>

          {snippetInfo ? (
            <CodeExcerpt
              path={finding.primary_path}
              code={snippetInfo.code}
              startLine={snippetInfo.startLine}
              highlightStart={finding.primary_start_line || undefined}
              highlightEnd={finding.primary_end_line || undefined}
            />
          ) : (
            <div className="p-4 bg-[var(--bg-0)] rounded-[var(--radius-md)] border border-[var(--line-1)] font-mono text-xs text-[var(--fg-2)]">
              Location: {finding.primary_path}
              {finding.primary_start_line && ` (line ${finding.primary_start_line})`}
            </div>
          )}
        </div>
      )}

      {/* Why It Matters */}
      <div className="space-y-2">
        <h2 className="text-xs font-semibold text-[var(--fg-1)] uppercase tracking-wider">
          Why It Matters
        </h2>
        <div className="bg-[var(--bg-1)] p-4 rounded-[var(--radius-md)] border border-[var(--line-1)] text-xs text-[var(--fg-1)] leading-relaxed">
          {finding.explanation || finding.summary || "No extended explanation provided."}
        </div>
      </div>

      {/* Machine-Checkable Evidence (docs/08 §11 S-08: each evidence item with its source: rule hit, structural check, retrieved context) */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold text-[var(--fg-1)] uppercase tracking-wider">
            Machine-Checkable Evidence
          </h2>
          <span className="text-[11px] text-[var(--fg-2)]">
            {finding.evidence ? `${finding.evidence.length} verified item(s)` : "0 items"}
          </span>
        </div>

        {finding.evidence && finding.evidence.length > 0 ? (
          <div className="space-y-2">
            {finding.evidence.map((item: FindingEvidenceItem) => (
              <div
                key={item.id}
                className="p-3 bg-[var(--bg-0)] rounded-[var(--radius-md)] border border-[var(--line-1)] space-y-2 text-xs"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded-[var(--radius-chip)] bg-[rgba(78,161,255,0.1)] text-[var(--ref)] border border-[rgba(78,161,255,0.3)] text-[10px] font-mono uppercase">
                      {item.role.replace(/_/g, " ")}
                    </span>
                    <span className="font-mono text-[var(--fg-0)]">
                      {item.path}#L{item.start_line}-L{item.end_line}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-[var(--fg-3)]">
                      {item.snippet_hash}
                    </span>
                    <span
                      className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${
                        item.is_current
                          ? "bg-[rgba(32,227,162,0.1)] text-[var(--signal)]"
                          : "bg-[rgba(255,107,94,0.1)] text-[var(--danger)]"
                      }`}
                    >
                      {item.is_current ? "current" : "stale"}
                    </span>
                  </div>
                </div>

                {/* Structured Evidence Detail Key-Values */}
                {item.detail && Object.keys(item.detail).length > 0 && (
                  <div className="bg-[var(--bg-1)] p-2.5 rounded-[var(--radius-sm)] border border-[var(--line-1)] font-mono text-[11px] text-[var(--fg-2)] space-y-1">
                    {Object.entries(item.detail).map(([k, v]) => (
                      <div key={k} className="flex items-start gap-2">
                        <span className="text-[var(--fg-3)] shrink-0">{k}:</span>
                        <span className="text-[var(--fg-1)] break-all">{String(v)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="p-4 bg-[var(--bg-0)] rounded-[var(--radius-md)] border border-[var(--line-1)] text-xs text-[var(--fg-2)] text-center">
            No discrete evidence records attached.
          </div>
        )}
      </div>

      {/* Suggested Remediation (docs/08 §11 S-08: proposal only; 'Review and apply yourself', no auto-apply) */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold text-[var(--fg-1)] uppercase tracking-wider">
            Suggested Remediation
          </h2>
          <span className="text-[11px] font-medium text-[var(--warn)]">
            Proposal only · Review and apply yourself (no auto-apply)
          </span>
        </div>

        {suggestedFix ? (
          <div className="bg-[var(--bg-1)] p-4 rounded-[var(--radius-md)] border border-[var(--line-1)] space-y-3">
            {suggestedFix.summary && (
              <div className="text-xs font-medium text-[var(--fg-0)]">{suggestedFix.summary}</div>
            )}

            {suggestedFix.remediation_steps && suggestedFix.remediation_steps.length > 0 && (
              <div className="space-y-1.5">
                <div className="text-[11px] font-semibold text-[var(--fg-2)] uppercase tracking-wider">
                  Action Steps:
                </div>
                <ul className="list-disc list-inside space-y-1 text-xs text-[var(--fg-1)]">
                  {suggestedFix.remediation_steps.map((step, idx) => (
                    <li key={idx}>{step}</li>
                  ))}
                </ul>
              </div>
            )}

            {suggestedFix.code_suggestion && (
              <div className="space-y-1">
                <div className="text-[11px] font-semibold text-[var(--fg-2)] uppercase tracking-wider">
                  Suggested Diff:
                </div>
                <pre className="bg-[var(--bg-0)] p-3 rounded-[var(--radius-sm)] border border-[var(--line-1)] font-mono text-xs text-[var(--fg-1)] overflow-x-auto whitespace-pre">
                  {suggestedFix.code_suggestion}
                </pre>
              </div>
            )}
          </div>
        ) : (
          <div className="bg-[var(--bg-1)] p-4 rounded-[var(--radius-md)] border border-[var(--line-1)] text-xs text-[var(--fg-2)]">
            No specific code suggestion generated for this finding. Follow the rule documentation to
            remediate.
          </div>
        )}
      </div>

      {/* Status History Audit Timeline */}
      <div className="space-y-2">
        <h2 className="text-xs font-semibold text-[var(--fg-1)] uppercase tracking-wider">
          Status History & Audit Trail
        </h2>

        {finding.history && finding.history.length > 0 ? (
          <div className="border border-[var(--line-1)] rounded-[var(--radius-md)] bg-[var(--bg-0)] divide-y divide-[var(--line-1)]">
            {finding.history.map((hist) => (
              <div key={hist.id} className="p-3 text-xs space-y-1">
                <div className="flex items-center justify-between text-[11px]">
                  <div className="flex items-center gap-1.5 font-mono">
                    <span className="text-[var(--fg-2)] capitalize">{hist.from_status}</span>
                    <span className="text-[var(--fg-3)]">→</span>
                    <span className="text-[var(--signal)] font-semibold capitalize">
                      {hist.to_status}
                    </span>
                  </div>
                  <span className="text-[var(--fg-3)]">
                    {new Date(hist.created_at).toLocaleString()}
                  </span>
                </div>
                <div className="text-[var(--fg-1)]">
                  <span>{`Actor (${hist.actor_kind}): ${hist.actor_id || "system"}`}</span>
                  {hist.reason && (
                    <span className="text-[var(--fg-2)] ml-2">{`— "${hist.reason}"`}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-4 bg-[var(--bg-0)] rounded-[var(--radius-md)] border border-[var(--line-1)] text-xs text-[var(--fg-2)]">
            No prior status transitions recorded.
          </div>
        )}
      </div>

      {/* Triage Modal */}
      <FindingTriageModal
        isOpen={isTriageOpen}
        onClose={() => setIsTriageOpen(false)}
        finding={finding}
        hasMaintainerPermission={hasMaintainerPermission}
        onConfirm={handleTriageSubmit}
      />
    </div>
  );
}
