"use client";

import React, { useState } from "react";
import Link from "next/link";
import type { BrainFileContent, BrainSymbolDetail, ProjectBrainMode } from "./types";
import { Button } from "../ui/Button";

export interface CodeSymbolPaneProps {
  projectId: string;
  fileContent: BrainFileContent | null;
  projectMode: ProjectBrainMode;
  selectedSymbolId: string | null;
  onSelectSymbol: (symbol: BrainSymbolDetail) => void;
  className?: string;
}

export function CodeSymbolPane({
  projectId,
  fileContent,
  projectMode,
  selectedSymbolId,
  onSelectSymbol,
  className = "",
}: CodeSymbolPaneProps) {
  const [copied, setCopied] = useState<boolean>(false);

  if (!fileContent) {
    return (
      <main
        className={`flex-1 flex flex-col items-center justify-center p-8 text-center text-xs font-mono text-[var(--fg-3)] bg-[var(--bg-0)] ${className}`}
      >
        <p>Select a file from the repository tree to inspect symbols and code.</p>
      </main>
    );
  }

  const handleCopyPath = async () => {
    try {
      await navigator.clipboard.writeText(fileContent.path);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard fallback
    }
  };

  const lines = fileContent.content.split("\n");

  return (
    <main className={`flex-1 flex flex-col h-full bg-[var(--bg-0)] overflow-hidden ${className}`}>
      {/* File Header Bar */}
      <div className="px-6 py-3 border-b border-[var(--line-1)] bg-[var(--bg-1)] flex flex-wrap items-center justify-between gap-3 shrink-0 font-mono text-xs">
        <div className="flex items-center gap-2 overflow-hidden text-ellipsis">
          <span className="font-semibold text-[var(--fg-0)] truncate">{fileContent.path}</span>
          <span className="text-[10px] px-1.5 py-0.2 rounded bg-[var(--bg-2)] text-[var(--fg-2)] border border-[var(--line-1)]">
            {fileContent.languageTier.toUpperCase()}
          </span>
          <span className="text-[10px] text-[var(--fg-3)]">{`${fileContent.lineCount} lines`}</span>
        </div>

        <div className="flex items-center gap-3">
          <div
            className="text-[10px] text-[var(--fg-3)] hidden sm:inline"
            title={fileContent.contentHash}
          >
            hash:{" "}
            <span className="text-[var(--fg-2)]">{fileContent.contentHash.slice(0, 12)}...</span>
          </div>

          <button
            type="button"
            onClick={handleCopyPath}
            className="text-[11px] text-[var(--fg-3)] hover:text-[var(--fg-0)] transition-colors"
          >
            {copied ? "Copied!" : "Copy path"}
          </button>
        </div>
      </div>

      {/* Symbol Quick-Jump Bar */}
      {fileContent.symbols && fileContent.symbols.length > 0 && (
        <div className="px-6 py-2 border-b border-[var(--line-1)] bg-[var(--bg-0)] flex items-center gap-2 overflow-x-auto shrink-0 font-mono text-xs select-none">
          <span className="text-[10px] text-[var(--fg-3)] shrink-0">Symbols:</span>
          <div className="flex items-center gap-1.5">
            {fileContent.symbols.map((sym) => {
              const isSelected = selectedSymbolId === sym.id;
              return (
                <button
                  key={sym.id}
                  type="button"
                  onClick={() => onSelectSymbol(sym)}
                  className={`px-2 py-0.5 rounded text-[11px] transition-colors shrink-0 flex items-center gap-1 ${
                    isSelected
                      ? "bg-[rgba(78,161,255,0.18)] text-[var(--ref)] border border-[rgba(78,161,255,0.4)] font-bold"
                      : "bg-[var(--bg-1)] text-[var(--fg-2)] hover:text-[var(--fg-0)] border border-[var(--line-1)]"
                  }`}
                >
                  <span className="text-[9px] text-[var(--fg-3)]">{sym.kind}</span>
                  <span>{sym.name}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Main Content Area: Metadata-Only Mode vs Source Code */}
      <div className="flex-1 overflow-y-auto">
        {projectMode === "metadata_only" ? (
          /* Metadata-Only State (docs/08 §11 S-05: metadata_only projects show structure and symbols but no source text) */
          <div className="p-8 max-w-2xl mx-auto space-y-6 text-center">
            <div className="p-6 rounded-[var(--radius-lg)] border-2 border-[var(--warn)] bg-[rgba(240,180,76,0.08)] space-y-3">
              <div className="w-10 h-10 rounded-full bg-[rgba(240,180,76,0.15)] text-[var(--warn)] text-lg flex items-center justify-center mx-auto">
                🔒
              </div>
              <h3 className="text-sm font-semibold text-[var(--fg-0)] font-mono">
                Metadata-Only Mode: Source Text Redacted
              </h3>
              <p className="text-xs text-[var(--fg-2)] leading-relaxed">
                This project is configured in metadata-only mode (ADR-034). DevMind has indexed
                symbols, file structural hashes, and dependency relationships, but actual source
                code text is withheld from server storage.
              </p>
              <div className="pt-2">
                <Link href={`/projects/${projectId}/settings`}>
                  <Button variant="primary" size="sm">
                    Enable Indexed Mode with Consent
                  </Button>
                </Link>
              </div>
            </div>

            {/* Extracted Semantic Symbols in Metadata Mode */}
            <div className="text-left space-y-3">
              <div className="text-xs font-semibold font-mono text-[var(--fg-1)] uppercase tracking-wider">
                {`Extracted AST Symbols (${fileContent.symbols.length})`}
              </div>
              <div className="divide-y divide-[var(--line-1)] border border-[var(--line-1)] rounded-[var(--radius-md)] bg-[var(--bg-1)] overflow-hidden">
                {fileContent.symbols.map((sym) => (
                  <div key={sym.id} className="p-3 font-mono text-xs space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-[var(--ref)]">{sym.name}</span>
                      <span className="text-[10px] text-[var(--fg-3)]">
                        L{sym.startLine}-L{sym.endLine}
                      </span>
                    </div>
                    {sym.signature && (
                      <div className="text-[11px] text-[var(--fg-2)]">{sym.signature}</div>
                    )}
                    {sym.docstring && (
                      <div className="text-[10px] text-[var(--fg-3)] italic">{sym.docstring}</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : fileContent.isUnindexed ? (
          /* Unindexed File State (shows tier and reason) */
          <div className="p-8 max-w-lg mx-auto text-center space-y-3 font-mono text-xs">
            <div className="p-4 rounded-[var(--radius-md)] border border-[var(--line-1)] bg-[var(--bg-1)] space-y-2">
              <span className="text-lg">📄</span>
              <div className="font-bold text-[var(--fg-1)]">Unindexed File</div>
              <p className="text-[var(--fg-3)] text-[11px] leading-relaxed">
                {fileContent.unindexedReason ||
                  "This file is outside parsed language tiers or marked ignored by .devmindignore."}
              </p>
            </div>
          </div>
        ) : (
          /* Indexed Mode: Code Viewer with line numbers */
          <div className="flex font-mono text-xs leading-relaxed overflow-x-auto min-h-full">
            {/* Line Numbers Column */}
            <div className="py-4 pl-4 pr-3 select-none text-right text-[var(--fg-3)] bg-[var(--bg-1)] border-r border-[var(--line-1)] shrink-0 w-12">
              {lines.map((_, i) => (
                <div key={i}>{i + 1}</div>
              ))}
            </div>

            {/* Code Content Column */}
            <pre className="p-4 flex-1 text-[var(--fg-1)] whitespace-pre overflow-x-visible">
              {lines.map((line, i) => (
                <div key={i} className="hover:bg-[rgba(78,161,255,0.06)] px-1 -mx-1 rounded">
                  {line || " "}
                </div>
              ))}
            </pre>
          </div>
        )}
      </div>
    </main>
  );
}
