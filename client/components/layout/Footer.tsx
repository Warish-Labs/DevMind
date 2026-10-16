import Link from "next/link";
import Image from "next/image";

export function Footer() {
  return (
    <footer className="w-full border-t border-[var(--line-1)] bg-[var(--bg-0)] py-12 px-4 sm:px-6">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6 text-xs text-[var(--fg-1)]">
        {/* Left: Lockup and mission */}
        <div className="flex items-center gap-3">
          <Image
            src="/favicon.svg"
            alt="DevMind Logo"
            width={20}
            height={20}
            className="w-5 h-5 opacity-80"
          />
          <span className="font-mono text-[var(--fg-0)]">DevMind</span>
          <span className="text-[var(--line-3)]">·</span>
          <span>Continuous Project Brain for Agentic Software Engineering</span>
        </div>

        {/* Center: Status Note */}
        <div className="text-center md:text-left text-[var(--fg-2)] font-mono text-[11px]">
          DevMind is in its design and build phase. Example data is labeled.
        </div>

        {/* Right: Credits and links */}
        <div className="flex flex-wrap items-center justify-center md:justify-end gap-x-4 gap-y-2 text-xs font-mono">
          <Link href="/about" className="hover:text-[var(--fg-0)] transition-colors">
            About
          </Link>
          <Link href="/contact" className="hover:text-[var(--fg-0)] transition-colors">
            Contact
          </Link>
          <Link href="/privacy" className="hover:text-[var(--fg-0)] transition-colors">
            Privacy
          </Link>
          <Link href="/disclaimer" className="hover:text-[var(--fg-0)] transition-colors">
            Disclaimer
          </Link>
          <Link href="/early-access" className="hover:text-[var(--fg-0)] transition-colors">
            Early Access
          </Link>
          <a
            href="https://warishlabs.in"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-[var(--fg-0)] transition-colors text-[var(--ref)]"
          >
            WarishLabs ↗
          </a>
        </div>
      </div>
    </footer>
  );
}
