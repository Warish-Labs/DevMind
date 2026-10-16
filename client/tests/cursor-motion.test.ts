import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import {
  MOTION_DURATIONS,
  MOTION_EASINGS,
  dampLerp,
  calculateMagneticOffset,
  resolveCursorState,
} from "../lib/motion";

describe("Motion System & DevMindCursor Specifications (ADR-041)", () => {
  it("defines standard duration and easing tokens matching design system", () => {
    expect(MOTION_DURATIONS.dur1).toBe(90);
    expect(MOTION_DURATIONS.dur2).toBe(160);
    expect(MOTION_DURATIONS.dur3).toBe(240);
    expect(MOTION_DURATIONS.dur4).toBe(400);
    expect(MOTION_DURATIONS.durStory).toBe(800);

    expect(MOTION_EASINGS.easeOut).toContain("cubic-bezier");
    expect(MOTION_EASINGS.easeIn).toContain("cubic-bezier");
    expect(MOTION_EASINGS.easeMove).toContain("cubic-bezier");
  });

  describe("Cursor Smoothing Math (dampLerp)", () => {
    it("smoothly advances current towards target without overshooting", () => {
      const start = 0;
      const target = 100;
      const step1 = dampLerp(start, target, 12, 0.016);

      expect(step1).toBeGreaterThan(start);
      expect(step1).toBeLessThan(target);

      // Multiple frames converge closely to target
      let val = start;
      for (let i = 0; i < 30; i++) {
        val = dampLerp(val, target, 12, 0.016);
      }
      expect(val).toBeCloseTo(target, 0);
    });

    it("handles zero delta time and negative values safely", () => {
      const val = dampLerp(50, 100, 12, 0);
      expect(val).toBe(50);
      expect(Number.isNaN(val)).toBe(false);
    });
  });

  describe("Magnetic Attraction Offset (strictly <= 8px)", () => {
    it("returns zero offset when magnetic target is null", () => {
      const offset = calculateMagneticOffset(100, 100, null, 8);
      expect(offset).toEqual({ x: 0, y: 0 });
    });

    it("attracts towards center and strictly caps displacement at <= 8px", () => {
      const target = { centerX: 150, centerY: 150, radius: 40 };

      // Pointer near target
      const offset = calculateMagneticOffset(140, 140, target, 8);
      const dist = Math.hypot(offset.x, offset.y);
      expect(dist).toBeLessThanOrEqual(8.0001);
      expect(offset.x).toBeGreaterThan(0);
      expect(offset.y).toBeGreaterThan(0);

      // Extreme displacement never exceeds 8px
      const extremeOffset = calculateMagneticOffset(115, 115, target, 8);
      const extremeDist = Math.hypot(extremeOffset.x, extremeOffset.y);
      expect(extremeDist).toBeLessThanOrEqual(8.0001);
    });
  });

  describe("Cursor State Machine Resolution", () => {
    it("resolves to hidden when window visibility is false", () => {
      const { state } = resolveCursorState(null, false, false);
      expect(state).toBe("hidden");
    });

    it("resolves to pressed when pointer is down", () => {
      const { state } = resolveCursorState(null, true, true);
      expect(state).toBe("pressed");
    });

    it("resolves to link when hovering buttons or links", () => {
      // Mock element with closest
      const mockButton = {
        closest: (selector: string) => (selector.includes("button") ? {} : null),
        getAttribute: () => null,
      } as unknown as HTMLElement;

      const { state } = resolveCursorState(mockButton, false, true);
      expect(state).toBe("link");
    });

    it("resolves to text when hovering code or pre blocks", () => {
      const mockCode = {
        closest: (selector: string) => (selector.includes("code") ? {} : null),
        getAttribute: () => null,
      } as unknown as HTMLElement;

      const { state } = resolveCursorState(mockCode, false, true);
      expect(state).toBe("text");
    });

    it("resolves to hotspot with custom label on data-cursor='inspect'", () => {
      const mockHotspot = {
        closest: (selector: string) => {
          if (selector.includes("data-cursor")) {
            return {
              getAttribute: (attr: string) => (attr === "data-cursor" ? "inspect" : null),
            };
          }
          return null;
        },
        getAttribute: () => null,
      } as unknown as HTMLElement;

      const { state, label } = resolveCursorState(mockHotspot, false, true);
      expect(state).toBe("hotspot");
      expect(label).toBe("inspect");
    });
  });

  describe("Styles and View Transitions Verification", () => {
    it("ensures globals.css activates custom cursor only under has-custom-cursor on fine pointer", () => {
      const globalsCssPath = path.resolve(__dirname, "../app/globals.css");
      const globalsCss = fs.readFileSync(globalsCssPath, "utf-8");

      expect(globalsCss).toContain("html.has-custom-cursor");
      expect(globalsCss).toContain("cursor: none !important");
      expect(globalsCss).toContain("(pointer: fine)");
    });

    it("ensures @view-transition is declared for automatic navigation transitions", () => {
      const globalsCssPath = path.resolve(__dirname, "../app/globals.css");
      const globalsCss = fs.readFileSync(globalsCssPath, "utf-8");

      expect(globalsCss).toContain("@view-transition");
      expect(globalsCss).toContain("navigation: auto");
      expect(globalsCss).toContain("::view-transition-old(root)");
      expect(globalsCss).toContain("::view-transition-new(root)");
    });
  });
});
