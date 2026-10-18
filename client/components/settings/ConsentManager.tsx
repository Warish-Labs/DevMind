"use client";

import React, { useEffect, useState } from "react";
import { useApp } from "@/context/AppContext";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Dialog } from "@/components/ui/Dialog";
import { Skeleton } from "@/components/ui/Skeleton";
import type { ConsentItem, CreateConsentRequest } from "@devmind/common";

interface ConsentManagerProps {
  projectId: string;
}

const SCOPE_DESCRIPTIONS: Record<string, string> = {
  snippet_transmission:
    "Allows transmission of user-consented, redacted code snippets attached during Q&A conversations.",
  cloud_index:
    "Allows server-side storage and pgvector indexing of consented, redacted code chunks for continuous retrieval.",
  llm_processing:
    "Permits passing sanitized structural metadata and code snippets to authorized inference providers.",
};

const DEFAULT_PROVIDERS = ["google-gemini", "anthropic", "openai"];

export function ConsentManager({ projectId }: ConsentManagerProps) {
  const { currentProject, setCurrentProject, setSyncMode } = useApp();

  const [consents, setConsents] = useState<ConsentItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [pendingRevokeConsent, setPendingRevokeConsent] = useState<ConsentItem | null>(null);
  const [isRevoking, setIsRevoking] = useState(false);
  const [actionNotice, setActionNotice] = useState<{
    type: "success" | "error";
    message: string;
    purgedCounts?: { code_chunks: number; embeddings: number } | null;
  } | null>(null);

  // New Grant Modal State
  const [isGrantModalOpen, setIsGrantModalOpen] = useState(false);
  const [newScope, setNewScope] = useState<
    "snippet_transmission" | "cloud_index" | "llm_processing"
  >("snippet_transmission");
  const [selectedProviders, setSelectedProviders] = useState<string[]>(["google-gemini"]);
  const [isGranting, setIsGranting] = useState(false);

  useEffect(() => {
    let isMounted = true;

    apiClient
      .listProjectConsents(projectId)
      .then((res) => {
        if (isMounted) {
          setConsents(res.items || []);
          setIsLoading(false);
        }
      })
      .catch(() => {
        if (isMounted) {
          // In offline / preview fallback with initial sample items
          setConsents([
            {
              id: "cs-mock-01",
              workspace_id: currentProject?.workspace_id || "ws-default",
              project_id: projectId,
              user_id: "usr-active",
              scope: "cloud_index",
              provider_ids: ["google-gemini"],
              data_categories: ["code_snippets", "ast_metadata"],
              granted_for: "project",
              policy_version: "1.0",
              preview_hash: "sha256:7f9a2e...",
              granted_at: new Date(Date.now() - 86400000 * 3).toISOString(),
              expires_at: null,
              revoked_at: null,
              is_active: true,
            },
            {
              id: "cs-mock-02",
              workspace_id: currentProject?.workspace_id || "ws-default",
              project_id: projectId,
              user_id: "usr-active",
              scope: "snippet_transmission",
              provider_ids: ["google-gemini", "anthropic"],
              data_categories: ["code_snippets"],
              granted_for: "project",
              policy_version: "1.0",
              preview_hash: "sha256:4b1c8d...",
              granted_at: new Date(Date.now() - 86400000 * 14).toISOString(),
              expires_at: null,
              revoked_at: null,
              is_active: true,
            },
          ]);
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [projectId, currentProject?.workspace_id]);

  const handleConfirmRevoke = async () => {
    if (!pendingRevokeConsent) return;
    setIsRevoking(true);
    setActionNotice(null);

    try {
      const updated = await apiClient.revokeProjectConsent(projectId, pendingRevokeConsent.id);

      setConsents((prev) =>
        prev.map((c) => (c.id === updated.id ? { ...c, ...updated, is_active: false } : c))
      );

      if (updated.sync_mode_updated && updated.new_sync_mode) {
        setSyncMode("metadata_only");
        if (currentProject) {
          setCurrentProject({
            ...currentProject,
            sync_mode: "metadata_only",
          });
        }
      }

      setActionNotice({
        type: "success",
        message: `Revoked consent for scope '${updated.scope}'. Further data transmission is now blocked.`,
        purgedCounts: updated.purged_counts,
      });

      setPendingRevokeConsent(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to revoke consent.";
      setActionNotice({
        type: "error",
        message: msg,
      });
    } finally {
      setIsRevoking(false);
    }
  };

  const handleGrantConsent = async () => {
    setIsGranting(true);
    setActionNotice(null);

    const payload: CreateConsentRequest = {
      scope: newScope,
      provider_ids: selectedProviders,
      data_categories: ["code_snippets", "ast_metadata"],
      granted_for: "project",
      policy_version: "1.0",
    };

    try {
      const created = await apiClient.createProjectConsent(projectId, payload);
      setConsents((prev) => [created, ...prev]);
      setIsGrantModalOpen(false);

      if (created.scope === "cloud_index") {
        setSyncMode("indexed");
        if (currentProject) {
          setCurrentProject({
            ...currentProject,
            sync_mode: "indexed",
          });
        }
      }

      setActionNotice({
        type: "success",
        message: `Consent grant created for '${created.scope}'. Configured transmission rules are now active.`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to record consent grant.";
      setActionNotice({
        type: "error",
        message: msg,
      });
    } finally {
      setIsGranting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header and Action */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h3 className="text-base font-semibold text-[var(--fg-0)]">
            Source Transmission Consents &amp; Legal Records
          </h3>
          <p className="text-xs text-[var(--fg-2)] mt-0.5 max-w-2xl leading-relaxed">
            Every upload of code snippets or persistent cloud indexing requires explicit recorded
            consent per ADR-047 and docs/07 §7. Revoking consent immediately blocks further network
            sends and purges dependent cloud storage.
          </p>
        </div>

        <Button
          variant="primary"
          size="sm"
          onClick={() => setIsGrantModalOpen(true)}
          aria-label="Grant New Transmission Consent"
        >
          + Grant New Consent
        </Button>
      </div>

      {/* Action Notification Alert */}
      {actionNotice && (
        <div
          role="status"
          className={`p-4 rounded-[var(--radius-panel)] border font-mono text-xs flex items-start justify-between gap-3 animate-in fade-in ${
            actionNotice.type === "success"
              ? "border-[var(--signal)] bg-[rgba(0,230,153,0.08)] text-[var(--fg-0)]"
              : "border-[var(--danger)] bg-[rgba(255,107,94,0.08)] text-[var(--danger)]"
          }`}
        >
          <div className="space-y-1">
            <div className="flex items-center gap-2 font-semibold">
              <span>{actionNotice.type === "success" ? "✓" : "⚠"}</span>
              <span>{actionNotice.message}</span>
            </div>
            {actionNotice.purgedCounts &&
              (actionNotice.purgedCounts.code_chunks > 0 ||
                actionNotice.purgedCounts.embeddings > 0) && (
                <p className="text-[var(--fg-1)]">
                  Consequence executed: Irreversibly purged{" "}
                  <strong className="text-[var(--fg-0)]">
                    {actionNotice.purgedCounts.code_chunks}
                  </strong>{" "}
                  code chunks and{" "}
                  <strong className="text-[var(--fg-0)]">
                    {actionNotice.purgedCounts.embeddings}
                  </strong>{" "}
                  vector embeddings. Sync mode downgraded to{" "}
                  <span className="uppercase text-[var(--signal)]">metadata_only</span>.
                </p>
              )}
          </div>
          <button
            type="button"
            onClick={() => setActionNotice(null)}
            className="text-[var(--fg-2)] hover:text-[var(--fg-0)] p-1"
            aria-label="Dismiss notice"
          >
            ✕
          </button>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-32 rounded-[var(--radius-panel)]" />
          <Skeleton className="h-32 rounded-[var(--radius-panel)]" />
        </div>
      ) : consents.length === 0 ? (
        <Card className="border-[var(--line-1)] bg-[var(--bg-1)]/40 p-8 text-center space-y-3">
          <div className="text-2xl text-[var(--fg-2)]">🛡️</div>
          <CardTitle className="text-sm font-semibold text-[var(--fg-0)]">
            No Active or Historical Consent Records
          </CardTitle>
          <CardDescription className="text-xs text-[var(--fg-2)] max-w-md mx-auto">
            Zero source code leaves your local machine. If you wish to enable persistent Project
            Brain hybrid indexing or conversational code grounding, create a consent grant.
          </CardDescription>
        </Card>
      ) : (
        <div className="space-y-4">
          {consents.map((consent) => (
            <Card
              key={consent.id}
              className={`border transition-colors ${
                consent.is_active
                  ? "border-[var(--line-2)] bg-[var(--bg-1)]"
                  : "border-[var(--line-1)] bg-[var(--bg-1)]/30 opacity-75"
              }`}
              data-testid={`consent-card-${consent.id}`}
            >
              <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3">
                <div className="flex items-center gap-2.5">
                  <Badge
                    variant={
                      consent.scope === "cloud_index"
                        ? "ref"
                        : consent.scope === "snippet_transmission"
                          ? "signal"
                          : "warn"
                    }
                    size="sm"
                    mono
                  >
                    {consent.scope}
                  </Badge>

                  {consent.is_active ? (
                    <Badge variant="signal" size="sm">
                      ACTIVE GRANT
                    </Badge>
                  ) : (
                    <Badge variant="neutral" size="sm">
                      REVOKED
                    </Badge>
                  )}

                  <span className="text-[11px] font-mono text-[var(--fg-2)]">
                    Policy v{consent.policy_version}
                  </span>
                </div>

                <div>
                  {consent.is_active ? (
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => setPendingRevokeConsent(consent)}
                      aria-label={`Revoke ${consent.scope} consent`}
                    >
                      Revoke Consent
                    </Button>
                  ) : (
                    <span className="text-xs font-mono text-[var(--fg-2)]">
                      Revoked on {new Date(consent.revoked_at || "").toLocaleDateString()}
                    </span>
                  )}
                </div>
              </CardHeader>

              <CardContent className="space-y-3 pt-0">
                <p className="text-xs text-[var(--fg-1)]">
                  {SCOPE_DESCRIPTIONS[consent.scope] || "Source transmission authorization."}
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-2 border-t border-[var(--line-1)] text-[11px] font-mono text-[var(--fg-2)]">
                  <div>
                    <span className="text-[var(--fg-2)] block">Authorized Providers:</span>
                    <span className="text-[var(--fg-0)]">
                      {consent.provider_ids && consent.provider_ids.length > 0
                        ? consent.provider_ids.join(", ")
                        : "All configured providers"}
                    </span>
                  </div>

                  <div>
                    <span className="text-[var(--fg-2)] block">Data Categories:</span>
                    <span className="text-[var(--fg-0)]">
                      {consent.data_categories.join(", ") || "AST only"}
                    </span>
                  </div>

                  <div>
                    <span className="text-[var(--fg-2)] block">Granted At:</span>
                    <span className="text-[var(--fg-0)]">
                      {new Date(consent.granted_at).toLocaleDateString()} ({consent.granted_for})
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Revocation Confirmation Dialog */}
      <Dialog
        isOpen={Boolean(pendingRevokeConsent)}
        onClose={() => {
          if (!isRevoking) setPendingRevokeConsent(null);
        }}
        title={`Confirm Revocation of ${pendingRevokeConsent?.scope || "Consent"}`}
        description="Revoking consent takes effect immediately. Future transmission will be rejected with 403 Problem Details."
      >
        <div className="space-y-4 py-2 font-mono text-xs">
          {pendingRevokeConsent?.scope === "cloud_index" ? (
            <div className="p-3 rounded-[var(--radius-sm)] border border-[var(--danger)]/50 bg-[rgba(255,107,94,0.08)] text-[var(--danger)] space-y-2">
              <div className="font-semibold flex items-center gap-1.5">
                <span>⚠</span>
                <span>Immediate Data Purge Warning</span>
              </div>
              <p className="text-[11px] leading-relaxed">
                Revoking <strong>cloud_index</strong> consent permanently deletes all stored code
                chunks and vector embeddings for this project. The project will automatically be
                downgraded to <strong>metadata_only</strong> mode.
              </p>
            </div>
          ) : (
            <div className="p-3 rounded-[var(--radius-sm)] border border-[var(--warn)]/50 bg-[rgba(240,180,76,0.08)] text-[var(--warn)] space-y-1">
              <div className="font-semibold flex items-center gap-1.5">
                <span>ℹ</span>
                <span>Transmission Cutoff</span>
              </div>
              <p className="text-[11px] leading-relaxed">
                The VS Code extension and website will cease transmitting any source snippets under
                this authorization scope.
              </p>
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={isRevoking}
              onClick={() => setPendingRevokeConsent(null)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              disabled={isRevoking}
              onClick={handleConfirmRevoke}
            >
              {isRevoking ? "Revoking..." : "Confirm Revocation & Purge"}
            </Button>
          </div>
        </div>
      </Dialog>

      {/* Grant New Consent Modal */}
      <Dialog
        isOpen={isGrantModalOpen}
        onClose={() => {
          if (!isGranting) setIsGrantModalOpen(false);
        }}
        title="Grant Source Transmission Consent"
        description="Authorize specific data categories and AI provider destinations per docs/07 §7."
      >
        <div className="space-y-4 py-2 font-mono text-xs">
          <div className="space-y-1.5">
            <label className="text-[var(--fg-1)] block font-semibold">Consent Scope:</label>
            <select
              value={newScope}
              onChange={(e) =>
                setNewScope(
                  e.target.value as "snippet_transmission" | "cloud_index" | "llm_processing"
                )
              }
              className="w-full h-9 px-3 rounded-[var(--radius-control)] bg-[var(--bg-0)] border border-[var(--line-2)] text-[var(--fg-0)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)]"
            >
              <option value="snippet_transmission">
                snippet_transmission (Chat snippet uploads)
              </option>
              <option value="cloud_index">
                cloud_index (Persistent chunks &amp; pgvector embeddings)
              </option>
              <option value="llm_processing">llm_processing (Inference provider passing)</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-[var(--fg-1)] block font-semibold">
              Authorized Inference Providers:
            </label>
            <div className="space-y-1">
              {DEFAULT_PROVIDERS.map((provider) => (
                <label
                  key={provider}
                  className="flex items-center gap-2 text-[var(--fg-1)] cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedProviders.includes(provider)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedProviders([...selectedProviders, provider]);
                      } else {
                        setSelectedProviders(selectedProviders.filter((p) => p !== provider));
                      }
                    }}
                    className="accent-[var(--signal)]"
                  />
                  <span>{provider}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-[var(--line-1)]">
            <Button
              variant="secondary"
              size="sm"
              disabled={isGranting}
              onClick={() => setIsGrantModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              disabled={isGranting || selectedProviders.length === 0}
              onClick={handleGrantConsent}
            >
              {isGranting ? "Recording Grant..." : "Authorize & Grant Consent"}
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
