"use client";

import React from "react";

export type BadgeVariant = "neutral" | "signal" | "warn" | "danger" | "ref";
export type EvidenceLevel = "E0" | "E1" | "E2";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  evidenceLevel?: EvidenceLevel;
  mono?: boolean;
  glyph?: React.ReactNode;
}

const variantStyles: Record<BadgeVariant, string> = {
  neutral: "bg-[var(--bg-2)] text-[var(--fg-1)] border-[var(--line-2)]",
  signal: "bg-[rgba(32,227,162,0.1)] text-[var(--signal)] border-[rgba(32,227,162,0.3)]",
  warn: "bg-[rgba(240,180,76,0.1)] text-[var(--warn)] border-[rgba(240,180,76,0.3)]",
  danger: "bg-[rgba(255,107,94,0.1)] text-[var(--danger)] border-[rgba(255,107,94,0.3)]",
  ref: "bg-[rgba(78,161,255,0.1)] text-[var(--ref)] border-[rgba(78,161,255,0.3)]",
};

const defaultGlyphs: Record<BadgeVariant, string> = {
  neutral: "●",
  signal: "✓",
  warn: "▲",
  danger: "✕",
  ref: "◆",
};

export function Badge({
  variant = "neutral",
  evidenceLevel,
  mono = false,
  glyph,
  className = "",
  children,
  ...props
}: BadgeProps) {
  // If evidence level is specified, format per docs/08 §3.4 & §6
  const activeVariant =
    evidenceLevel === "E2"
      ? "danger"
      : evidenceLevel === "E1"
        ? "warn"
        : evidenceLevel === "E0"
          ? "neutral"
          : variant;

  const displayGlyph = glyph !== undefined ? glyph : defaultGlyphs[activeVariant];
  const isMono = mono || Boolean(evidenceLevel);

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-[11px] leading-4 border rounded-[var(--radius-chip)] select-none ${
        isMono ? "font-mono tracking-tight" : "font-sans"
      } ${variantStyles[activeVariant]} ${className}`}
      {...props}
    >
      {displayGlyph && (
        <span className="text-[9px] leading-none shrink-0" aria-hidden="true">
          {displayGlyph}
        </span>
      )}
      <span>{evidenceLevel ? `${evidenceLevel} · ${children || ""}`.trim() : children}</span>
    </span>
  );
}
