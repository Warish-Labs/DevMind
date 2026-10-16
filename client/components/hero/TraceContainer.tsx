"use client";

import React, { useState } from "react";
import { Trace } from "./Trace";
import { MarginNote } from "./MarginNote";

interface TraceContainerProps {
  visibleLineCount: number;
  scanningActive: boolean;
  scanProgress: number;
  diagnosticActive: boolean;
  noteVisible: boolean;
  evidenceStep: "empty" | "e1";
  rippleVisible: boolean;
}

export function TraceContainer({
  visibleLineCount,
  scanningActive,
  scanProgress,
  diagnosticActive,
  noteVisible,
  evidenceStep,
  rippleVisible,
}: TraceContainerProps) {
  const [parallax, setParallax] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (typeof window !== "undefined" && window.matchMedia("(pointer: fine)").matches) {
      const rect = e.currentTarget.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      e.currentTarget.style.setProperty("--mx", `${x}px`);
      e.currentTarget.style.setProperty("--my", `${y}px`);

      // Parallax capped strictly to <= 6px
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      const deltaX = Math.min(Math.max((x - centerX) / centerX, -1), 1) * 6;
      const deltaY = Math.min(Math.max((y - centerY) / centerY, -1), 1) * 6;
      setParallax({ x: deltaX, y: deltaY });
    }
  };

  const handlePointerLeave = () => {
    setParallax({ x: 0, y: 0 });
  };

  return (
    <div
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
      className="pointer-lit-card rounded-panel p-2 sm:p-4 bg-[var(--bg-1)] border border-[var(--line-1)] relative"
    >
      <div className="flex flex-col items-stretch gap-4">
        {/* Upper Part: Code Editor Pane (Trace) */}
        <div className="w-full min-w-0">
          <Trace
            visibleLineCount={visibleLineCount}
            scanningActive={scanningActive}
            scanProgress={scanProgress}
            diagnosticActive={diagnosticActive}
          />
        </div>

        {/* Animated Connector Flow between Code & Details */}
        <div className="flex items-center justify-between px-2 text-[11px] font-mono text-[var(--fg-2)] select-none">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[var(--signal)] animate-ping" />
            <span className="text-[var(--signal)] font-medium">AST Analysis Pipeline</span>
            <span className="text-[var(--line-3)]">·</span>
            <span>Line 07 Route Handler</span>
          </div>
          <div className="flex items-center gap-1.5 text-[var(--ref)]">
            <span>Derived Finding</span>
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M12 5v14M19 12l-7 7-7-7" />
            </svg>
          </div>
        </div>

        {/* Bottom Part: Margin Note Finding Details */}
        <div className="w-full">
          <MarginNote
            visible={noteVisible}
            evidenceStep={evidenceStep}
            rippleVisible={rippleVisible}
            parallaxStyle={{
              transform: `translate3d(${parallax.x.toFixed(2)}px, ${parallax.y.toFixed(2)}px, 0)`,
            }}
          />
        </div>
      </div>
    </div>
  );
}
