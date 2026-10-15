"use client";

import React, { useState, useEffect, useRef, useCallback, useSyncExternalStore } from "react";
import Link from "next/link";
import { TraceContainer } from "./TraceContainer";

function subscribeReducedMotion(callback: () => void) {
  if (typeof window === "undefined") return () => {};
  const query = window.matchMedia("(prefers-reduced-motion: reduce)");
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
}

function getReducedMotionSnapshot() {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function getServerSnapshot() {
  return false;
}

export function Hero() {
  const reducedMotion = useSyncExternalStore(
    subscribeReducedMotion,
    getReducedMotionSnapshot,
    getServerSnapshot
  );

  // Default to final frame so SSR & no-JS show full content immediately
  const [isPlaying, setIsPlaying] = useState(false);
  const [visibleLineCount, setVisibleLineCount] = useState(8);
  const [scanningActive, setScanningActive] = useState(false);
  const [scanProgress, setScanProgress] = useState(0);
  const [diagnosticActive, setDiagnosticActive] = useState(true);
  const [noteVisible, setNoteVisible] = useState(true);
  const [evidenceStep, setEvidenceStep] = useState<"empty" | "e1">("e1");
  const [rippleVisible, setRippleVisible] = useState(true);

  const timersRef = useRef<NodeJS.Timeout[]>([]);
  const hasAutoPlayedRef = useRef(false);

  const clearAllTimers = useCallback(() => {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
  }, []);

  const runSequence = useCallback(() => {
    clearAllTimers();
    setIsPlaying(true);

    // Initial reset for sequence start
    setVisibleLineCount(0);
    setScanningActive(false);
    setScanProgress(0);
    setDiagnosticActive(false);
    setNoteVisible(false);
    setEvidenceStep("empty");
    setRippleVisible(false);

    // 0.0s: Staggered line reveal (40ms each for 8 lines)
    for (let i = 1; i <= 8; i++) {
      const timer = setTimeout(() => {
        setVisibleLineCount(i);
      }, i * 40);
      timersRef.current.push(timer);
    }

    // 1.2s: Scan line travels down gutter (600ms duration)
    const scanStartTimer = setTimeout(() => {
      setScanningActive(true);
      const startTime = performance.now();
      const duration = 600;

      const stepScan = (currentTime: number) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        setScanProgress(progress);
        if (progress < 1) {
          requestAnimationFrame(stepScan);
        } else {
          setScanningActive(false);
        }
      };
      requestAnimationFrame(stepScan);
    }, 1200);
    timersRef.current.push(scanStartTimer);

    // 2.2s: Wavy underline & diagnostic glyph on line 7
    const diagTimer = setTimeout(() => {
      setDiagnosticActive(true);
    }, 2200);
    timersRef.current.push(diagTimer);

    // 3.2s: Margin note draws in and evidence bar fills to E1
    const noteTimer = setTimeout(() => {
      setNoteVisible(true);
      setEvidenceStep("e1");
    }, 3200);
    timersRef.current.push(noteTimer);

    // 5.0s: Ripple tags reveal with connectors
    const rippleTimer = setTimeout(() => {
      setRippleVisible(true);
    }, 5000);
    timersRef.current.push(rippleTimer);

    // 7.0s: Idle / sequence complete
    const finishTimer = setTimeout(() => {
      setIsPlaying(false);
    }, 7000);
    timersRef.current.push(finishTimer);
  }, [clearAllTimers]);

  useEffect(() => {
    if (!reducedMotion && !hasAutoPlayedRef.current) {
      hasAutoPlayedRef.current = true;
      const initialDelay = setTimeout(() => {
        runSequence();
      }, 150);
      return () => {
        clearTimeout(initialDelay);
        clearAllTimers();
      };
    }
    return () => clearAllTimers();
  }, [reducedMotion, runSequence, clearAllTimers]);

  return (
    <section id="section-01" className="scroll-mt-24 pt-6 sm:pt-10 flex flex-col gap-10">
      {/* Asymmetric Two-Zone Hero Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-start">
        {/* Left Column (Message & CTAs, ~5/12) */}
        <div className="lg:col-span-5 flex flex-col justify-center">
          {/* Eyebrow Label */}
          <div className="inline-flex items-center gap-2 mb-4 font-mono text-xs text-[var(--signal)]">
            <span className="text-[var(--ref)]">@@</span>
            <span className="font-semibold tracking-wider">DevMind</span>
            <span className="text-[var(--ref)]">@@</span>
          </div>

          {/* Headline */}
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-display text-[var(--fg-0)] mb-5 tracking-tight leading-[1.08]">
            Know what your code actually allows.
          </h1>

          {/* Supporting Line */}
          <p className="text-base sm:text-lg text-[var(--fg-1)] mb-8 leading-relaxed">
            DevMind keeps one evidence-backed model of your project (code, security, bugs, docs,
            reviews, deploys) and shows its work down to the line.
          </p>

          {/* CTAs */}
          <div className="flex flex-wrap items-center gap-4 mb-8">
            <Link
              href="/early-access"
              className="px-6 py-3 rounded-control text-sm font-medium bg-[var(--signal)] text-[var(--bg-0)] hover:opacity-90 transition-opacity font-mono"
            >
              Open DevMind
            </Link>

            <a
              href="#section-05"
              className="px-5 py-3 rounded-control text-sm font-medium border border-[var(--line-2)] text-[var(--fg-0)] hover:bg-[var(--bg-1)] transition-colors font-mono"
            >
              See how a finding is made ↓
            </a>

            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-chip text-xs font-mono text-[var(--fg-2)] border border-[var(--line-1)] bg-[var(--bg-1)]/50 select-none">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--warn)]" />
              <span>Extension in development</span>
            </span>
          </div>

          {/* Status Strip & Replay Control */}
          <div className="flex items-center justify-between gap-4 pt-4 border-t border-[var(--line-1)] text-xs font-mono text-[var(--fg-2)]">
            <div className="truncate">
              local-first · nothing leaves your machine without consent preview
            </div>

            {!reducedMotion && (
              <button
                type="button"
                onClick={runSequence}
                disabled={isPlaying}
                className={`shrink-0 text-[11px] underline underline-offset-4 transition-colors ${
                  isPlaying
                    ? "text-[var(--fg-2)] cursor-not-allowed opacity-50"
                    : "text-[var(--ref)] hover:text-[var(--fg-0)] cursor-pointer"
                }`}
              >
                {isPlaying ? "Scanning..." : "Replay"}
              </button>
            )}
          </div>
        </div>

        {/* Right Column: Trace Artifact (~7/12) */}
        <div className="lg:col-span-7 w-full overflow-visible">
          <TraceContainer
            visibleLineCount={visibleLineCount}
            scanningActive={scanningActive}
            scanProgress={scanProgress}
            diagnosticActive={diagnosticActive}
            noteVisible={noteVisible}
            evidenceStep={evidenceStep}
            rippleVisible={rippleVisible}
          />
        </div>
      </div>
    </section>
  );
}
