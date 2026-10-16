import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Early Access & Development Status · DevMind",
  description:
    "DevMind is in its design and build phase. Follow our open development progress, inspect the architecture, or register for early access.",
};

import { EarlyAccessForm } from "../../components/early-access/EarlyAccessForm";

export default function EarlyAccessPage() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-16 sm:py-24">
      {/* Status Chip */}
      <div className="inline-flex items-center gap-2 px-3 py-1 mb-8 rounded-chip bg-[var(--bg-1)] border border-[var(--line-1)] text-xs text-[var(--signal)] font-mono">
        <span className="inline-block w-2 h-2 rounded-full bg-[var(--signal)] animate-pulse" />
        <span>CURRENT STATUS: SPECIFICATION &amp; BUILD PHASE</span>
      </div>

      <h1 className="text-4xl sm:text-6xl font-display text-[var(--fg-0)] mb-6 tracking-tight leading-[1.1]">
        Building the Continuous Project Brain
      </h1>

      <p className="text-base sm:text-lg text-[var(--fg-1)] mb-12 max-w-2xl leading-relaxed">
        DevMind is being built entirely in public with rigorous architectural decisions and
        deterministic verification. We are not selling hype or closed prototypes.
      </p>

      {/* Grid of What Exists vs What is Next */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-16">
        <div className="p-6 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]">
          <div className="text-xs font-mono uppercase text-[var(--signal)] tracking-wider mb-3">
            ✓ Available Today
          </div>
          <h2 className="text-xl font-display text-[var(--fg-0)] mb-3">
            Open Architecture &amp; Foundations
          </h2>
          <ul className="space-y-2 text-sm text-[var(--fg-1)] leading-relaxed">
            <li className="flex items-start gap-2">
              <span className="text-[var(--signal)]">✓</span>
              <span>47 Architecture Decision Records (ADRs) fully documented</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-[var(--signal)]">✓</span>
              <span>
                Formal data models &amp; Zod schemas in <code>@devmind/common</code>
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-[var(--signal)]">✓</span>
              <span>
                Continuous integration with <code>ci-gate</code> and CodeQL
              </span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-[var(--signal)]">✓</span>
              <span>Local-first privacy model &amp; threat boundaries</span>
            </li>
          </ul>
        </div>

        <div className="p-6 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]">
          <div className="text-xs font-mono uppercase text-[var(--ref)] tracking-wider mb-3">
            ➔ Next Milestones
          </div>
          <h2 className="text-xl font-display text-[var(--fg-0)] mb-3">
            MVP Engine &amp; Companion
          </h2>
          <ul className="space-y-2 text-sm text-[var(--fg-1)] leading-relaxed">
            <li className="flex items-start gap-2">
              <span className="text-[var(--ref)]">➔</span>
              <span>Interactive homepage with hero trace &amp; brain strata (Phase S1)</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-[var(--ref)]">➔</span>
              <span>VS Code Companion extension UI &amp; local scanner (Phase S2)</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-[var(--ref)]">➔</span>
              <span>FastAPI modular monolith + PostgreSQL pgvector (Milestone M1)</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-[var(--ref)]">➔</span>
              <span>LangGraph agent orchestration &amp; E0-E3 findings</span>
            </li>
          </ul>
        </div>
      </div>

      {/* Early Access Form */}
      <div className="p-8 rounded-panel bg-[var(--bg-1)] border border-[var(--line-2)] mb-12">
        <h2 className="text-2xl font-display text-[var(--fg-0)] mb-2">Request Early Access</h2>
        <p className="text-sm text-[var(--fg-1)] mb-6 max-w-xl">
          Enter your developer email to receive notifications when testing builds for the VS Code
          extension and web workspace become available.
        </p>

        <EarlyAccessForm />
      </div>

      {/* Navigation Footer Links */}
      <div className="flex flex-wrap items-center justify-between gap-4 pt-6 border-t border-[var(--line-1)] text-xs text-[var(--fg-2)] font-mono">
        <Link href="/" className="hover:text-[var(--fg-0)] transition-colors">
          ← Back to Homepage
        </Link>
        <a
          href="https://github.com/Warish-Labs/DevMind"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-[var(--fg-0)] transition-colors"
        >
          GitHub Repository (Warish-Labs/DevMind) ↗
        </a>
      </div>
    </div>
  );
}
