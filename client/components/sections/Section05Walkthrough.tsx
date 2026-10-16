"use client";

import React, { useState } from "react";
import { walkthroughData } from "../../lib/sections-data";

export function Section05Walkthrough() {
  const [activeStepIndex, setActiveStepIndex] = useState(0);

  const activeStep = walkthroughData[activeStepIndex] || walkthroughData[0]!;

  return (
    <section id="section-05" className="scroll-mt-24 flex flex-col gap-8">
      {/* Anchor for Secondary CTA linking to walkthrough */}
      <div id="walkthrough" className="scroll-mt-28" />

      {/* Section Header */}
      <div>
        <div className="inline-flex items-center gap-2 px-3 py-1 mb-4 rounded-chip bg-[var(--bg-1)] border border-[var(--line-1)] text-xs text-[var(--signal)] font-mono">
          <span>SECTION 05 · COMPLETE STORY</span>
        </div>
        <h2 className="text-3xl sm:text-4xl lg:text-5xl font-display text-[var(--fg-0)] mb-4 tracking-tight">
          Follow One Feature: 14-Step Lifecycle
        </h2>
        <p className="max-w-2xl text-base text-[var(--fg-1)] leading-relaxed">
          Watch a single administrative route travel from local developer draft to security finding,
          cross-agent review, pull request analysis, and production deployment diagnosis.
        </p>
      </div>

      {/* Sticky Walkthrough Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left (7/12): Step Selector Gutter List */}
        <div className="lg:col-span-7 flex flex-col gap-2 font-mono text-xs select-none">
          {walkthroughData.map((item, idx) => {
            const isActive = idx === activeStepIndex;
            const isPlanned = item.status === "planned";

            return (
              <button
                key={item.step}
                type="button"
                onClick={() => setActiveStepIndex(idx)}
                className={`flex items-start gap-3 p-3 rounded-control text-left transition-all duration-150 cursor-pointer border ${
                  isActive
                    ? "bg-[var(--bg-2)] border-[var(--signal)] shadow-md translate-x-1"
                    : "bg-[var(--bg-1)] border-[var(--line-1)] hover:border-[var(--line-2)] hover:bg-[var(--bg-2)]/30"
                }`}
              >
                {/* Step Number Badge */}
                <span
                  className={`w-7 text-center py-0.5 rounded-xs font-semibold shrink-0 text-xs ${
                    isActive
                      ? "bg-[var(--signal)] text-[var(--bg-0)]"
                      : "bg-[var(--line-1)] text-[var(--fg-1)]"
                  }`}
                >
                  {String(item.step).padStart(2, "0")}
                </span>

                {/* Step Title & Agent */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="text-[11px] font-semibold text-[var(--ref)] truncate">
                      {item.agent}
                    </span>
                    <span
                      className={`text-[9px] px-1.5 py-0.2 rounded-xs uppercase tracking-wider font-bold ${
                        isPlanned
                          ? "bg-[var(--line-1)] text-[var(--fg-1)]"
                          : "bg-[var(--signal)]/15 text-[var(--signal)]"
                      }`}
                    >
                      {item.status}
                    </span>
                  </div>
                  <p
                    className={`font-sans text-xs leading-normal line-clamp-2 ${
                      isActive ? "text-[var(--fg-0)] font-medium" : "text-[var(--fg-1)]"
                    }`}
                  >
                    {item.title}
                  </p>
                </div>
              </button>
            );
          })}
        </div>

        {/* Right (5/12): Sticky Step State & Brain Inspection Card */}
        <div className="lg:col-span-5 sticky top-24 rounded-panel bg-[var(--bg-1)] border border-[var(--line-2)] p-6 flex flex-col gap-5 shadow-2xl">
          <div className="flex items-center justify-between pb-3 border-b border-[var(--line-1)]">
            <div className="flex items-center gap-2">
              <span className="w-7 h-7 rounded-control flex items-center justify-center bg-[var(--signal)] text-[var(--bg-0)] font-mono text-xs font-bold">
                {String(activeStep.step).padStart(2, "0")}
              </span>
              <span className="font-mono text-xs text-[var(--signal)] font-medium">
                Step Inspection
              </span>
            </div>
            <span
              className={`text-[10px] font-mono px-2 py-0.5 rounded-chip uppercase tracking-wider font-bold ${
                activeStep.status === "planned"
                  ? "bg-[var(--line-1)] text-[var(--fg-1)]"
                  : "bg-[var(--signal)]/15 text-[var(--signal)] border border-[var(--signal)]/30"
              }`}
            >
              {activeStep.status}
            </span>
          </div>

          <div>
            <div className="text-[11px] font-mono text-[var(--ref)] font-semibold uppercase tracking-wider mb-1.5">
              Active Agent / Actor
            </div>
            <h3 className="text-xl font-display text-[var(--fg-0)] mb-3 font-medium">
              {activeStep.agent}
            </h3>
            <p className="text-sm text-[var(--fg-1)] leading-relaxed">{activeStep.title}</p>
          </div>

          <div className="p-4 rounded-control bg-[var(--bg-0)] border border-[var(--line-1)] flex flex-col gap-2">
            <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-[var(--warn)]">
              <span>Project Brain State</span>
              <span>LIVE SNAPSHOT</span>
            </div>
            <p className="font-mono text-xs text-[var(--signal)] leading-relaxed select-text">
              {activeStep.brainState}
            </p>
          </div>

          {/* Quick Step Navigation */}
          <div className="flex items-center justify-between pt-2 border-t border-[var(--line-1)] text-xs font-mono">
            <button
              type="button"
              disabled={activeStepIndex === 0}
              onClick={() => setActiveStepIndex((prev) => Math.max(0, prev - 1))}
              className={`px-3 py-1.5 rounded-control border transition-colors ${
                activeStepIndex === 0
                  ? "border-transparent text-[var(--fg-2)] opacity-40 cursor-not-allowed"
                  : "border-[var(--line-2)] text-[var(--fg-1)] hover:bg-[var(--bg-2)] hover:text-[var(--fg-0)] cursor-pointer"
              }`}
            >
              ← Previous Step
            </button>

            <span className="text-[var(--fg-2)]">
              {activeStepIndex + 1} / {walkthroughData.length}
            </span>

            <button
              type="button"
              disabled={activeStepIndex === walkthroughData.length - 1}
              onClick={() =>
                setActiveStepIndex((prev) => Math.min(walkthroughData.length - 1, prev + 1))
              }
              className={`px-3 py-1.5 rounded-control border transition-colors ${
                activeStepIndex === walkthroughData.length - 1
                  ? "border-transparent text-[var(--fg-2)] opacity-40 cursor-not-allowed"
                  : "border-[var(--line-2)] text-[var(--fg-1)] hover:bg-[var(--bg-2)] hover:text-[var(--fg-0)] cursor-pointer"
              }`}
            >
              Next Step →
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
