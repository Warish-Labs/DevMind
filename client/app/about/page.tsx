import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "About Us · DevMind & WarishLabs",
  description:
    "DevMind is the Continuous Project Brain for agentic software engineering. Built by WarishLabs with a local-first, zero-leak architecture.",
};

export default function AboutPage() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-16 sm:py-24">
      {/* Eyebrow Label */}
      <div className="inline-flex items-center gap-2 px-3 py-1 mb-8 rounded-chip bg-[var(--bg-1)] border border-[var(--line-1)] text-xs text-[var(--signal)] font-mono">
        <span className="inline-block w-2 h-2 rounded-full bg-[var(--signal)]" />
        <span>ABOUT DEVMIND &amp; WARISHLABS</span>
      </div>

      <h1 className="text-4xl sm:text-6xl font-display text-[var(--fg-0)] mb-6 tracking-tight leading-[1.1]">
        Deterministic Intelligence for Complex Software
      </h1>

      <p className="text-lg text-[var(--fg-1)] mb-12 max-w-2xl leading-relaxed font-sans">
        DevMind is built to bridge the trust gap between autonomous AI coding agents and
        production-grade software engineering. We believe agents cannot make safe architectural
        changes without an evidence-backed model of your codebase.
      </p>

      {/* Core Principles */}
      <div className="space-y-8 mb-16">
        <div className="p-6 sm:p-8 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]">
          <div className="text-xs font-mono uppercase text-[var(--signal)] tracking-wider mb-2">
            01 · The Problem We Solve
          </div>
          <h2 className="text-2xl font-display text-[var(--fg-0)] mb-3">
            LLMs Guess; Compilers and ASTs Know
          </h2>
          <p className="text-sm sm:text-base text-[var(--fg-1)] leading-relaxed">
            Existing developer AI tools hallucinate code boundaries, miss critical role
            authorization checks, and provide superficial diffs without understanding
            whole-repository blast radius. DevMind anchors every insight to verifiable evidence
            levels (E0 to E3), ensuring zero speculative warnings.
          </p>
        </div>

        <div className="p-6 sm:p-8 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]">
          <div className="text-xs font-mono uppercase text-[var(--ref)] tracking-wider mb-2">
            02 · Architectural Integrity
          </div>
          <h2 className="text-2xl font-display text-[var(--fg-0)] mb-3">
            Local-First &amp; Zero Unauthorized Sync
          </h2>
          <p className="text-sm sm:text-base text-[var(--fg-1)] leading-relaxed">
            By default, all code parsing, Tree-sitter extraction, and secret scanning run locally in
            the VS Code extension without making network calls. Source code never leaves your
            workstation without an explicit, consented cryptographic preview.
          </p>
        </div>

        <div className="p-6 sm:p-8 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]">
          <div className="text-xs font-mono uppercase text-[var(--warn)] tracking-wider mb-2">
            03 · Built by WarishLabs
          </div>
          <h2 className="text-2xl font-display text-[var(--fg-0)] mb-3">
            Open Engineering, Rigorous ADRs
          </h2>
          <p className="text-sm sm:text-base text-[var(--fg-1)] leading-relaxed mb-4">
            DevMind is engineered by{" "}
            <a
              href="https://warishlabs.in"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--ref)] underline underline-offset-4"
            >
              WarishLabs
            </a>{" "}
            under an open, verifiable roadmap with 47 documented Architecture Decision Records
            (ADRs) and deterministic automated test gates.
          </p>
          <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-[var(--fg-2)] pt-4 border-t border-[var(--line-1)]">
            <span>Free-tier optimized (ADR-046)</span>
            <span>·</span>
            <span>Zero plaintext secrets (ADR-047)</span>
            <span>·</span>
            <span>Modular monolith architecture</span>
          </div>
        </div>
      </div>

      {/* Navigation Footer */}
      <div className="flex items-center justify-between pt-8 border-t border-[var(--line-1)] text-sm font-mono">
        <Link href="/" className="text-[var(--ref)] hover:text-[var(--fg-0)] transition-colors">
          ← Back to Home
        </Link>
        <Link
          href="/contact"
          className="px-5 py-2.5 rounded-control bg-[var(--signal)] text-[var(--bg-0)] font-medium hover:opacity-90 transition-opacity"
        >
          Contact the Team →
        </Link>
      </div>
    </div>
  );
}
