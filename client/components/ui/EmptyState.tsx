"use client";

import React from "react";
import Link from "next/link";
import { Button } from "./Button";

export interface EmptyStateProps {
  title: string;
  description: string;
  action?: {
    label: string;
    onClick?: () => void;
    href?: string;
    variant?: "primary" | "secondary";
  };
  secondaryAction?: {
    label: string;
    onClick?: () => void;
    href?: string;
  };
  docsUrl?: string;
  className?: string;
}

export function EmptyState({
  title,
  description,
  action,
  secondaryAction,
  docsUrl,
  className = "",
}: EmptyStateProps) {
  const headingId = React.useId();

  return (
    <div
      role="region"
      aria-labelledby={headingId}
      className={`flex flex-col items-center justify-center p-8 sm:p-12 text-center rounded-[var(--radius-panel)] border border-[var(--line-1)] bg-[var(--bg-1)]/50 max-w-xl mx-auto my-6 ${className}`}
    >
      {/* DevMind status glyph: clean non-illustrative indicator */}
      <div
        className="w-10 h-10 rounded-full border border-[var(--line-2)] bg-[var(--bg-2)] flex items-center justify-center mb-4 text-[var(--fg-2)] font-mono text-sm select-none"
        aria-hidden="true"
      >
        —
      </div>

      <h3
        id={headingId}
        className="text-[16px] font-semibold text-[var(--fg-0)] tracking-tight mb-2"
      >
        {title}
      </h3>

      <p className="text-[13px] text-[var(--fg-2)] leading-relaxed max-w-md mb-6">{description}</p>

      {(action || secondaryAction || docsUrl) && (
        <div className="flex flex-wrap items-center justify-center gap-3">
          {action &&
            (action.href ? (
              <Link
                href={action.href}
                className="inline-flex items-center justify-center font-sans font-semibold rounded-[var(--radius-control)] h-9 px-4 text-[14px] bg-[var(--signal)] text-[var(--bg-0)] hover:brightness-110 active:brightness-95 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-0)]"
              >
                {action.label}
              </Link>
            ) : (
              <Button variant={action.variant || "primary"} onClick={action.onClick}>
                {action.label}
              </Button>
            ))}

          {secondaryAction &&
            (secondaryAction.href ? (
              <Link
                href={secondaryAction.href}
                className="inline-flex items-center justify-center font-sans rounded-[var(--radius-control)] h-9 px-4 text-[14px] bg-transparent text-[var(--fg-0)] border border-[var(--line-3)] hover:bg-[var(--bg-2)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-0)]"
              >
                {secondaryAction.label}
              </Link>
            ) : (
              <Button variant="secondary" onClick={secondaryAction.onClick}>
                {secondaryAction.label}
              </Button>
            ))}

          {docsUrl && (
            <a
              href={docsUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[12px] font-mono text-[var(--fg-2)] hover:text-[var(--ref)] transition-colors underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)] rounded-control px-2 py-1"
            >
              Docs ↗
            </a>
          )}
        </div>
      )}
    </div>
  );
}
