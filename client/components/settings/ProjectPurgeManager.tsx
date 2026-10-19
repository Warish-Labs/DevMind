"use client";

import React, { useState } from "react";
import { useApp } from "@/context/AppContext";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Dialog } from "@/components/ui/Dialog";
import type { DeletionVerificationReport } from "@devmind/common";

interface ProjectPurgeManagerProps {
  projectId: string;
}

export function ProjectPurgeManager({ projectId }: ProjectPurgeManagerProps) {
  const { currentProject, setCurrentProject, setSyncMode } = useApp();

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [typedSlug, setTypedSlug] = useState("");
  const [selectedScope, setSelectedScope] = useState<"all" | "chunks_and_embeddings">("all");
  const [isPurging, setIsPurging] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [verificationReport, setVerificationReport] = useState<DeletionVerificationReport | null>(
    null
  );
  const [copiedHash, setCopiedHash] = useState(false);

  const projectSlug = currentProject?.slug || projectId;
  const isSlugMatched = typedSlug.trim() === projectSlug;

  const handleOpenDialog = () => {
    setTypedSlug("");
    setErrorMessage(null);
    setIsDialogOpen(true);
  };

  const handleExecutePurge = async () => {
    if (!isSlugMatched) return;
    setIsPurging(true);
    setErrorMessage(null);

    try {
      const report = await apiClient.purgeProjectData(projectId, {
        scope: selectedScope,
        confirmation_slug: typedSlug.trim(),
      });

      setVerificationReport(report);
      setSyncMode("metadata_only");
      if (currentProject) {
        setCurrentProject({
          ...currentProject,
          sync_mode: "metadata_only",
        });
      }
      setIsDialogOpen(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to execute project data purge.";
      setErrorMessage(msg);
    } finally {
      setIsPurging(false);
    }
  };

  const handleCopyHash = () => {
    if (!verificationReport) return;
    navigator.clipboard.writeText(verificationReport.verification_hash);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Danger Zone Purge Action Card */}
      <Card
        className="border-[var(--danger)]/50 bg-[rgba(255,107,94,0.03)] font-mono text-xs"
        data-testid="project-purge-card"
      >
        <CardHeader>
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-[var(--danger)] font-bold tracking-wider uppercase">
              Irreversible Operation · ADR-047
            </span>
            <Badge variant="danger" size="sm" mono>
              E2E-6
            </Badge>
          </div>
          <CardTitle className="text-base font-semibold text-[var(--danger)] mt-1">
            Purge Project Data Across Cloud Stores
          </CardTitle>
          <CardDescription className="text-xs text-[var(--fg-1)] leading-relaxed">
            Permanently purges code chunks, vector embeddings, job events, and thread checkpoints
            across PostgreSQL, Redis, and LangGraph datastores with per-store counts and an
            immutable SHA-256 verification report.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="p-3 rounded-[var(--radius-sm)] border border-[var(--danger)]/30 bg-[rgba(255,107,94,0.06)] text-[var(--danger)] space-y-1">
            <div className="font-semibold flex items-center gap-1.5">
              <span>⚠</span>
              <span>Consequence Notice: Zero Residual Storage at Rest</span>
            </div>
            <p className="text-[11px] text-[var(--fg-1)] leading-relaxed">
              Purging data resets project synchronization mode to{" "}
              <strong className="text-[var(--fg-0)]">metadata_only</strong>. Structural symbols and
              finding triage records are retained, but all indexed vectors and snippet texts are
              destroyed.
            </p>
          </div>

          <div className="pt-2 border-t border-[var(--line-1)] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <span className="text-[11px] text-[var(--fg-2)]">
              Requires Project Maintainer or Admin permissions
            </span>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleOpenDialog}
              aria-label="Initiate Project Data Purge"
            >
              Initiate Project Data Purge...
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Deletion Verification Report (Displayed when completed) */}
      {verificationReport && (
        <Card
          className="border-[var(--signal)] bg-[rgba(0,230,153,0.03)] font-mono text-xs animate-in fade-in"
          data-testid="deletion-verification-report"
          role="region"
          aria-labelledby="report-heading"
        >
          <CardHeader className="border-b border-[var(--line-1)] pb-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="text-[var(--signal)] text-base">✓</span>
                <CardTitle id="report-heading" className="text-sm font-semibold text-[var(--fg-0)]">
                  Deletion Verification Report
                </CardTitle>
                <Badge variant="signal" size="sm" mono>
                  VERIFIED
                </Badge>
              </div>
              <span className="text-[11px] text-[var(--fg-2)]">
                Purged on {new Date(verificationReport.purged_at).toLocaleString()}
              </span>
            </div>
            <CardDescription className="text-xs text-[var(--fg-1)]">
              Cryptographically verified deletion record. Project sync mode downgraded to{" "}
              <span className="text-[var(--signal)] uppercase">{verificationReport.sync_mode}</span>
              .
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 pt-4">
            {/* Per-Store Deletion Counts Grid */}
            <div className="space-y-2">
              <span className="font-semibold text-[var(--fg-0)] block">
                Per-Store Deletion Breakdown:
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="p-3 rounded-[var(--radius-sm)] border border-[var(--line-1)] bg-[var(--bg-0)]">
                  <div className="text-[10px] text-[var(--fg-2)] uppercase font-semibold">
                    PostgreSQL Store
                  </div>
                  <div className="mt-2 space-y-1 text-xs">
                    <div className="flex justify-between">
                      <span className="text-[var(--fg-2)]">Code Chunks:</span>
                      <strong className="text-[var(--fg-0)]">
                        {verificationReport.stores.postgres?.code_chunks ?? 0}
                      </strong>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--fg-2)]">Chunk Vectors:</span>
                      <strong className="text-[var(--fg-0)]">
                        {verificationReport.stores.postgres?.chunk_embeddings ?? 0}
                      </strong>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--fg-2)]">Evidence Snippets:</span>
                      <strong className="text-[var(--fg-0)]">
                        {verificationReport.stores.postgres?.evidence_snippets ?? 0}
                      </strong>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--fg-2)]">Job Events:</span>
                      <strong className="text-[var(--fg-0)]">
                        {verificationReport.stores.postgres?.job_events ?? 0}
                      </strong>
                    </div>
                  </div>
                </div>

                <div className="p-3 rounded-[var(--radius-sm)] border border-[var(--line-1)] bg-[var(--bg-0)]">
                  <div className="text-[10px] text-[var(--fg-2)] uppercase font-semibold">
                    Redis Cache
                  </div>
                  <div className="mt-2 space-y-1 text-xs">
                    <div className="flex justify-between">
                      <span className="text-[var(--fg-2)]">Cache Keys Purged:</span>
                      <strong className="text-[var(--fg-0)]">
                        {verificationReport.stores.redis?.cache_keys_purged ?? 0}
                      </strong>
                    </div>
                    <div className="text-[11px] text-[var(--fg-2)] pt-2">
                      Project search &amp; graph cache keys evicted
                    </div>
                  </div>
                </div>

                <div className="p-3 rounded-[var(--radius-sm)] border border-[var(--line-1)] bg-[var(--bg-0)]">
                  <div className="text-[10px] text-[var(--fg-2)] uppercase font-semibold">
                    LangGraph Checkpoints
                  </div>
                  <div className="mt-2 space-y-1 text-xs">
                    <div className="flex justify-between">
                      <span className="text-[var(--fg-2)]">Agent Threads:</span>
                      <strong className="text-[var(--fg-0)]">
                        {verificationReport.stores.checkpoints?.threads_purged ?? 0}
                      </strong>
                    </div>
                    <div className="text-[11px] text-[var(--fg-2)] pt-2">
                      Execution thread states deleted from langgraph schema
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Cryptographic Verification Hash Box */}
            <div className="space-y-1.5 pt-2 border-t border-[var(--line-1)]">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-[var(--fg-0)]">
                  Cryptographic Verification Hash (SHA-256):
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleCopyHash}
                  aria-label="Copy verification hash to clipboard"
                >
                  {copiedHash ? "Copied ✓" : "Copy Hash"}
                </Button>
              </div>
              <div className="p-2.5 rounded-[var(--radius-control)] bg-[var(--bg-0)] border border-[var(--line-2)] text-[11px] text-[var(--signal)] break-all select-all">
                {verificationReport.verification_hash}
              </div>
              <p className="text-[10px] text-[var(--fg-2)]">
                Recorded to immutable append-only audit trail with actor ID{" "}
                <span className="text-[var(--fg-1)]">{verificationReport.requested_by}</span>.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Typed Confirmation Dialog */}
      <Dialog
        isOpen={isDialogOpen}
        onClose={() => {
          if (!isPurging) setIsDialogOpen(false);
        }}
        title="Confirm Irreversible Data Purge"
        description="This action cannot be undone. All persistent vectors, chunks, and cache entries will be wiped across all stores."
      >
        <div className="space-y-4 py-2 font-mono text-xs">
          {errorMessage && (
            <div className="p-2.5 rounded-[var(--radius-sm)] border border-[var(--danger)] bg-[rgba(255,107,94,0.08)] text-[var(--danger)]">
              {errorMessage}
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-[var(--fg-1)] block font-semibold">Select Purge Scope:</label>
            <div className="space-y-2">
              <label className="flex items-start gap-2 p-2.5 rounded-[var(--radius-sm)] border border-[var(--line-2)] hover:bg-[var(--bg-1)] cursor-pointer">
                <input
                  type="radio"
                  name="purgeScope"
                  value="all"
                  checked={selectedScope === "all"}
                  onChange={() => setSelectedScope("all")}
                  className="mt-0.5 accent-[var(--danger)]"
                />
                <div>
                  <strong className="text-[var(--fg-0)] block">
                    Full Data Purge (Recommended for decommissioning)
                  </strong>
                  <span className="text-[11px] text-[var(--fg-2)]">
                    Purges code chunks, vector embeddings, evidence snippets, job events, and
                    checkpoint threads across PostgreSQL, Redis, and LangGraph.
                  </span>
                </div>
              </label>

              <label className="flex items-start gap-2 p-2.5 rounded-[var(--radius-sm)] border border-[var(--line-2)] hover:bg-[var(--bg-1)] cursor-pointer">
                <input
                  type="radio"
                  name="purgeScope"
                  value="chunks_and_embeddings"
                  checked={selectedScope === "chunks_and_embeddings"}
                  onChange={() => setSelectedScope("chunks_and_embeddings")}
                  className="mt-0.5 accent-[var(--danger)]"
                />
                <div>
                  <strong className="text-[var(--fg-0)] block">Chunks &amp; Embeddings Only</strong>
                  <span className="text-[11px] text-[var(--fg-2)]">
                    Destroys persistent vector embeddings and raw code text while retaining job logs
                    and conversation threads.
                  </span>
                </div>
              </label>
            </div>
          </div>

          <div className="space-y-1.5 pt-2 border-t border-[var(--line-1)]">
            <label htmlFor="confirm-slug-input" className="text-[var(--fg-1)] block">
              To confirm, type{" "}
              <strong className="text-[var(--danger)] select-all">{projectSlug}</strong> below:
            </label>
            <input
              id="confirm-slug-input"
              type="text"
              value={typedSlug}
              onChange={(e) => setTypedSlug(e.target.value)}
              placeholder={projectSlug}
              className="w-full h-9 px-3 rounded-[var(--radius-control)] bg-[var(--bg-0)] border border-[var(--line-2)] text-[var(--fg-0)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--danger)]"
              autoComplete="off"
              disabled={isPurging}
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-[var(--line-1)]">
            <Button
              variant="secondary"
              size="sm"
              disabled={isPurging}
              onClick={() => setIsDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              disabled={!isSlugMatched || isPurging}
              onClick={handleExecutePurge}
            >
              {isPurging ? "Purging Stores..." : "I Understand the Consequences, Purge Data"}
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
