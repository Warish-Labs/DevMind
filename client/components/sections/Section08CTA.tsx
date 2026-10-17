"use client";

import React, { useSyncExternalStore } from "react";
import Link from "next/link";

function subscribePreferences(callback: () => void) {
  if (typeof window === "undefined") return () => {};
  window.addEventListener("storage", callback);
  window.addEventListener("devmind:preferences-changed", callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("devmind:preferences-changed", callback);
  };
}

function getCursorSnapshot(): boolean {
  if (typeof window === "undefined") return true;
  const stored = localStorage.getItem("devmind_cursor_enabled");
  return stored !== null ? stored === "true" : true;
}

function getMotionSnapshot(): boolean {
  if (typeof window === "undefined") return false;
  const stored = localStorage.getItem("devmind_reduced_motion");
  if (stored !== null) return stored === "true";
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function getServerCursorSnapshot(): boolean {
  return true;
}

function getServerMotionSnapshot(): boolean {
  return false;
}

export function Section08CTA() {
  const cursorEnabled = useSyncExternalStore(
    subscribePreferences,
    getCursorSnapshot,
    getServerCursorSnapshot
  );

  const reducedMotionEnabled = useSyncExternalStore(
    subscribePreferences,
    getMotionSnapshot,
    getServerMotionSnapshot
  );

  const handleCursorToggle = () => {
    const nextVal = !cursorEnabled;
    if (typeof window !== "undefined") {
      localStorage.setItem("devmind_cursor_enabled", String(nextVal));
      window.dispatchEvent(new Event("devmind:preferences-changed"));
      window.dispatchEvent(new CustomEvent("devmind:cursor-toggle", { detail: nextVal }));
    }
  };

  const handleMotionToggle = () => {
    const nextVal = !reducedMotionEnabled;
    if (typeof window !== "undefined") {
      localStorage.setItem("devmind_reduced_motion", String(nextVal));
      window.dispatchEvent(new Event("devmind:preferences-changed"));
      window.dispatchEvent(new CustomEvent("devmind:motion-toggle", { detail: nextVal }));
    }
  };

  return (
    <section
      id="section-08"
      className="scroll-mt-24 p-8 sm:p-12 rounded-panel bg-[var(--bg-1)] border border-[var(--line-2)] flex flex-col gap-10 shadow-2xl"
    >
      {/* Primary Conversion CTA */}
      <div className="max-w-2xl mx-auto text-center flex flex-col items-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 mb-4 rounded-chip bg-[var(--bg-2)] border border-[var(--line-1)] text-xs text-[var(--signal)] font-mono">
          <span>BUILD PHASE · EARLY ACCESS</span>
        </div>

        <h2 className="text-3xl sm:text-4xl lg:text-5xl font-display text-[var(--fg-0)] mb-4 tracking-tight leading-tight">
          Know What Your Code Actually Allows.
        </h2>

        <p className="text-base text-[var(--fg-1)] mb-8 leading-relaxed">
          DevMind replaces fragmented tools with one evidence-backed Project Brain. Local-first
          scanning, zero unconsented data egress, and transparent free-tier infrastructure.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-4">
          <Link
            href="/early-access"
            className="px-6 py-3 rounded-control text-sm font-medium bg-[var(--signal)] text-[var(--bg-0)] hover:opacity-90 transition-opacity font-mono cursor-pointer"
          >
            Open DevMind
          </Link>
          <a
            href="https://marketplace.visualstudio.com/items?itemName=WarishLabs.devmind-vscode"
            target="_blank"
            rel="noopener noreferrer"
            className="px-6 py-3 rounded-control text-sm font-medium border border-[var(--signal)]/50 bg-[var(--bg-0)] text-[var(--fg-0)] hover:border-[var(--signal)] hover:text-[var(--signal)] transition-colors font-mono inline-flex items-center gap-2 cursor-pointer"
          >
            <span className="w-2 h-2 rounded-full bg-[var(--signal)] animate-pulse" />
            <span>Install VS Code Extension ↗</span>
          </a>
        </div>
      </div>

      {/* Interactive Preferences Control & Navigation Links */}
      <div className="pt-8 border-t border-[var(--line-1)] flex flex-col md:flex-row items-center justify-between gap-6 font-mono text-xs text-[var(--fg-2)]">
        {/* In-App Preferences Toggles */}
        <div className="flex items-center gap-4 flex-wrap">
          <span className="text-[var(--fg-1)]">Preferences:</span>

          {/* Cursor Toggle */}
          <button
            type="button"
            onClick={handleCursorToggle}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-chip border transition-colors cursor-pointer ${
              cursorEnabled
                ? "bg-[var(--ref)]/15 border-[var(--ref)] text-[var(--fg-0)]"
                : "bg-[var(--bg-0)] border-[var(--line-1)] text-[var(--fg-2)] hover:text-[var(--fg-0)]"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                cursorEnabled ? "bg-[var(--ref)]" : "bg-[var(--line-3)]"
              }`}
            />
            <span>Custom Cursor: {cursorEnabled ? "ON" : "OFF"}</span>
          </button>

          {/* Reduced Motion Toggle */}
          <button
            type="button"
            onClick={handleMotionToggle}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-chip border transition-colors cursor-pointer ${
              reducedMotionEnabled
                ? "bg-[var(--signal)]/15 border-[var(--signal)] text-[var(--fg-0)]"
                : "bg-[var(--bg-0)] border-[var(--line-1)] text-[var(--fg-2)] hover:text-[var(--fg-0)]"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                reducedMotionEnabled ? "bg-[var(--signal)]" : "bg-[var(--line-3)]"
              }`}
            />
            <span>Reduced Motion: {reducedMotionEnabled ? "ON" : "OFF"}</span>
          </button>
        </div>

        {/* Legal & Spec Quick Links */}
        <div className="flex flex-wrap items-center gap-3">
          <Link href="/about" className="hover:text-[var(--fg-0)] transition-colors">
            About
          </Link>
          <span>·</span>
          <Link href="/contact" className="hover:text-[var(--fg-0)] transition-colors">
            Contact
          </Link>
          <span>·</span>
          <Link href="/privacy" className="hover:text-[var(--fg-0)] transition-colors">
            Privacy
          </Link>
          <span>·</span>
          <Link href="/disclaimer" className="hover:text-[var(--fg-0)] transition-colors">
            Disclaimer
          </Link>
          <span>·</span>
          <span className="text-[var(--signal)] flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--signal)] animate-ping" />
            <span>Specification Phase</span>
          </span>
        </div>
      </div>
    </section>
  );
}
