"use client";

import React, { useState } from "react";
import Link from "next/link";
import type { BrainRelationshipItem } from "./types";
import type { FindingItem } from "@devmind/common/api";

export interface RelationshipsPaneProps {
  projectId: string;
  relationships: BrainRelationshipItem[];
  findings: FindingItem[];
  selectedSymbolName?: string;
  onExpandGraph?: () => void;
  className?: string;
}

export function RelationshipsPane({
  projectId,
  relationships,
  findings,
  selectedSymbolName,
  onExpandGraph,
  className = "",
}: RelationshipsPaneProps) {
  const [activeTab, setActiveTab] = useState<"relationships" | "findings">("relationships");

  return (
    <aside
      className={`border-l border-[var(--line-1)] bg-[var(--bg-1)] flex flex-col h-full font-mono text-xs ${className}`}
    >
      {/* Pane Tabs Header */}
      <div className="flex border-b border-[var(--line-1)] bg-[var(--bg-1)] select-none">
        <button
          type="button"
          onClick={() => setActiveTab("relationships")}
          className={`flex-1 py-2.5 px-3 text-center border-b-2 font-semibold transition-colors flex items-center justify-center gap-1.5 ${
            activeTab === "relationships"
              ? "border-[var(--ref)] text-[var(--fg-0)] bg-[var(--bg-0)]"
              : "border-transparent text-[var(--fg-3)] hover:text-[var(--fg-1)]"
          }`}
        >
          <span>Relationships</span>
          <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-[var(--bg-2)] text-[var(--fg-2)]">
            {relationships.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("findings")}
          className={`flex-1 py-2.5 px-3 text-center border-b-2 font-semibold transition-colors flex items-center justify-center gap-1.5 ${
            activeTab === "findings"
              ? "border-[var(--ref)] text-[var(--fg-0)] bg-[var(--bg-0)]"
              : "border-transparent text-[var(--fg-3)] hover:text-[var(--fg-1)]"
          }`}
        >
          <span>Findings</span>
          <span
            className={`text-[10px] px-1.5 py-0.2 rounded-full ${
              findings.length > 0
                ? "bg-[rgba(235,90,90,0.15)] text-[var(--danger)] font-bold"
                : "bg-[var(--bg-2)] text-[var(--fg-2)]"
            }`}
          >
            {findings.length}
          </span>
        </button>
      </div>

      {/* Pane Body */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {activeTab === "relationships" ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-[11px] text-[var(--fg-3)]">
              <span>
                {selectedSymbolName ? `Edges for: ${selectedSymbolName}` : "File Dependency Graph"}
              </span>

              {onExpandGraph && (
                <button
                  type="button"
                  onClick={onExpandGraph}
                  className="text-[var(--ref)] hover:underline flex items-center gap-0.5"
                >
                  <span>Expand Graph</span>
                  <span>↗</span>
                </button>
              )}
            </div>

            {relationships.length === 0 ? (
              <div className="p-6 text-center text-xs text-[var(--fg-3)] bg-[var(--bg-0)] rounded-[var(--radius-md)] border border-[var(--line-1)]">
                No relationship edges discovered for this selection.
              </div>
            ) : (
              <div className="space-y-2">
                {relationships.map((rel) => (
                  <div
                    key={rel.id}
                    className="p-2.5 rounded-[var(--radius-md)] border border-[var(--line-1)] bg-[var(--bg-0)] hover:border-[var(--line-strong)] transition-colors space-y-1.5"
                  >
                    <div className="flex items-center justify-between text-[10px]">
                      <span className="px-1.5 py-0.2 rounded bg-[var(--bg-2)] text-[var(--fg-2)] uppercase font-semibold">
                        {rel.kind}
                      </span>
                      <span className="text-[var(--fg-3)]">
                        {rel.direction === "outgoing" ? "outgoing →" : "← incoming"}
                      </span>
                    </div>

                    <div className="text-xs font-semibold text-[var(--fg-0)] truncate">
                      {rel.direction === "outgoing" ? rel.targetSymbol : rel.sourceSymbol}
                    </div>

                    {rel.targetPath && (
                      <div className="text-[10px] text-[var(--fg-3)] truncate">
                        {rel.targetPath}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            <div className="text-[11px] text-[var(--fg-3)]">
              Security Findings Attached to Selection
            </div>

            {findings.length === 0 ? (
              <div className="p-6 text-center text-xs text-[var(--fg-3)] bg-[var(--bg-0)] rounded-[var(--radius-md)] border border-[var(--line-1)]">
                No security findings associated with this file.
              </div>
            ) : (
              <div className="space-y-2">
                {findings.map((f) => (
                  <div
                    key={f.id}
                    className="p-3 rounded-[var(--radius-md)] border border-[var(--line-1)] bg-[var(--bg-0)] hover:border-[var(--line-strong)] transition-colors space-y-2"
                  >
                    <div className="flex items-center justify-between gap-1.5">
                      <span
                        className={`text-[9px] px-1.5 py-0.2 rounded font-bold uppercase ${
                          f.severity === "critical"
                            ? "bg-[rgba(235,90,90,0.15)] text-[var(--danger)]"
                            : "bg-[rgba(240,180,76,0.15)] text-[var(--warn)]"
                        }`}
                      >
                        {f.severity}
                      </span>

                      <span className="text-[9px] px-1.5 py-0.2 rounded bg-[var(--bg-2)] text-[var(--fg-2)] font-mono">
                        {f.evidence_level}
                      </span>
                    </div>

                    <div className="text-xs font-semibold text-[var(--fg-0)] leading-snug">
                      {f.title}
                    </div>

                    <div className="flex items-center justify-between text-[11px] pt-1 border-t border-[var(--line-1)]">
                      <span className="text-[10px] text-[var(--fg-3)] font-mono">{f.rule_id}</span>

                      <Link
                        href={`/projects/${projectId}/findings/${f.id}`}
                        className="text-[var(--ref)] hover:underline flex items-center gap-1"
                      >
                        <span>View finding</span>
                        <span>→</span>
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
