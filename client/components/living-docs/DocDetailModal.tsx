"use client";

import React from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CloseIcon } from "@/components/shell/icons";
import type { DocRecordDetailResponse } from "./types";

interface DocDetailModalProps {
  doc: DocRecordDetailResponse | null;
  isOpen: boolean;
  onClose: () => void;
}

export function DocDetailModal({ doc, isOpen, onClose }: DocDetailModalProps) {
  if (!isOpen || !doc) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="doc-detail-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--overlay-bg,rgba(0,0,0,0.75))] backdrop-blur-sm font-mono"
    >
      <div className="relative w-full max-w-2xl max-h-[90vh] bg-[var(--bg-0)] border border-[var(--line-2)] rounded-panel shadow-2xl flex flex-col overflow-hidden text-xs">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--line-1)] bg-[var(--bg-1)]">
          <div className="flex items-center gap-2 overflow-hidden pr-2">
            <h3 id="doc-detail-title" className="text-sm font-bold text-[var(--fg-0)] truncate">
              {doc.title}
            </h3>
            <Badge variant="neutral" className="uppercase text-[10px]">
              {doc.kind}
            </Badge>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            className="text-[var(--fg-2)] hover:text-[var(--fg-0)] p-1 rounded hover:bg-[var(--bg-2)] transition-colors"
          >
            <CloseIcon size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 flex flex-col gap-4 overflow-y-auto">
          {/* Metadata */}
          <div className="bg-[var(--bg-1)] p-3 rounded-control border border-[var(--line-1)] flex flex-col gap-1.5 text-[11px]">
            <div>
              <span className="text-[var(--fg-2)]">File Path: </span>
              <code className="text-[var(--ref)] font-bold">{doc.path}</code>
            </div>
            <div>
              <span className="text-[var(--fg-2)]">SHA-256 Version: </span>
              <code className="text-[var(--signal)] break-all">{doc.current_version_hash}</code>
            </div>
          </div>

          {/* Extracted Symbols */}
          <div className="flex flex-col gap-1.5">
            <span className="text-[11px] font-semibold text-[var(--fg-2)] uppercase tracking-wider">
              Deterministically Extracted Symbols ({doc.extracted_symbols?.length || 0})
            </span>
            {!doc.extracted_symbols || doc.extracted_symbols.length === 0 ? (
              <div className="p-3 bg-[var(--bg-1)] border border-[var(--line-1)] rounded-control text-center text-[var(--fg-2)] text-xs">
                No route patterns or code symbols extracted from this document.
              </div>
            ) : (
              <div className="border border-[var(--line-1)] bg-[var(--bg-1)] rounded-control overflow-hidden max-h-44 overflow-y-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-[var(--line-1)] text-[10px] uppercase text-[var(--fg-2)] bg-[var(--bg-0)]">
                      <th className="py-1.5 px-3">Type</th>
                      <th className="py-1.5 px-3">Identifier / Path</th>
                      <th className="py-1.5 px-3 text-right">Line</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--line-1)]">
                    {doc.extracted_symbols.map((symbolItem: unknown, idx: number) => {
                      const sym = (
                        typeof symbolItem === "object" && symbolItem !== null ? symbolItem : {}
                      ) as Record<string, unknown>;
                      const symType = String(sym.type || sym.kind || "route");
                      const method = sym.method ? String(sym.method) : undefined;
                      const identifier = String(sym.path || sym.name || JSON.stringify(sym));
                      const line = sym.line ? String(sym.line) : "—";
                      return (
                        <tr key={idx} className="hover:bg-[var(--bg-2)]">
                          <td className="py-1.5 px-3 whitespace-nowrap">
                            <span className="text-[10px] text-[var(--ref)] font-bold uppercase">
                              {symType}
                            </span>
                          </td>
                          <td className="py-1.5 px-3 font-mono truncate max-w-xs">
                            {method && (
                              <span className="text-[var(--signal)] font-bold mr-1">{method}</span>
                            )}
                            <span className="text-[var(--fg-0)]">{identifier}</span>
                          </td>
                          <td className="py-1.5 px-3 text-right font-mono text-[var(--fg-2)] text-[11px]">
                            {line}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Snapshot Content */}
          {doc.content_snapshot && (
            <div className="flex flex-col gap-1.5">
              <span className="text-[11px] font-semibold text-[var(--fg-2)] uppercase tracking-wider">
                Cached Content Snapshot
              </span>
              <pre className="p-3 bg-[var(--bg-1)] border border-[var(--line-1)] rounded-control text-[11px] text-[var(--fg-0)] overflow-x-auto whitespace-pre-wrap max-h-56">
                {doc.content_snapshot}
              </pre>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-[var(--line-1)] bg-[var(--bg-1)] flex items-center justify-end">
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}
