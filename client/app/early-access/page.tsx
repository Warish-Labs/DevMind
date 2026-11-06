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

      <p className="text-base sm:text-lg text-[var(--fg-1)] mb-8 max-w-2xl leading-relaxed">
        DevMind is being built entirely in public with rigorous architectural decisions and
        deterministic verification. We are not selling hype or closed prototypes.
      </p>

      {/* Platform Access Hub - Sign In / Sign Up Cards */}
      <div className="mb-12 p-6 sm:p-8 rounded-panel border border-[var(--signal)]/40 bg-[var(--bg-1)] shadow-lg">
        <div className="mb-6 pb-6 border-b border-[var(--line-1)]">
          <div className="text-xs font-mono uppercase tracking-wider text-[var(--signal)] font-semibold mb-1">
            Platform Authentication · Clerk Live Integration
          </div>
          <h2 className="text-2xl font-display text-[var(--fg-0)]">
            Sign In or Create Your Account
          </h2>
          <p className="text-sm text-[var(--fg-1)] mt-1">
            Access your Project Brain, developer workspaces, AST findings, and architectural scans.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Link
            href="/sign-up"
            className="p-5 rounded-control border border-[var(--signal)] bg-[var(--signal)]/10 hover:bg-[var(--signal)]/20 transition-all flex flex-col justify-between group cursor-pointer"
          >
            <div>
              <div className="text-xs font-mono uppercase text-[var(--signal)] font-semibold mb-1">
                New User
              </div>
              <div className="text-lg font-semibold text-[var(--fg-0)] group-hover:text-[var(--signal)] transition-colors">
                Create Account (Sign Up) →
              </div>
              <p className="text-xs text-[var(--fg-1)] mt-2">
                Register via Clerk with GitHub, Google, or Email to start a Project Brain.
              </p>
            </div>
            <span className="mt-4 inline-flex items-center text-xs font-mono text-[var(--signal)] font-medium">
              Register with Clerk →
            </span>
          </Link>

          <Link
            href="/sign-in"
            className="p-5 rounded-control border border-[var(--line-2)] bg-[var(--bg-0)] hover:border-[var(--signal)]/60 transition-all flex flex-col justify-between group cursor-pointer"
          >
            <div>
              <div className="text-xs font-mono uppercase text-[var(--ref)] font-semibold mb-1">
                Returning User
              </div>
              <div className="text-lg font-semibold text-[var(--fg-0)] group-hover:text-[var(--ref)] transition-colors">
                Sign In with Clerk →
              </div>
              <p className="text-xs text-[var(--fg-1)] mt-2">
                Log into your existing workspace, inspect active scans, and review pull requests.
              </p>
            </div>
            <span className="mt-4 inline-flex items-center text-xs font-mono text-[var(--ref)] font-medium">
              Open Sign-In Screen →
            </span>
          </Link>

          <Link
            href="/workspaces"
            className="p-5 rounded-control border border-[var(--line-1)] bg-[var(--bg-0)] hover:border-[var(--line-2)] transition-all flex flex-col justify-between group cursor-pointer"
          >
            <div>
              <div className="text-xs font-mono uppercase text-[var(--fg-2)] font-semibold mb-1">
                Already Signed In?
              </div>
              <div className="text-lg font-semibold text-[var(--fg-0)] group-hover:text-[var(--signal)] transition-colors">
                Open Workspaces Dashboard →
              </div>
              <p className="text-xs text-[var(--fg-1)] mt-2">
                Jump directly to your active workspaces, projects, and findings.
              </p>
            </div>
            <span className="mt-4 inline-flex items-center text-xs font-mono text-[var(--fg-2)] font-medium">
              View Workspaces →
            </span>
          </Link>
        </div>
      </div>

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
              <span>49 Architecture Decision Records (ADRs) fully documented</span>
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
          <div className="text-xs font-mono uppercase text-[var(--signal)] tracking-wider mb-3">
            ● Available on Marketplace
          </div>
          <h2 className="text-xl font-display text-[var(--fg-0)] mb-2">
            VS Code Companion Extension
          </h2>
          <p className="text-sm text-[var(--fg-1)] mb-4 leading-relaxed">
            The official DevMind Companion is published on Visual Studio Marketplace. Install it
            directly in VS Code for local-first AST scanning and privacy audits:
          </p>
          <div className="p-3 rounded-control bg-[var(--bg-0)] border border-[var(--line-2)] font-mono text-xs text-[var(--signal)] mb-4 select-all">
            ext install WarishLabs.devmind-vscode
          </div>
          <a
            href="https://marketplace.visualstudio.com/items?itemName=WarishLabs.devmind-vscode"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-control text-xs font-mono font-medium border border-[var(--signal)]/50 bg-[var(--signal)]/10 text-[var(--fg-0)] hover:bg-[var(--signal)] hover:text-[var(--bg-0)] transition-colors"
          >
            <span>Install from VS Code Marketplace</span>
            <span>↗</span>
          </a>
        </div>
      </div>

      {/* Early Access Form */}
      <div className="p-8 rounded-panel bg-[var(--bg-1)] border border-[var(--line-2)] mb-12">
        <h2 className="text-2xl font-display text-[var(--fg-0)] mb-2">Request Early Access</h2>
        <p className="text-sm text-[var(--fg-1)] mb-6 max-w-xl">
          Enter your developer email to join the cloud workspace private beta and receive product
          updates. You can install the companion extension right now from the Marketplace above.
        </p>

        <EarlyAccessForm />
      </div>

      {/* Navigation Footer Links */}
      <div className="flex flex-wrap items-center justify-between gap-4 pt-6 border-t border-[var(--line-1)] text-xs text-[var(--fg-2)] font-mono">
        <Link href="/" className="hover:text-[var(--fg-0)] transition-colors">
          ← Back to Homepage
        </Link>
        <a
          href="https://marketplace.visualstudio.com/items?itemName=WarishLabs.devmind-vscode"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-[var(--fg-0)] transition-colors text-[var(--signal)]"
        >
          VS Code Extension (Marketplace) ↗
        </a>
      </div>
    </div>
  );
}
