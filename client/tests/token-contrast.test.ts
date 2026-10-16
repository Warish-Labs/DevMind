import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";

/**
 * Calculates WCAG 2.1 relative luminance for a given hex color string (#RRGGBB).
 */
export function getRelativeLuminance(hex: string): number {
  const cleanHex = hex.replace("#", "");
  const r = parseInt(cleanHex.substring(0, 2), 16) / 255;
  const g = parseInt(cleanHex.substring(2, 4), 16) / 255;
  const b = parseInt(cleanHex.substring(4, 6), 16) / 255;

  const toLinear = (c: number) => (c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));

  const R = toLinear(r);
  const G = toLinear(g);
  const B = toLinear(b);

  return 0.2126 * R + 0.7152 * G + 0.0722 * B;
}

/**
 * Calculates contrast ratio between two hex colors according to WCAG 2.1.
 */
export function getContrastRatio(hex1: string, hex2: string): number {
  const lum1 = getRelativeLuminance(hex1);
  const lum2 = getRelativeLuminance(hex2);
  const lighter = Math.max(lum1, lum2);
  const darker = Math.min(lum1, lum2);
  return (lighter + 0.05) / (darker + 0.05);
}

function parseTokensCss(): Record<string, string> {
  const tokensPath = path.resolve(__dirname, "../app/tokens.css");
  const content = fs.readFileSync(tokensPath, "utf8");
  const tokenMap: Record<string, string> = {};

  const matches = content.matchAll(/--([a-zA-Z0-9_-]+):\s*(#[a-fA-F0-9]{6})/g);
  for (const match of matches) {
    tokenMap[`--${match[1]}`] = match[2];
  }
  return tokenMap;
}

describe("Token Contrast Verification (docs/08 §3.2)", () => {
  const tokens = parseTokensCss();

  it("extracts core tokens from tokens.css", () => {
    expect(tokens["--bg-0"]).toBe("#0B0F12");
    expect(tokens["--bg-1"]).toBe("#10151A");
    expect(tokens["--bg-2"]).toBe("#161C22");
    expect(tokens["--fg-0"]).toBe("#E8E6E1");
    expect(tokens["--fg-1"]).toBe("#A9B0B6");
    expect(tokens["--fg-2"]).toBe("#7C858D");
    expect(tokens["--signal"]).toBe("#20E3A2");
    expect(tokens["--ref"]).toBe("#4EA1FF");
    expect(tokens["--warn"]).toBe("#F0B44C");
    expect(tokens["--danger"]).toBe("#FF6B5E");
    expect(tokens["--line-3"]).toBe("#5F6C78");
  });

  it("asserts primary text (--fg-0) achieves AAA contrast (>= 7:1) on all backgrounds", () => {
    const onBg0 = getContrastRatio(tokens["--fg-0"], tokens["--bg-0"]);
    const onBg1 = getContrastRatio(tokens["--fg-0"], tokens["--bg-1"]);
    const onBg2 = getContrastRatio(tokens["--fg-0"], tokens["--bg-2"]);

    expect(onBg0).toBeGreaterThanOrEqual(7.0);
    expect(onBg1).toBeGreaterThanOrEqual(7.0);
    expect(onBg2).toBeGreaterThanOrEqual(7.0);

    // Exact values from docs/08 §3.2 table: 15.43 / 14.72 / 13.76
    expect(onBg0).toBeCloseTo(15.43, 1);
    expect(onBg1).toBeCloseTo(14.72, 1);
    expect(onBg2).toBeCloseTo(13.76, 1);
  });

  it("asserts secondary text (--fg-1) achieves AA contrast (>= 4.5:1) on all backgrounds", () => {
    const onBg0 = getContrastRatio(tokens["--fg-1"], tokens["--bg-0"]);
    const onBg1 = getContrastRatio(tokens["--fg-1"], tokens["--bg-1"]);
    const onBg2 = getContrastRatio(tokens["--fg-1"], tokens["--bg-2"]);

    expect(onBg0).toBeGreaterThanOrEqual(4.5);
    expect(onBg1).toBeGreaterThanOrEqual(4.5);
    expect(onBg2).toBeGreaterThanOrEqual(4.5);

    // Docs/08 §3.2 table: 8.77 / 8.37 / 7.83
    expect(onBg0).toBeCloseTo(8.77, 1);
    expect(onBg1).toBeCloseTo(8.37, 1);
    expect(onBg2).toBeCloseTo(7.83, 1);
  });

  it("asserts tertiary text (--fg-2) achieves AA contrast (>= 4.5:1) on all backgrounds", () => {
    const onBg0 = getContrastRatio(tokens["--fg-2"], tokens["--bg-0"]);
    const onBg1 = getContrastRatio(tokens["--fg-2"], tokens["--bg-1"]);
    const onBg2 = getContrastRatio(tokens["--fg-2"], tokens["--bg-2"]);

    expect(onBg0).toBeGreaterThanOrEqual(4.5);
    expect(onBg1).toBeGreaterThanOrEqual(4.5);
    expect(onBg2).toBeGreaterThanOrEqual(4.5);

    // Docs/08 §3.2 table: 5.13 / 4.89 / 4.57
    expect(onBg0).toBeCloseTo(5.13, 1);
    expect(onBg1).toBeCloseTo(4.89, 1);
    expect(onBg2).toBeCloseTo(4.57, 1);
  });

  it("asserts accent colors on --bg-0 meet readable contrast thresholds", () => {
    // --signal: active, verified (11.52)
    const signalContrast = getContrastRatio(tokens["--signal"], tokens["--bg-0"]);
    expect(signalContrast).toBeGreaterThanOrEqual(7.0);
    expect(signalContrast).toBeCloseTo(11.52, 1);

    // --ref: links, focus ring (7.21)
    const refContrast = getContrastRatio(tokens["--ref"], tokens["--bg-0"]);
    expect(refContrast).toBeGreaterThanOrEqual(4.5);
    expect(refContrast).toBeCloseTo(7.21, 1);

    // --warn: medium severity (10.39)
    const warnContrast = getContrastRatio(tokens["--warn"], tokens["--bg-0"]);
    expect(warnContrast).toBeGreaterThanOrEqual(4.5);
    expect(warnContrast).toBeCloseTo(10.39, 1);

    // --danger: high/critical severity (6.89)
    const dangerContrast = getContrastRatio(tokens["--danger"], tokens["--bg-0"]);
    expect(dangerContrast).toBeGreaterThanOrEqual(4.5);
    expect(dangerContrast).toBeCloseTo(6.89, 1);
  });

  it("asserts text on filled accents (--signal / --ref) using --bg-0 meets AA/AAA", () => {
    const bg0OnSignal = getContrastRatio(tokens["--bg-0"], tokens["--signal"]);
    const bg0OnRef = getContrastRatio(tokens["--bg-0"], tokens["--ref"]);

    expect(bg0OnSignal).toBeGreaterThanOrEqual(7.0);
    expect(bg0OnRef).toBeGreaterThanOrEqual(4.5);
  });

  it("asserts control boundaries (--line-3) meet 3:1 non-text contrast on all backgrounds", () => {
    const onBg0 = getContrastRatio(tokens["--line-3"], tokens["--bg-0"]);
    const onBg1 = getContrastRatio(tokens["--line-3"], tokens["--bg-1"]);
    const onBg2 = getContrastRatio(tokens["--line-3"], tokens["--bg-2"]);

    // Must meet 3:1 per WCAG 2.1 Non-text Contrast (1.4.11)
    expect(onBg0).toBeGreaterThanOrEqual(3.0);
    expect(onBg1).toBeGreaterThanOrEqual(3.0);
    expect(onBg2).toBeGreaterThanOrEqual(3.0);

    // Docs/08 §3.2 table: 3.58 / 3.41 / 3.19
    expect(onBg0).toBeCloseTo(3.58, 1);
    expect(onBg1).toBeCloseTo(3.41, 1);
    expect(onBg2).toBeCloseTo(3.19, 1);
  });
});
