"use client";

import React, { useEffect, useState } from "react";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/Card";
import { Dialog } from "@/components/ui/Dialog";
import { Skeleton } from "@/components/ui/Skeleton";
import type {
  EffectiveRetentionCategory,
  EffectiveRetentionSummary,
  RetentionSweepReport,
} from "@devmind/common";

interface RetentionPolicyManagerProps {
  projectId: string;
}

export function RetentionPolicyManager({ projectId }: RetentionPolicyManagerProps) {
  const [summary, setSummary] = useState<EffectiveRetentionSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [editingCategory, setEditingCategory] = useState<EffectiveRetentionCategory | null>(null);
  const [editDays, setEditDays] = useState<number>(30);
  const [isSaving, setIsSaving] = useState(false);
  const [isSweeping, setIsSweeping] = useState(false);
  const [sweepReport, setSweepReport] = useState<RetentionSweepReport | null>(null);
  const [notice, setNotice] = useState<{ type: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    let isMounted = true;
    apiClient
      .getProjectRetention(projectId)
      .then((res) => {
        if (isMounted) {
          setSummary(res);
          setIsLoading(false);
        }
      })
      .catch(() => {
        if (isMounted) {
          setNotice({
            type: "error",
            message: "Failed to load retention settings from server.",
          });
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [projectId]);

  const reloadRetention = async () => {
    try {
      setIsLoading(true);
      const res = await apiClient.getProjectRetention(projectId);
      setSummary(res);
    } catch {
      setNotice({
        type: "error",
        message: "Failed to load retention settings from server.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleOpenEdit = (category: EffectiveRetentionCategory) => {
    setEditingCategory(category);
    setEditDays(category.days);
  };

  const handleSaveEdit = async () => {
    if (!editingCategory) return;
    try {
      setIsSaving(true);
      await apiClient.updateProjectRetention(projectId, editingCategory.kind, { days: editDays });
      setNotice({
        type: "success",
        message: `Updated retention window for ${editingCategory.kind} to ${editDays} days.`,
      });
      setEditingCategory(null);
      await reloadRetention();
    } catch (err: unknown) {
      const apiErr = err as { detail?: string; message?: string };
      setNotice({
        type: "error",
        message: apiErr?.detail || apiErr?.message || "Failed to update retention window.",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleResetOverride = async (category: EffectiveRetentionCategory) => {
    try {
      setIsSaving(true);
      await apiClient.resetProjectRetention(projectId, category.kind);
      setNotice({
        type: "success",
        message: `Reset ${category.kind} retention override back to default.`,
      });
      await reloadRetention();
    } catch (err: unknown) {
      const apiErr = err as { detail?: string; message?: string };
      setNotice({
        type: "error",
        message: apiErr?.detail || apiErr?.message || "Failed to reset retention override.",
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleTriggerSweep = async () => {
    try {
      setIsSweeping(true);
      setSweepReport(null);
      const report = await apiClient.triggerProjectRetentionSweep(projectId);
      setSweepReport(report);
      const totalPurged = Object.values(report.purged_counts || {}).reduce((a, b) => a + b, 0);
      setNotice({
        type: "success",
        message: `Retention sweep finished. ${totalPurged} expired records purged.`,
      });
    } catch (err: unknown) {
      const apiErr = err as { detail?: string; message?: string };
      setNotice({
        type: "error",
        message: apiErr?.detail || apiErr?.message || "Failed to execute retention cleanup sweep.",
      });
    } finally {
      setIsSweeping(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-28 w-full" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Skeleton className="h-36 w-full" />
          <Skeleton className="h-36 w-full" />
          <Skeleton className="h-36 w-full" />
          <Skeleton className="h-36 w-full" />
        </div>
      </div>
    );
  }

  const categories = summary?.categories || [];

  return (
    <div className="space-y-6">
      {/* Notice Alert */}
      {notice && (
        <div
          role="status"
          className={`p-3 rounded-[var(--radius-control)] border text-xs flex items-center justify-between font-mono ${
            notice.type === "success"
              ? "bg-[var(--signal)]/10 border-[var(--signal)]/30 text-[var(--signal)]"
              : "bg-[var(--danger)]/10 border-[var(--danger)]/30 text-[var(--danger)]"
          }`}
        >
          <span>{notice.message}</span>
          <button
            type="button"
            onClick={() => setNotice(null)}
            className="text-[var(--fg-2)] hover:text-[var(--fg-0)] ml-4"
          >
            ✕
          </button>
        </div>
      )}

      {/* Header Banner & Manual Sweep Action */}
      <Card className="border-[var(--line-1)] bg-[var(--bg-1)]/40">
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <CardTitle className="text-sm font-semibold text-[var(--fg-0)]">
                  Configured Retention Windows (ADR-026)
                </CardTitle>
                <Badge variant="neutral" size="sm" mono>
                  Interim Defaults
                </Badge>
              </div>
              <CardDescription className="text-xs text-[var(--fg-2)] mt-1 max-w-2xl">
                Automated scheduler cleanup sweeps execute periodically to purge transient analysis
                records, non-current file snapshots, and expired checkpoints per docs/03 §3.1 and
                docs/07 §9.
              </CardDescription>
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={handleTriggerSweep}
              disabled={isSweeping}
              className="border-[var(--line-2)] hover:border-[var(--signal)] hover:text-[var(--signal)] shrink-0"
            >
              {isSweeping ? "Sweeping Expired Records..." : "Run Retention Sweep Now"}
            </Button>
          </div>
        </CardHeader>
      </Card>

      {/* Sweep Result Banner */}
      {sweepReport && (
        <Card className="border-[var(--signal)]/40 bg-[var(--signal)]/5 font-mono text-xs">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-[var(--signal)]">Retention Sweep Report</span>
              <span className="text-[11px] text-[var(--fg-2)]">
                Swept at: {new Date(sweepReport.swept_at).toLocaleTimeString()}
              </span>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 text-[11px]">
              {Object.entries(sweepReport.purged_counts || {}).map(([kind, count]) => (
                <div
                  key={kind}
                  className="p-2 rounded border border-[var(--line-1)] bg-[var(--bg-0)]"
                >
                  <span className="text-[var(--fg-2)] block capitalize">
                    {kind.replace(/_/g, " ")}
                  </span>
                  <span className="text-sm font-bold text-[var(--fg-0)]">{count} purged</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Category Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {categories.map((cat) => (
          <Card
            key={cat.kind}
            className="border-[var(--line-1)] bg-[var(--bg-1)]/30 hover:border-[var(--line-2)] transition-colors flex flex-col justify-between"
          >
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <span className="text-[10px] font-mono uppercase text-[var(--fg-2)]">
                    {cat.kind}
                  </span>
                  <CardTitle className="text-sm font-semibold text-[var(--fg-0)] capitalize">
                    {cat.kind.replace(/_/g, " ")}
                  </CardTitle>
                </div>
                {cat.source === "project_override" ? (
                  <Badge variant="ref" size="sm" mono>
                    Project Override
                  </Badge>
                ) : cat.source === "workspace_policy" ? (
                  <Badge variant="neutral" size="sm" mono>
                    Workspace Setting
                  </Badge>
                ) : (
                  <Badge variant="neutral" size="sm" mono>
                    ADR-026 Default
                  </Badge>
                )}
              </div>
              <CardDescription className="text-xs text-[var(--fg-2)] mt-1">
                {cat.description}
              </CardDescription>
            </CardHeader>

            <CardContent className="pt-0">
              <div className="flex items-center justify-between border-t border-[var(--line-1)] pt-3 mt-1 font-mono text-xs">
                <div>
                  <span className="text-base font-bold text-[var(--fg-0)]">{cat.days}</span>
                  <span className="text-xs text-[var(--fg-2)] ml-1">Days</span>
                  {cat.days !== cat.default_days && (
                    <span className="text-[10px] text-[var(--fg-2)] block">
                      (Default: {cat.default_days}d)
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  {cat.source === "project_override" && (
                    <Button
                      variant="tertiary"
                      size="sm"
                      onClick={() => handleResetOverride(cat)}
                      disabled={isSaving}
                      className="text-[11px] text-[var(--fg-2)] hover:text-[var(--danger)]"
                    >
                      Reset
                    </Button>
                  )}
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => handleOpenEdit(cat)}
                    disabled={isSaving}
                    className="text-xs"
                  >
                    Configure
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Provider Backup Retention Disclosure */}
      <div className="p-3.5 rounded-[var(--radius-control)] border border-[var(--line-1)] bg-[var(--bg-1)]/20 text-xs font-mono text-[var(--fg-2)] leading-relaxed">
        <span className="font-semibold text-[var(--fg-1)] block mb-1">
          Provider Backup Disclosure (ADR-026 &amp; docs/03 §8)
        </span>
        {summary?.backup_retention_notice ||
          "Provider automated backups retain deleted data until backup expiration per ADR-026 and docs/03 §8. Backups are immutable and expire naturally according to platform backup cycle."}
      </div>

      {/* Edit Retention Window Dialog */}
      {editingCategory && (
        <Dialog
          isOpen={!!editingCategory}
          onClose={() => setEditingCategory(null)}
          title={`Configure Retention: ${editingCategory.kind.replace(/_/g, " ")}`}
          description={editingCategory.description}
          footer={
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-[var(--line-1)] w-full">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setEditingCategory(null)}
                disabled={isSaving}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleSaveEdit}
                disabled={isSaving || editDays < 1}
              >
                {isSaving ? "Saving..." : "Save Window"}
              </Button>
            </div>
          }
        >
          <div className="space-y-4 font-mono text-xs py-2">
            <div>
              <label
                htmlFor="retention-days-input"
                className="block text-[var(--fg-1)] font-medium mb-1.5"
              >
                Retention Window (Days)
              </label>
              <input
                id="retention-days-input"
                type="number"
                min="1"
                max="3650"
                value={editDays}
                onChange={(e) => setEditDays(Math.max(1, parseInt(e.target.value, 10) || 1))}
                className="w-full bg-[var(--bg-0)] border border-[var(--line-2)] rounded-[var(--radius-control)] px-3 py-2 text-[var(--fg-0)] focus:outline-none focus:ring-1 focus:ring-[var(--ref)]"
              />
              <span className="text-[11px] text-[var(--fg-2)] mt-1 block">
                Default for this category is {editingCategory.default_days} days. Setting a project
                override takes precedence over workspace defaults.
              </span>
            </div>
          </div>
        </Dialog>
      )}
    </div>
  );
}
