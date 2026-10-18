"use client";

import React, { useState } from "react";
import { useApp } from "@/context/AppContext";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Dialog } from "@/components/ui/Dialog";
import type { SyncModeTransitionResponse } from "@devmind/common";

interface SyncModeManagerProps {
  projectId: string;
  initialSyncMode?: "metadata_only" | "indexed";
}

export function SyncModeManager({ projectId, initialSyncMode }: SyncModeManagerProps) {
  const { currentProject, setCurrentProject, setSyncMode } = useApp();
  const activeSyncMode: "metadata_only" | "indexed" =
    initialSyncMode ??
    (currentProject?.sync_mode as "metadata_only" | "indexed") ??
    "metadata_only";

  const [pendingMode, setPendingMode] = useState<"metadata_only" | "indexed" | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [transitionResult, setTransitionResult] = useState<SyncModeTransitionResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleOpenConfirm = (targetMode: "metadata_only" | "indexed") => {
    if (targetMode === activeSyncMode) return;
    setPendingMode(targetMode);
    setErrorMessage(null);
  };

  const handleConfirmTransition = async () => {
    if (!pendingMode) return;
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const result = await apiClient.updateProjectSyncMode(projectId, pendingMode);
      setTransitionResult(result);
      setSyncMode(result.new_sync_mode);
      if (currentProject) {
        setCurrentProject({
          ...currentProject,
          sync_mode: result.new_sync_mode,
        });
      }
      setPendingMode(null);
    } catch (err: unknown) {
      const errorMsg =
        err instanceof Error ? err.message : "Failed to update project synchronization mode.";
      setErrorMessage(errorMsg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Success Notification Banner */}
      {transitionResult && (
        <div
          role="status"
          className="p-4 rounded-[var(--radius-panel)] border border-[var(--signal)] bg-[rgba(0,230,153,0.08)] flex items-start justify-between gap-3 font-mono text-xs text-[var(--fg-0)] animate-in fade-in"
        >
          <div className="space-y-1">
            <div className="flex items-center gap-2 font-semibold text-[var(--signal)]">
              <span>✓</span>
              <span>
                Synchronization mode transitioned to{" "}
                <span className="uppercase">{transitionResult.new_sync_mode}</span>
              </span>
            </div>
            {transitionResult.new_sync_mode === "metadata_only" ? (
              <p className="text-[var(--fg-1)]">
                Consequence executed: Permanently purged{" "}
                <strong className="text-[var(--fg-0)]">
                  {transitionResult.purged_counts.code_chunks}
                </strong>{" "}
                code chunks and{" "}
                <strong className="text-[var(--fg-0)]">
                  {transitionResult.purged_counts.embeddings}
                </strong>{" "}
                vector embeddings from DevMind cloud stores.
              </p>
            ) : (
              <p className="text-[var(--fg-1)]">
                Indexed mode enabled. Consented, redacted snippets will now be indexed for full
                conversation grounding.
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={() => setTransitionResult(null)}
            className="text-[var(--fg-2)] hover:text-[var(--fg-0)] p-1"
            aria-label="Dismiss transition notice"
          >
            ✕
          </button>
        </div>
      )}

      {/* Sync Modes Comparison Diptych (ADR-022 & docs/08 §11 S-10) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Mode 1: Metadata-Only Mode */}
        <Card
          className={`relative transition-all duration-[var(--dur-2)] ${
            activeSyncMode === "metadata_only"
              ? "border-[var(--signal)] ring-1 ring-[var(--signal)]/50 bg-[var(--bg-1)]"
              : "border-[var(--line-1)] bg-[var(--bg-1)]/40 hover:border-[var(--line-2)]"
          }`}
          data-testid="sync-mode-card-metadata"
        >
          <CardHeader>
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] text-[var(--fg-2)]">MODE 01</span>
              {activeSyncMode === "metadata_only" && (
                <Badge variant="signal" size="sm">
                  ACTIVE MODE
                </Badge>
              )}
            </div>
            <CardTitle className="text-[17px] font-semibold text-[var(--fg-0)] mt-2">
              Metadata-Only Mode
            </CardTitle>
            <CardDescription className="text-xs text-[var(--fg-2)] leading-relaxed">
              Zero source code leaves your local workstation. Only AST symbols, file hashes,
              structural dependencies, and finding records reside on the server.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ul className="text-xs space-y-2 text-[var(--fg-1)] font-mono">
              <li className="flex items-center gap-2">
                <span className="text-[var(--signal)]">✓</span>
                <span>Symbol signatures and relationships stored</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="text-[var(--signal)]">✓</span>
                <span>Deterministic E0-E2 security finding metadata</span>
              </li>
              <li className="flex items-center gap-2 text-[var(--warn)]">
                <span>⚠</span>
                <span>Persistent code chunks and embeddings purged</span>
              </li>
              <li className="flex items-center gap-2 text-[var(--fg-2)]">
                <span>—</span>
                <span>Code answers require user snippet attachment</span>
              </li>
            </ul>

            <div className="pt-4 border-t border-[var(--line-1)] flex items-center justify-between">
              <span className="text-[11px] font-mono text-[var(--fg-2)]">Default setting</span>
              <Button
                variant={activeSyncMode === "metadata_only" ? "secondary" : "primary"}
                size="sm"
                disabled={activeSyncMode === "metadata_only" || isSubmitting}
                onClick={() => handleOpenConfirm("metadata_only")}
                aria-label="Switch to Metadata-Only Sync Mode"
              >
                {activeSyncMode === "metadata_only"
                  ? "Currently Active"
                  : "Switch to Metadata-Only"}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Mode 2: Indexed Mode */}
        <Card
          className={`relative transition-all duration-[var(--dur-2)] ${
            activeSyncMode === "indexed"
              ? "border-[var(--signal)] ring-1 ring-[var(--signal)]/50 bg-[var(--bg-1)]"
              : "border-[var(--line-1)] bg-[var(--bg-1)]/40 hover:border-[var(--line-2)]"
          }`}
          data-testid="sync-mode-card-indexed"
        >
          <CardHeader>
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] text-[var(--fg-2)]">MODE 02</span>
              {activeSyncMode === "indexed" && (
                <Badge variant="signal" size="sm">
                  ACTIVE MODE
                </Badge>
              )}
            </div>
            <CardTitle className="text-[17px] font-semibold text-[var(--fg-0)] mt-2">
              Indexed Mode (Persistent Retrieval)
            </CardTitle>
            <CardDescription className="text-xs text-[var(--fg-2)] leading-relaxed">
              Consented, redacted code chunks are stored and indexed with pgvector embeddings to
              enable continuous Project Brain reasoning and AI chat grounding.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ul className="text-xs space-y-2 text-[var(--fg-1)] font-mono">
              <li className="flex items-center gap-2">
                <span className="text-[var(--signal)]">✓</span>
                <span>Persistent AST &amp; vector hybrid search</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="text-[var(--signal)]">✓</span>
                <span>Full conversational Q&amp;A with line citations</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="text-[var(--signal)]">✓</span>
                <span>Automated secret redaction before storage</span>
              </li>
              <li className="flex items-center gap-2 text-[var(--ref)]">
                <span>ℹ</span>
                <span>Reversible anytime with verifiable purge</span>
              </li>
            </ul>

            <div className="pt-4 border-t border-[var(--line-1)] flex items-center justify-between">
              <span className="text-[11px] font-mono text-[var(--fg-2)]">Consented storage</span>
              <Button
                variant={activeSyncMode === "indexed" ? "secondary" : "primary"}
                size="sm"
                disabled={activeSyncMode === "indexed" || isSubmitting}
                onClick={() => handleOpenConfirm("indexed")}
                aria-label="Switch to Indexed Sync Mode"
              >
                {activeSyncMode === "indexed" ? "Currently Active" : "Switch to Indexed Mode"}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Confirmation Dialog with Purge Consequences Warning */}
      <Dialog
        isOpen={Boolean(pendingMode)}
        onClose={() => {
          if (!isSubmitting) setPendingMode(null);
        }}
        title={
          pendingMode === "metadata_only"
            ? "Confirm Switch to Metadata-Only Mode"
            : "Confirm Enable Indexed Sync Mode"
        }
        description={
          pendingMode === "metadata_only"
            ? "Consequence warning: This action will permanently delete all stored code chunks and embeddings from DevMind cloud datastores."
            : "This mode stores consented, redacted code chunks on the server to power Project Brain hybrid retrieval."
        }
      >
        <div className="space-y-4 py-2 font-mono text-xs">
          {pendingMode === "metadata_only" ? (
            <div className="p-3 rounded-[var(--radius-sm)] border border-[var(--danger)]/50 bg-[rgba(255,107,94,0.08)] text-[var(--danger)] space-y-2">
              <div className="font-semibold flex items-center gap-1.5">
                <span>⚠</span>
                <span>Permanent Data Purge (ADR-022)</span>
              </div>
              <p className="text-[11px] leading-relaxed text-[var(--fg-1)]">
                All full-text code chunks, vector embeddings, and cached code excerpts for project{" "}
                <strong className="text-[var(--fg-0)]">{projectId}</strong> will be immediately
                erased from PostgreSQL and vector index tables. An immutable audit record with
                deletion metrics will be recorded.
              </p>
            </div>
          ) : (
            <div className="p-3 rounded-[var(--radius-sm)] border border-[var(--signal)]/50 bg-[rgba(0,230,153,0.08)] text-[var(--fg-1)] space-y-2">
              <div className="font-semibold text-[var(--signal)] flex items-center gap-1.5">
                <span>✓</span>
                <span>Privacy &amp; Redaction Guarantee (ADR-047)</span>
              </div>
              <p className="text-[11px] leading-relaxed">
                Source files leave your machine only with explicit extension sync consent. All API
                keys, credentials, and customer secrets are redacted locally before transit.
              </p>
            </div>
          )}

          {errorMessage && (
            <div
              role="alert"
              className="p-2.5 rounded-[var(--radius-sm)] bg-[var(--danger)]/10 text-[var(--danger)] border border-[var(--danger)]/30 text-[11px]"
            >
              ✕ {errorMessage}
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-[var(--line-1)]">
            <Button
              variant="secondary"
              size="sm"
              disabled={isSubmitting}
              onClick={() => setPendingMode(null)}
            >
              Cancel
            </Button>
            <Button
              variant={pendingMode === "metadata_only" ? "destructive" : "primary"}
              size="sm"
              isLoading={isSubmitting}
              onClick={handleConfirmTransition}
            >
              {pendingMode === "metadata_only"
                ? "Confirm & Purge Stored Chunks"
                : "Enable Indexed Sync"}
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
