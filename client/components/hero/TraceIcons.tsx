import React from "react";

export function CheckIcon({
  className = "w-3.5 h-3.5 text-[var(--signal)]",
}: {
  className?: string;
}) {
  return (
    <svg
      role="img"
      aria-label="Satisfied"
      viewBox="0 0 14 14"
      fill="none"
      stroke="currentColor"
      className={className}
    >
      <path
        d="M2.5 7.5L5.5 10.5L11.5 3.5"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function CrossIcon({
  className = "w-3.5 h-3.5 text-[var(--danger)]",
}: {
  className?: string;
}) {
  return (
    <svg
      role="img"
      aria-label="Failed"
      viewBox="0 0 14 14"
      fill="none"
      stroke="currentColor"
      className={className}
    >
      <path
        d="M3.5 3.5L10.5 10.5M10.5 3.5L3.5 10.5"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function GutterDiagnosticGlyph({
  className = "w-3 h-3 text-[var(--warn)]",
}: {
  className?: string;
}) {
  return (
    <svg
      role="img"
      aria-label="Diagnostic Warning"
      viewBox="0 0 12 12"
      fill="currentColor"
      className={className}
    >
      <path
        d="M6 1L11.5 10.5H0.5L6 1Z"
        fill="currentColor"
        fillOpacity="0.2"
        stroke="currentColor"
        strokeWidth="1"
      />
      <circle cx="6" cy="8" r="0.75" fill="currentColor" />
      <line
        x1="6"
        y1="4"
        x2="6"
        y2="6.5"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
      />
    </svg>
  );
}
