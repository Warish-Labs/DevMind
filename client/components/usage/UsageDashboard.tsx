"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Badge, Button } from "@/components/ui";
import { QuotaOverview } from "./QuotaOverview";
import { UsageBreakdownPane } from "./UsageBreakdownPane";
import { ExtensionDevicesPane } from "./ExtensionDevicesPane";
import { AuditLogModal } from "@/components/audit";
import {
  INITIAL_QUOTAS,
  INITIAL_TASK_USAGE,
  INITIAL_PROJECT_USAGE,
  INITIAL_EXTENSION_DEVICES,
  type QuotaItem,
  type TaskUsageBreakdown,
  type ProjectUsageBreakdown,
  type ExtensionDeviceItem,
} from "./types";

interface UsageDashboardProps {
  workspaceId?: string;
  projectId?: string;
  workspaceName?: string;
  initialQuotas?: QuotaItem[];
  initialTasks?: TaskUsageBreakdown[];
  initialProjects?: ProjectUsageBreakdown[];
  initialDevices?: ExtensionDeviceItem[];
}

export function UsageDashboard({
  workspaceId = "ws-devmind-default",
  projectId,
  workspaceName = "Warish Labs Core",
  initialQuotas = INITIAL_QUOTAS,
  initialTasks = INITIAL_TASK_USAGE,
  initialProjects = INITIAL_PROJECT_USAGE,
  initialDevices = INITIAL_EXTENSION_DEVICES,
}: UsageDashboardProps) {
  const [quotas] = useState<QuotaItem[]>(initialQuotas);
  const [tasks] = useState<TaskUsageBreakdown[]>(initialTasks);
  const [projects] = useState<ProjectUsageBreakdown[]>(initialProjects);
  const [devices] = useState<ExtensionDeviceItem[]>(initialDevices);
  const [isAuditModalOpen, setIsAuditModalOpen] = useState(false);

  // Calculate totals
  const totalTokens = tasks.reduce((acc, t) => acc + t.totalTokens, 0);
  const totalJobs = tasks.reduce((acc, t) => acc + t.jobCount, 0);
  const activeDevicesCount = devices.filter((d) => d.status === "active").length;

  return (
    <div className="space-y-8 font-mono text-xs">
      {/* S-12 Header & Breadcrumb Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[var(--line-1)]">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-[var(--fg-2)]">
            <Link
              href={projectId ? `/projects/${projectId}` : "/projects"}
              className="hover:text-[var(--fg-0)] hover:underline"
            >
              {projectId ? "Project" : "Workspace"}
            </Link>
            <span className="text-[var(--line-3)]">/</span>
            <span className="text-[var(--signal)]">S-12 Usage &amp; Quotas</span>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl sm:text-2xl font-bold text-[var(--fg-0)] tracking-tight">
              {workspaceName} Usage Dashboard
            </h1>

            <Badge variant="signal" size="sm">
              Free Profile
            </Badge>
          </div>

          <p className="text-xs text-[var(--fg-2)] max-w-2xl">
            Inference token metering, resource quota limits, and connected developer extension
            devices.
          </p>
        </div>

        {/* Workspace controls & Audit link */}
        <div className="flex items-center gap-3">
          <div className="px-2.5 py-1.5 rounded bg-[var(--bg-1)] border border-[var(--line-1)] text-[11px] text-[var(--fg-1)]">
            Period: <span className="text-[var(--signal)] font-semibold">October 2026</span>
          </div>

          <Button
            variant="secondary"
            size="sm"
            className="font-mono text-xs"
            onClick={() => setIsAuditModalOpen(true)}
          >
            Audit Events &rarr;
          </Button>
        </div>
      </div>

      {/* 1. Quota Overview & Thresholds */}
      <section aria-labelledby="quotas-section-title">
        <h2 id="quotas-section-title" className="sr-only">
          Resource Quotas and Capacity
        </h2>
        <QuotaOverview
          quotas={quotas}
          totalTokens={totalTokens}
          totalJobs={totalJobs}
          activeDevicesCount={activeDevicesCount}
        />
      </section>

      {/* 2. Token Consumption Accounting Pane */}
      <section aria-labelledby="accounting-section-title">
        <h2 id="accounting-section-title" className="sr-only">
          Token Consumption Breakdown
        </h2>
        <UsageBreakdownPane tasks={tasks} projects={projects} totalTokens={totalTokens} />
      </section>

      {/* 3. Authorized VS Code Extension Devices */}
      <section aria-labelledby="devices-section-title">
        <h2 id="devices-section-title" className="sr-only">
          Connected Extension Devices
        </h2>
        <ExtensionDevicesPane devices={devices} />
      </section>

      {/* 4. Audit Log Dialog Modal */}
      <AuditLogModal
        isOpen={isAuditModalOpen}
        onClose={() => setIsAuditModalOpen(false)}
        workspaceId={workspaceId}
        projectId={projectId}
        title={`${workspaceName} Audit Events`}
      />
    </div>
  );
}
