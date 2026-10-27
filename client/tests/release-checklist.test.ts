import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";

describe("MVP Release Checklist & Notes Verification (M13-06)", () => {
  const repoRoot = path.resolve(__dirname, "../..");

  it("verifies release-checklist.md exists and contains all required verification phases", () => {
    const checklistPath = path.join(repoRoot, "docs/runbooks/release-checklist.md");
    expect(fs.existsSync(checklistPath)).toBe(true);

    const content = fs.readFileSync(checklistPath, "utf8");

    // Section 1: Overview & Philosophy
    expect(content).toContain("Overview & Release Philosophy");
    expect(content).toContain("ADR-046");

    // Section 2: Quality Gates G1 to G5
    expect(content).toContain("Gate 1 — Static Analysis & Architecture Boundaries");
    expect(content).toContain("Gate 2 — Automated Test Suites");
    expect(content).toContain("Gate 3 — Security & Tenant Isolation");
    expect(content).toContain("Gate 4 — Documentation & Brand Integrity");
    expect(content).toContain("Gate 5 — API Contract Parity");

    // Section 3: Cloud Topology
    expect(content).toContain("Vercel Frontend");
    expect(content).toContain("Render Web Service");
    expect(content).toContain("Neon PostgreSQL Database");
    expect(content).toContain("Upstash Redis");

    // Section 4: VS Code Extension
    expect(content).toContain("VS Code Companion Extension Distribution Checklist");
    expect(content).toContain("Zero Live DB Enforcement");

    // Section 5: End-to-End Smoke Protocol
    expect(content).toContain("End-to-End Post-Deployment Smoke Protocol");
    expect(content).toContain("Local AST Scan & Privacy Consent");
    expect(content).toContain("Project Brain Snapshot & Graph Explorer");
    expect(content).toContain("Security Sentinel & Finding Triage");
    expect(content).toContain("Project AI Assistant (BrainQA)");

    // Section 6: Known Limitations Ledger
    expect(content).toContain("Known Limitations Ledger (MVP v0.1.0)");
    expect(content).toContain("Language Support Tiers");
    expect(content).toContain("Zero live DB connections");

    // Section 7: Emergency & Rollback
    expect(content).toContain("Rollback & Emergency Runbook References");
  });

  it("verifies root CHANGELOG.md documents v0.1.0 release and known limitations ledger", () => {
    const changelogPath = path.join(repoRoot, "CHANGELOG.md");
    expect(fs.existsSync(changelogPath)).toBe(true);

    const content = fs.readFileSync(changelogPath, "utf8");

    // Version heading
    expect(content).toContain("## [0.1.0]");
    expect(content).toContain("MVP Release — Initial Public Release Candidate");

    // Core functional pillars
    expect(content).toContain("Core Platform & Project Brain (CAP-01)");
    expect(content).toContain("Security Intelligence (CAP-02)");
    expect(content).toContain("Web Application & Design System");
    expect(content).toContain("VS Code Companion Extension (`devmind-vscode`)");
    expect(content).toContain("Backend & Worker Architecture");
    expect(content).toContain("Quality & Operations");

    // Known Limitations Ledger
    expect(content).toContain("Known Limitations Ledger");
    expect(content).toContain("Language Tiers");
    expect(content).toContain("Tier 1 (Full AST & Symbol Graph)");
    expect(content).toContain("Tier 2 (Structural Patterns & Secrets)");
    expect(content).toContain("Zero Live Database Connections");
    expect(content).toContain("No In-Extension AI Chat");
    expect(content).toContain("Evidence Grounding Boundaries");
  });

  it("verifies extension CHANGELOG.md aligns with release readiness constraints", () => {
    const extChangelogPath = path.join(repoRoot, "extension/CHANGELOG.md");
    expect(fs.existsSync(extChangelogPath)).toBe(true);

    const content = fs.readFileSync(extChangelogPath, "utf8");
    expect(content).toContain("Known Limitations Ledger");
    expect(content).toContain("Language Tier Support");
    expect(content).toContain("Zero Live Database Connections");
  });
});
