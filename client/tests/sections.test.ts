import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import {
  SECTION_02_CONSEQUENCES,
  BRAIN_STRATA,
  capabilitiesData,
  releaseStatusData,
  walkthroughData,
  privacyLedgerData,
} from "../lib/sections-data";

const ROOT_DIR = path.resolve(__dirname, "../..");

describe("Homepage Sections 02–08 Specifications & Data Integrity", () => {
  it("Section 02: specifies five distinct consequences with correct highlighted lines", () => {
    expect(SECTION_02_CONSEQUENCES).toHaveLength(5);
    const ids = SECTION_02_CONSEQUENCES.map((c) => c.id);
    expect(ids).toEqual(["security", "review", "docs", "pr", "health"]);

    for (const c of SECTION_02_CONSEQUENCES) {
      expect(c.title).toBeTruthy();
      expect(c.description.length).toBeGreaterThan(20);
      expect(c.highlightedLines.length).toBeGreaterThan(0);
      expect(c.highlightedLines).toContain(7);
    }
  });

  it("Section 03: defines exactly ten Project Brain strata with hero path on 1, 3, 5, 8", () => {
    expect(BRAIN_STRATA).toHaveLength(10);

    const heroLayers = BRAIN_STRATA.filter((s) => s.isHeroPath).map((s) => s.number);
    expect(heroLayers).toEqual([1, 3, 5, 8]);

    for (const s of BRAIN_STRATA) {
      expect(s.number).toBeGreaterThanOrEqual(1);
      expect(s.number).toBeLessThanOrEqual(10);
      expect(s.name.length).toBeGreaterThan(5);
      expect(s.definition.length).toBeGreaterThan(15);
      expect(s.notDefinition.length).toBeGreaterThan(10);
      expect(s.whereItLives.length).toBeGreaterThan(5);
      expect(s.exampleRecord).toContain("{");
    }
  });

  it("Section 04: loads 9 capabilities matching release-status.json without claiming unreleased features", () => {
    expect(capabilitiesData).toHaveLength(9);
    expect(releaseStatusData.capabilities).toHaveLength(9);

    const releaseStatusMap = new Map(
      releaseStatusData.capabilities.map((c) => [c.id, c.release.toLowerCase()])
    );

    for (const item of capabilitiesData) {
      const declaredRelease = releaseStatusMap.get(item.id);
      expect(declaredRelease).toBeDefined();
      expect(item.release.toLowerCase()).toBe(declaredRelease);
      expect(item.question).toContain("?");
      expect(item.summary.length).toBeGreaterThan(15);
    }
  });

  it("Section 05: walkthrough timeline contains exactly 14 chronological steps", () => {
    expect(walkthroughData).toHaveLength(14);
    walkthroughData.forEach((step, idx) => {
      expect(step.step).toBe(idx + 1);
      expect(step.title.length).toBeGreaterThan(10);
      expect(step.agent.length).toBeGreaterThan(3);
      expect(step.brainState.length).toBeGreaterThan(10);
      expect(["mvp", "planned"]).toContain(step.status);
    });
  });

  it("Section 07: privacy ledger matches common/data/privacy-ledger.json exactly", () => {
    const rawPath = path.join(ROOT_DIR, "common/data/privacy-ledger.json");
    expect(fs.existsSync(rawPath)).toBe(true);
    const rawJson = JSON.parse(fs.readFileSync(rawPath, "utf-8"));

    expect(privacyLedgerData.entries).toHaveLength(rawJson.entries.length);
    expect(privacyLedgerData.entries.length).toBe(9);

    for (let i = 0; i < rawJson.entries.length; i++) {
      const diskEntry = rawJson.entries[i];
      const memEntry = privacyLedgerData.entries[i];
      expect(memEntry?.category).toBe(diskEntry.category);
      expect(memEntry?.staysLocal).toBe(diskEntry.staysLocal);
      expect(memEntry?.storedInDevMind).toBe(diskEntry.storedInDevMind);
      expect(memEntry?.embedded).toBe(diskEntry.embedded);
      expect(memEntry?.reachesLLM).toBe(diskEntry.reachesLLM);
    }
  });

  it("HomePage integration: all section anchors 01 to 08 and walkthrough anchor exist", () => {
    const pageTsxPath = path.resolve(__dirname, "../app/page.tsx");
    const pageTsx = fs.readFileSync(pageTsxPath, "utf-8");

    expect(pageTsx).toContain("Section02BlastRadius");
    expect(pageTsx).toContain("Section03BrainStrata");
    expect(pageTsx).toContain("Section04Capabilities");
    expect(pageTsx).toContain("Section05Walkthrough");
    expect(pageTsx).toContain("Section06Diptych");
    expect(pageTsx).toContain("Section07PrivacyLedger");
    expect(pageTsx).toContain("Section08CTA");
  });
});
