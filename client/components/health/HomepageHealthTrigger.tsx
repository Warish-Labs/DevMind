"use client";

import { useEffect } from "react";
import { triggerHomepageHealthCheck } from "../../lib/health/health-check";

/**
 * Non-blocking client trigger for backend liveness probe on homepage visit.
 * Throttled to at most once per hour per browser.
 */
export function HomepageHealthTrigger() {
  useEffect(() => {
    // Run after initial render without blocking any interactivity
    const timer = setTimeout(() => {
      void triggerHomepageHealthCheck();
    }, 100);

    return () => clearTimeout(timer);
  }, []);

  return null;
}
