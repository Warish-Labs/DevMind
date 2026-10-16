"use client";

import React, { useState } from "react";
import { privacyLedgerData } from "../../lib/sections-data";

export function Section07PrivacyLedger() {
  const [selectedMode, setSelectedMode] = useState<"all" | "metadata_only" | "indexed">("all");

  const filteredEntries = privacyLedgerData.entries.filter((entry) => {
    if (selectedMode === "all") return true;
    return entry.modes.includes(selectedMode);
  });

  return (
    <section id="section-07" className="scroll-mt-24 flex flex-col gap-8">
      {/* Section Header */}
      <div>
        <div className="inline-flex items-center gap-2 px-3 py-1 mb-4 rounded-chip bg-[var(--bg-1)] border border-[var(--line-1)] text-xs text-[var(--signal)] font-mono">
          <span>SECTION 07 · TRANSPARENCY</span>
        </div>
        <h2 className="text-3xl sm:text-4xl lg:text-5xl font-display text-[var(--fg-0)] mb-4 tracking-tight">
          Privacy Ledger: What Goes Where
        </h2>
        <p className="max-w-2xl text-base text-[var(--fg-1)] leading-relaxed">
          An explicit, auditable data contract. We disclose exactly which artifacts stay strictly on
          your machine, what is stored in DevMind, what is vectorized, and what ever reaches an LLM.
        </p>
      </div>

      {/* Mode Controls & Documentation Link */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 rounded-control bg-[var(--bg-1)] border border-[var(--line-2)] font-mono text-xs">
        <div className="flex items-center gap-3">
          <span className="text-[var(--fg-2)]">Filter By Sync Mode:</span>
          <div className="inline-flex rounded-control border border-[var(--line-1)] p-0.5 bg-[var(--bg-0)]">
            {(["all", "metadata_only", "indexed"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setSelectedMode(mode)}
                className={`px-3 py-1 rounded-xs transition-colors cursor-pointer ${
                  selectedMode === mode
                    ? "bg-[var(--signal)] text-[var(--bg-0)] font-semibold"
                    : "text-[var(--fg-1)] hover:text-[var(--fg-0)]"
                }`}
              >
                {mode}
              </button>
            ))}
          </div>
        </div>

        <a
          href="https://github.com/Warish-Labs/DevMind/blob/main/docs/07-security-privacy-and-threat-model.md"
          target="_blank"
          rel="noopener noreferrer"
          className="text-[var(--ref)] hover:underline inline-flex items-center gap-1 text-[11px]"
        >
          <span>Read Security &amp; Threat Model (docs/07) ↗</span>
        </a>
      </div>

      {/* Auditable Privacy Matrix Table */}
      <div className="rounded-panel border border-[var(--line-1)] bg-[var(--bg-1)] overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs border-collapse">
            <thead>
              <tr className="border-b border-[var(--line-2)] bg-[var(--bg-2)]/60 text-[var(--fg-2)] select-none">
                <th className="py-3 px-4 font-medium text-[var(--fg-0)]">Data Category</th>
                <th className="py-3 px-4 w-28 text-center">Stays Local</th>
                <th className="py-3 px-4 w-32 text-center">Stored in DevMind</th>
                <th className="py-3 px-4 w-28 text-center">Embedded</th>
                <th className="py-3 px-4 w-28 text-center">Reaches LLM</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--line-1)]">
              {filteredEntries.map((row, idx) => {
                // If metadata_only is selected and row is consented chunk, adjust representation
                const isConsentedChunk = row.category.includes("Consented source");
                const reachesLlm =
                  selectedMode === "metadata_only" && isConsentedChunk ? false : row.reachesLLM;

                return (
                  <tr key={idx} className="hover:bg-[var(--bg-2)]/30 transition-colors">
                    {/* Category */}
                    <td className="py-3 px-4 font-sans text-xs text-[var(--fg-0)] font-medium">
                      {row.category}
                    </td>

                    {/* Stays Local */}
                    <td className="py-3 px-4 text-center">
                      {row.staysLocal ? (
                        <span className="inline-block px-2 py-0.5 rounded-chip text-[10px] font-bold bg-[var(--signal)]/15 text-[var(--signal)] border border-[var(--signal)]/30">
                          YES
                        </span>
                      ) : (
                        <span className="inline-block px-2 py-0.5 rounded-chip text-[10px] font-bold bg-[var(--line-1)] text-[var(--fg-2)]">
                          NO
                        </span>
                      )}
                    </td>

                    {/* Stored in DevMind */}
                    <td className="py-3 px-4 text-center">
                      {row.storedInDevMind ? (
                        <span className="inline-block px-2 py-0.5 rounded-chip text-[10px] font-bold bg-[var(--ref)]/15 text-[var(--ref)] border border-[var(--ref)]/30">
                          STORED
                        </span>
                      ) : (
                        <span className="inline-block px-2 py-0.5 rounded-chip text-[10px] font-bold bg-[var(--line-1)] text-[var(--fg-2)]">
                          NEVER
                        </span>
                      )}
                    </td>

                    {/* Embedded */}
                    <td className="py-3 px-4 text-center">
                      {row.embedded ? (
                        <span className="inline-block px-2 py-0.5 rounded-chip text-[10px] font-bold bg-[var(--warn)]/15 text-[var(--warn)] border border-[var(--warn)]/30">
                          pgvector
                        </span>
                      ) : (
                        <span className="inline-block px-2 py-0.5 rounded-chip text-[10px] font-bold bg-[var(--line-1)] text-[var(--fg-2)]">
                          NO
                        </span>
                      )}
                    </td>

                    {/* Reaches LLM */}
                    <td className="py-3 px-4 text-center">
                      {reachesLlm ? (
                        <span className="inline-block px-2 py-0.5 rounded-chip text-[10px] font-bold bg-[var(--ref)]/15 text-[var(--ref)] border border-[var(--ref)]/30">
                          CONSENTED
                        </span>
                      ) : (
                        <span className="inline-block px-2 py-0.5 rounded-chip text-[10px] font-bold bg-[var(--line-1)] text-[var(--fg-2)]">
                          NEVER
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
