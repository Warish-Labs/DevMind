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
      <div className="flex flex-col lg:flex-row items-stretch lg:items-start gap-4 lg:gap-6">
        {/* Editor Code Pane (Trace) */}
        <div className="flex-1 min-w-0">
          <Trace
            visibleLineCount={visibleLineCount}
            scanningActive={scanningActive}
            scanProgress={scanProgress}
            diagnosticActive={diagnosticActive}
          />
        </div>

        {/* Hairline Connector Line (Desktop only) */}
        <div className="hidden lg:flex items-center self-center text-[var(--line-2)] -mx-2 select-none pointer-events-none">
          <svg width="24" height="2" viewBox="0 0 24 2" fill="none">
            <line x1="0" y1="1" x2="24" y2="1" stroke="currentColor" strokeDasharray="3 3" />
          </svg>
        </div>

        {/* Margin Note Pane with fine-pointer Parallax */}
        <div className="w-full lg:w-96 shrink-0">
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
