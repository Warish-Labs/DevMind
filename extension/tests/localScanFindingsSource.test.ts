import { describe, it, expect, vi, beforeEach } from "vitest";
import path from "node:path";
import fs from "node:fs/promises";
import os from "node:os";
import * as vscode from "vscode";
import { LocalScanFindingsSource } from "../src/sources/localScanFindingsSource";
import { FindingsViewProvider, SeverityGroupTreeItem } from "../src/views/findingsView";
import { StructureViewProvider, ModuleTreeItem, RouteTreeItem } from "../src/views/structureView";
import { DatabaseViewProvider, DatabaseModelTreeItem } from "../src/views/databaseView";
import { ScanViewProvider } from "../src/views/scanView";
import { DiagnosticService } from "../src/services/diagnostics";

const ROOT = path.resolve(__dirname, "../../");
const EXPRESS_FIXTURE = path.join(ROOT, "evals/scanner/fixtures/express-admin");
const FASTAPI_FIXTURE = path.join(ROOT, "evals/scanner/fixtures/fastapi-admin");

describe("LocalScanFindingsSource (M3-05)", () => {
  let tmpStorageDir: string;

  beforeEach(async () => {
    tmpStorageDir = await fs.mkdtemp(path.join(os.tmpdir(), "devmind-scan-test-"));
    vscode.workspace.workspaceFolders = [{ uri: { fsPath: EXPRESS_FIXTURE } }];
  });

  describe("Fixture Mode Integration", () => {
    it("delegates to FixtureFindingsSource when fixtureMode is active", async () => {
      const source = new LocalScanFindingsSource(tmpStorageDir);
      const findings = await source.getFindings(EXPRESS_FIXTURE);

      expect(findings.length).toBeGreaterThan(0);
      expect(findings[0]?.ruleId).toBe("devmind.authz.missing_role_check");
      expect(findings[0]?.evidenceLevel).toBe("E1");

      const modules = await source.getStructure(EXPRESS_FIXTURE);
      expect(modules.length).toBeGreaterThan(0);

      const dbModels = await source.getDatabaseModels(EXPRESS_FIXTURE);
      expect(dbModels.length).toBeGreaterThan(0);
    });
  });

  describe("Real Local Workspace Scanning Pipeline", () => {
    it("performs real local scan on express-admin fixture without network calls", async () => {
      const fetchSpy = vi.fn();
      vi.stubGlobal("fetch", fetchSpy);

      const source = new LocalScanFindingsSource(tmpStorageDir);
      const progressSteps: string[] = [];

      const result = await source.scan(
        EXPRESS_FIXTURE,
        (msg) => {
          progressSteps.push(msg);
        },
        true // forceReal = true
      );

      // Verify zero network calls were made
      expect(fetchSpy).not.toHaveBeenCalled();

      // Verify scan results
      expect(result.workspaceRoot).toBe(EXPRESS_FIXTURE);
      expect(result.analyzedFilesCount).toBeGreaterThan(0);
      expect(result.manifestUpdated).toBe(true);
      expect(progressSteps.length).toBeGreaterThan(0);

      // Verify findings
      expect(result.findings.length).toBeGreaterThan(0);
      const authFinding = result.findings.find(
        (f) => f.ruleId === "devmind.authz.missing_role_check"
      );
      expect(authFinding).toBeDefined();
      expect(authFinding?.severity).toBe("high");
      expect(authFinding?.evidenceLevel).toBe("E1");
      expect(authFinding?.evidenceLabel).toBe("E1 · Possible");
      expect(authFinding?.file).toBe("src/routes/admin.ts");

      // Invariant: Evidence level ceiling <= E1
      for (const f of result.findings) {
        expect(["E0", "E1"]).toContain(f.evidenceLevel);
        expect(f.message.toLowerCase()).not.toContain("vulnerable");
      }

      // Verify project modules
      expect(result.modules.length).toBeGreaterThan(0);
      const adminModule = result.modules.find((m) => m.name === "admin");
      expect(adminModule).toBeDefined();
      expect(adminModule?.routes.length).toBe(2);

      // Verify database models (ADR-034: extracted from files, zero live DB connections)
      expect(result.databaseModels.length).toBeGreaterThan(0);
      const userModel = result.databaseModels.find((m) => m.name === "User");
      expect(userModel).toBeDefined();

      vi.unstubAllGlobals();
    });

    it("performs real local scan on fastapi-admin fixture", async () => {
      const source = new LocalScanFindingsSource(tmpStorageDir);
      const result = await source.scan(FASTAPI_FIXTURE, undefined, true);

      expect(result.analyzedFilesCount).toBeGreaterThan(0);
      const authFinding = result.findings.find(
        (f) => f.ruleId === "devmind.authz.missing_role_check"
      );
      expect(authFinding).toBeDefined();
      expect(authFinding?.file).toBe("app/routes/admin.py");
      expect(authFinding?.evidenceLevel).toBe("E1");

      const adminModule = result.modules.find((m) => m.name === "admin");
      expect(adminModule).toBeDefined();
      expect(adminModule?.routes.length).toBe(2);
    });

    it("evaluates hardcoded secrets with deterministic ADR-047 redaction during scan", async () => {
      // Create a temporary workspace with a secret in source code
      const secretWorkspace = await fs.mkdtemp(path.join(os.tmpdir(), "devmind-secret-workspace-"));
      // Construct secret dynamically to avoid static push protection triggers (>= 24 chars)
      const rawSecret = ["sk", "live", "testkey1234567890abcdefg"].join("_");
      const srcDir = path.join(secretWorkspace, "src");
      await fs.mkdir(srcDir, { recursive: true });
      await fs.writeFile(
        path.join(srcDir, "payment.ts"),
        `const stripeApiKey = "${rawSecret}";\nexport function pay() {}\n`
      );

      const source = new LocalScanFindingsSource(tmpStorageDir);
      const result = await source.scan(secretWorkspace, undefined, true);

      const secretFinding = result.findings.find(
        (f) => f.ruleId === "devmind.secrets.hardcoded_credential"
      );
      expect(secretFinding).toBeDefined();
      expect(secretFinding?.severity).toBe("critical");
      expect(secretFinding?.evidenceLevel).toBe("E1");

      // Invariant: ADR-047 deterministic redaction
      expect(secretFinding?.codeSnippet).not.toContain(rawSecret);
      expect(secretFinding?.codeSnippet).toMatch(/\[REDACTED:token:[a-zA-Z0-9_]{8}\]/);
      expect(secretFinding?.message).not.toContain(rawSecret);

      await fs.rm(secretWorkspace, { recursive: true, force: true });
    });
  });

  describe("TreeView and Diagnostics Integration", () => {
    it("wires findings, structure, database, and diagnostics cleanly from scan results", async () => {
      const source = new LocalScanFindingsSource(tmpStorageDir);
      await source.scan(EXPRESS_FIXTURE, undefined, true);

      // 1. Findings View Provider
      const findingsProvider = new FindingsViewProvider(source);
      const findingRoots = await findingsProvider.getChildren();
      expect(findingRoots.length).toBeGreaterThan(0);
      const highGroup = findingRoots.find(
        (r): r is SeverityGroupTreeItem =>
          r instanceof SeverityGroupTreeItem && r.severity === "high"
      );
      expect(highGroup).toBeDefined();

      // 2. Structure View Provider
      const structureProvider = new StructureViewProvider(source);
      const structureRoots = await structureProvider.getChildren();
      expect(structureRoots.length).toBeGreaterThan(0);
      const modItem = structureRoots[0] as ModuleTreeItem;
      expect(modItem.module.name).toBe("admin");
      const routeItems = await structureProvider.getChildren(modItem);
      expect(routeItems.length).toBe(2);
      const routeItem = routeItems[0] as RouteTreeItem;
      expect(routeItem.route.path).toBe("/admin/users");

      // 3. Database View Provider
      const dbProvider = new DatabaseViewProvider(source);
      const dbRoots = await dbProvider.getChildren();
      expect(dbRoots.length).toBeGreaterThan(1); // Notice item + model items
      const modelItem = dbRoots.find(
        (r): r is DatabaseModelTreeItem => r instanceof DatabaseModelTreeItem
      );
      expect(modelItem).toBeDefined();
      expect(modelItem?.model.name).toBe("User");

      // 4. Scan View Provider
      const scanProvider = new ScanViewProvider();
      const lastResult = source.getLastResult();
      expect(lastResult).toBeDefined();
      scanProvider.setCompleted(lastResult!.analyzedFilesCount, lastResult!.skippedFiles);
      const scanRoots = await scanProvider.getChildren();
      expect(scanRoots.length).toBeGreaterThan(0);

      // 5. Diagnostics Collection
      const diagService = new DiagnosticService();
      diagService.updateDiagnostics(lastResult!.findings, EXPRESS_FIXTURE);
      const diags = diagService
        .getCollection()
        .get({ fsPath: path.join(EXPRESS_FIXTURE, "src/routes/admin.ts") });
      expect(diags.length).toBeGreaterThan(0);
      expect(diags[0]?.code).toBe("devmind.authz.missing_role_check");
      expect(diags[0]?.message).toContain("Possible: [HIGH · E1 · Possible]");
      expect(diags[0]?.message.toLowerCase()).not.toContain("vulnerable");

      diagService.dispose();
    });
  });
});
