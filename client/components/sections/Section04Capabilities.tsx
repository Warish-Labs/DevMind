"use client";

import React, { useState } from "react";
import { capabilitiesData, releaseStatusData } from "../../lib/sections-data";

export function Section04Capabilities() {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Map release status from releaseStatusData to ensure single source of truth
  const releaseStatusMap = new Map(
    releaseStatusData.capabilities.map((c) => [c.id, { release: c.release, status: c.status }])
  );

  return (
    <section id="section-04" className="scroll-mt-24 flex flex-col gap-8">
      {/* Section Header */}
      <div>
        <div className="inline-flex items-center gap-2 px-3 py-1 mb-4 rounded-chip bg-[var(--bg-1)] border border-[var(--line-1)] text-xs text-[var(--warn)] font-mono">
          <span>SECTION 04 · CAPABILITY INDEX</span>
        </div>
        <h2 className="text-3xl sm:text-4xl lg:text-5xl font-display text-[var(--fg-0)] mb-4 tracking-tight">
          Nine Capabilities. One Concrete Question Each.
        </h2>
        <p className="max-w-2xl text-base text-[var(--fg-1)] leading-relaxed">
          DevMind maps every feature directly to a question an engineer asks daily. We disclose
          release statuses honestly—unshipped capabilities are clearly marked.
        </p>
      </div>

      {/* Capabilities Index Table */}
      <div className="rounded-panel border border-[var(--line-1)] bg-[var(--bg-1)] overflow-hidden shadow-xl">
        <div
          tabIndex={0}
          role="region"
          aria-label="Capabilities matrix"
          className="overflow-x-auto focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--ref)]"
        >
          <table className="w-full text-left font-mono text-xs border-collapse">
            <thead>
              <tr className="border-b border-[var(--line-2)] bg-[var(--bg-2)]/60 text-[var(--fg-1)] select-none">
                <th className="py-3 px-4 w-20">ID</th>
                <th className="py-3 px-4 font-medium text-[var(--fg-0)]">Question You Ask</th>
                <th className="py-3 px-4 hidden md:table-cell">Capability</th>
                <th className="py-3 px-4 w-28 text-center">Release</th>
                <th className="py-3 px-4 w-16 text-center">Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--line-1)]">
              {capabilitiesData.map((item) => {
                const isExpanded = expandedId === item.id;
                const statusMeta = releaseStatusMap.get(item.id);
                const releaseBadge = statusMeta ? statusMeta.release.toUpperCase() : item.release;
                const isMvp = releaseBadge.toLowerCase() === "mvp";

                return (
                  <React.Fragment key={item.id}>
                    <tr
                      onClick={() => setExpandedId(isExpanded ? null : item.id)}
                      className={`cursor-pointer transition-colors ${
                        isExpanded ? "bg-[var(--bg-2)]/80" : "hover:bg-[var(--bg-2)]/40"
                      }`}
                    >
                      {/* ID */}
                      <td className="py-3.5 px-4 text-[var(--fg-2)] font-semibold">{item.id}</td>

                      {/* Question */}
                      <td className="py-3.5 px-4 font-sans text-sm text-[var(--fg-0)] font-medium">
                        {item.question}
                      </td>

                      {/* Capability Name */}
                      <td className="py-3.5 px-4 hidden md:table-cell text-[var(--fg-1)]">
                        {item.capability}
                      </td>

                      {/* Release Status Badge */}
                      <td className="py-3.5 px-4 text-center">
                        <span
                          className={`inline-block px-2 py-0.5 rounded-chip text-[10px] font-bold uppercase tracking-wider ${
                            isMvp
                              ? "bg-[var(--signal)]/15 text-[var(--signal)] border border-[var(--signal)]/30"
                              : "bg-[var(--line-1)] text-[var(--fg-1)] border border-[var(--line-2)]"
                          }`}
                        >
                          {releaseBadge}
                        </span>
                      </td>

                      {/* Expand Toggle */}
                      <td className="py-3.5 px-4 text-center text-[var(--ref)] font-semibold select-none">
                        {isExpanded ? "−" : "+"}
                      </td>
                    </tr>

                    {/* Expanded Detail Row */}
                    {isExpanded && (
                      <tr className="bg-[var(--bg-0)]/70">
                        <td colSpan={5} className="p-4 border-t border-[var(--line-1)] font-sans">
                          <div className="flex flex-col sm:flex-row items-start justify-between gap-4">
                            <div className="max-w-xl">
                              <div className="text-xs font-mono text-[var(--ref)] font-semibold uppercase tracking-wider mb-1">
                                {item.capability} · Scope
                              </div>
                              <p className="text-sm text-[var(--fg-1)] leading-relaxed mb-3">
                                {item.summary}
                              </p>
                              <div className="flex items-center gap-2 text-xs font-mono text-[var(--fg-2)]">
                                <span>Status in release catalog:</span>
                                <span className="font-semibold text-[var(--fg-0)]">
                                  {statusMeta?.status || "planned"}
                                </span>
                              </div>
                            </div>

                            {/* Realistic Example Output */}
                            <div className="w-full sm:w-80 shrink-0 p-3 rounded-control bg-[var(--bg-1)] border border-[var(--line-2)] font-mono text-xs">
                              <div className="flex items-center justify-between pb-1.5 mb-2 border-b border-[var(--line-1)] text-[10px] text-[var(--fg-2)] select-none">
                                <span>ARTIFACT PREVIEW</span>
                                <span className="text-[var(--warn)] uppercase font-semibold">
                                  example
                                </span>
                              </div>
                              <pre className="text-[11px] text-[var(--signal)] leading-tight whitespace-pre select-text">
                                {item.id === "CAP-01" &&
                                  '{\n  "symbol": "Router.get",\n  "callers": 4,\n  "tier": "Tier-1 AST"\n}'}
                                {item.id === "CAP-02" &&
                                  '{\n  "finding": "authz.missing_role",\n  "evidence": "E1",\n  "verifiable": true\n}'}
                                {item.id === "CAP-03" &&
                                  '{\n  "bugCluster": "auth_leak_403",\n  "priorFix": "PR #42",\n  "similarity": 0.91\n}'}
                                {item.id === "CAP-04" &&
                                  '{\n  "drift": "missing_openapi_spec",\n  "route": "/admin/users",\n  "status": "stale"\n}'}
                                {item.id === "CAP-05" &&
                                  '{\n  "checklist": ["auth", "input_val"],\n  "verdict": "blocked_no_tests"\n}'}
                                {item.id === "CAP-06" &&
                                  '{\n  "impactedModules": 3,\n  "blastRadius": "high",\n  "crossTenantRisk": "none"\n}'}
                                {item.id === "CAP-07" &&
                                  '{\n  "stackLine": "admin.ts:7",\n  "astNode": "router.get",\n  "confidence": 0.88\n}'}
                                {item.id === "CAP-08" &&
                                  '{\n  "nextTask": "add_role_guard",\n  "blocksRelease": true,\n  "rank": 1\n}'}
                                {item.id === "CAP-09" &&
                                  '{\n  "securityScore": "82/100",\n  "tier1Coverage": "94%",\n  "verdict": "ready"\n}'}
                              </pre>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
