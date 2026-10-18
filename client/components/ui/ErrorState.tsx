"use client";

import React from "react";
import Link from "next/link";
import { Button } from "./Button";

export interface ErrorStateProps {
  title?: string;
  code?: string;
  message?: string;
  cause?: string;
  nextStep?: string;
  requestId?: string;
  retry?: () => void;
  homeHref?: string;
  className?: string;
}

export function ErrorState({
  title = "Something went wrong",
  code,
  message,
  cause,
  nextStep,
  requestId,
  retry,
  homeHref = "/projects",
  className = "",
}: ErrorStateProps) {
  const headingId = React.useId();

  return (
    <div
      role="alert"
      aria-labelledby={headingId}
      className={`rounded-[var(--radius-panel)] border border-[var(--danger)]/40 bg-[rgba(255,107,94,0.04)] p-6 sm:p-8 max-w-xl mx-auto my-6 space-y-4 ${className}`}
    >
      <div className="flex items-start gap-3">
        <div
          className="w-7 h-7 rounded-full bg-[var(--danger)]/15 border border-[var(--danger)]/30 flex items-center justify-center shrink-0 text-[var(--danger)] font-mono text-xs select-none"
          aria-hidden="true"
        >
          ✕
        </div>
        <div className="space-y-1 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 id={headingId} className="text-[16px] font-semibold text-[var(--fg-0)]">
              {title}
            </h3>
            {code && (
              <span className="font-mono text-[11px] px-2 py-0.5 rounded-[var(--radius-chip)] bg-[var(--bg-2)] border border-[var(--line-1)] text-[var(--fg-2)]">
                {code}
              </span>
            )}
          </div>

          {message && <p className="text-[13px] text-[var(--fg-1)] leading-relaxed">{message}</p>}
        </div>
      </div>

      {(cause || nextStep) && (
        <div className="text-[12px] bg-[var(--bg-1)] p-3 rounded-[var(--radius-sm)] border border-[var(--line-1)] space-y-1 font-mono">
          {cause && (
            <div className="text-[var(--fg-2)]">
              <span className="text-[var(--fg-3)] select-none">cause: </span>
              {cause}
            </div>
          )}
          {nextStep && (
            <div className="text-[var(--fg-1)]">
              <span className="text-[var(--fg-3)] select-none">action: </span>
              {nextStep}
            </div>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-[var(--line-1)]">
        <div className="flex items-center gap-2">
          {retry && (
            <Button variant="secondary" size="sm" onClick={retry}>
              Retry request
            </Button>
          )}
          {homeHref && (
            <Link
              href={homeHref}
              className="inline-flex items-center justify-center font-sans rounded-[var(--radius-control)] h-8 px-3 text-[13px] bg-transparent text-[var(--fg-1)] hover:text-[var(--fg-0)] hover:underline hover:decoration-[var(--ref)] underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)]"
            >
              Return to overview
            </Link>
          )}
        </div>

        {requestId && (
          <span
            className="text-[11px] font-mono text-[var(--fg-3)]"
            title="Request identifier for audit & support"
          >
            {`request_id: ${requestId.slice(0, 12)}…`}
          </span>
        )}
      </div>
    </div>
  );
}
