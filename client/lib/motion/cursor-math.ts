/**
 * DevMind Cursor Smoothing Math and State Types
 * Source of truth: docs/ANTIGRAVITY_PROMPT.md §6.4 (ADR-041)
 */

export type CursorState = "default" | "link" | "text" | "hotspot" | "pressed" | "hidden";

export interface CursorPosition {
  x: number;
  y: number;
}

export interface MagneticTarget {
  centerX: number;
  centerY: number;
  radius: number;
}

/**
 * Frame-rate independent critically damped lerp.
 * factor between 0.16 and 0.22 at 60fps (~16.6ms).
 */
export function dampLerp(
  current: number,
  target: number,
  speed: number = 12,
  dtSeconds: number = 0.016
): number {
  const t = 1 - Math.exp(-speed * Math.max(0, Math.min(dtSeconds, 0.1)));
  return current + (target - current) * t;
}

/**
 * Calculates magnetic attraction toward element center.
 * Strictly capped at <= 8px per ADR-041 / ANTIGRAVITY_PROMPT.md §6.4.
 */
export function calculateMagneticOffset(
  pointerX: number,
  pointerY: number,
  target: MagneticTarget | null,
  maxOffset: number = 8
): CursorPosition {
  if (!target) return { x: 0, y: 0 };

  const dx = target.centerX - pointerX;
  const dy = target.centerY - pointerY;
  const distance = Math.hypot(dx, dy);

  if (distance === 0 || distance > target.radius * 1.5) {
    return { x: 0, y: 0 };
  }

  // Linear magnetic falloff from center to edge
  const strength = Math.max(0, 1 - distance / (target.radius * 1.5));
  const pull = Math.min(distance * strength * 0.35, maxOffset);

  const angle = Math.atan2(dy, dx);
  return {
    x: Math.cos(angle) * pull,
    y: Math.sin(angle) * pull,
  };
}

/**
 * Resolves cursor state from DOM element or target metadata.
 */
export function resolveCursorState(
  element: HTMLElement | null,
  isPressed: boolean,
  isWindowVisible: boolean
): { state: CursorState; label?: string } {
  if (!isWindowVisible) {
    return { state: "hidden" };
  }

  if (isPressed) {
    return { state: "pressed" };
  }

  if (!element) {
    return { state: "default" };
  }

  // 1. Hotspot check (data-cursor="inspect" or data-cursor="replay")
  const hotspotAttr = element.closest("[data-cursor]")?.getAttribute("data-cursor");
  if (
    hotspotAttr &&
    hotspotAttr !== "link" &&
    hotspotAttr !== "text" &&
    hotspotAttr !== "default"
  ) {
    return { state: "hotspot", label: hotspotAttr };
  }

  // 2. Text/Code check
  if (
    hotspotAttr === "text" ||
    element.closest("pre, code, input[type='text'], textarea, [contenteditable='true']")
  ) {
    return { state: "text" };
  }

  // 3. Link/Button check
  if (
    hotspotAttr === "link" ||
    element.closest("a, button, [role='button'], [role='tab'], select, input[type='submit']")
  ) {
    return { state: "link" };
  }

  return { state: "default" };
}
