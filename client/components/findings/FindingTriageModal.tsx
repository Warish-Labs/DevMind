"use client";

import React, { useState } from "react";
import type { FindingItem } from "@devmind/common/api";
import { Dialog } from "../ui/Dialog";
import { Button } from "../ui/Button";

export type TriageAction = "dismissed" | "accepted_risk";

export interface FindingTriageModalProps {
  isOpen: boolean;
  onClose: () => void;
  finding: FindingItem | null;
  hasMaintainerPermission?: boolean;
  onConfirm: (payload: { to_status: string; reason: string }) => Promise<void> | void;
}

export function FindingTriageModal({
  isOpen,
  onClose,
  finding,
  hasMaintainerPermission = true,
  onConfirm,
}: FindingTriageModalProps) {
  const [triageAction, setTriageAction] = useState<TriageAction>("dismissed");
  const [reasonCode, setReasonCode] = useState<string>("false_positive");
  const [detailReason, setDetailReason] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!finding) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!hasMaintainerPermission) return;

    const trimmedReason = detailReason.trim();
    if (!trimmedReason && triageAction === "accepted_risk") {
      setErrorMessage("Please provide a risk rationale or mitigation plan.");
      return;
    }

    const formattedReason =
      triageAction === "dismissed"
        ? `${reasonCode}: ${trimmedReason || "No extra detail"}`
        : trimmedReason;

    try {
      setIsSubmitting(true);
      setErrorMessage(null);
      await onConfirm({
        to_status: triageAction,
        reason: formattedReason,
      });
      onClose();
    } catch (err: unknown) {
      const errObj = err as { message?: string };
      setErrorMessage(errObj.message || "Failed to update finding status");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog
      isOpen={isOpen}
      onClose={onClose}
      title={`Triage Finding · ${finding.rule_id}`}
      description="Triage transitions (Dismiss or Accept Risk) require maintainer permission and are logged to audit history."
      className="max-w-lg"
      footer={
        <div className="flex items-center justify-between w-full">
          <div>
            {!hasMaintainerPermission && (
              <span className="text-[11px] text-[var(--danger)]">
                Maintainer permission required to triage.
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="tertiary"
              size="sm"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              form="triage-finding-form"
              variant={triageAction === "dismissed" ? "secondary" : "destructive"}
              size="sm"
              isLoading={isSubmitting}
              disabled={!hasMaintainerPermission || isSubmitting}
            >
              Confirm {triageAction === "dismissed" ? "Dismissal" : "Accepted Risk"}
            </Button>
          </div>
        </div>
      }
    >
      <form id="triage-finding-form" onSubmit={handleSubmit} className="space-y-4">
        {errorMessage && (
          <div className="p-2.5 rounded-[var(--radius-sm)] border border-[var(--danger)] bg-[rgba(255,107,94,0.1)] text-xs text-[var(--danger)]">
            {errorMessage}
          </div>
        )}

        {/* Action Type Selector */}
        <div>
          <label className="block text-xs font-medium text-[var(--fg-1)] mb-1.5">
            Triage Decision
          </label>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => {
                setTriageAction("dismissed");
                setErrorMessage(null);
              }}
              className={`p-3 rounded-[var(--radius-sm)] border text-left transition-colors ${
                triageAction === "dismissed"
                  ? "border-[var(--line-strong)] bg-[var(--bg-2)] text-[var(--fg-0)]"
                  : "border-[var(--line-1)] bg-[var(--bg-1)] text-[var(--fg-2)] hover:text-[var(--fg-1)]"
              }`}
            >
              <div className="text-xs font-semibold">Dismiss Finding</div>
              <div className="text-[11px] text-[var(--fg-2)] mt-0.5">
                Mark as false positive or non-applicable
              </div>
            </button>

            <button
              type="button"
              onClick={() => {
                setTriageAction("accepted_risk");
                setErrorMessage(null);
              }}
              className={`p-3 rounded-[var(--radius-sm)] border text-left transition-colors ${
                triageAction === "accepted_risk"
                  ? "border-[var(--warn)] bg-[rgba(240,180,76,0.08)] text-[var(--warn)]"
                  : "border-[var(--line-1)] bg-[var(--bg-1)] text-[var(--fg-2)] hover:text-[var(--fg-1)]"
              }`}
            >
              <div className="text-xs font-semibold">Accept Risk</div>
              <div className="text-[11px] text-[var(--fg-2)] mt-0.5">
                Acknowledge known risk with compensating control
              </div>
            </button>
          </div>
        </div>

        {/* Dismiss Reason Code */}
        {triageAction === "dismissed" && (
          <div>
            <label
              htmlFor="reason-code-select"
              className="block text-xs font-medium text-[var(--fg-1)] mb-1"
            >
              Dismiss Reason Code <span className="text-[var(--danger)]">*</span>
            </label>
            <select
              id="reason-code-select"
              value={reasonCode}
              onChange={(e) => setReasonCode(e.target.value)}
              className="w-full px-3 py-1.5 text-xs rounded-[var(--radius-sm)] bg-[var(--bg-2)] border border-[var(--line-1)] text-[var(--fg-0)] focus:outline-none focus:border-[var(--ref)]"
            >
              <option value="false_positive">False positive (Detection logic incorrect)</option>
              <option value="not_applicable">
                Not applicable (Compensating control outside repo)
              </option>
              <option value="duplicate">Duplicate (Tracked under another finding)</option>
              <option value="other">Other reason</option>
            </select>
          </div>
        )}

        {/* Detailed Explanation / Rationale */}
        <div>
          <label
            htmlFor="detail-reason-input"
            className="block text-xs font-medium text-[var(--fg-1)] mb-1"
          >
            {triageAction === "dismissed" ? "Triage Notes / Explanation" : "Risk Rationale & Plan"}{" "}
            {triageAction === "accepted_risk" && <span className="text-[var(--danger)]">*</span>}
          </label>
          <textarea
            id="detail-reason-input"
            rows={3}
            value={detailReason}
            onChange={(e) => setDetailReason(e.target.value)}
            placeholder={
              triageAction === "dismissed"
                ? "Describe why this rule match does not pose a risk in this codebase..."
                : "Explain compensating controls or context why this risk is acceptable..."
            }
            className="w-full px-3 py-2 text-xs rounded-[var(--radius-sm)] bg-[var(--bg-2)] border border-[var(--line-1)] text-[var(--fg-0)] placeholder-[var(--fg-3)] focus:outline-none focus:border-[var(--ref)] resize-none"
          />
        </div>

        <div className="text-[11px] text-[var(--fg-2)] bg-[var(--bg-1)] p-2.5 rounded-[var(--radius-sm)] border border-[var(--line-1)]">
          <strong>Audit notice:</strong> This status change is permanently recorded in{" "}
          <code className="text-[var(--fg-1)]">finding_status_history</code> and logged to project
          audit events with your user identity.
        </div>
      </form>
    </Dialog>
  );
}
