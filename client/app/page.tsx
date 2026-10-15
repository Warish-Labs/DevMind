import Link from "next/link";
import { Hero } from "../components/hero/Hero";

export default function HomePage() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 flex flex-col gap-24">
      {/* 01: Hero Trace Section */}
      <Hero />

      {/* 02: One Change / Five Consequences */}
      <section
        id="section-02"
        className="scroll-mt-24 p-8 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]"
      >
        <div className="text-xs font-mono text-[var(--ref)] mb-2 uppercase tracking-wider">
          Section 02 · Blast Radius
        </div>
        <h2 className="text-2xl sm:text-3xl font-display text-[var(--fg-0)] mb-4">
          One Change. Five Consequences.
        </h2>
        <p className="text-sm text-[var(--fg-1)] max-w-2xl leading-relaxed">
          A single route modification ripples through authentication, call graphs, living docs, pull
          request risks, and deployment health. DevMind traces the entire blast radius.
        </p>
      </section>

      {/* 03: Project Brain Strata */}
      <section
        id="section-03"
        className="scroll-mt-24 p-8 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]"
      >
        <div className="text-xs font-mono text-[var(--signal)] mb-2 uppercase tracking-wider">
          Section 03 · Knowledge Model
        </div>
        <h2 className="text-2xl sm:text-3xl font-display text-[var(--fg-0)] mb-4">
          Project Brain Strata
        </h2>
        <p className="text-sm text-[var(--fg-1)] max-w-2xl leading-relaxed">
          Ten structured layers—from raw AST and symbols to security invariants, incident history,
          and living documentation—stored in hybrid PostgreSQL + pgvector.
        </p>
      </section>

      {/* 04: Capability Index */}
      <section
        id="section-04"
        className="scroll-mt-24 p-8 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]"
      >
        <div className="text-xs font-mono text-[var(--warn)] mb-2 uppercase tracking-wider">
          Section 04 · Capabilities
        </div>
        <h2 className="text-2xl sm:text-3xl font-display text-[var(--fg-0)] mb-4">
          Nine Intelligence Capabilities
        </h2>
        <p className="text-sm text-[var(--fg-1)] max-w-2xl leading-relaxed">
          From Code and Security Intelligence in MVP to Bug Memory, Living Documentation, and
          Deployment Diagnosis in subsequent releases.
        </p>
      </section>

      {/* 05: Walkthrough Sticky Timeline */}
      <section
        id="section-05"
        className="scroll-mt-24 p-8 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]"
      >
        <div className="text-xs font-mono text-[var(--signal)] mb-2 uppercase tracking-wider">
          Section 05 · Complete Story
        </div>
        <h2 className="text-2xl sm:text-3xl font-display text-[var(--fg-0)] mb-4">
          14-Step Lifecycle Walkthrough
        </h2>
        <p className="text-sm text-[var(--fg-1)] max-w-2xl leading-relaxed">
          Follow a single administrative API endpoint from developer draft to security finding, pull
          request risk analysis, production deployment, and project health evaluation.
        </p>
      </section>

      {/* 06: Local-First Diptych */}
      <section
        id="section-06"
        className="scroll-mt-24 p-8 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]"
      >
        <div className="text-xs font-mono text-[var(--ref)] mb-2 uppercase tracking-wider">
          Section 06 · Architecture Diptych
        </div>
        <h2 className="text-2xl sm:text-3xl font-display text-[var(--fg-0)] mb-4">
          Local-First Scanning · Cloud-Assisted Brain
        </h2>
        <p className="text-sm text-[var(--fg-1)] max-w-2xl leading-relaxed">
          The VS Code companion operates entirely on your workstation without live database
          connections. Only explicitly consented metadata or chunks are ever uploaded.
        </p>
      </section>

      {/* 07: Privacy Ledger */}
      <section
        id="section-07"
        className="scroll-mt-24 p-8 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]"
      >
        <div className="text-xs font-mono text-[var(--signal)] mb-2 uppercase tracking-wider">
          Section 07 · Transparency
        </div>
        <h2 className="text-2xl sm:text-3xl font-display text-[var(--fg-0)] mb-4">
          Privacy Ledger: What Goes Where
        </h2>
        <p className="text-sm text-[var(--fg-1)] max-w-2xl leading-relaxed">
          An explicit, non-negotiable contract detailing exactly which data stays local, what is
          stored in DevMind, what is embedded, and what may reach an LLM provider.
        </p>
      </section>

      {/* 08: CTA & Release Status */}
      <section
        id="section-08"
        className="scroll-mt-24 p-12 rounded-panel bg-[var(--bg-1)] border border-[var(--line-2)] text-center"
      >
        <div className="inline-flex items-center gap-2 px-3 py-1 mb-4 rounded-chip bg-[var(--bg-2)] border border-[var(--line-1)] text-xs text-[var(--signal)] font-mono">
          <span>SPECIFICATION &amp; BUILD PHASE</span>
        </div>
        <h2 className="text-3xl sm:text-4xl font-display text-[var(--fg-0)] mb-4">
          Open Architecture. Deterministic Code Intelligence.
        </h2>
        <p className="text-sm sm:text-base text-[var(--fg-1)] max-w-xl mx-auto mb-8 leading-relaxed">
          DevMind is built with a public repository, free-tier deployment profile, and zero paid API
          surprises. Follow our progress or join the waitlist.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-4">
          <Link
            href="/early-access"
            className="px-6 py-3 rounded-control text-sm font-medium bg-[var(--signal)] text-[var(--bg-0)] hover:opacity-90 transition-opacity font-mono cursor-pointer"
          >
            Join Early Access
          </Link>
          <a
            href="https://github.com/Warish-Labs/DevMind"
            target="_blank"
            rel="noopener noreferrer"
            className="px-6 py-3 rounded-control text-sm font-medium border border-[var(--line-2)] text-[var(--fg-0)] hover:bg-[var(--bg-2)] transition-colors font-mono"
          >
            View on GitHub ↗
          </a>
        </div>
      </section>
    </div>
  );
}
