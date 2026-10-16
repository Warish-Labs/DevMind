"use client";

import React, { useState } from "react";
import { SECTION_02_CONSEQUENCES, ConsequenceItem } from "../../lib/sections-data";

export function Section02BlastRadius() {
  const [activeConsequence, setActiveConsequence] = useState<ConsequenceItem | null>(null);

  const diffLines = [
    { line: 4, type: "context", text: " const router = Router();" },
    { line: 5, type: "context", text: " " },
    { line: 6, type: "context", text: " // Administrative endpoint route declarations" },
    {
      line: 7,
      type: "add",
      text: '+ router.get("/admin/users", requireAuth, listUsers);',
    },
    {
      line: 8,
      type: "add",
      text: '+ router.delete("/admin/users/:id", requireAuth, requireRole("admin"), deleteUser);',
    },
    { line: 9, type: "context", text: " " },
    { line: 10, type: "context", text: " export default router;" },
  ];

  return (
    <section id="section-02" className="scroll-mt-24 flex flex-col gap-8">
      {/* Section Header */}
      <div>
        <div className="inline-flex items-center gap-2 px-3 py-1 mb-4 rounded-chip bg-[var(--bg-1)] border border-[var(--line-1)] text-xs text-[var(--ref)] font-mono">
          <span>SECTION 02 · BLAST RADIUS</span>
        </div>
        <h2 className="text-3xl sm:text-4xl lg:text-5xl font-display text-[var(--fg-0)] mb-4 tracking-tight">
          One Change. Five Connected Consequences.
        </h2>
        <p className="max-w-2xl text-base text-[var(--fg-1)] leading-relaxed">
          In fragmented developer toolchains, a single route addition ripples through security,
          review gates, documentation, and pull request risks—each caught by a separate disconnected
          tool, or missed completely.
        </p>
      </div>

      {/* Diptych: Diff Hunk (Left) and Consequences (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left: The Diff Hunk */}
        <div className="lg:col-span-6 rounded-panel bg-[var(--bg-1)] border border-[var(--line-2)] overflow-hidden font-mono text-xs shadow-xl">
          <div className="flex items-center justify-between px-4 py-2.5 bg-[var(--bg-2)]/60 border-b border-[var(--line-1)] text-[11px] text-[var(--fg-2)] select-none">
            <span className="text-[var(--fg-0)] font-medium">diff --git a/src/routes/admin.ts</span>
            <span className="text-[var(--signal)]">+2 lines</span>
          </div>

          <div
            tabIndex={0}
            role="region"
            aria-label="Diff hunk code lines"
            className="p-4 overflow-x-auto space-y-1 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--ref)]"
          >
            <div className="text-[var(--ref)] mb-2 select-none">
              @@ -4,4 +4,6 @@ const router = Router();
            </div>

            {diffLines.map((l) => {
              const isHighlighted =
                activeConsequence && activeConsequence.highlightedLines.includes(l.line);
              const isAdded = l.type === "add";

              return (
                <div
                  key={l.line}
                  className={`flex items-start px-2 py-0.5 rounded-xs transition-colors duration-200 ${
                    isHighlighted
                      ? "bg-[var(--warn)]/20 text-[var(--fg-0)] font-medium ring-1 ring-[var(--warn)]/40"
                      : isAdded
                        ? "bg-[var(--signal)]/10 text-[var(--fg-0)]"
                        : "text-[var(--fg-2)]"
                  }`}
                >
                  <span aria-hidden="true" className="w-8 shrink-0 select-none text-[var(--fg-2)]">
                    {l.line}
                  </span>
                  <span className="whitespace-pre flex-1">{l.text}</span>
                </div>
              );
            })}
          </div>

          <div className="px-4 py-2.5 bg-[var(--bg-2)]/30 border-t border-[var(--line-1)] text-[10px] text-[var(--fg-2)] flex items-center justify-between">
            <span>Hover or focus a consequence to highlight its subject lines</span>
            {activeConsequence && (
              <span className="text-[var(--warn)] font-medium">
                Focus: {activeConsequence.category}
              </span>
            )}
          </div>
        </div>

        {/* Right: Vertical List of 5 Consequences */}
        <div className="lg:col-span-6 flex flex-col gap-3">
          {SECTION_02_CONSEQUENCES.map((item) => {
            const isActive = activeConsequence?.id === item.id;
            return (
              <div
                key={item.id}
                onMouseEnter={() => setActiveConsequence(item)}
                onMouseLeave={() => setActiveConsequence(null)}
                onFocus={() => setActiveConsequence(item)}
                onBlur={() => setActiveConsequence(null)}
                tabIndex={0}
                className={`p-4 rounded-panel border transition-all duration-200 cursor-pointer outline-none ${
                  isActive
                    ? "bg-[var(--bg-2)] border-[var(--ref)] shadow-lg translate-x-1"
                    : "bg-[var(--bg-1)] border-[var(--line-1)] hover:border-[var(--line-2)] hover:bg-[var(--bg-2)]/50"
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        item.id === "security"
                          ? "bg-[var(--danger)]"
                          : item.id === "health"
                            ? "bg-[var(--warn)]"
                            : "bg-[var(--ref)]"
                      }`}
                    />
                    <h3 className="text-sm font-semibold text-[var(--fg-0)]">{item.title}</h3>
                  </div>
                  <span className="text-[10px] font-mono text-[var(--fg-2)] uppercase tracking-wider">
                    {item.tag}
                  </span>
                </div>

                <p className="text-xs text-[var(--fg-1)] leading-relaxed pl-4">
                  {item.description}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
