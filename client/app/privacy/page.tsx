import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy · DevMind",
  description:
    "DevMind Privacy Policy: Local scanning by default, zero unauthorized uploads, cryptographic secret redaction, and deterministic consent boundaries.",
};

export default function PrivacyPolicyPage() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-16 sm:py-24">
      {/* Eyebrow Label */}
      <div className="inline-flex items-center gap-2 px-3 py-1 mb-8 rounded-chip bg-[var(--bg-1)] border border-[var(--line-1)] text-xs text-[var(--signal)] font-mono">
        <span className="inline-block w-2 h-2 rounded-full bg-[var(--signal)]" />
        <span>ZERO-UNAUTHORIZED-UPLOAD ARCHITECTURE</span>
      </div>

      <h1 className="text-4xl sm:text-6xl font-display text-[var(--fg-0)] mb-6 tracking-tight leading-[1.1]">
        Privacy Policy &amp; Security Ledger
      </h1>

      <p className="text-lg text-[var(--fg-1)] mb-12 max-w-2xl leading-relaxed">
        DevMind is architected around one non-negotiable invariant: your source code is your
        property. We do not quietly upload your files, train models on your proprietary logic, or
        retain secrets.
      </p>

      {/* Main Sections */}
      <div className="space-y-10 mb-16 font-sans">
        <section className="p-6 sm:p-8 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]">
          <h2 className="text-2xl font-display text-[var(--fg-0)] mb-4">
            1. Local-First Scanning by Default
          </h2>
          <p className="text-sm sm:text-base text-[var(--fg-1)] leading-relaxed mb-4">
            In standard mode (
            <code className="font-mono text-xs px-1.5 py-0.5 rounded bg-[var(--bg-2)] text-[var(--signal)]">
              metadata_only
            </code>
            ), the DevMind VS Code extension scans code locally using Tree-sitter parsers and
            deterministic rules. No code lines, file contents, or repository snapshots are uploaded
            to any server.
          </p>
          <div className="font-mono text-xs text-[var(--fg-2)] p-4 rounded-panel bg-[var(--bg-2)] border border-[var(--line-1)] space-y-1">
            <div>✓ Local manifest maintained inside VS Code</div>
            <div>✓ Diagnostics (E0/E1) emitted in editor without network calls</div>
            <div>✓ Zero external cloud egress during regular code editing</div>
          </div>
        </section>

        <section className="p-6 sm:p-8 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]">
          <h2 className="text-2xl font-display text-[var(--fg-0)] mb-4">
            2. Explicit Consent Preview for Indexed Mode
          </h2>
          <p className="text-sm sm:text-base text-[var(--fg-1)] leading-relaxed mb-4">
            When you activate deep semantic search or Project Brain indexing (
            <code className="font-mono text-xs px-1.5 py-0.5 rounded bg-[var(--bg-2)] text-[var(--ref)]">
              indexed
            </code>{" "}
            mode), source code leaves your computer only after you inspect and approve a
            cryptographic consent preview dialog.
          </p>
          <p className="text-sm text-[var(--fg-1)] leading-relaxed">
            The consent preview shows exact bytes, hashes, and files scheduled for sync. You retain
            the ability to revoke consent or purge your project data at any time from the DevMind
            dashboard.
          </p>
        </section>

        <section className="p-6 sm:p-8 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]">
          <h2 className="text-2xl font-display text-[var(--fg-0)] mb-4">
            3. Client-Side &amp; Server-Side Secret Redaction
          </h2>
          <p className="text-sm sm:text-base text-[var(--fg-1)] leading-relaxed mb-4">
            Secrets, API tokens (<code className="font-mono text-xs">sk_live_...</code>,{" "}
            <code className="font-mono text-xs">ghp_...</code>), database passwords, and
            cryptographic keys are automatically detected and replaced with secure SHA-256 hashes
            before entering log streams or leaving the workstation.
          </p>
          <p className="text-sm text-[var(--fg-1)] leading-relaxed">
            Even if a developer accidentally commits a secret into a local source file, DevMind
            prevents it from being sent to any LLM provider.
          </p>
        </section>

        <section className="p-6 sm:p-8 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]">
          <h2 className="text-2xl font-display text-[var(--fg-0)] mb-4">
            4. Zero Model Training on Customer Code
          </h2>
          <p className="text-sm sm:text-base text-[var(--fg-1)] leading-relaxed mb-4">
            DevMind does not use customer source code, AST graphs, or analysis findings to train,
            fine-tune, or improve foundation models. All LLM interactions go through our isolated
            gateway with strict zero-data-retention agreements.
          </p>
        </section>

        <section className="p-6 sm:p-8 rounded-panel bg-[var(--bg-1)] border border-[var(--line-1)]">
          <h2 className="text-2xl font-display text-[var(--fg-0)] mb-4">
            5. Data Retention &amp; Permanent Purge
          </h2>
          <p className="text-sm sm:text-base text-[var(--fg-1)] leading-relaxed">
            When a workspace or project is deleted, all associated metadata, file hashes, symbol
            relationships, and pgvector embeddings are immediately hard-deleted from our PostgreSQL
            databases and Valkey/Redis cache clusters within 24 hours.
          </p>
        </section>
      </div>

      {/* Navigation Footer */}
      <div className="flex items-center justify-between pt-8 border-t border-[var(--line-1)] text-sm font-mono">
        <Link href="/" className="text-[var(--ref)] hover:text-[var(--fg-0)] transition-colors">
          ← Back to Home
        </Link>
        <Link
          href="/disclaimer"
          className="text-[var(--fg-1)] hover:text-[var(--fg-0)] transition-colors"
        >
          Read Disclaimer &amp; Terms →
        </Link>
      </div>
    </div>
  );
}
