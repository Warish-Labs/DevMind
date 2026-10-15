import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import {
  RuleDefinitionSchema,
  validateRuleCatalog,
  validateReleaseStatus,
  validatePrivacyLedger,
  validateCapabilities,
  validateWalkthrough,
  themeColors,
} from "../src/index.js";

const DATA_DIR = path.resolve(__dirname, "../data");

function readJsonFile(filename: string): unknown {
  const filePath = path.join(DATA_DIR, filename);
  const raw = fs.readFileSync(filePath, "utf-8");
  return JSON.parse(raw);
}

describe("@devmind/common schemas", () => {
  it("validates a rule definition successfully", () => {
    const validRule = {
      rule_id: "devmind.authz.missing_role_check",
      name: "Missing role check",
      description: "Route lacks authorization role check",
      severity: "high",
      category: "security",
      default_evidence_level: "E1",
    };

    const parsed = RuleDefinitionSchema.parse(validRule);
    expect(parsed.rule_id).toBe("devmind.authz.missing_role_check");
    expect(parsed.severity).toBe("high");
  });

  it("rejects invalid severity level", () => {
    const invalidRule = {
      rule_id: "invalid.rule",
      name: "Bad rule",
      description: "Invalid severity",
      severity: "critical-danger",
      category: "security",
      default_evidence_level: "E1",
    };

    expect(() => RuleDefinitionSchema.parse(invalidRule)).toThrow();
  });

  it("exports theme colors matching brand design tokens", () => {
    expect(themeColors.bg0).toBe("#0B0F12");
    expect(themeColors.signal).toBe("#38D39F");
    expect(themeColors.ref).toBe("#6CA8F9");
  });
});

describe("common/data/*.json file integrity and acceptance checks", () => {
  it("validates rule-catalog.json and verifies devmind.authz.missing_role_check is present", () => {
    const data = readJsonFile("rule-catalog.json");
    const catalog = validateRuleCatalog(data);

    expect(catalog.version).toBeDefined();
    expect(catalog.rules.length).toBeGreaterThan(0);

    const targetRule = catalog.rules.find((r) => r.rule_id === "devmind.authz.missing_role_check");
    expect(targetRule).toBeDefined();
    expect(targetRule?.severity).toBe("high");
    expect(targetRule?.default_evidence_level).toBe("E1");
  });

  it("validates release-status.json and verifies projectStatus is specification", () => {
    const data = readJsonFile("release-status.json");
    const status = validateReleaseStatus(data);

    expect(status.projectStatus).toBe("specification");
    expect(status.capabilities.length).toBe(9);
  });

  it("validates privacy-ledger.json", () => {
    const data = readJsonFile("privacy-ledger.json");
    const ledger = validatePrivacyLedger(data);

    expect(ledger.version).toBeDefined();
    expect(ledger.entries.length).toBeGreaterThan(0);
    const staysLocalEntry = ledger.entries.find((e) => e.category.includes("File contents"));
    expect(staysLocalEntry?.staysLocal).toBe(true);
  });

  it("validates capabilities.json with all 9 capabilities", () => {
    const data = readJsonFile("capabilities.json");
    const capabilities = validateCapabilities(data);

    expect(capabilities).toHaveLength(9);
    expect(capabilities.map((c) => c.id)).toContain("CAP-01");
    expect(capabilities.map((c) => c.id)).toContain("CAP-02");
    expect(capabilities.map((c) => c.id)).toContain("CAP-09");
  });

  it("validates walkthrough.json and confirms it has exactly 14 steps", () => {
    const data = readJsonFile("walkthrough.json");
    const walkthrough = validateWalkthrough(data);

    expect(walkthrough).toHaveLength(14);
    for (let i = 1; i <= 14; i++) {
      const step = walkthrough.find((s) => s.step === i);
      expect(step).toBeDefined();
      expect(step?.title).toBeDefined();
    }
  });
});
