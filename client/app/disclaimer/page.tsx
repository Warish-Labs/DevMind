import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Disclaimer & Terms · DevMind",
  description:
    "DevMind Disclaimer & Terms: Build phase status, evidence-backed findings (E0-E3) scope, and software usage terms.",
};

export default function DisclaimerPage() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-16 sm:py-24">
      {/* Eyebrow Label */}
      <div className="inline-flex items-center gap-2 px-3 py-1 mb-8 rounded-chip bg-[var(--bg-1)] border border-[var(--line-1)] text-xs text-[var(--warn)] font-mono">
        <span className="inline-block w-2 h-2 rounded-full bg-[var(--warn)]" />
        <span>LEGAL NOTICES &amp; EVIDENCE BOUNDARIES</span>
      </div>

      <h1 className="text-4xl sm:text-6xl font-display text-[var(--fg-0)] mb-6 tracking-tight leading-[1.1]">
        Disclaimer &amp; Terms of Service
      </h1>

      <p className="text-lg text-[var(--fg-1)] mb-12 max-w-2xl leading-relaxed">
        Please read these terms and disclaimers regarding the DevMind platform, automated code
        intelligence, and evidence classifications.
      </p>

      <div className="space-y-8 mb-16 font-sans">
        <section className="p-6 sm:p-8 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]">
          <h2 className="text-2xl font-display text-[var(--fg-0)] mb-3">
            1. Early Access &amp; Development Phase Status
          </h2>
          <p className="text-sm sm:text-base text-[var(--fg-1)] leading-relaxed">
            DevMind is currently in its specification and initial implementation phase. Features
            marked as planned or in development in the capability index are subject to active
            evolution based on continuous automated testing and community feedback. Example datasets
            and screenshots presented on the platform are explicitly labeled as fixtures.
          </p>
        </section>

        <section className="p-6 sm:p-8 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]">
          <h2 className="text-2xl font-display text-[var(--fg-0)] mb-3">
            2. Evidence Levels and Security Findings (E0 to E3)
          </h2>
          <p className="text-sm sm:text-base text-[var(--fg-1)] leading-relaxed mb-4">
            DevMind findings are classified by formal evidence tiers:
          </p>
          <ul className="space-y-2 text-sm text-[var(--fg-1)] font-mono">
            <li>
              <strong className="text-[var(--fg-0)]">E0 (Heuristic):</strong> Pattern match without
              whole-project structural verification.
            </li>
            <li>
              <strong className="text-[var(--signal)]">E1 (Single-AST):</strong> Syntactic AST
              extraction verified locally inside one source module.
            </li>
            <li>
              <strong className="text-[var(--ref)]">E2 (Cross-Module):</strong> Verified across
              caller-callee AST relationships and middleware chains.
            </li>
            <li>
              <strong className="text-[var(--fg-0)]">E3 (Provable):</strong> Verified with test or
              proof evidence. Never emitted speculatively.
            </li>
          </ul>
          <p className="text-sm text-[var(--fg-1)] leading-relaxed mt-4">
            DevMind does not label E0 or E1 findings as definitive vulnerabilities without
            resolvable code evidence. Developers remain responsible for verifying their code and
            enforcing organization-specific security policies.
          </p>
        </section>

        <section className="p-6 sm:p-8 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]">
          <h2 className="text-2xl font-display text-[var(--fg-0)] mb-3">
            3. Limitation of Liability
          </h2>
          <p className="text-sm sm:text-base text-[var(--fg-1)] leading-relaxed">
            DevMind and WarishLabs provide the software &quot;as is&quot;, without warranty of any
            kind, express or implied. In no event shall the authors or copyright holders be liable
            for any claim, damages, or other liability arising from the use of or inability to use
            the software.
          </p>
        </section>

        <section className="p-6 sm:p-8 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]">
          <h2 className="text-2xl font-display text-[var(--fg-0)] mb-3">
            4. Free Deployment Profile &amp; Fair Use
          </h2>
          <p className="text-sm sm:text-base text-[var(--fg-1)] leading-relaxed">
            Per ADR-046, public preview services operate under free-tier resource quotas (Render
            Free and Neon Free). Automated keep-alive pingers or abuse of shared rate limits are
            prohibited to ensure fair resource allocation for all community members.
          </p>
        </section>
      </div>

      {/* Navigation Footer */}
      <div className="flex items-center justify-between pt-8 border-t border-[var(--line-1)] text-sm font-mono">
        <Link href="/" className="text-[var(--ref)] hover:text-[var(--fg-0)] transition-colors">
          ← Back to Home
        </Link>
        <Link
          href="/about"
          className="text-[var(--fg-1)] hover:text-[var(--fg-0)] transition-colors"
        >
          About DevMind →
        </Link>
      </div>
    </div>
  );
}
