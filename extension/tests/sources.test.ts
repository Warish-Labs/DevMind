import { describe, it, expect } from "vitest";
import path from "node:path";
import { FixtureFindingsSource } from "../src/sources/fixtureFindingsSource";

const ROOT = path.resolve(__dirname, "../../");
const EXPRESS_FIXTURE = path.join(ROOT, "evals/scanner/fixtures/express-admin");
const FASTAPI_FIXTURE = path.join(ROOT, "evals/scanner/fixtures/fastapi-admin");

describe("FixtureFindingsSource", () => {
  const source = new FixtureFindingsSource();

  it("loads findings for express-admin fixture", async () => {
    const findings = await source.getFindings(EXPRESS_FIXTURE);
    expect(findings.length).toBeGreaterThan(0);

    const finding = findings[0]!;
    expect(finding.ruleId).toBe("devmind.authz.missing_role_check");
    expect(finding.severity).toBe("high");
    expect(finding.evidenceLevel).toBe("E1");
    expect(finding.evidenceLabel).toBe("E1 · Possible");
    expect(finding.file).toBe("src/routes/admin.ts");
    expect(finding.lineStart).toBe(7);
    expect(finding.remediation).toBeTruthy();
  });

  it("loads module structure for express-admin fixture", async () => {
    const modules = await source.getStructure(EXPRESS_FIXTURE);
    expect(modules.length).toBeGreaterThan(0);

    const adminModule = modules.find((m) => m.name === "admin");
    expect(adminModule).toBeDefined();
    expect(adminModule?.routes.length).toBe(2);

    const getRoute = adminModule?.routes.find((r) => r.method === "GET");
    expect(getRoute?.path).toBe("/admin/users");
    expect(getRoute?.auth).toBe(true);
    expect(getRoute?.roleGuard).toBe(false);

    const deleteRoute = adminModule?.routes.find((r) => r.method === "DELETE");
    expect(deleteRoute?.path).toBe("/admin/users/:id");
    expect(deleteRoute?.auth).toBe(true);
    expect(deleteRoute?.roleGuard).toBe(true);
  });

  it("loads findings for fastapi-admin fixture", async () => {
    const findings = await source.getFindings(FASTAPI_FIXTURE);
    expect(findings.length).toBeGreaterThan(0);

    const finding = findings[0]!;
    expect(finding.ruleId).toBe("devmind.authz.missing_role_check");
    expect(finding.file).toBe("app/routes/admin.py");
    expect(finding.evidenceLevel).toBe("E1");
  });

  it("loads module structure for fastapi-admin fixture", async () => {
    const modules = await source.getStructure(FASTAPI_FIXTURE);
    expect(modules.length).toBeGreaterThan(0);

    const adminModule = modules.find((m) => m.name === "admin");
    expect(adminModule).toBeDefined();
    expect(adminModule?.routes.length).toBe(2);
  });

  it("returns express fallback findings when no workspace path is passed", async () => {
    const findings = await source.getFindings();
    expect(findings.length).toBe(1);
    expect(findings[0]?.id).toBe("exp-find-01");
  });
});
