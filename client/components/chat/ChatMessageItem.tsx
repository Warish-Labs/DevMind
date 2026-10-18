"use client";

import React, { useState } from "react";
import type { ChatMessage } from "./types";

export interface ChatMessageItemProps {
  message: ChatMessage;
  onSelectCitation: (citationId: string) => void;
  onOpenCitationsPanel?: () => void;
  className?: string;
}

export function ChatMessageItem({
  message,
  onSelectCitation,
  onOpenCitationsPanel,
  className = "",
}: ChatMessageItemProps) {
  const [copied, setCopied] = useState<boolean>(false);
  const [showActivity, setShowActivity] = useState<boolean>(true);

  const isUser = message.role === "user";

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard fallback
    }
  };

  // Render text with clickable inline citation pills
  const renderFormattedContent = (content: string) => {
    const parts = content.split(/(\[\d+\])/g);
    return parts.map((part, i) => {
      const match = part.match(/\[(\d+)\]/);
      if (match && message.citations) {
        const citationIndex = parseInt(match[1], 10);
        const citation = message.citations.find((c) => c.index === citationIndex);
        if (citation) {
          return (
            <button
              key={i}
              type="button"
              onClick={() => {
                onSelectCitation(citation.id);
                if (onOpenCitationsPanel) onOpenCitationsPanel();
              }}
              className="inline-flex items-center px-1.5 py-0.2 mx-0.5 rounded-[var(--radius-chip)] bg-[rgba(78,161,255,0.15)] text-[var(--ref)] hover:bg-[rgba(78,161,255,0.25)] border border-[rgba(78,161,255,0.3)] text-[10px] font-mono font-bold align-baseline transition-colors select-none"
              title={`View citation ${citationIndex}: ${citation.path}`}
            >
              {`[${citationIndex}]`}
            </button>
          );
        }
      }
      return <span key={i}>{part}</span>;
    });
  };

  if (isUser) {
    return (
      <div className={`flex justify-end ${className}`}>
        <div className="max-w-2xl bg-[var(--line-strong)] text-[var(--fg-0)] rounded-2xl rounded-tr-sm px-4 py-3 text-xs leading-relaxed space-y-1 shadow-sm">
          <div className="whitespace-pre-wrap">{message.content}</div>
          <div className="text-[10px] text-[var(--fg-2)] text-right font-mono">
            {new Date(message.createdAt).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex items-start gap-3 max-w-3xl ${className}`}>
      {/* DevMind Avatar */}
      <div className="w-7 h-7 rounded-full bg-[var(--bg-2)] border border-[var(--line-1)] flex items-center justify-center shrink-0 text-xs font-bold text-[var(--signal)] select-none">
        DM
      </div>

      <div className="flex-1 space-y-3 min-w-0">
        {/* Agent Activity Lines (docs/08 §11 S-06: agent activity lines appear above the answer) */}
        {message.activityLines && message.activityLines.length > 0 && (
          <div className="rounded-[var(--radius-md)] border border-[var(--line-1)] bg-[var(--bg-1)] overflow-hidden font-mono text-[11px]">
            <button
              type="button"
              onClick={() => setShowActivity((prev) => !prev)}
              className="w-full flex items-center justify-between px-3 py-1.5 bg-[var(--bg-2)] text-[var(--fg-2)] hover:text-[var(--fg-0)] transition-colors select-none"
            >
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[var(--signal)]" />
                <span className="font-medium text-[10px] uppercase tracking-wider">
                  {`Agent Execution Trace (${message.activityLines.length})`}
                </span>
              </div>
              <span className="text-[10px]">{showActivity ? "Hide ▲" : "Show ▼"}</span>
            </button>

            {showActivity && (
              <div className="p-2.5 space-y-1 border-t border-[var(--line-1)] divide-y divide-[var(--line-1)]">
                {message.activityLines.map((line, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-2 pt-1 first:pt-0 text-[var(--fg-2)]"
                  >
                    <span className="text-[var(--signal)] shrink-0 font-bold">✓</span>
                    <span className="leading-snug">{line}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Message Content */}
        <div className="bg-[var(--bg-0)] border border-[var(--line-1)] rounded-2xl rounded-tl-sm p-4 space-y-3 text-xs leading-relaxed text-[var(--fg-1)]">
          <div className="whitespace-pre-wrap">{renderFormattedContent(message.content)}</div>

          {/* Insufficient Evidence Banner (docs/08 §11 S-06: an insufficient evidence answer has a distinct style with suggested next steps) */}
          {message.hasInsufficientEvidence && (
            <div className="p-4 rounded-[var(--radius-md)] border-2 border-[var(--warn)] bg-[rgba(240,180,76,0.08)] space-y-2.5">
              <div className="flex items-start gap-2">
                <span className="text-base leading-none">⚠️</span>
                <div className="space-y-0.5">
                  <div className="font-bold text-xs text-[var(--warn)] font-mono">
                    Insufficient Evidence for Grounded Answer
                  </div>
                  {message.insufficientEvidenceReason && (
                    <p className="text-[11px] text-[var(--fg-1)] leading-relaxed">
                      {message.insufficientEvidenceReason}
                    </p>
                  )}
                </div>
              </div>

              {message.suggestedNextSteps && message.suggestedNextSteps.length > 0 && (
                <div className="pt-2 border-t border-[rgba(240,180,76,0.2)] space-y-1">
                  <div className="text-[10px] font-semibold text-[var(--fg-2)] uppercase tracking-wider font-mono">
                    Suggested Next Steps:
                  </div>
                  <ul className="list-disc list-inside space-y-0.5 text-[11px] text-[var(--fg-1)]">
                    {message.suggestedNextSteps.map((step, idx) => (
                      <li key={idx}>{step}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Bottom Actions Bar */}
          <div className="flex items-center justify-between pt-2 border-t border-[var(--line-1)] text-[11px] font-mono text-[var(--fg-3)]">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handleCopy}
                className="hover:text-[var(--fg-0)] transition-colors"
              >
                {copied ? "Copied!" : "Copy markdown"}
              </button>

              {message.citations && message.citations.length > 0 && onOpenCitationsPanel && (
                <button
                  type="button"
                  onClick={onOpenCitationsPanel}
                  className="text-[var(--ref)] hover:underline flex items-center gap-1"
                >
                  <span>{`Citations (${message.citations.length})`}</span>
                </button>
              )}
            </div>

            <span>
              {new Date(message.createdAt).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
