"use client";

import React from "react";
import Link from "next/link";
import type { CitationItem } from "./types";

export interface CitationsPanelProps {
  projectId: string;
  citations: CitationItem[];
  selectedCitationId: string | null;
  onSelectCitation: (id: string) => void;
  onClose: () => void;
  className?: string;
}

export function CitationsPanel({
  projectId,
  citations,
  selectedCitationId,
  onSelectCitation,
  onClose,
  className = "",
}: CitationsPanelProps) {
  if (citations.length === 0) {
    return (
      <aside
        className={`w-full lg:w-80 border-l border-[var(--line-1)] bg-[var(--bg-1)] p-4 flex flex-col items-center justify-center text-center text-xs text-[var(--fg-3)] font-mono ${className}`}
      >
        <p>No citations referenced in selected response.</p>
      </aside>
    );
  }

  return (
    <aside
      className={`w-full lg:w-88 border-l border-[var(--line-1)] bg-[var(--bg-1)] flex flex-col font-mono text-xs ${className}`}
    >
      {/* Panel Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--line-1)] select-none">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-[var(--fg-0)]">
            {`Referenced Citations (${citations.length})`}
          </span>
          <span className="text-[10px] text-[var(--fg-3)]">AST Verified</span>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="text-[var(--fg-3)] hover:text-[var(--fg-0)] p-1 rounded transition-colors"
          aria-label="Close citations panel"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Citations List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {citations.map((cit) => {
          const isSelected = selectedCitationId === cit.id;

          return (
            <div
              key={cit.id}
              onClick={() => onSelectCitation(cit.id)}
              className={`rounded-[var(--radius-md)] border p-3 transition-colors cursor-pointer space-y-2 ${
                isSelected
                  ? "border-[var(--ref)] bg-[var(--bg-0)] shadow-sm ring-1 ring-[var(--ref)]"
                  : "border-[var(--line-1)] bg-[var(--bg-0)] hover:border-[var(--line-strong)]"
              }`}
            >
              {/* Citation Title & Index */}
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5 overflow-hidden text-ellipsis">
                  <span className="px-1.5 py-0.2 rounded-[var(--radius-chip)] bg-[rgba(78,161,255,0.12)] text-[var(--ref)] border border-[rgba(78,161,255,0.3)] text-[10px] font-bold">
                    {`[${cit.index}]`}
                  </span>
                  <span className="font-semibold text-xs text-[var(--fg-0)] truncate">
                    {cit.path}
                  </span>
                </div>

                <span className="text-[11px] text-[var(--fg-3)] shrink-0">
                  {`L${cit.startLine}-L${cit.endLine}`}
                </span>
              </div>

              {/* Symbol / Role Tag */}
              {cit.symbolName && (
                <div className="text-[10px] text-[var(--fg-2)] flex items-center gap-1">
                  <span className="text-[var(--fg-3)]">symbol:</span>
                  <code className="text-[var(--ref)]">{cit.symbolName}</code>
                </div>
              )}

              {/* Code Snippet Box */}
              <pre className="bg-[var(--bg-1)] p-2.5 rounded-[var(--radius-sm)] border border-[var(--line-1)] text-[11px] text-[var(--fg-1)] overflow-x-auto whitespace-pre font-mono leading-relaxed max-h-48">
                {cit.snippet}
              </pre>

              {/* Footer Links */}
              <div className="flex items-center justify-between pt-1 text-[11px]">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    navigator.clipboard?.writeText(`${cit.path}#L${cit.startLine}-L${cit.endLine}`);
                  }}
                  className="text-[var(--fg-3)] hover:text-[var(--fg-0)] transition-colors"
                >
                  Copy reference
                </button>

                <Link
                  href={`/projects/${projectId}/brain?file=${encodeURIComponent(cit.path)}`}
                  className="text-[var(--ref)] hover:underline flex items-center gap-1"
                >
                  <span>Brain Explorer</span>
                  <span>→</span>
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
