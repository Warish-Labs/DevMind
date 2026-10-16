"use client";

import React, { useEffect, useRef } from "react";
import {
  dampLerp,
  calculateMagneticOffset,
  resolveCursorState,
  CursorState,
  MagneticTarget,
} from "../../lib/motion/cursor-math";

export function DevMindCursor() {
  const dotRef = useRef<HTMLDivElement>(null);
  const ringRef = useRef<HTMLDivElement>(null);
  const labelRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    // 1. Guard check: only fine pointers with hover capability, no reduced motion, and toggle enabled
    if (typeof window === "undefined") return;

    const isFinePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
    if (!isFinePointer) return;

    const checkPreferences = () => {
      try {
        const storedMotion = localStorage.getItem("devmind_reduced_motion");
        const reducedMotion =
          storedMotion !== null
            ? storedMotion === "true"
            : window.matchMedia("(prefers-reduced-motion: reduce)").matches;

        if (reducedMotion) return false;

        const storedCursor = localStorage.getItem("devmind_cursor_enabled");
        return storedCursor !== "false";
      } catch {
        return true;
      }
    };

    let isEnabled = checkPreferences();
    if (isEnabled) {
      document.documentElement.classList.add("has-custom-cursor");
    } else {
      document.documentElement.classList.remove("has-custom-cursor");
    }

    // Cursor state variables (no React state per frame to guarantee 60/120fps)
    let pointerX = -100;
    let pointerY = -100;
    let ringX = -100;
    let ringY = -100;
    let isPressed = false;
    let isVisible = false;
    let currentState: CursorState = "default";
    let currentLabel: string | undefined = undefined;
    let magneticTarget: MagneticTarget | null = null;
    let lastMoveTime = performance.now();
    let rafId: number | null = null;
    let lastFrameTime = performance.now();

    const dotEl = dotRef.current;
    const ringEl = ringRef.current;
    const labelEl = labelRef.current;

    // Update visual styles based on cursor state
    const applyStateStyles = (state: CursorState, label?: string) => {
      if (!ringEl || !dotEl) return;

      if (state === "hidden") {
        ringEl.style.opacity = "0";
        dotEl.style.opacity = "0";
        return;
      }

      ringEl.style.opacity = "1";
      dotEl.style.opacity = "1";

      if (state === "link") {
        ringEl.style.width = "44px";
        ringEl.style.height = "44px";
        ringEl.style.borderRadius = "9999px";
        ringEl.style.borderColor = "var(--ref)";
        ringEl.style.backgroundColor = "rgba(78, 161, 255, 0.12)";
        ringEl.style.transform = `translate3d(${ringX - 22}px, ${ringY - 22}px, 0)`;
        if (labelEl) labelEl.textContent = "";
      } else if (state === "text") {
        ringEl.style.width = "2px";
        ringEl.style.height = "22px";
        ringEl.style.borderRadius = "2px";
        ringEl.style.borderColor = "var(--signal)";
        ringEl.style.backgroundColor = "var(--signal)";
        ringEl.style.transform = `translate3d(${ringX - 1}px, ${ringY - 11}px, 0)`;
        if (labelEl) labelEl.textContent = "";
      } else if (state === "hotspot") {
        ringEl.style.width = "48px";
        ringEl.style.height = "48px";
        ringEl.style.borderRadius = "9999px";
        ringEl.style.borderColor = "var(--signal)";
        ringEl.style.backgroundColor = "rgba(32, 227, 162, 0.1)";
        ringEl.style.transform = `translate3d(${ringX - 24}px, ${ringY - 24}px, 0)`;
        if (labelEl) labelEl.textContent = label || "inspect";
      } else if (state === "pressed") {
        ringEl.style.width = "24px";
        ringEl.style.height = "24px";
        ringEl.style.borderRadius = "9999px";
        ringEl.style.borderColor = "var(--ref)";
        ringEl.style.backgroundColor = "transparent";
        ringEl.style.transform = `translate3d(${ringX - 12}px, ${ringY - 12}px, 0)`;
        if (labelEl) labelEl.textContent = "";
      } else {
        // default state: 28px ring, 8px dot
        ringEl.style.width = "28px";
        ringEl.style.height = "28px";
        ringEl.style.borderRadius = "9999px";
        ringEl.style.borderColor = "var(--ref)";
        ringEl.style.backgroundColor = "transparent";
        ringEl.style.transform = `translate3d(${ringX - 14}px, ${ringY - 14}px, 0)`;
        if (labelEl) labelEl.textContent = "";
      }
    };

    // Frame animation loop
    const onFrame = (now: number) => {
      const dtSeconds = Math.min((now - lastFrameTime) / 1000, 0.1);
      lastFrameTime = now;

      // Calculate magnetic offset
      const magnet = calculateMagneticOffset(pointerX, pointerY, magneticTarget, 8);
      const targetRingX = pointerX + magnet.x;
      const targetRingY = pointerY + magnet.y;

      // Smoothed critically damped lerp for ring
      ringX = dampLerp(ringX, targetRingX, 16, dtSeconds);
      ringY = dampLerp(ringY, targetRingY, 16, dtSeconds);

      // Write direct transform3d styles
      if (dotEl) {
        dotEl.style.transform = `translate3d(${pointerX - 4}px, ${pointerY - 4}px, 0)`;
      }

      applyStateStyles(currentState, currentLabel);

      // Pause loop after 1s of inactivity to conserve GPU/CPU cycles
      if (now - lastMoveTime < 1000) {
        rafId = requestAnimationFrame(onFrame);
      } else {
        rafId = null;
      }
    };

    const scheduleFrame = () => {
      lastMoveTime = performance.now();
      if (!rafId) {
        lastFrameTime = performance.now();
        rafId = requestAnimationFrame(onFrame);
      }
    };

    // Event handlers
    const onPointerMove = (e: PointerEvent) => {
      pointerX = e.clientX;
      pointerY = e.clientY;
      if (!isVisible) {
        isVisible = true;
        ringX = pointerX;
        ringY = pointerY;
      }

      // Check target element without heavy layout reads
      const targetEl = e.target as HTMLElement | null;
      const resolved = resolveCursorState(targetEl, isPressed, isVisible);
      currentState = resolved.state;
      currentLabel = resolved.label;

      // Cache magnetic target rect only if hovering a button/link
      if (resolved.state === "link" && targetEl) {
        const interactive = targetEl.closest("a, button, [role='button']") as HTMLElement | null;
        if (interactive) {
          const rect = interactive.getBoundingClientRect();
          magneticTarget = {
            centerX: rect.left + rect.width / 2,
            centerY: rect.top + rect.height / 2,
            radius: Math.max(rect.width, rect.height) / 2,
          };
        } else {
          magneticTarget = null;
        }
      } else {
        magneticTarget = null;
      }

      scheduleFrame();
    };

    const onPointerDown = () => {
      isPressed = true;
      currentState = "pressed";
      scheduleFrame();
    };

    const onPointerUp = (e: PointerEvent) => {
      isPressed = false;
      const targetEl = e.target as HTMLElement | null;
      const resolved = resolveCursorState(targetEl, false, isVisible);
      currentState = resolved.state;
      currentLabel = resolved.label;
      scheduleFrame();
    };

    const onMouseLeave = () => {
      isVisible = false;
      currentState = "hidden";
      scheduleFrame();
    };

    // Preferences toggle listener
    const onPreferencesChanged = () => {
      isEnabled = checkPreferences();
      if (!isEnabled) {
        document.documentElement.classList.remove("has-custom-cursor");
        if (dotEl) dotEl.style.display = "none";
        if (ringEl) ringEl.style.display = "none";
        if (rafId) {
          cancelAnimationFrame(rafId);
          rafId = null;
        }
      } else {
        document.documentElement.classList.add("has-custom-cursor");
        if (dotEl) {
          dotEl.style.display = "block";
          dotEl.style.opacity = "1";
        }
        if (ringEl) {
          ringEl.style.display = "flex";
          ringEl.style.opacity = "1";
        }
        isVisible = true;
        scheduleFrame();
      }
    };

    window.addEventListener("pointermove", onPointerMove, { passive: true });
    window.addEventListener("pointerdown", onPointerDown, { passive: true });
    window.addEventListener("pointerup", onPointerUp, { passive: true });
    document.addEventListener("mouseleave", onMouseLeave);
    window.addEventListener("devmind:preferences-changed", onPreferencesChanged);
    window.addEventListener("devmind:cursor-toggle", onPreferencesChanged);
    window.addEventListener("storage", onPreferencesChanged);

    // Initial display sync
    if (!isEnabled) {
      if (dotEl) dotEl.style.display = "none";
      if (ringEl) ringEl.style.display = "none";
    }

    return () => {
      document.documentElement.classList.remove("has-custom-cursor");
      if (rafId) cancelAnimationFrame(rafId);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("pointerup", onPointerUp);
      document.removeEventListener("mouseleave", onMouseLeave);
      window.removeEventListener("devmind:preferences-changed", onPreferencesChanged);
      window.removeEventListener("devmind:cursor-toggle", onPreferencesChanged);
      window.removeEventListener("storage", onPreferencesChanged);
    };
  }, []);

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-50 overflow-hidden select-none"
    >
      {/* Evidence Node Core Dot (8px, --signal) */}
      <div
        ref={dotRef}
        className="fixed top-0 left-0 w-2 h-2 rounded-full bg-[var(--signal)] pointer-events-none shadow-sm opacity-0 transition-opacity duration-150 will-change-transform"
        style={{ transform: "translate3d(-100px, -100px, 0)" }}
      />

      {/* Lagged Tracker Ring (28px default, --ref, magnetic) */}
      <div
        ref={ringRef}
        className="fixed top-0 left-0 w-7 h-7 rounded-full border border-[var(--ref)] pointer-events-none flex items-center justify-center opacity-0 transition-[width,height,background-color,border-color,border-radius] duration-200 ease-out will-change-transform shadow-xs"
        style={{ transform: "translate3d(-100px, -100px, 0)" }}
      >
        <span
          ref={labelRef}
          className="text-[9px] font-mono uppercase tracking-wider text-[var(--signal)] font-bold pointer-events-none select-none"
        />
      </div>
    </div>
  );
}
