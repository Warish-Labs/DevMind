"use client";

import React, { useState } from "react";

export interface CodeExcerptProps {
  path: string;
  code: string;
  startLine: number;
  highlightStart?: number;
  highlightEnd?: number;
  className?: string;
}

export function CodeExcerpt({
  path,
  code,
  startLine,
  highlightStart,
  highlightEnd,
  className = "",
}: CodeExcerptProps) {
  const [copied, setCopied] = useState<boolean>(false);

  const lines = code.split("\n");

  const handleCopyPath = async () => {
    try {
      const lineSuffix =
        highlightStart !== undefined
          ? `#L${highlightStart}${highlightEnd && highlightEnd !== highlightStart ? `-${highlightEnd}` : ""}`
          : "";
      await navigator.clipboard.writeText(`${path}${lineSuffix}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard copy fallback
    }
  };

  return (
    <div
      className={`rounded-[var(--radius-md)] border border-[var(--line-1)] bg-[var(--bg-0)] overflow-hidden font-mono text-xs ${className}`}
    >
      {/* File Path Header */}
      <div className="flex items-center justify-between px-3.5 py-2 bg-[var(--bg-1)] border-b border-[var(--line-1)] select-none">
        <div className="flex items-center gap-2 overflow-hidden text-ellipsis">
          <svg
            className="w-3.5 h-3.5 text-[var(--fg-2)] shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <span className="text-[var(--fg-0)] font-medium truncate">{path}</span>
          {highlightStart !== undefined && (
            <span className="text-[var(--fg-2)] text-[11px] shrink-0">
              {highlightEnd && highlightEnd !== highlightStart
                ? `(lines ${highlightStart}-${highlightEnd})`
                : `(line ${highlightStart})`}
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={handleCopyPath}
          className="text-[11px] text-[var(--fg-2)] hover:text-[var(--fg-0)] px-2 py-0.5 rounded-[var(--radius-sm)] hover:bg-[var(--bg-2)] transition-colors shrink-0"
        >
          {copied ? "Copied!" : "Copy reference"}
        </button>
      </div>

      {/* Code with Line Numbers */}
      <div className="overflow-x-auto py-2">
        <table className="w-full border-collapse">
          <tbody>
            {lines.map((lineContent, index) => {
              const lineNumber = startLine + index;
              const isHighlighted =
                highlightStart !== undefined &&
                highlightEnd !== undefined &&
                lineNumber >= highlightStart &&
                lineNumber <= highlightEnd;

              return (
                <tr
                  key={lineNumber}
                  className={`transition-colors ${
                    isHighlighted
                      ? "bg-[rgba(255,107,94,0.12)] border-l-2 border-l-[var(--danger)]"
                      : "border-l-2 border-l-transparent hover:bg-[var(--bg-1)]"
                  }`}
                >
                  <td className="w-12 px-3 py-0.5 text-right text-[var(--fg-3)] select-none text-[11px] align-top">
                    {lineNumber}
                  </td>
                  <td className="px-3 py-0.5 text-[var(--fg-1)] whitespace-pre align-top font-mono">
                    {lineContent || " "}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
