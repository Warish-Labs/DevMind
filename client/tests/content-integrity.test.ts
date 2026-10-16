import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { HERO_RULE_ID, HERO_MARGIN_NOTE } from "../lib/hero-data";

// Paths to common single sources of truth
const ROOT = path.resolve(__dirname, "../../");
const COMMON_DATA = path.join(ROOT, "common/data");

interface RuleCatalogEntry {
  rule_id: string;
  name: string;
  description: string;
  severity: string;
  category: string;
  default_evidence_level: string;
}

interface RuleCatalog {
  version: string;
  rules: RuleCatalogEntry[];
}

interface CapabilityItem {
  id: string;
  question: string;
  capability: string;
  release: string;
  summary: string;
}

interface ReleaseStatusCapability {
  id: string;
  name: string;
  release: string;
  status: string;
}

interface ReleaseStatusData {
  projectStatus: string;
  lastUpdated: string;
  capabilities: ReleaseStatusCapability[];
}

interface PrivacyLedgerEntry {
  category: string;
  staysLocal: boolean;
  storedInDevMind: boolean;
  embedded: boolean;
  reachesLLM: boolean;
  modes: string[];
}

interface PrivacyLedgerData {
  version: string;
  entries: PrivacyLedgerEntry[];
}

interface WalkthroughStep {
  step: number;
  title: string;
  agent: string;
  brainState: string;
  status: string;
}

describe("Content Integrity & Single Source of Truth", () => {
  it("verifies hero rule ID and margin note match rule catalog exactly", () => {
    const rawCatalog = fs.readFileSync(path.join(COMMON_DATA, "rule-catalog.json"), "utf8");
    const catalog: RuleCatalog = JSON.parse(rawCatalog);

    const matchedRule = catalog.rules.find((r) => r.rule_id === HERO_RULE_ID);
    expect(matchedRule).toBeDefined();
    expect(matchedRule?.rule_id).toBe("devmind.authz.missing_role_check");
    expect(matchedRule?.description).toBe(HERO_MARGIN_NOTE.ruleDescription);
    expect(HERO_MARGIN_NOTE.evidenceLevel).toContain(matchedRule?.default_evidence_level);
  });

  it("verifies capabilities data matches release status mappings", () => {
    const rawCaps = fs.readFileSync(path.join(COMMON_DATA, "capabilities.json"), "utf8");
    const caps: CapabilityItem[] = JSON.parse(rawCaps);

    const rawStatus = fs.readFileSync(path.join(COMMON_DATA, "release-status.json"), "utf8");
    const status: ReleaseStatusData = JSON.parse(rawStatus);

    expect(caps.length).toBeGreaterThanOrEqual(9);

    for (const cap of caps) {
      expect(cap.id).toBeTruthy();
      expect(cap.capability).toBeTruthy();
      expect(cap.question).toBeTruthy();
      expect(cap.summary).toBeTruthy();

      const matchedInStatus = status.capabilities.find((s) => s.id === cap.id);
      expect(matchedInStatus).toBeDefined();
      expect(matchedInStatus?.name).toBe(cap.capability);
    }
  });

  it("verifies privacy ledger schema and non-empty rows", () => {
    const rawLedger = fs.readFileSync(path.join(COMMON_DATA, "privacy-ledger.json"), "utf8");
    const ledger: PrivacyLedgerData = JSON.parse(rawLedger);

    expect(ledger.entries.length).toBeGreaterThan(0);
    for (const entry of ledger.entries) {
      expect(entry.category).toBeTruthy();
      expect(typeof entry.staysLocal).toBe("boolean");
      expect(typeof entry.storedInDevMind).toBe("boolean");
      expect(typeof entry.embedded).toBe("boolean");
      expect(typeof entry.reachesLLM).toBe("boolean");
      expect(Array.isArray(entry.modes)).toBe(true);
    }
  });

  it("verifies walkthrough 14 lifecycle steps are sequential and populated", () => {
    const rawWalkthrough = fs.readFileSync(path.join(COMMON_DATA, "walkthrough.json"), "utf8");
    const steps: WalkthroughStep[] = JSON.parse(rawWalkthrough);

    expect(steps.length).toBe(14);
    for (let i = 0; i < 14; i++) {
      const step = steps[i];
      expect(step.step).toBe(i + 1);
      expect(step.title).toBeTruthy();
      expect(step.agent).toBeTruthy();
      expect(step.brainState).toBeTruthy();
      expect(step.status).toBeTruthy();
    }
  });

  it("prohibits forbidden marketing and AI fluff words", () => {
    const forbidden = [
      /\bmagic\b/i,
      /\bmagical\b/i,
      /\bautonomous\b/i,
      /\b100% secure\b/i,
      /\bunbreakable\b/i,
      /\bfoolproof\b/i,
    ];

    const heroRaw = fs.readFileSync(path.resolve(__dirname, "../lib/hero-data.ts"), "utf8");
    for (const pattern of forbidden) {
      expect(heroRaw).not.toMatch(pattern);
    }
  });
});
