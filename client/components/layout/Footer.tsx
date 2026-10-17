import Image from "next/image";
import Link from "next/link";

export function Footer() {
  return (
    <footer className="w-full border-t border-[var(--line-1)] bg-[var(--bg-0)] py-16 px-4 sm:px-6 lg:px-8 text-xs text-[var(--fg-1)]">
      <div className="max-w-7xl mx-auto flex flex-col gap-12">
        {/* Top Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-8 lg:gap-12">
          {/* Brand & Vision (5 columns) */}
          <div className="lg:col-span-5 flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <Image
                src="/favicon.svg"
                alt="DevMind Logo"
                width={22}
                height={22}
                className="w-5 h-5 opacity-90"
              />
              <span className="font-mono text-sm font-semibold tracking-tight text-[var(--fg-0)]">
                DevMind
              </span>
              <span className="text-[var(--line-3)]">·</span>
              <span className="text-[11px] font-mono text-[var(--fg-2)]">Project Brain Engine</span>
            </div>

            <p className="text-xs leading-relaxed text-[var(--fg-1)] max-w-sm">
              Continuous Project Brain for Agentic Software Engineering. Grounding autonomous coding
              agents in deterministic codebase reality, evidence-ranked blast radius, and
              permission-aware boundaries.
            </p>

            {/* System Status Pill */}
            <div className="flex items-center gap-2 pt-2">
              <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-[var(--bg-1)] border border-[var(--line-1)] font-mono text-[11px] text-[var(--fg-2)]">
                <span className="w-1.5 h-1.5 rounded-full bg-[var(--signal)] animate-pulse" />
                <span className="text-[var(--fg-0)]">Operational</span>
                <span className="text-[var(--line-3)]">·</span>
                <span>System Active</span>
              </div>
            </div>
          </div>

          {/* Architecture & Strata (2 columns) */}
          <div className="lg:col-span-2 flex flex-col gap-3 font-mono">
            <span className="text-[var(--fg-0)] font-semibold uppercase tracking-wider text-[11px]">
              Architecture
            </span>
            <ul className="flex flex-col gap-2 text-[11px] text-[var(--fg-2)]">
              <li>
                <Link href="/#section-02" className="hover:text-[var(--fg-0)] transition-colors">
                  02 Blast Radius
                </Link>
              </li>
              <li>
                <Link href="/#section-03" className="hover:text-[var(--fg-0)] transition-colors">
                  03 Brain Strata
                </Link>
              </li>
              <li>
                <Link href="/#section-04" className="hover:text-[var(--fg-0)] transition-colors">
                  04 Capability Index
                </Link>
              </li>
              <li>
                <Link href="/#walkthrough" className="hover:text-[var(--fg-0)] transition-colors">
                  05 Walkthrough
                </Link>
              </li>
              <li>
                <Link href="/#section-06" className="hover:text-[var(--fg-0)] transition-colors">
                  06 Local-first Sync
                </Link>
              </li>
              <li>
                <Link href="/#section-07" className="hover:text-[var(--fg-0)] transition-colors">
                  07 Privacy Ledger
                </Link>
              </li>
            </ul>
          </div>

          {/* Developer & Specs (3 columns) */}
          <div className="lg:col-span-3 flex flex-col gap-3 font-mono">
            <span className="text-[var(--fg-0)] font-semibold uppercase tracking-wider text-[11px]">
              Open Engine & Specs
            </span>
            <ul className="flex flex-col gap-2 text-[11px] text-[var(--fg-2)]">
              <li>
                <a
                  href="https://marketplace.visualstudio.com/items?itemName=WarishLabs.devmind-vscode"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[var(--signal)] hover:underline inline-flex items-center gap-1 font-semibold"
                >
                  VS Code Extension (Marketplace) ↗
                </a>
              </li>
              <li>
                <Link
                  href="/early-access"
                  className="hover:text-[var(--fg-0)] transition-colors inline-flex items-center gap-1 text-[var(--signal)]"
                >
                  Early Access Waitlist →
                </Link>
              </li>
              <li>
                <Link
                  href="/privacy"
                  className="hover:text-[var(--fg-0)] transition-colors inline-flex items-center gap-1"
                >
                  Privacy Ledger &amp; Security →
                </Link>
              </li>
              <li>
                <Link
                  href="/disclaimer"
                  className="hover:text-[var(--fg-0)] transition-colors inline-flex items-center gap-1"
                >
                  Security Disclaimer →
                </Link>
              </li>
              <li>
                <Link
                  href="/contact"
                  className="hover:text-[var(--fg-0)] transition-colors inline-flex items-center gap-1"
                >
                  Developer Support →
                </Link>
              </li>
            </ul>
          </div>

          {/* Legal & Governance (2 columns) */}
          <div className="lg:col-span-2 flex flex-col gap-3 font-mono">
            <span className="text-[var(--fg-0)] font-semibold uppercase tracking-wider text-[11px]">
              WarishLabs
            </span>
            <ul className="flex flex-col gap-2 text-[11px] text-[var(--fg-2)]">
              <li>
                <Link href="/about" className="hover:text-[var(--fg-0)] transition-colors">
                  About DevMind
                </Link>
              </li>
              <li>
                <Link href="/contact" className="hover:text-[var(--fg-0)] transition-colors">
                  Contact Team
                </Link>
              </li>
              <li>
                <Link href="/privacy" className="hover:text-[var(--fg-0)] transition-colors">
                  Privacy Policy
                </Link>
              </li>
              <li>
                <Link href="/disclaimer" className="hover:text-[var(--fg-0)] transition-colors">
                  Security Disclaimer
                </Link>
              </li>
              <li>
                <a
                  href="https://warishlabs.in"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-[var(--fg-0)] transition-colors text-[var(--ref)] inline-flex items-center gap-1"
                >
                  WarishLabs ↗
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Sub-Footer Bar */}
        <div className="pt-8 border-t border-[var(--line-1)] flex flex-col sm:flex-row items-center justify-between gap-4 font-mono text-[11px] text-[var(--fg-2)]">
          <div className="flex items-center gap-2 flex-wrap text-center sm:text-left">
            <span>© 2026 WarishLabs.</span>
            <span className="text-[var(--line-3)]">·</span>
            <span>Local-first architecture · Zero unconsented source egress.</span>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-[var(--signal)]">Continuous Project Brain</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
