"use client";

import { useSyncExternalStore } from "react";

function subscribeReducedMotion(callback: () => void) {
  if (typeof window === "undefined") return () => {};

  const query = window.matchMedia("(prefers-reduced-motion: reduce)");
  query.addEventListener("change", callback);
  window.addEventListener("storage", callback);
  window.addEventListener("devmind:motion-toggle", callback);
  window.addEventListener("devmind:preferences-changed", callback);

  return () => {
    query.removeEventListener("change", callback);
    window.removeEventListener("storage", callback);
    window.removeEventListener("devmind:motion-toggle", callback);
    window.removeEventListener("devmind:preferences-changed", callback);
  };
}

function getReducedMotionSnapshot(): boolean {
  if (typeof window === "undefined") return false;

  const stored = localStorage.getItem("devmind_reduced_motion");
  if (stored !== null) {
    return stored === "true";
  }

  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function getServerSnapshot(): boolean {
  return false;
}

export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(subscribeReducedMotion, getReducedMotionSnapshot, getServerSnapshot);
}
