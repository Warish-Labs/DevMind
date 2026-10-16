"use client";

import React, { useState } from "react";

export function Section06Diptych() {
  const [syncMode, setSyncMode] = useState<"metadata_only" | "indexed">("metadata_only");

  return (
    <section id="section-06" className="scroll-mt-24 flex flex-col gap-8">
      {/* Section Header */}
      <div>
        <div className="inline-flex items-center gap-2 px-3 py-1 mb-4 rounded-chip bg-[var(--bg-1)] border border-[var(--line-1)] text-xs text-[var(--ref)] font-mono">
          <span>SECTION 06 · ARCHITECTURE DIPTYCH</span>
        </div>
        <h2 className="text-3xl sm:text-4xl lg:text-5xl font-display text-[var(--fg-0)] mb-4 tracking-tight">
          Local-First Companion. Cloud-Assisted Brain.
        </h2>
        <p className="max-w-2xl text-base text-[var(--fg-1)] leading-relaxed">
          The VS Code extension runs offline scanners directly against your disk without live
          database connections or direct LLM calls. Nothing leaves your machine without explicit
          consent preview.
        </p>
      </div>

      {/* Sync Mode Switcher */}
      <div className="flex items-center justify-between flex-wrap gap-4 p-4 rounded-control bg-[var(--bg-1)] border border-[var(--line-2)] font-mono text-xs">
        <div className="flex items-center gap-3">
          <span className="text-[var(--fg-2)]">Sync Mode:</span>
          <div className="inline-flex rounded-control border border-[var(--line-1)] p-0.5 bg-[var(--bg-0)]">
            <button
              type="button"
              onClick={() => setSyncMode("metadata_only")}
              className={`px-3 py-1 rounded-xs transition-colors cursor-pointer ${
                syncMode === "metadata_only"
                  ? "bg-[var(--ref)] text-[var(--bg-0)] font-semibold"
                  : "text-[var(--fg-1)] hover:text-[var(--fg-0)]"
              }`}
            >
              metadata_only
            </button>
            <button
              type="button"
              onClick={() => setSyncMode("indexed")}
              className={`px-3 py-1 rounded-xs transition-colors cursor-pointer ${
                syncMode === "indexed"
                  ? "bg-[var(--signal)] text-[var(--bg-0)] font-semibold"
                  : "text-[var(--fg-1)] hover:text-[var(--fg-0)]"
              }`}
            >
              indexed
            </button>
          </div>
        </div>

        <div className="text-[11px] text-[var(--fg-2)]">
          {syncMode === "metadata_only"
            ? "Syncs hashes, symbols & structure only. Zero source code leaves workstation."
            : "Uploads consented code chunks & creates pgvector embeddings for full RAG."}
        </div>
      </div>

      {/* Architecture Diptych Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left (5/12): VS Code Companion Editor View */}
        <div className="lg:col-span-5 rounded-panel bg-[var(--bg-1)] border border-[var(--line-2)] overflow-hidden font-mono text-xs shadow-xl">
          <div className="flex items-center justify-between px-4 py-2.5 bg-[var(--bg-2)]/60 border-b border-[var(--line-1)] text-[11px] text-[var(--fg-2)] select-none">
            <span className="text-[var(--fg-0)] font-medium">VS Code Extension (Local Host)</span>
            <span className="text-[var(--signal)]">Offline Capable</span>
          </div>

          <div className="p-4 space-y-4">
            <div className="p-3 rounded-control bg-[var(--bg-0)] border border-[var(--line-1)]">
              <div className="text-[10px] text-[var(--fg-2)] uppercase tracking-wider mb-2">
                Local Diagnostics
              </div>
              <div className="space-y-1.5 text-[11px]">
                <div className="flex items-center gap-2 text-[var(--warn)]">
                  <span>⚠</span>
                  <span className="truncate">Possible: authz.missing_role_check (line 7)</span>
                </div>
                <div className="text-[10px] text-[var(--fg-2)] pl-5">
                  Source: DevMind AST Scanner · E1 Local Finding
                </div>
              </div>
            </div>

            <div className="p-3 rounded-control bg-[var(--bg-0)] border border-[var(--line-1)]">
              <div className="text-[10px] text-[var(--fg-2)] uppercase tracking-wider mb-1">
                Status Bar State
              </div>
              <div className="flex items-center gap-2 text-xs text-[var(--fg-0)]">
                <span className="w-2 h-2 rounded-full bg-[var(--signal)]" />
                <span>$(shield) DevMind · {syncMode} · idle</span>
              </div>
            </div>

            <div className="text-[11px] text-[var(--fg-2)] leading-relaxed">
              No live database connection. No LLM credentials on workstation. Scans locally with
              Tree-sitter.
            </div>
          </div>
        </div>

        {/* Center / Preview (2/12): Consent Preview Bridge */}
        <div className="lg:col-span-2 flex flex-col items-center justify-center py-6 px-2 text-center text-xs font-mono text-[var(--fg-2)]">
          <div className="w-full border-t border-[var(--line-2)] my-2" />
          <div className="p-2 rounded-control bg-[var(--bg-2)] border border-[var(--line-2)] text-[10px] text-[var(--signal)] mb-2">
            CONSENT GATE
          </div>
          <p className="text-[10px] text-[var(--fg-1)]">
            Explicit review before any data packet leaves machine
          </p>
          <div className="w-full border-t border-[var(--line-2)] my-2" />
        </div>

        {/* Right (5/12): Cloud Project Brain View */}
        <div className="lg:col-span-5 rounded-panel bg-[var(--bg-1)] border border-[var(--line-2)] overflow-hidden font-mono text-xs shadow-xl">
          <div className="flex items-center justify-between px-4 py-2.5 bg-[var(--bg-2)]/60 border-b border-[var(--line-1)] text-[11px] text-[var(--fg-2)] select-none">
            <span className="text-[var(--fg-0)] font-medium">DevMind Web &amp; Brain Service</span>
            <span className="text-[var(--ref)]">Hybrid PostgreSQL</span>
          </div>

          <div className="p-4 space-y-4">
            <div className="p-3 rounded-control bg-[var(--bg-0)] border border-[var(--line-1)]">
              <div className="text-[10px] text-[var(--fg-2)] uppercase tracking-wider mb-2">
                Knowledge Model State
              </div>
              <div className="space-y-1.5 text-[11px]">
                <div className="flex justify-between text-[var(--fg-1)]">
                  <span>Symbol Graph:</span>
                  <span className="text-[var(--signal)]">Synchronized</span>
                </div>
                <div className="flex justify-between text-[var(--fg-1)]">
                  <span>Source Chunks:</span>
                  <span
                    className={
                      syncMode === "indexed" ? "text-[var(--signal)]" : "text-[var(--warn)]"
                    }
                  >
                    {syncMode === "indexed" ? "Stored & Vectorized" : "Omitted (Local only)"}
                  </span>
                </div>
                <div className="flex justify-between text-[var(--fg-1)]">
                  <span>Verified Findings:</span>
                  <span className="text-[var(--fg-0)]">E1 · Possible</span>
                </div>
              </div>
            </div>

            <div className="p-3 rounded-control bg-[var(--bg-0)] border border-[var(--line-1)]">
              <div className="text-[10px] text-[var(--fg-2)] uppercase tracking-wider mb-1">
                Multi-Agent Reasoning
              </div>
              <p className="text-[11px] text-[var(--fg-1)] leading-relaxed">
                Assembles ephemeral context packs for LangGraph agents (AuthCheck, ReviewBuddy).
                Never stores raw completions permanently.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Continuous Diptych Sync Monitor */}
      <div className="rounded-panel p-4 bg-[var(--bg-1)] border border-[var(--line-1)] flex flex-col sm:flex-row items-center justify-between gap-4 font-mono text-xs">
        <div className="flex items-center gap-3">
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--signal)] opacity-75" />
            <span className="relative inline-flex rounded-full h-3 w-3 bg-[var(--signal)]" />
          </span>
          <span className="text-[var(--fg-0)] font-semibold">
            Consent Gate &amp; Egress Firewall:
          </span>
          <span className="text-[var(--fg-2)] hidden sm:inline">
            Active cryptographic hash verification &amp; secret scrubbing
          </span>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-[var(--signal)]">
          <span className="animate-pulse">● 0 unconsented bytes transmitted</span>
          <span className="text-[var(--line-3)]">|</span>
          <span className="text-[var(--ref)]">Local WASM SQLite</span>
        </div>
      </div>
    </section>
  );
}
