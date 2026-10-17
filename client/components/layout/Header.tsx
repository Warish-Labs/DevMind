"use client";

import Link from "next/link";
import Image from "next/image";

export function Header() {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-[var(--line-1)] bg-[var(--bg-0)]/90 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
        {/* Brand Lockup */}
        <Link
          href="/"
          className="flex items-center gap-3 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ref)] rounded-control"
        >
          <div className="relative w-7 h-7 flex-shrink-0">
            <Image
              src="/favicon.svg"
              alt="DevMind Logo"
              width={28}
              height={28}
              className="w-7 h-7"
              priority
            />
          </div>
          <span className="font-display text-xl tracking-tight text-[var(--fg-0)] group-hover:text-[var(--signal)] transition-colors">
            DevMind
          </span>
          <span className="hidden sm:inline-block text-[10px] font-mono px-1.5 py-0.5 rounded-chip bg-[var(--bg-2)] border border-[var(--line-1)] text-[var(--fg-2)] uppercase">
            Spec
          </span>
        </Link>

        {/* Navigation Links */}
        <nav
          aria-label="Main Navigation"
          className="hidden md:flex items-center gap-6 text-sm text-[var(--fg-1)]"
        >
          <Link href="/#section-01" className="hover:text-[var(--fg-0)] transition-colors">
            Trace
          </Link>
          <Link href="/#section-03" className="hover:text-[var(--fg-0)] transition-colors">
            Brain Strata
          </Link>
          <Link href="/#section-05" className="hover:text-[var(--fg-0)] transition-colors">
            Walkthrough
          </Link>
          <Link href="/#section-07" className="hover:text-[var(--fg-0)] transition-colors">
            Privacy Ledger
          </Link>
          <Link href="/about" className="hover:text-[var(--fg-0)] transition-colors">
            About
          </Link>
          <Link href="/privacy" className="hover:text-[var(--fg-0)] transition-colors">
            Privacy
          </Link>
          <Link href="/contact" className="hover:text-[var(--fg-0)] transition-colors">
            Contact
          </Link>
        </nav>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <a
            href="https://marketplace.visualstudio.com/items?itemName=WarishLabs.devmind-vscode"
            target="_blank"
            rel="noopener noreferrer"
            className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-control text-xs font-mono font-medium border border-[var(--line-2)] text-[var(--fg-1)] hover:text-[var(--fg-0)] hover:bg-[var(--bg-1)] transition-colors"
          >
            <span>VS Code Extension</span>
            <span className="text-[var(--signal)]">↗</span>
          </a>
          <Link
            href="/early-access"
            className="inline-flex items-center justify-center px-4 py-2 rounded-control text-xs sm:text-sm font-medium bg-[var(--signal)] text-[var(--bg-0)] hover:opacity-90 transition-opacity font-mono cursor-pointer"
          >
            Open DevMind
          </Link>
        </div>
      </div>
    </header>
  );
}
