"use client";

import React from "react";
import { Card, CardHeader, CardTitle, CardContent, Badge } from "@/components/ui";
import type { QuotaItem } from "./types";

interface QuotaOverviewProps {
  quotas: QuotaItem[];
  totalTokens: number;
  totalJobs: number;
  activeDevicesCount: number;
}

export function QuotaOverview({
  quotas,
  totalTokens,
  totalJobs,
  activeDevicesCount,
}: QuotaOverviewProps) {
  const formatNumber = (num: number) => num.toLocaleString("en-US");

  return (
    <div className="space-y-6">
      {/* Stat Cards Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card variant="default">
          <CardHeader className="pb-1">
            <span className="text-[10px] uppercase tracking-wider text-[var(--fg-2)] font-mono">
              Inference Metering
            </span>
            <CardTitle className="text-xl font-bold font-mono text-[var(--fg-0)]">
              {formatNumber(totalTokens)}
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <p className="text-[11px] text-[var(--fg-2)] font-mono">Tokens recorded this period</p>
          </CardContent>
        </Card>

        <Card variant="default">
          <CardHeader className="pb-1">
            <span className="text-[10px] uppercase tracking-wider text-[var(--fg-2)] font-mono">
              Analysis Workflows
            </span>
            <CardTitle className="text-xl font-bold font-mono text-[var(--fg-0)]">
              {totalJobs} Jobs
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <p className="text-[11px] text-[var(--fg-2)] font-mono">AST &amp; security runs</p>
          </CardContent>
        </Card>

        <Card variant="default">
          <CardHeader className="pb-1">
            <span className="text-[10px] uppercase tracking-wider text-[var(--fg-2)] font-mono">
              Extension Devices
            </span>
            <CardTitle className="text-xl font-bold font-mono text-[var(--fg-0)]">
              {activeDevicesCount} Connected
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <p className="text-[11px] text-[var(--fg-2)] font-mono">VS Code companion tokens</p>
          </CardContent>
        </Card>

        <Card variant="default" className="border-[var(--line-2)]">
          <CardHeader className="pb-1 flex flex-row items-center justify-between space-y-0">
            <span className="text-[10px] uppercase tracking-wider text-[var(--signal)] font-mono">
              Deployment Profile
            </span>
            <Badge variant="signal" size="sm">
              ADR-046
            </Badge>
          </CardHeader>
          <CardContent className="pt-2">
            <div className="text-sm font-semibold text-[var(--fg-0)] font-mono">
              Free Operational Tier
            </div>
            <p className="text-[11px] text-[var(--fg-2)] font-mono mt-0.5">
              Render · Neon · Upstash
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Quota Progress Bars */}
      <Card variant="elevated">
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <CardTitle className="text-base font-semibold">Workspace Quota Limits</CardTitle>
              <p className="text-xs text-[var(--fg-2)] mt-0.5">
                Resource enforcement under the active tenant policy. Reaching 100% pauses
                non-essential background jobs.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block w-2 h-2 rounded-full bg-[var(--signal)]" />
              <span className="text-[10px] text-[var(--fg-2)] font-mono">
                Real-time Quota Engine
              </span>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {quotas.map((quota) => {
              const isWarning = quota.percent >= 80 && quota.percent < 95;
              const isDanger = quota.percent >= 95;
              const barColor = isDanger
                ? "bg-red-400"
                : isWarning
                  ? "bg-amber-400"
                  : "bg-[var(--signal)]";

              const badgeVariant = isDanger ? "danger" : isWarning ? "warn" : "signal";

              return (
                <div
                  key={quota.resource}
                  className="p-4 rounded-md bg-[var(--bg-1)] border border-[var(--line-1)] space-y-3"
                  data-testid={`quota-card-${quota.resource.replace(/\s+/g, "-").toLowerCase()}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-medium text-[var(--fg-0)] font-mono">
                      {quota.resource}
                    </span>
                    <Badge variant={badgeVariant} size="sm">
                      {quota.percent.toFixed(1)}%
                    </Badge>
                  </div>

                  {/* Progress bar container */}
                  <div
                    className="w-full h-2 rounded-full bg-[var(--bg-2)] overflow-hidden"
                    role="progressbar"
                    aria-valuenow={quota.used}
                    aria-valuemin={0}
                    aria-valuemax={quota.limit}
                    aria-label={quota.resource}
                  >
                    <div
                      className={`h-full transition-all duration-300 rounded-full ${barColor}`}
                      style={{ width: `${Math.min(quota.percent, 100)}%` }}
                    />
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-[var(--fg-2)] font-mono">
                    <span>
                      {formatNumber(quota.used)} {quota.unit} used
                    </span>
                    <span>
                      Cap: {formatNumber(quota.limit)} {quota.unit}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
