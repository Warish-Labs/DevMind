import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import {
  HERO_RULE_ID,
  HERO_CODE_LINES,
  HERO_MARGIN_NOTE,
  HERO_RIPPLE_TAGS,
} from "../lib/hero-data";
import { CheckIcon, CrossIcon } from "../components/hero/TraceIcons";

const ROOT_DIR = path.resolve(__dirname, "../..");
const RULE_CATALOG_PATH = path.join(ROOT_DIR, "common/data/rule-catalog.json");

describe("Hero Trace Specification & Integrity", () => {
  it("strictly matches a verified rule in rule-catalog.json", () => {
    expect(fs.existsSync(RULE_CATALOG_PATH)).toBe(true);
    const catalogRaw = fs.readFileSync(RULE_CATALOG_PATH, "utf-8");
    const catalog = JSON.parse(catalogRaw);

    const matchingRule = catalog.rules.find((r: { rule_id: string }) => r.rule_id === HERO_RULE_ID);
    expect(matchingRule).toBeDefined();
    expect(matchingRule.rule_id).toBe("devmind.authz.missing_role_check");
    expect(matchingRule.category).toBe("authorization");
    expect(matchingRule.default_evidence_level).toBe("E1");
    expect(matchingRule.severity).toBe("high");
  });

  it("defines the exact 8 code lines specified in docs/08 §8.2", () => {
    expect(HERO_CODE_LINES).toHaveLength(8);

    // Line 1
    const l1Text = HERO_CODE_LINES[0]?.tokens.map((t) => t.text).join("");
    expect(l1Text).toBe('import { Router } from "express";');

    // Line 7 is subject
    const l7 = HERO_CODE_LINES[6];
    expect(l7?.isTarget).toBe(true);
    const l7Text = l7?.tokens.map((t) => t.text).join("");
    expect(l7Text).toContain("/admin/users");
    expect(l7Text).toContain("requireAuth, listUsers");

    // Line 8 has requireRole("admin")
    const l8Text = HERO_CODE_LINES[7]?.tokens.map((t) => t.text).join("");
    expect(l8Text).toContain('requireRole("admin")');
  });

  it("specifies margin note content with receipt details", () => {
    expect(HERO_MARGIN_NOTE.header).toBe("@@ /admin/users @@");
    expect(HERO_MARGIN_NOTE.authnStatus).toBe("required");
    expect(HERO_MARGIN_NOTE.authnDetail).toContain("auth.ts:12");
    expect(HERO_MARGIN_NOTE.authzStatus).toBe("missing");
    expect(HERO_MARGIN_NOTE.authzDetail).toBe("no role check on route or handler");
    expect(HERO_MARGIN_NOTE.evidenceLevel).toBe("E1 · Possible");
    expect(HERO_MARGIN_NOTE.ruleId).toBe(HERO_RULE_ID);
  });

  it("defines three shared-Brain consequence ripple tags with peek descriptions", () => {
    expect(HERO_RIPPLE_TAGS).toHaveLength(3);
    const ids = HERO_RIPPLE_TAGS.map((t) => t.id);
    expect(ids).toEqual(["review", "docs", "pr"]);

    for (const tag of HERO_RIPPLE_TAGS) {
      expect(tag.label.length).toBeGreaterThan(5);
      expect(tag.peek.length).toBeGreaterThan(15);
    }
  });

  it("verifies CheckIcon and CrossIcon render SVG shapes, not unicode emoji", () => {
    const checkEl = CheckIcon({});
    expect(checkEl.type).toBe("svg");
    expect(checkEl.props["aria-label"]).toBe("Satisfied");

    const crossEl = CrossIcon({});
    expect(crossEl.type).toBe("svg");
    expect(crossEl.props["aria-label"]).toBe("Failed");
  });

  it("verifies pointer-lit-card stylesheet contains fine-pointer scoping and opacity limit <= 0.35", () => {
    const globalsCssPath = path.resolve(__dirname, "../app/globals.css");
    const globalsCss = fs.readFileSync(globalsCssPath, "utf-8");

    expect(globalsCss).toContain(".pointer-lit-card");
    expect(globalsCss).toContain("(pointer: fine)");
    expect(globalsCss).toContain("opacity: 0.35");
    expect(globalsCss).not.toContain("#"); // no hex literals
  });
});
