"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useApp } from "@/context/AppContext";
import { SyncModeManager } from "./SyncModeManager";
import { ConsentManager } from "./ConsentManager";
import { ProjectPurgeManager } from "./ProjectPurgeManager";
import { RetentionPolicyManager } from "./RetentionPolicyManager";
import { AuditLogViewer } from "@/components/audit";
import { Badge } from "@/components/ui/Badge";

interface ProjectSettingsClientProps {
  projectId: string;
}

export function ProjectSettingsClient({ projectId }: ProjectSettingsClientProps) {
  const { currentProject } = useApp();
  const [activeTab, setActiveTab] = useState<
    "sync" | "consents" | "retention" | "audit" | "danger"
  >("sync");

  const projectName = currentProject?.name || "Codebase Project";
  const projectSlug = currentProject?.slug || projectId;

  return (
    <div className="space-y-6">
      {/* Top Header & Breadcrumbs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--line-1)] pb-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-[var(--fg-2)] mb-1">
            <Link href="/projects" className="hover:text-[var(--fg-0)]">
              Projects
            </Link>
            <span>/</span>
            <Link href={`/projects/${projectId}`} className="hover:text-[var(--fg-0)]">
              {projectSlug}
            </Link>
            <span>/</span>
            <span className="text-[var(--fg-0)]">Settings (S-10)</span>
          </div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold text-[var(--fg-0)] tracking-tight">
              Project Settings &amp; Privacy Controls
            </h1>
            <Badge variant="neutral" size="sm" mono>
              S-10
            </Badge>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href={`/projects/${projectId}`}
            className="inline-flex items-center justify-center font-sans rounded-[var(--radius-control)] h-9 px-3 text-[13px] border border-[var(--line-2)] hover:bg-[var(--bg-1)] text-[var(--fg-1)] hover:text-[var(--fg-0)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)]"
          >
            ← Return to Overview
          </Link>
        </div>
      </div>

      {/* Settings Navigation Tabs */}
      <div
        role="tablist"
        aria-label="Project Settings Sections"
        className="flex items-center gap-1 border-b border-[var(--line-1)] pb-px font-mono text-xs select-none"
      >
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "sync"}
          onClick={() => setActiveTab("sync")}
          className={`px-4 py-2 border-b-2 font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)] ${
            activeTab === "sync"
              ? "border-[var(--signal)] text-[var(--fg-0)]"
              : "border-transparent text-[var(--fg-2)] hover:text-[var(--fg-1)]"
          }`}
        >
          Sync Modes &amp; Privacy (ADR-022)
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "consents"}
          onClick={() => setActiveTab("consents")}
          className={`px-4 py-2 border-b-2 font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)] ${
            activeTab === "consents"
              ? "border-[var(--signal)] text-[var(--fg-0)]"
              : "border-transparent text-[var(--fg-2)] hover:text-[var(--fg-1)]"
          }`}
        >
          Consent Records (docs/07 §7)
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "retention"}
          onClick={() => setActiveTab("retention")}
          className={`px-4 py-2 border-b-2 font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)] ${
            activeTab === "retention"
              ? "border-[var(--signal)] text-[var(--fg-0)]"
              : "border-transparent text-[var(--fg-2)] hover:text-[var(--fg-1)]"
          }`}
        >
          Retention Windows (ADR-026)
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "audit"}
          onClick={() => setActiveTab("audit")}
          className={`px-4 py-2 border-b-2 font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)] ${
            activeTab === "audit"
              ? "border-[var(--signal)] text-[var(--fg-0)]"
              : "border-transparent text-[var(--fg-2)] hover:text-[var(--fg-1)]"
          }`}
        >
          Audit Trail (docs/07 §16)
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "danger"}
          onClick={() => setActiveTab("danger")}
          className={`px-4 py-2 border-b-2 font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)] ${
            activeTab === "danger"
              ? "border-[var(--danger)] text-[var(--danger)]"
              : "border-transparent text-[var(--fg-2)] hover:text-[var(--fg-1)]"
          }`}
        >
          Danger Zone &amp; Deletion
        </button>
      </div>

      {/* Tab Panels */}
      {activeTab === "sync" && (
        <section aria-labelledby="sync-mode-heading" className="space-y-4">
          <div>
            <h2 id="sync-mode-heading" className="text-lg font-semibold text-[var(--fg-0)]">
              Synchronization Mode &amp; Cloud Storage Boundary
            </h2>
            <p className="text-xs text-[var(--fg-2)] mt-0.5 max-w-2xl leading-relaxed">
              Configure how DevMind stores and indexes your codebase. Switching modes enforces
              immediate verifiable purge consequences per ADR-022 and the DevMind Privacy Ledger.
            </p>
          </div>

          <SyncModeManager projectId={projectId} />
        </section>
      )}

      {activeTab === "consents" && (
        <section aria-labelledby="consents-heading" className="space-y-4">
          <ConsentManager projectId={projectId} />
        </section>
      )}

      {activeTab === "retention" && (
        <section aria-labelledby="retention-heading" className="space-y-6">
          <div>
            <h2 id="retention-heading" className="text-lg font-semibold text-[var(--fg-0)]">
              Data Retention Windows &amp; Expiration (ADR-026)
            </h2>
            <p className="text-xs text-[var(--fg-2)] mt-0.5 max-w-2xl leading-relaxed">
              Automated cleanup schedules for transient analysis logs, snapshot versions, and vector
              embeddings per docs/03 §3.1 and docs/07 §9.
            </p>
          </div>

          <RetentionPolicyManager projectId={projectId} />
        </section>
      )}

      {activeTab === "audit" && (
        <section aria-labelledby="audit-heading" className="space-y-6">
          <div>
            <h2 id="audit-heading" className="text-lg font-semibold text-[var(--fg-0)]">
              Project Audit Trail &amp; Governance Events
            </h2>
            <p className="text-xs text-[var(--fg-2)] mt-0.5 max-w-2xl leading-relaxed">
              Immutable security record of data purge requests, consent grants/revocations, and sync
              mode transitions.
            </p>
          </div>

          <AuditLogViewer projectId={projectId} showHeader={false} />
        </section>
      )}

      {activeTab === "danger" && (
        <section aria-labelledby="danger-heading" className="space-y-6">
          <div>
            <h2 id="danger-heading" className="text-lg font-semibold text-[var(--danger)]">
              Danger Zone &amp; Cloud Data Purge
            </h2>
            <p className="text-xs text-[var(--fg-2)] mt-0.5 max-w-2xl leading-relaxed">
              Irreversible actions for project {projectName}. Be cautious when initiating full data
              purges across cloud stores.
            </p>
          </div>

          <ProjectPurgeManager projectId={projectId} />
        </section>
      )}
    </div>
  );
}
