import React from "react";
import { HERO_CODE_LINES, HeroCodeLine } from "../../lib/hero-data";
import { GutterDiagnosticGlyph } from "./TraceIcons";

interface TraceProps {
  visibleLineCount: number;
  scanningActive: boolean;
  scanProgress: number; // 0 to 1
  diagnosticActive: boolean;
}

export function Trace({
  visibleLineCount,
  scanningActive,
  scanProgress,
  diagnosticActive,
}: TraceProps) {
  return (
    <div
      role="region"
      aria-label="Code trace analysis example"
      className="relative rounded-sm bg-[var(--bg-2)] border border-[var(--line-1)] overflow-hidden font-mono text-xs sm:text-sm select-text"
    >
      {/* Corner Example Tab */}
      <div className="absolute top-0 right-0 px-2.5 py-0.5 rounded-bl-sm bg-[var(--bg-1)] border-b border-l border-[var(--line-1)] text-[10px] text-[var(--fg-2)] uppercase tracking-widest font-mono z-10 select-none">
        example
      </div>

      {/* Editor Header Bar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-[var(--line-1)] bg-[var(--bg-1)]/60 text-[11px] text-[var(--fg-2)] select-none">
        <span className="w-2 h-2 rounded-full bg-[var(--line-3)]" />
        <span className="w-2 h-2 rounded-full bg-[var(--line-3)]" />
        <span className="w-2 h-2 rounded-full bg-[var(--line-3)]" />
        <span className="ml-2 text-[var(--fg-1)]">src/routes/admin.ts</span>
      </div>

      {/* Code Editor Body */}
      <div
        tabIndex={0}
        role="region"
        aria-label="Code editor lines"
        className="relative p-4 sm:p-5 overflow-x-auto focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--ref)]"
      >
        {/* Animated Scan Line travelling down gutter */}
        {scanningActive && (
          <div
            className="absolute left-8 w-1 h-6 rounded-full bg-[var(--signal)] shadow-sm pointer-events-none transition-transform duration-75 select-none"
            style={{
              top: `${16 + scanProgress * 180}px`,
            }}
          />
        )}

        <div className="space-y-1 min-w-[420px]">
          {HERO_CODE_LINES.map((line: HeroCodeLine, index) => {
            const isVisible = index < visibleLineCount;
            const isLine7 = line.lineNumber === 7;

            return (
              <div
                key={line.lineNumber}
                className={`flex items-start transition-opacity duration-300 ${
                  isVisible ? "opacity-100" : "opacity-0"
                } ${isLine7 && diagnosticActive ? "bg-[var(--warn)]/5 -mx-4 px-4 py-0.5 rounded-xs" : ""}`}
              >
                {/* Gutter Line Number & Glyph */}
                <div className="w-10 shrink-0 text-right pr-4 text-[var(--fg-2)] select-none flex items-center justify-end gap-1 font-mono text-xs">
                  {isLine7 && diagnosticActive && (
                    <span className="animate-in fade-in duration-300">
                      <GutterDiagnosticGlyph />
                    </span>
                  )}
                  <span>{line.lineNumber}</span>
                </div>

                {/* Code Content */}
                <div className="flex-1 whitespace-pre leading-relaxed font-mono">
                  {line.tokens.length === 0 ? (
                    <span>&nbsp;</span>
                  ) : isLine7 ? (
                    // Specialized rendering for line 7 diagnostic highlight
                    <span>
                      <span className="text-[var(--fg-2)]">router.</span>
                      <span className="text-[var(--fg-0)]">get</span>
                      <span className="text-[var(--fg-2)]">(&quot;</span>
                      <span className="text-[var(--signal)]">/admin/users</span>
                      <span className="text-[var(--fg-2)]">&quot;, </span>
                      <span
                        className={`transition-all duration-300 ${
                          diagnosticActive
                            ? "underline decoration-wavy decoration-[var(--warn)] underline-offset-4 text-[var(--fg-0)] bg-[var(--warn)]/10 px-1 rounded-xs"
                            : "text-[var(--fg-0)]"
                        }`}
                      >
                        requireAuth, listUsers
                      </span>
                      <span className="text-[var(--fg-2)]">);</span>
                    </span>
                  ) : (
                    line.tokens.map((token, tIdx) => {
                      let toneClass = "text-[var(--fg-1)]";
                      if (token.tone === "keyword") toneClass = "text-[var(--ref)] font-medium";
                      else if (token.tone === "ident") toneClass = "text-[var(--fg-0)]";
                      else if (token.tone === "string") toneClass = "text-[var(--signal)]";
                      else if (token.tone === "punct") toneClass = "text-[var(--fg-2)]";

                      return (
                        <span key={tIdx} className={toneClass}>
                          {token.text}
                        </span>
                      );
                    })
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
