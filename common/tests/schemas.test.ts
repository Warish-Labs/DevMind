import { describe, it, expect } from "vitest";
import {
  RuleDefinitionSchema,
  RuleCatalogSchema,
  ReleaseStatusSchema,
  PrivacyLedgerSchema,
  themeColors,
} from "../src/index.js";

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
      severity: "critical-danger", // invalid
      category: "security",
      default_evidence_level: "E1",
    };

    expect(() => RuleDefinitionSchema.parse(invalidRule)).toThrow();
  });

  it("validates rule catalog structure", () => {
    const catalog = {
      version: "1.0.0",
      rules: [
        {
          rule_id: "devmind.authz.missing_role_check",
          name: "Missing role check",
          description: "Route lacks authorization role check",
          severity: "high",
          category: "security",
          default_evidence_level: "E1",
        },
      ],
    };

    const parsed = RuleCatalogSchema.parse(catalog);
    expect(parsed.rules).toHaveLength(1);
  });

  it("validates release status schema", () => {
    const status = {
      projectStatus: "specification",
      lastUpdated: "2026-10-15",
      capabilities: [
        {
          id: "CAP-01",
          name: "Code Intelligence",
          release: "mvp",
          status: "in-progress",
        },
      ],
    };

    const parsed = ReleaseStatusSchema.parse(status);
    expect(parsed.projectStatus).toBe("specification");
    expect(parsed.capabilities[0].id).toBe("CAP-01");
  });

  it("validates privacy ledger schema", () => {
    const ledger = {
      version: "1.0.0",
      entries: [
        {
          category: "File metadata (paths, hashes, sizes)",
          staysLocal: false,
          storedInDevMind: true,
          embedded: false,
          reachesLLM: false,
          modes: ["metadata_only", "indexed"],
        },
      ],
    };

    const parsed = PrivacyLedgerSchema.parse(ledger);
    expect(parsed.entries).toHaveLength(1);
    expect(parsed.entries[0].modes).toContain("metadata_only");
  });

  it("exports theme colors matching brand design tokens", () => {
    expect(themeColors.bg0).toBe("#0B0F12");
    expect(themeColors.signal).toBe("#38D39F");
    expect(themeColors.ref).toBe("#6CA8F9");
  });
});
