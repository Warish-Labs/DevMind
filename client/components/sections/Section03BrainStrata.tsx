"use client";

import React, { useState } from "react";
import { BRAIN_STRATA, BrainStratum } from "../../lib/sections-data";

export function Section03BrainStrata() {
  const [selectedStratum, setSelectedStratum] = useState<BrainStratum>(BRAIN_STRATA[0]!);

  const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      const nextIndex = (index + 1) % BRAIN_STRATA.length;
      setSelectedStratum(BRAIN_STRATA[nextIndex]!);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      const prevIndex = (index - 1 + BRAIN_STRATA.length) % BRAIN_STRATA.length;
      setSelectedStratum(BRAIN_STRATA[prevIndex]!);
    }
  };

  return (
    <section id="section-03" className="scroll-mt-24 flex flex-col gap-8">
      {/* Section Header */}
      <div>
        <div className="inline-flex items-center gap-2 px-3 py-1 mb-4 rounded-chip bg-[var(--bg-1)] border border-[var(--line-1)] text-xs text-[var(--signal)] font-mono">
          <span>SECTION 03 · KNOWLEDGE MODEL</span>
        </div>
        <h2 className="text-3xl sm:text-4xl lg:text-5xl font-display text-[var(--fg-0)] mb-4 tracking-tight">
          The Project Brain: Ten Strata of Truth
        </h2>
        <p className="max-w-2xl text-base text-[var(--fg-1)] leading-relaxed">
          The Project Brain is not an ungrounded prompt or flat vector dump. It is a layered
          cross-section of deterministic structures, evidence-linked findings, and historical state.
        </p>
      </div>

      {/* Hero Finding Path Indicator Banner */}
      <div className="flex items-center gap-3 p-3 rounded-control bg-[var(--bg-1)] border border-[var(--line-2)] text-xs font-mono text-[var(--fg-1)]">
        <span className="w-2 h-2 rounded-full bg-[var(--signal)] animate-pulse shrink-0" />
        <span className="text-[var(--fg-0)] font-medium">Hero Finding Trace:</span>
        <span className="text-[var(--fg-2)] hidden sm:inline">Path touches 4 core strata:</span>
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="px-1.5 py-0.5 rounded-xs bg-[var(--signal)]/15 text-[var(--signal)] border border-[var(--signal)]/30 text-[11px]">
            1. Manifest
          </span>
          <span className="text-[var(--fg-2)]">→</span>
          <span className="px-1.5 py-0.5 rounded-xs bg-[var(--signal)]/15 text-[var(--signal)] border border-[var(--signal)]/30 text-[11px]">
            3. Code Index
          </span>
          <span className="text-[var(--fg-2)]">→</span>
          <span className="px-1.5 py-0.5 rounded-xs bg-[var(--signal)]/15 text-[var(--signal)] border border-[var(--signal)]/30 text-[11px]">
            5. Relations
          </span>
          <span className="text-[var(--fg-2)]">→</span>
          <span className="px-1.5 py-0.5 rounded-xs bg-[var(--signal)]/15 text-[var(--signal)] border border-[var(--signal)]/30 text-[11px]">
            8. Findings
          </span>
        </div>
      </div>

      {/* Main Grid: Strata Layer Stack (Left) + Selected Stratum Detail Card (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left (7/12): Interactive Stratum Stack */}
        <div
          role="tablist"
          aria-label="Project Brain Strata Layers"
          className="lg:col-span-7 flex flex-col gap-1.5 font-mono text-xs select-none"
        >
          {BRAIN_STRATA.map((stratum, idx) => {
            const isSelected = selectedStratum.number === stratum.number;
            return (
              <button
                key={stratum.number}
                type="button"
                role="tab"
                aria-selected={isSelected}
                tabIndex={isSelected ? 0 : -1}
                onClick={() => setSelectedStratum(stratum)}
                onKeyDown={(e) => handleKeyDown(e, idx)}
                className={`flex items-center justify-between p-3 rounded-control border text-left transition-all duration-150 cursor-pointer ${
                  isSelected
                    ? "bg-[var(--bg-2)] border-[var(--signal)] shadow-md translate-x-1"
                    : "bg-[var(--bg-1)] border-[var(--line-1)] hover:border-[var(--line-2)] hover:bg-[var(--bg-2)]/40"
                }`}
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`w-6 text-center py-0.5 rounded-xs text-[11px] font-semibold ${
                      isSelected
                        ? "bg-[var(--signal)] text-[var(--bg-0)]"
                        : stratum.isHeroPath
                          ? "bg-[var(--signal)]/20 text-[var(--signal)] border border-[var(--signal)]/40"
                          : "bg-[var(--line-1)] text-[var(--fg-1)]"
                    }`}
                  >
                    {stratum.number}
                  </span>

                  <span
                    className={`font-sans font-medium text-sm ${
                      isSelected ? "text-[var(--fg-0)]" : "text-[var(--fg-1)]"
                    }`}
                  >
                    {stratum.name}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  {stratum.isHeroPath && (
                    <span className="hidden sm:inline-block text-[10px] px-1.5 py-0.5 rounded-xs bg-[var(--signal)]/10 text-[var(--signal)] border border-[var(--signal)]/20 uppercase tracking-wider">
                      Hero Trace
                    </span>
                  )}
                  <span className="text-[11px] text-[var(--fg-2)] truncate max-w-[150px] sm:max-w-[180px] text-right">
                    {stratum.whereItLives}
                  </span>
                </div>
              </button>
            );
          })}
        </div>

        {/* Right (5/12): Detailed Stratum Inspector */}
        <div className="lg:col-span-5 sticky top-24 rounded-panel bg-[var(--bg-1)] border border-[var(--line-2)] p-6 flex flex-col gap-5 shadow-2xl">
          <div className="flex items-center justify-between pb-3 border-b border-[var(--line-1)]">
            <div className="flex items-center gap-2">
              <span className="w-6 h-6 rounded-control flex items-center justify-center bg-[var(--signal)] text-[var(--bg-0)] font-mono text-xs font-bold">
                {selectedStratum.number}
              </span>
              <span className="font-mono text-xs text-[var(--signal)] font-medium">
                Stratum Detail
              </span>
            </div>
            <span className="text-[11px] font-mono text-[var(--fg-2)]">
              {selectedStratum.whereItLives}
            </span>
          </div>

          <div>
            <h3 className="text-xl font-display text-[var(--fg-0)] mb-2 font-medium">
              {selectedStratum.name}
            </h3>
            <p className="text-sm text-[var(--fg-1)] leading-relaxed">
              {selectedStratum.definition}
            </p>
          </div>

          <div className="p-3 rounded-control bg-[var(--bg-0)] border border-[var(--line-1)] text-xs">
            <div className="text-[10px] font-mono uppercase tracking-wider text-[var(--warn)] mb-1 font-semibold">
              What it is NOT
            </div>
            <p className="text-[var(--fg-2)] leading-relaxed">{selectedStratum.notDefinition}</p>
          </div>

          <div className="flex flex-col gap-1.5 font-mono text-xs">
            <div className="text-[10px] uppercase tracking-wider text-[var(--fg-2)]">
              Example Data Shape (labeled example)
            </div>
            <pre className="p-3 rounded-control bg-[var(--bg-0)] border border-[var(--line-1)] text-[var(--signal)] text-[11px] overflow-x-auto whitespace-pre leading-normal select-text">
              {selectedStratum.exampleRecord}
            </pre>
          </div>
        </div>
      </div>
    </section>
  );
}
