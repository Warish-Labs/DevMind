import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center px-6 py-24 text-center">
      <div className="inline-flex items-center gap-2 px-3 py-1 mb-6 rounded-chip bg-[var(--bg-2)] border border-[var(--line-1)] text-xs text-[var(--warn)] font-mono">
        <span>⚠</span>
        <span>ERROR 404 · SIGNAL LOST</span>
      </div>

      <h1 className="text-4xl sm:text-5xl font-display text-[var(--fg-0)] mb-4 tracking-tight">
        Path Not Found in Project Brain
      </h1>

      <p className="max-w-md text-sm sm:text-base text-[var(--fg-1)] mb-8 leading-relaxed">
        The requested AST node or route does not exist in the active mental model. It may have been
        refactored, deleted, or unindexed.
      </p>

      <div className="flex flex-wrap items-center justify-center gap-4">
        <Link
          href="/"
          className="inline-flex items-center justify-center px-5 py-2.5 rounded-control text-sm font-medium bg-[var(--signal)] text-[var(--bg-0)] hover:opacity-90 transition-opacity"
        >
          Return to Overview
        </Link>
        <Link
          href="/early-access"
          className="inline-flex items-center justify-center px-5 py-2.5 rounded-control text-sm font-medium border border-[var(--line-2)] text-[var(--fg-0)] hover:bg-[var(--bg-1)] transition-colors"
        >
          Early Access Status
        </Link>
      </div>
    </div>
  );
}
