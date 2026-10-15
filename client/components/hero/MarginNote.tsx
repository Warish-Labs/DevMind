"use client";

import React, { useState, useEffect } from "react";
import { CheckIcon, CrossIcon } from "./TraceIcons";
import { HERO_MARGIN_NOTE, HERO_RIPPLE_TAGS, RippleTagData } from "../../lib/hero-data";

interface MarginNoteProps {
  visible: boolean;
  evidenceStep: "empty" | "e1";
  rippleVisible: boolean;
  parallaxStyle?: React.CSSProperties;
}

export function MarginNote({
  visible,
  evidenceStep,
  rippleVisible,
  parallaxStyle,
}: MarginNoteProps) {
  const [activeTag, setActiveTag] = useState<RippleTagData | null>(null);

  // Dismiss peek on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setActiveTag(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div
      style={parallaxStyle}
      className={`transition-all duration-500 ease-out flex flex-col gap-3 ${
        visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2 pointer-events-none"
      }`}
    >
      {/* Margin Note Card */}
      <div className="p-4 rounded-panel bg-[var(--bg-1)] border border-[var(--line-2)] shadow-xl max-w-sm sm:max-w-md font-mono text-xs">
        <div className="flex items-center justify-between pb-2 mb-3 border-b border-[var(--line-1)] text-[var(--signal)]">
          <span className="font-semibold tracking-wide">{HERO_MARGIN_NOTE.header}</span>
          <span className="text-[10px] text-[var(--fg-2)] uppercase tracking-wider">
            Finding Trace
          </span>
        </div>

        <div className="space-y-2.5">
          {/* Authentication Row */}
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-[var(--fg-2)] w-28 shrink-0">{HERO_MARGIN_NOTE.authnLabel}</span>
            <div className="flex items-center gap-1.5 text-[var(--signal)] font-medium shrink-0">
              <CheckIcon />
              <span>{HERO_MARGIN_NOTE.authnStatus}</span>
            </div>
            <span className="text-[var(--fg-1)] text-right truncate">
              {HERO_MARGIN_NOTE.authnDetail}
            </span>
          </div>

          {/* Authorization Row */}
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-[var(--fg-2)] w-28 shrink-0">{HERO_MARGIN_NOTE.authzLabel}</span>
            <div className="flex items-center gap-1.5 text-[var(--danger)] font-medium shrink-0">
              <CrossIcon />
              <span>{HERO_MARGIN_NOTE.authzStatus}</span>
            </div>
            <span className="text-[var(--fg-1)] text-right truncate">
              {HERO_MARGIN_NOTE.authzDetail}
            </span>
          </div>

          {/* Evidence Row */}
          <div className="flex items-baseline justify-between gap-2 pt-1 border-t border-[var(--line-1)]">
            <span className="text-[var(--fg-2)] w-28 shrink-0">
              {HERO_MARGIN_NOTE.evidenceLabel}
            </span>
            <div className="flex items-center gap-1 shrink-0">
              {/* Evidence segments: 4 blocks (E0, E1 filled if evidenceStep === 'e1') */}
              <span
                className={`w-2 h-3.5 rounded-xs transition-colors duration-300 ${
                  evidenceStep === "e1" ? "bg-[var(--warn)]" : "bg-[var(--line-2)]"
                }`}
                title="E0: Syntax/Local"
              />
              <span
                className={`w-2 h-3.5 rounded-xs transition-colors duration-300 ${
                  evidenceStep === "e1" ? "bg-[var(--warn)]" : "bg-[var(--line-2)]"
                }`}
                title="E1: Static Structure"
              />
              <span
                className="w-2 h-3.5 rounded-xs bg-[var(--line-1)] border border-[var(--line-2)]"
                title="E2: Verified Invariant (unverified)"
              />
              <span
                className="w-2 h-3.5 rounded-xs bg-[var(--line-1)] border border-[var(--line-2)]"
                title="E3: Dynamic Execution (unverified)"
              />
              <span className="ml-1 text-[var(--warn)] font-medium">
                {HERO_MARGIN_NOTE.evidenceLevel}
              </span>
            </div>
            <span
              className="text-[var(--fg-2)] text-[10px] text-right truncate max-w-[140px]"
              title={HERO_MARGIN_NOTE.ruleId}
            >
              {HERO_MARGIN_NOTE.ruleId}
            </span>
          </div>
        </div>
      </div>

      {/* Ripple Tags (Shared Brain Consequence tags) */}
      <div
        className={`flex flex-col gap-2 transition-all duration-500 delay-100 ${
          rippleVisible
            ? "opacity-100 translate-y-0"
            : "opacity-0 translate-y-2 pointer-events-none"
        }`}
      >
        <div className="text-[10px] font-mono uppercase tracking-wider text-[var(--fg-2)] pl-1">
          Shared Brain Ripples
        </div>

        <div className="flex flex-wrap gap-2">
          {HERO_RIPPLE_TAGS.map((tag) => {
            const isSelected = activeTag?.id === tag.id;
            return (
              <div key={tag.id} className="relative">
                <button
                  type="button"
                  onClick={() => setActiveTag(isSelected ? null : tag)}
                  onMouseEnter={() => setActiveTag(tag)}
                  onMouseLeave={() => setActiveTag(null)}
                  onFocus={() => setActiveTag(tag)}
                  onBlur={() => setActiveTag(null)}
                  aria-expanded={isSelected}
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-chip text-xs font-mono transition-all border ${
                    isSelected
                      ? "bg-[var(--ref)]/15 border-[var(--ref)] text-[var(--fg-0)]"
                      : "bg-[var(--bg-1)] border-[var(--line-2)] text-[var(--fg-1)] hover:border-[var(--line-3)] hover:text-[var(--fg-0)]"
                  }`}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--ref)]" />
                  <span>{tag.label}</span>
                </button>

                {/* Peek Card Popover */}
                {isSelected && (
                  <div
                    role="tooltip"
                    className="absolute z-20 left-0 bottom-full mb-2 w-64 p-2.5 rounded-panel bg-[var(--bg-1)]/95 backdrop-blur border border-[var(--line-3)] text-xs font-mono text-[var(--fg-0)] shadow-2xl animate-in fade-in zoom-in-95 duration-150"
                  >
                    <div className="text-[10px] text-[var(--ref)] font-semibold uppercase tracking-wider mb-1">
                      Consequence Detail
                    </div>
                    <p className="text-[11px] leading-relaxed text-[var(--fg-1)]">{tag.peek}</p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
