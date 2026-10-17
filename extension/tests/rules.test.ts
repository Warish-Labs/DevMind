import { describe, it, expect } from "vitest";
import path from "node:path";
import fs from "node:fs/promises";
import { LocalRuleEngine } from "../src/scanner/rulesEngine";
import { SemanticExtractor } from "../src/scanner/extractor";
import { DiscoveredFile } from "../src/scanner/types";

const ROOT = path.resolve(__dirname, "../../");
const EXPRESS_ADMIN_PATH = path.join(
  ROOT,
  "evals/scanner/fixtures/express-admin/src/routes/admin.ts"
);
const FASTAPI_ADMIN_PATH = path.join(
  ROOT,
  "evals/scanner/fixtures/fastapi-admin/app/routes/admin.py"
);

describe("Local Rule Engine & E0/E1 Findings Evaluator (docs/06 §8-§9)", () => {
  const engine = new LocalRuleEngine();
  const extractor = new SemanticExtractor();

  it("evaluates Express fixture and matches expected finding (exp-find-01)", async () => {
    const content = await fs.readFile(EXPRESS_ADMIN_PATH, "utf-8");
    const relPath = "src/routes/admin.ts";

    const extracted = extractor.extract(content, relPath);
    const file: DiscoveredFile = {
      relativePath: relPath,
      absolutePath: EXPRESS_ADMIN_PATH,
      size: content.length,
      mtimeMs: 1000,
      languageTier: 1,
      languageId: "typescript",
      status: "ok",
      isCredential: false,
    };

    const findings = engine.evaluate(file, content, extracted.modules);

    expect(findings).toHaveLength(1);
    const f = findings[0];
    expect(f.id).toBe("exp-find-01");
    expect(f.ruleId).toBe("devmind.authz.missing_role_check");
    expect(f.name).toBe("Missing Role Authorization Check");
    expect(f.severity).toBe("high");
    expect(f.evidenceLevel).toBe("E1");
    expect(f.evidenceLabel).toBe("E1 · Possible");
    expect(f.file).toBe(relPath);
    expect(f.lineStart).toBe(7);
    expect(f.codeSnippet).toContain('router.get("/admin/users", requireAuth');
    expect(f.remediation).toBe('Add requireRole("admin") to route middleware stack.');
  });

  it("evaluates FastAPI fixture and matches expected finding (py-find-01)", async () => {
    const content = await fs.readFile(FASTAPI_ADMIN_PATH, "utf-8");
    const relPath = "app/routes/admin.py";

    const extracted = extractor.extract(content, relPath);
    const file: DiscoveredFile = {
      relativePath: relPath,
      absolutePath: FASTAPI_ADMIN_PATH,
      size: content.length,
      mtimeMs: 1000,
      languageTier: 1,
      languageId: "python",
      status: "ok",
      isCredential: false,
    };

    const findings = engine.evaluate(file, content, extracted.modules);

    expect(findings).toHaveLength(1);
    const f = findings[0];
    expect(f.id).toBe("py-find-01");
    expect(f.ruleId).toBe("devmind.authz.missing_role_check");
    expect(f.name).toBe("Missing Role Authorization Check");
    expect(f.severity).toBe("high");
    expect(f.evidenceLevel).toBe("E1");
    expect(f.lineStart).toBe(7);
    expect(f.remediation).toBe("Replace Depends(get_current_user) with Depends(require_admin).");
  });

  it("detects hardcoded secrets and enforces deterministic hash redaction [REDACTED:token:hash8]", () => {
    const dummyStripe = ["sk", "live", "1234567890abcdef1234567890"].join("_");
    const dummyGithub = ["ghp", "1234567890abcdefghijklmnopqrstuvwxyz"].join("_");
    const secretContent = `
      // Sample configuration
      const stripeKey = "${dummyStripe}";
      const githubToken = "${dummyGithub}";
    `;

    const file: DiscoveredFile = {
      relativePath: "src/config.ts",
      absolutePath: "/workspace/src/config.ts",
      size: secretContent.length,
      mtimeMs: 2000,
      languageTier: 1,
      languageId: "typescript",
      status: "ok",
      isCredential: false,
    };

    const findings = engine.evaluate(file, secretContent, []);

    expect(findings.length).toBeGreaterThanOrEqual(2);

    for (const f of findings) {
      expect(f.ruleId).toBe("devmind.secrets.hardcoded_credential");
      expect(f.severity).toBe("critical");
      expect(f.evidenceLevel).toBe("E1");
      // NON-NEGOTIABLE: Raw secret must NOT appear in code snippet or message
      expect(f.codeSnippet).not.toContain(dummyStripe);
      expect(f.codeSnippet).not.toContain(dummyGithub);
      expect(f.codeSnippet).toMatch(/\[REDACTED:token:[0-9a-f]{8}\]/);
    }
  });

  it("evaluates credential file path-only rule without reading content", () => {
    const credFile: DiscoveredFile = {
      relativePath: ".env.production",
      absolutePath: "/workspace/.env.production",
      size: 50,
      mtimeMs: 100,
      languageTier: 3,
      languageId: "env",
      status: "skipped_credential",
      isCredential: true,
    };

    const findings = engine.evaluate(credFile);
    expect(findings).toHaveLength(1);
    expect(findings[0].ruleId).toBe("devmind.secrets.exposed_env_file");
    expect(findings[0].file).toBe(".env.production");
    expect(findings[0].codeSnippet).toBeUndefined(); // Path-only: zero content read
  });

  it("strictly asserts all local findings are <= E1 and never emits E2 or E3", () => {
    const dummyStripe2 = ["sk", "live", "9876543210fedcba9876543210"].join("_");
    const content = `
      router.get("/admin/system", requireAuth, (req, res) => { res.send(1); });
      const key = "${dummyStripe2}";
    `;

    const extracted = extractor.extract(content, "src/admin.ts");
    const file: DiscoveredFile = {
      relativePath: "src/admin.ts",
      absolutePath: "/workspace/src/admin.ts",
      size: content.length,
      mtimeMs: 100,
      languageTier: 1,
      languageId: "typescript",
      status: "ok",
      isCredential: false,
    };

    const findings = engine.evaluate(file, content, extracted.modules);
    for (const f of findings) {
      expect(["E0", "E1"]).toContain(f.evidenceLevel);
      expect(f.evidenceLevel).not.toBe("E2");
      expect(f.evidenceLevel).not.toBe("E3");
    }
  });
});
